"""CLI interface for council."""

from pathlib import Path
from typing import Optional

import click

from .council import run_council, DEFAULT_MODELS, DEFAULT_CHAIR


@click.group()
@click.version_option()
def cli():
    """Council - Multi-model planning for Claude Code projects."""
    pass


def load_context_files(context_paths: Optional[str]) -> Optional[str]:
    """Load and concatenate context files."""
    if not context_paths:
        return None

    context_parts = []
    for path_str in context_paths.split(","):
        path = Path(path_str.strip())
        if path.exists():
            content = path.read_text()
            context_parts.append(f"### {path.name}\n\n{content}")
        else:
            click.echo(f"Warning: Context file not found: {path}", err=True)

    if context_parts:
        return "\n\n---\n\n".join(context_parts)
    return None


@cli.command()
@click.argument("idea")
@click.option(
    "--models", "-m",
    default=None,
    help="Comma-separated model list (default: claude-sonnet + gpt-4.1)"
)
@click.option(
    "--chair", "-c",
    default=None,
    help="Chair model for synthesis"
)
@click.option(
    "--output", "-o",
    default="PLAN.md",
    help="Output file (default: PLAN.md)"
)
@click.option(
    "--context", "-ctx",
    default=None,
    help="Comma-separated context files to include (e.g., README.md,docs/spec.md)"
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show progress"
)
def plan(idea: str, models: Optional[str], chair: Optional[str], output: str, context: Optional[str], verbose: bool):
    """Generate a project plan with multi-model council.

    Example:
        council plan "build a CLI that converts markdown to PDF"
        council plan "add auth to my app" --context README.md,src/app.py
    """
    # Parse models if provided
    model_list = models.split(",") if models else None

    # Load context files
    context_content = load_context_files(context)

    if verbose:
        click.echo(f"Models: {model_list or DEFAULT_MODELS}")
        click.echo(f"Chair: {chair or DEFAULT_CHAIR}")
        click.echo(f"Output: {output}")
        if context_content:
            click.echo(f"Context: {context}")
        click.echo()

    try:
        result = run_council(idea, models=model_list, chair=chair, mode="plan", verbose=verbose, context=context_content)
        Path(output).write_text(result)
        click.echo(f"\nPlan written to {output}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@cli.command()
@click.argument("question")
@click.option(
    "--models", "-m",
    default=None,
    help="Comma-separated model list"
)
@click.option(
    "--chair", "-c",
    default=None,
    help="Chair model for synthesis"
)
@click.option(
    "--append", "-a",
    is_flag=True,
    help="Append to PLAN.md instead of stdout"
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show progress"
)
def debate(question: str, models: Optional[str], chair: Optional[str], append: bool, verbose: bool):
    """Get multi-model perspectives on a decision.

    Example:
        council debate "REST vs GraphQL for a simple CRUD API"
    """
    model_list = models.split(",") if models else None

    try:
        result = run_council(question, models=model_list, chair=chair, mode="debate", verbose=verbose)

        if append:
            plan_path = Path("PLAN.md")
            if plan_path.exists():
                with open(plan_path, "a") as f:
                    f.write(f"\n\n---\n\n## Debate: {question}\n\n{result}")
                click.echo(f"Appended to PLAN.md")
            else:
                click.echo("PLAN.md not found, outputting to stdout:\n")
                click.echo(result)
        else:
            click.echo(result)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@cli.command()
@click.option(
    "--plan", "-p",
    default="PLAN.md",
    help="Plan file to read"
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show progress"
)
def bootstrap(plan: str, verbose: bool):
    """Generate Claude Code files from plan.

    Reads PLAN.md and generates:
    - CLAUDE.md (project context)
    - STATE.md (current work)
    - LOG.md (history)
    - .claude/settings.json
    - .claude/commands/*.md (if available in ~/.claude/commands/)
    """
    from .bootstrap import generate_claude_files

    plan_path = Path(plan)
    if not plan_path.exists():
        click.echo(f"Error: {plan} not found. Run 'council plan' first.", err=True)
        raise SystemExit(1)

    plan_content = plan_path.read_text()

    try:
        generate_claude_files(plan_content, verbose=verbose)
        click.echo("\nGenerated Claude Code files:")
        click.echo("  - CLAUDE.md")
        click.echo("  - STATE.md")
        click.echo("  - LOG.md")
        click.echo("  - .claude/settings.json")
        click.echo("  - .claude/commands/ (if available)")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@cli.command()
@click.argument("instruction")
@click.option(
    "--plan", "-p",
    default="PLAN.md",
    help="Plan file to refine"
)
@click.option(
    "--models", "-m",
    default=None,
    help="Comma-separated model list"
)
@click.option(
    "--chair", "-c",
    default=None,
    help="Chair model for synthesis"
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show progress"
)
def refine(instruction: str, plan: str, models: Optional[str], chair: Optional[str], verbose: bool):
    """Refine an existing plan based on feedback.

    Example:
        council refine "focus more on security considerations"
        council refine "simplify the architecture, we don't need microservices"
    """
    plan_path = Path(plan)
    if not plan_path.exists():
        click.echo(f"Error: {plan} not found. Run 'council plan' first.", err=True)
        raise SystemExit(1)

    existing_plan = plan_path.read_text()
    model_list = models.split(",") if models else None

    if verbose:
        click.echo(f"Refining {plan} with instruction: {instruction}")
        click.echo()

    try:
        result = run_council(
            instruction,
            models=model_list,
            chair=chair,
            mode="refine",
            verbose=verbose,
            context=existing_plan,
        )
        # Backup old plan
        backup_path = Path(f"{plan}.bak")
        backup_path.write_text(existing_plan)

        # Write refined plan
        plan_path.write_text(result)
        click.echo(f"\nRefined plan written to {plan}")
        click.echo(f"Original backed up to {backup_path}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
