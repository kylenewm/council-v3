"""
Command line interface for Agent Eval.

Usage:
    python -m council.agent_eval scenarios/
    python -m council.agent_eval scenario.yaml --format markdown
    python -m council.agent_eval scenarios/ --output report.md --verbose
"""

import argparse
import sys
from pathlib import Path
import logging

from ..config import Config
from ..models.scenario import Scenario
from ..orchestration.runner import AgentEvalRunner, DryRunner
from ..reporting.reporter import Reporter


def setup_logging(verbose: bool, quiet: bool):
    """Configure logging based on verbosity.

    Args:
        verbose: Enable debug logging
        quiet: Suppress all but errors
    """
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )


def load_scenarios(path: Path) -> list:
    """Load scenarios from file or directory.

    Args:
        path: Path to YAML file or directory

    Returns:
        List of Scenario objects
    """
    scenarios = []

    if path.is_file():
        try:
            scenarios.append(Scenario.from_yaml(path))
        except Exception as e:
            logging.error(f"Failed to load {path}: {e}")
    elif path.is_dir():
        yaml_files = list(path.rglob("*.yaml")) + list(path.rglob("*.yml"))
        for yaml_file in yaml_files:
            try:
                scenarios.append(Scenario.from_yaml(yaml_file))
            except Exception as e:
                logging.warning(f"Failed to load {yaml_file}: {e}")
    else:
        logging.error(f"Path not found: {path}")

    return scenarios


def run_command(args):
    """Run evaluation command."""
    # Load config
    if args.config and args.config.exists():
        config = Config.from_yaml(args.config)
    else:
        config = Config.default()

    # Override config with CLI args
    if args.timeout:
        config.agent.timeout_seconds = args.timeout
    if args.no_watchdog:
        config.watchdog.enabled = False
    if args.keep_env:
        config.execution.cleanup_on_success = False
        config.execution.cleanup_on_failure = False

    # Load scenarios
    scenarios = load_scenarios(args.scenarios)
    if not scenarios:
        print(f"No scenarios found in {args.scenarios}")
        sys.exit(1)

    print(f"Found {len(scenarios)} scenarios")

    # Filter by tags if specified
    if args.tags:
        tag_set = set(args.tags)
        scenarios = [s for s in scenarios if tag_set & set(s.tags)]
        print(f"Filtered to {len(scenarios)} scenarios with tags: {args.tags}")

    # Filter by difficulty if specified
    if args.difficulty:
        scenarios = [s for s in scenarios if s.difficulty.value == args.difficulty]
        print(f"Filtered to {len(scenarios)} scenarios with difficulty: {args.difficulty}")

    if not scenarios:
        print("No scenarios match filters")
        sys.exit(0)

    # Dry run
    if args.dry_run:
        print("\nScenarios to run (dry run):")
        dry = DryRunner()
        validation = dry.validate_scenarios(scenarios)
        for result in validation["results"]:
            status = "✅" if result["valid"] else "❌"
            print(
                f"  {status} [{result['scenario_id']}] {result['scenario_name']}"
            )
            if result["issues"]:
                for issue in result["issues"]:
                    print(f"       ⚠️  {issue}")
        print(f"\nValid: {validation['valid']}/{validation['total']}")
        sys.exit(0 if validation["invalid"] == 0 else 1)

    # Run evaluation
    runner = AgentEvalRunner(config)
    results = runner.run_scenarios(scenarios)

    # Generate report
    reporter = Reporter()
    report = reporter.generate(results)

    # Output
    if args.format == "json":
        output = reporter.to_json(report)
    elif args.format == "markdown":
        output = reporter.to_markdown(report)
    else:  # summary
        output = reporter.to_summary(report)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
        print(f"\nReport saved to: {args.output}")
    else:
        print(output)

    # Exit code based on results
    if report.errors > 0 or report.timeouts > 0:
        sys.exit(2)  # Errors occurred
    elif report.failed > 0:
        sys.exit(1)  # Some tests failed
    else:
        sys.exit(0)  # All passed


