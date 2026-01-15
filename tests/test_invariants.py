"""
Tests for scripts/check_invariants.py

Verifies that the invariants checker correctly:
- Parses invariants.yaml
- Detects forbidden path violations
- Detects protected path violations
- Respects --allow-protected flag
"""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from check_invariants import (
    check_invariants,
    load_invariants,
    match_patterns,
    InvariantsResult,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "repos"


class TestLoadInvariants:
    """Test invariants.yaml parsing."""

    def test_load_existing_invariants(self):
        """Should load invariants from YAML file."""
        inv = load_invariants(FIXTURES_DIR / "clean_diff" / ".council" / "invariants.yaml")
        assert "forbidden_paths" in inv
        assert "protected_paths" in inv
        assert len(inv["forbidden_paths"]) > 0

    def test_load_missing_invariants(self):
        """Should return empty lists for missing file."""
        inv = load_invariants(Path("/nonexistent/path/invariants.yaml"))
        assert inv.get("forbidden_paths", []) == []
        assert inv.get("protected_paths", []) == []


class TestMatchPatterns:
    """Test pattern matching logic."""

    def test_match_glob_pattern(self):
        """Should match glob patterns like *.env."""
        patterns = ["*.env", "credentials/*"]
        assert match_patterns(".env", patterns) == "*.env"
        assert match_patterns("production.env", patterns) == "*.env"

    def test_match_directory_pattern(self):
        """Should match directory patterns like credentials/*."""
        patterns = ["credentials/*"]
        assert match_patterns("credentials/api_key.txt", patterns) == "credentials/*"
        assert match_patterns("credentials/config.yaml", patterns) == "credentials/*"

    def test_no_match(self):
        """Should return None when no pattern matches."""
        patterns = ["*.env", "credentials/*"]
        assert match_patterns("main.py", patterns) is None
        assert match_patterns("src/utils.py", patterns) is None


class TestCheckInvariantsCleanDiff:
    """Test clean diff scenario."""

    def test_clean_diff_passes(self):
        """Should pass when no invariants violated."""
        result = check_invariants(
            invariants_path=FIXTURES_DIR / "clean_diff" / ".council" / "invariants.yaml",
            diff_ref="HEAD~1",
            repo_path=FIXTURES_DIR / "clean_diff"
        )
        assert result.exit_code == 0
        assert len(result.violations) == 0
        assert "No invariant violations" in result.output


class TestCheckInvariantsForbidden:
    """Test forbidden path violations."""

    def test_forbidden_path_blocks(self):
        """Should fail when touching forbidden paths."""
        result = check_invariants(
            invariants_path=FIXTURES_DIR / "forbidden_touched" / ".council" / "invariants.yaml",
            diff_ref="HEAD~1",
            repo_path=FIXTURES_DIR / "forbidden_touched"
        )
        assert result.exit_code == 1
        assert len(result.violations) > 0
        assert any(v.violation_type == "FORBIDDEN" for v in result.violations)
        assert "FORBIDDEN" in result.output


class TestCheckInvariantsProtected:
    """Test protected path violations."""

    def test_protected_path_warns(self):
        """Should fail on protected paths without --allow-protected."""
        result = check_invariants(
            invariants_path=FIXTURES_DIR / "protected_touched" / ".council" / "invariants.yaml",
            diff_ref="HEAD~1",
            repo_path=FIXTURES_DIR / "protected_touched"
        )
        assert result.exit_code == 1
        assert any(v.violation_type == "PROTECTED" for v in result.violations)
        assert "PROTECTED" in result.output

    def test_allow_protected_overrides(self):
        """Should pass protected with --allow-protected flag."""
        result = check_invariants(
            invariants_path=FIXTURES_DIR / "protected_touched" / ".council" / "invariants.yaml",
            diff_ref="HEAD~1",
            repo_path=FIXTURES_DIR / "protected_touched",
            allow_protected=True
        )
        # Should pass because protected is allowed
        assert result.exit_code == 0


class TestCheckInvariantsMixed:
    """Test mixed violations scenario."""

    def test_mixed_violations_fails(self):
        """Should catch multiple violation types."""
        result = check_invariants(
            invariants_path=FIXTURES_DIR / "mixed_violations" / ".council" / "invariants.yaml",
            diff_ref="HEAD~1",
            repo_path=FIXTURES_DIR / "mixed_violations"
        )
        assert result.exit_code == 1
        assert len(result.violations) >= 2  # At least .env and credentials/*
        violation_types = {v.violation_type for v in result.violations}
        assert "FORBIDDEN" in violation_types

    def test_allow_protected_still_blocks_forbidden(self):
        """--allow-protected should NOT bypass forbidden violations."""
        result = check_invariants(
            invariants_path=FIXTURES_DIR / "mixed_violations" / ".council" / "invariants.yaml",
            diff_ref="HEAD~1",
            repo_path=FIXTURES_DIR / "mixed_violations",
            allow_protected=True
        )
        # Should still fail because of FORBIDDEN paths
        assert result.exit_code == 1
        assert any(v.violation_type == "FORBIDDEN" for v in result.violations)


class TestOutputFormat:
    """Test output formatting."""

    def test_output_has_emoji_indicators(self):
        """Output should use visual indicators."""
        result = check_invariants(
            invariants_path=FIXTURES_DIR / "clean_diff" / ".council" / "invariants.yaml",
            diff_ref="HEAD~1",
            repo_path=FIXTURES_DIR / "clean_diff"
        )
        # Clean should have checkmark
        assert "✅" in result.output

    def test_violation_output_shows_pattern(self):
        """Violation output should show matched pattern."""
        result = check_invariants(
            invariants_path=FIXTURES_DIR / "forbidden_touched" / ".council" / "invariants.yaml",
            diff_ref="HEAD~1",
            repo_path=FIXTURES_DIR / "forbidden_touched"
        )
        assert "pattern" in result.output.lower()
