"""Core council logic - multi-model draft, critique, and synthesis."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

from .client import CompletionResult, Message, OpenRouterClient, get_client


# Default models for diversity (latest versions on OpenRouter)
DEFAULT_MODELS = [
    "anthropic/claude-opus-4.5",
    "openai/gpt-5.2",
]
DEFAULT_CHAIR = "anthropic/claude-opus-4.5"


# =============================================================================
# PROMPTS
# =============================================================================

PLAN_SYSTEM_PROMPT = """You are a senior software architect. Given a project idea, produce a comprehensive but concise project plan.

Include:
- Project overview (1-2 sentences)
- Core features (bulleted list)
- Technical approach (stack, architecture decisions)
- Key trade-offs and decisions to make
- First steps to implement (actionable)

Be practical. Focus on V0/MVP scope. No fluff."""

DEBATE_SYSTEM_PROMPT = """You are presenting one side of a technical debate. Argue your position clearly with:
- Specific pros and cons
- Concrete use cases where this approach shines
- Honest acknowledgment of trade-offs

Be direct and practical, not theoretical."""

CRITIQUE_SYSTEM_PROMPT = """You are a senior engineer reviewing draft proposals. Your job is to:
- Identify gaps, risks, or overlooked considerations
- Point out potential issues with the proposed approach
- Suggest improvements or alternatives where appropriate
- Be constructive but thorough

Focus on substance, not style."""

CHAIR_PLAN_PROMPT = """You are synthesizing perspectives from multiple models into a unified project plan.

## Drafts
{drafts}

## Critiques
{critiques}

## Original Request
{original_prompt}

Produce a SINGLE unified project plan that:
1. Incorporates the best ideas from all drafts
2. Addresses the concerns raised in critiques
3. Resolves any conflicts by making clear decisions
4. Is actionable and practical

Output the final plan in clean markdown. No meta-commentary about the synthesis process."""

CHAIR_DEBATE_PROMPT = """You are synthesizing a technical debate between multiple perspectives.

## Perspectives
{drafts}

## Critiques
{critiques}

## Original Question
{original_prompt}

Produce a synthesis that:
1. Summarizes each position fairly
2. Highlights the key trade-offs
3. Provides a recommendation (if possible)
4. Identifies when each approach is best suited

Be concise and actionable."""

REFINE_SYSTEM_PROMPT = """You are a senior software architect refining an existing project plan based on feedback.

You will receive:
1. An existing plan
2. Refinement instructions

Your job is to update the plan according to the instructions while:
- Preserving the good parts of the existing plan
- Making targeted changes based on the feedback
- Keeping the same overall structure and format
- Not removing important details unless specifically asked

Output the complete refined plan."""

CHAIR_REFINE_PROMPT = """You are synthesizing refinement suggestions from multiple models.

## Existing Plan
{context}

## Refinement Instruction
{original_prompt}

## Suggested Refinements
{drafts}

## Critiques of Refinements
{critiques}

Produce a SINGLE refined plan that:
1. Incorporates the best refinement suggestions
2. Addresses the original instruction
3. Preserves valuable parts of the existing plan
4. Is complete and ready to use