def list_command(args):
    """List available scenarios."""
    scenarios = load_scenarios(args.path)

    if not scenarios:
        print(f"No scenarios found in {args.path}")
        sys.exit(1)

    print(f"\nScenarios in {args.path}:\n")
    for s in scenarios:
        tags = f" [{', '.join(s.tags)}]" if s.tags else ""
        print(f"  [{s.id}] {s.name} ({s.difficulty.value}){tags}")

    print(f"\nTotal: {len(scenarios)} scenarios")


def validate_command(args):
    """Validate scenario files."""
    scenarios = load_scenarios(args.path)

    if not scenarios:
        print(f"No scenarios found in {args.path}")
        sys.exit(1)

    dry = DryRunner()
    validation = dry.validate_scenarios(scenarios)

    print(f"\nValidation Results:\n")
    for result in validation["results"]:
        status = "✅" if result["valid"] else "❌"
        print(f"{status} [{result['scenario_id']}] {result['scenario_name']}")
        if result["issues"]:
            for issue in result["issues"]:
                print(f"   ⚠️  {issue}")
        if args.verbose:
            print(f"   Setup: {result['setup_files']} files, {result['setup_commands']} commands")
            print(f"   Verification: {result['verification_checks']} checks")

    print(f"\nSummary: {validation['valid']}/{validation['total']} valid")
    sys.exit(0 if validation["invalid"] == 0 else 1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Agent Eval - Test and evaluate AI coding agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all scenarios in a directory
  python -m council.agent_eval run scenarios/

  # Run a single scenario
  python -m council.agent_eval run my_scenario.yaml

  # Dry run to validate without executing
  python -m council.agent_eval run scenarios/ --dry-run

  # Generate markdown report
  python -m council.agent_eval run scenarios/ --format markdown --output report.md

  # List available scenarios
  python -m council.agent_eval list scenarios/

  # Validate scenario files
  python -m council.agent_eval validate scenarios/
""",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Quiet output (errors only)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run scenarios")
    run_parser.add_argument(
        "scenarios",
        type=Path,
        help="Path to scenario YAML file or directory",
    )
    run_parser.add_argument(
        "--config",
        type=Path,
        help="Path to config YAML",
    )
    run_parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output file path",
    )
    run_parser.add_argument(
        "--format", "-f",
        choices=["json", "markdown", "summary"],
        default="summary",
        help="Output format (default: summary)",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List scenarios without running",
    )
    run_parser.add_argument(
        "--timeout",
        type=int,
        help="Override agent timeout (seconds)",
    )
    run_parser.add_argument(
        "--no-watchdog",
        action="store_true",
        help="Disable watchdog evaluation",
    )
    run_parser.add_argument(
        "--keep-env",
        action="store_true",
        help="Keep environment after run (for debugging)",
    )
    run_parser.add_argument(
        "--tags",
        nargs="+",
        help="Only run scenarios with these tags",
    )
    run_parser.add_argument(
        "--difficulty",
        choices=["trivial", "easy", "medium", "hard", "expert"],
        help="Only run scenarios with this difficulty",
    )
    run_parser.set_defaults(func=run_command)

    # List command
    list_parser = subparsers.add_parser("list", help="List scenarios")
    list_parser.add_argument(
        "path",
        type=Path,
        help="Path to scenarios",
    )
    list_parser.set_defaults(func=list_command)

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate scenarios")
    validate_parser.add_argument(
        "path",
        type=Path,
        help="Path to scenarios",
    )
    validate_parser.set_defaults(func=validate_command)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    setup_logging(args.verbose, args.quiet)

    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(130)
    except Exception as e:
        logging.error(f"Error: {e}")
        if args.verbose:
            logging.exception("Full traceback:")
        sys.exit(1)


if __name__ == "__main__":
    main()