Output the complete refined plan in clean markdown."""


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def draft_one(
    client: OpenRouterClient,
    model: str,
    prompt: str,
    mode: str,
    context: Optional[str] = None,
) -> Tuple[str, Optional[CompletionResult], Optional[str]]:
    """Generate a single draft from one model.

    Returns:
        (model, result or None, error or None)
    """
    if mode == "plan":
        system_prompt = PLAN_SYSTEM_PROMPT
    elif mode == "refine":
        system_prompt = REFINE_SYSTEM_PROMPT
    else:
        system_prompt = DEBATE_SYSTEM_PROMPT

    # Build user prompt with context if provided
    if context and mode == "plan":
        user_content = f"## Context\n\n{context}\n\n---\n\n## Project Idea\n\n{prompt}"
    elif context and mode == "refine":
        user_content = f"## Existing Plan\n\n{context}\n\n---\n\n## Refinement Instructions\n\n{prompt}"
    else:
        user_content = prompt

    messages = [
        Message(role="system", content=system_prompt),
        Message(role="user", content=user_content),
    ]

    try:
        result = client.complete(messages, model=model, timeout=120.0)
        return (model, result, None)
    except Exception as e:
        return (model, None, str(e))


def critique_drafts(
    client: OpenRouterClient,
    model: str,
    drafts: Dict[str, str],
    original_prompt: str,
) -> Tuple[str, Optional[CompletionResult], Optional[str]]:
    """Generate a critique of all drafts from one model.

    Returns:
        (model, result or None, error or None)
    """
    # Format drafts for critique
    drafts_text = ""
    for draft_model, content in drafts.items():
        drafts_text += f"\n### Draft from {draft_model}\n\n{content}\n\n---\n"

    messages = [
        Message(role="system", content=CRITIQUE_SYSTEM_PROMPT),
        Message(
            role="user",
            content=f"## Original Request\n{original_prompt}\n\n## Drafts to Review\n{drafts_text}\n\nProvide your critique.",
        ),
    ]

    try:
        result = client.complete(messages, model=model, timeout=120.0)
        return (model, result, None)
    except Exception as e:
        return (model, None, str(e))


def synthesize(
    client: OpenRouterClient,
    chair_model: str,
    drafts: Dict[str, str],
    critiques: Dict[str, str],
    original_prompt: str,
    mode: str,
    context: Optional[str] = None,
) -> str:
    """Chair synthesis of drafts and critiques.

    Returns:
        Synthesized content string
    """
    # Format drafts
    drafts_text = ""
    for model, content in drafts.items():
        drafts_text += f"\n### Draft from {model}\n\n{content}\n\n---\n"

    # Format critiques
    critiques_text = ""
    for model, content in critiques.items():
        critiques_text += f"\n### Critique from {model}\n\n{content}\n\n---\n"

    # Choose prompt template based on mode
    if mode == "plan":
        user_prompt = CHAIR_PLAN_PROMPT.format(
            drafts=drafts_text,
            critiques=critiques_text,
            original_prompt=original_prompt,
        )
    elif mode == "refine":
        user_prompt = CHAIR_REFINE_PROMPT.format(
            context=context or "",
            drafts=drafts_text,
            critiques=critiques_text,
            original_prompt=original_prompt,
        )
    else:
        user_prompt = CHAIR_DEBATE_PROMPT.format(
            drafts=drafts_text,
            critiques=critiques_text,
            original_prompt=original_prompt,
        )

    messages = [
        Message(role="system", content="You are the chair synthesizing council input into a final output."),
        Message(role="user", content=user_prompt),
    ]

    result = client.complete(messages, model=chair_model, timeout=180.0)
    return result.content


def run_council(
    prompt: str,
    models: Optional[List[str]] = None,
    chair: Optional[str] = None,
    mode: str = "plan",
    verbose: bool = False,
    context: Optional[str] = None,
) -> str:
    """Run a multi-model council.

    Args:
        prompt: The idea or question to discuss
        models: List of model IDs for drafting/critique (default: Claude + GPT-4.1)
        chair: Model ID for synthesis (default: Claude Sonnet)
        mode: "plan", "debate", or "refine"
        verbose: Print progress messages
        context: Optional context (files, existing plan) to include

    Returns:
        Synthesized output string

    Flow:
        1. Draft phase: Each model generates a draft (parallel)
        2. Critique phase: Each model critiques all drafts (parallel)
        3. Synthesis phase: Chair combines everything
    """
    models = models or DEFAULT_MODELS
    chair = chair or DEFAULT_CHAIR

    client = get_client()

    if verbose:
        print(f"Running council with {len(models)} models...")
        if context:
            print(f"Context provided: {len(context)} chars")

    # === PHASE 1: DRAFTS (parallel) ===
    if verbose:
        print("Phase 1: Generating drafts...")

    drafts: Dict[str, str] = {}
    errors: List[str] = []

    with ThreadPoolExecutor(max_workers=len(models)) as executor:
        futures = {
            executor.submit(draft_one, client, model, prompt, mode, context): model
            for model in models
        }

        for future in as_completed(futures):
            model, result, error = future.result()
            if result:
                drafts[model] = result.content
                if verbose:
                    print(f"  - {model}: done")
            else:
                errors.append(f"{model}: {error}")
                if verbose:
                    print(f"  - {model}: FAILED ({error})")

    if len(drafts) < 1:
        raise RuntimeError(f"All drafts failed: {errors}")

    # === PHASE 2: CRITIQUES (parallel) ===
    if verbose:
        print("Phase 2: Generating critiques...")

    critiques: Dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=len(models)) as executor:
        futures = {
            executor.submit(critique_drafts, client, model, drafts, prompt): model
            for model in models
        }

        for future in as_completed(futures):
            model, result, error = future.result()
            if result:
                critiques[model] = result.content
                if verbose:
                    print(f"  - {model}: done")
            else:
                if verbose:
                    print(f"  - {model}: FAILED ({error})")
                # Critiques are optional, continue without

    # === PHASE 3: SYNTHESIS ===
    if verbose:
        print(f"Phase 3: Chair synthesis ({chair})...")

    result = synthesize(client, chair, drafts, critiques, prompt, mode, context)

    if verbose:
        print("Council complete.")

    return result
