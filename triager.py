"""
triager.py - Triage failed test scenarios using parallel Claude Code instances.

Reads the backup manifest (manifest copy.js) containing FAIL scenarios,
spawns a Claude Code instance per scenario to classify each as either
INVALID_TEST or LEGITIMATE_BUG based on screenshots and test evidence.
"""

import json
import os
import subprocess
import tempfile
import time
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from config import CLAUDE_MODEL, CLAUDE_ENV, CLAUDE_TIMEOUT
from utils import format_claude_output_line
from prompts import sanitize_filename


# ============================================================================
# Types
# ============================================================================

@dataclass
class FailedScenario:
    """A single failed test scenario extracted from the manifest."""
    extension_name: str
    extension_folder: str
    feature_name: str
    scenario_name: str
    status: str
    steps: List[Dict[str, Any]]
    issues: List[str]
    observations: List[str]
    screenshots: List[str]
    step_count: int

    @property
    def id(self) -> str:
        return f"{self.extension_name}::{self.feature_name}::{self.scenario_name}"


@dataclass
class TriageVerdict:
    """Classification result from a Claude Code triage instance."""
    scenario: FailedScenario
    classification: str  # INVALID_TEST or LEGITIMATE_BUG
    confidence: str  # HIGH, MEDIUM, LOW
    reasoning: str
    evidence_summary: str
    raw_output: str = ""
    success: bool = False
    error: str = ""
    duration_seconds: float = 0.0


# ============================================================================
# Manifest Parser
# ============================================================================

MANIFEST_FILE = Path("manifest copy.js")
PREFIX = "window.MANIFEST_DATA = "


def parse_manifest(path: Path) -> Dict[str, Any]:
    """Read a manifest JS file and return parsed JSON data."""
    text = path.read_text(encoding="utf-8")
    json_start = text.index(PREFIX) + len(PREFIX)
    json_text = text[json_start:].rstrip().rstrip(";")
    return json.loads(json_text)


def extract_failed_scenarios(data: Dict[str, Any]) -> List[FailedScenario]:
    """Extract all FAIL scenarios from manifest data with full context."""
    output_folder = data.get("outputFolder", "repos")
    failed: List[FailedScenario] = []

    for ext_name, ext in data.get("results", {}).items():
        ext_folder = ext.get("folder", f"{ext_name}_result")

        for feat_name, feat in ext.get("features", {}).items():
            observations = feat.get("observations", [])
            screenshots = feat.get("screenshots", [])
            full_data = feat.get("full_data")

            # Build a lookup from full_data scenarios for step details
            full_scenarios: Dict[str, Dict] = {}
            if isinstance(full_data, dict):
                for ts in full_data.get("test_scenarios", []):
                    if isinstance(ts, dict):
                        full_scenarios[ts.get("scenario_name", "")] = ts

            for s in feat.get("scenarios", []):
                if s.get("status") != "FAIL":
                    continue

                scenario_name = s.get("name", "")
                full_s = full_scenarios.get(scenario_name, {})
                steps = full_s.get("steps", [])
                issues = full_s.get("issues", s.get("issues", []))

                failed.append(FailedScenario(
                    extension_name=ext_name,
                    extension_folder=ext_folder,
                    feature_name=feat_name,
                    scenario_name=scenario_name,
                    status="FAIL",
                    steps=steps,
                    issues=issues,
                    observations=observations,
                    screenshots=screenshots,
                    step_count=s.get("step_count", len(steps)),
                ))

    return failed


# ============================================================================
# Prompt Generation
# ============================================================================

def generate_triage_prompt(
    scenario: FailedScenario,
    repos_base_path: Path,
) -> str:
    """Build the triage prompt for a single failed scenario."""

    # Use absolute paths so Claude can reliably read screenshots
    abs_repos = repos_base_path.resolve()

    # Build step details
    steps_text = ""
    screenshot_paths = []
    for step in scenario.steps:
        sn = step.get("step_number", "?")
        action = step.get("action", "N/A")
        expected = step.get("expected", "N/A")
        actual = step.get("actual", "N/A")
        screenshot = step.get("screenshot", "")

        steps_text += f"""
### Step {sn}
- **Action**: {action}
- **Expected**: {expected}
- **Actual**: {actual}"""

        if screenshot:
            screenshot_path = abs_repos / scenario.extension_folder / screenshot
            steps_text += f"\n- **Screenshot**: `{screenshot_path}`"
            screenshot_paths.append(str(screenshot_path))

    # Build issues list
    issues_text = "\n".join(f"- {issue}" for issue in scenario.issues) if scenario.issues else "- None reported"

    # Build observations
    obs_text = "\n".join(f"- {obs}" for obs in scenario.observations[:5]) if scenario.observations else "- None"

    # Screenshot read instructions
    screenshot_instructions = ""
    if screenshot_paths:
        screenshot_instructions = "\n## Screenshots to Review\nUse the Read tool to view EACH of these screenshot images:\n"
        for sp in screenshot_paths:
            screenshot_instructions += f"- `{sp}`\n"

    prompt = f"""# Triage Task: Classify Failed Test Scenario

You are triaging a test scenario that was marked as FAIL during automated testing of Evoq CMS extensions. Your job is to determine whether this is a **real bug** or a **false positive** from the testing tool.

## Failed Scenario Details

- **Extension**: {scenario.extension_name}
- **Feature**: {scenario.feature_name}
- **Scenario**: {scenario.scenario_name}
- **Step Count**: {scenario.step_count}

## Test Steps and Evidence
{steps_text}

## Reported Issues
{issues_text}

## Observations from Test Run
{obs_text}
{screenshot_instructions}

## Your Instructions

1. **Read each screenshot** listed above using the Read tool. Examine what the UI actually shows.
2. **Analyze the test steps**: Compare what was expected vs what actually happened.
3. **Consider the issues**: Are they describing actual errors, or did the tool misunderstand?
4. **Make your classification**:

### Classification Rules

**LEGITIMATE_BUG** - Mark as this if ANY of these are true:
- There is an actual error message visible in the UI or logs (JavaScript errors, server errors, 500 errors)
- A button or UI element is broken, unresponsive, or produces unexpected errors when clicked
- Functionality that clearly SHOULD work based on the UI is failing (e.g., a save button that doesn't save)
- Data corruption or loss is occurring
- The application crashes, shows error dialogs, or enters an invalid state

**INVALID_TEST** - Mark as this if ANY of these are true:
- The test looked for UI/functionality that was never meant to exist (e.g., looking for a "Migration Tool" menu item that's actually an automatic background process)
- The test assumed something should be visible in the UI because it saw it in the code, but it's an internal/backend-only feature
- The test was checking implementation details rather than user-facing behavior (e.g., checking CSS classes, checking internal resource file strings)
- The failure is because the tester navigated to the wrong location or misunderstood where the feature lives
- The test created its own problem (e.g., conflicting with its own prior actions) and blamed the application
- The test was checking for something that requires specific preconditions that weren't met (not a bug, just an incomplete test setup)

## Output

After reviewing all evidence, output ONLY a valid JSON object (no markdown fences, no explanation outside the JSON):

{{
  "classification": "LEGITIMATE_BUG or INVALID_TEST",
  "confidence": "HIGH or MEDIUM or LOW",
  "reasoning": "1-2 sentence explanation of why you classified it this way",
  "evidence_summary": "Brief description of what the screenshots and test steps actually show"
}}
"""
    return prompt


# ============================================================================
# Triager Class
# ============================================================================

class ScenarioTriager:
    """Runs a single Claude Code instance to triage a failed scenario."""

    repos_base_path: Path

    def __init__(self, repos_base_path: Path) -> None:
        self.repos_base_path = repos_base_path

    def triage_scenario(
        self,
        scenario: FailedScenario,
        on_output: Optional[Callable[[FailedScenario, str], None]] = None,
    ) -> TriageVerdict:
        """Triage a single failed scenario using Claude Code CLI."""

        prompt = generate_triage_prompt(scenario, self.repos_base_path)

        # Write prompt to temp file
        safe_name = sanitize_filename(
            f"{scenario.extension_name}_{scenario.feature_name}_{scenario.scenario_name}"
        )
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".md",
            prefix=f"triage_{safe_name}_",
            dir=self.repos_base_path,
            delete=False,
            encoding="utf-8",
        )
        complex_prompt_filename = Path(temp_file.name)

        verdict = TriageVerdict(
            scenario=scenario,
            classification="UNKNOWN",
            confidence="LOW",
            reasoning="Triage did not complete",
            evidence_summary="",
        )

        try:
            temp_file.write(prompt)
            temp_file.close()

            simple_prompt = (
                f"Read the file {complex_prompt_filename} and follow ALL instructions in it completely."
            )

            start_time = time.time()

            # Build command
            import platform
            import shutil

            claude_cmd = "claude"
            if platform.system() == "Windows":
                claude_path = shutil.which("claude")
                if claude_path:
                    claude_cmd = claude_path
                elif shutil.which("claude.cmd"):
                    claude_cmd = "claude.cmd"

            cmd = [
                claude_cmd,
                "-p", simple_prompt,
                "--model", CLAUDE_MODEL,
                "--output-format", "stream-json",
                "--verbose",
                "--dangerously-skip-permissions",
                "--allowedTools", "Read,Grep,Glob",
            ]

            env = os.environ.copy()
            env.update(CLAUDE_ENV)

            process = subprocess.Popen(
                cmd,
                cwd=str(self.repos_base_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )

            context = f"{scenario.extension_name} > {scenario.feature_name} > {scenario.scenario_name}"
            print(f"🔍 Triaging: {context}")

            output_lines = []
            for line in process.stdout:
                formatted_line, raw_data = format_claude_output_line(line)
                if on_output:
                    on_output(scenario, line)
                elif formatted_line:
                    print(formatted_line)
                output_lines.append(line)

            process.wait(timeout=CLAUDE_TIMEOUT)
            duration = time.time() - start_time
            full_output = "\n".join(output_lines)

            verdict.raw_output = full_output
            verdict.duration_seconds = duration
            verdict.success = process.returncode == 0
            verdict.error = process.stderr.read()

            # Parse the verdict from Claude's output
            parsed = _parse_triage_output(full_output)
            if parsed:
                verdict.classification = parsed.get("classification", "UNKNOWN")
                verdict.confidence = parsed.get("confidence", "LOW")
                verdict.reasoning = parsed.get("reasoning", "")
                verdict.evidence_summary = parsed.get("evidence_summary", "")

            return verdict

        finally:
            if complex_prompt_filename.exists():
                complex_prompt_filename.unlink()


def _parse_triage_output(raw_output: str) -> Optional[Dict[str, Any]]:
    """Extract the JSON verdict from Claude's stream-json output."""
    # The stream-json format has multiple JSON lines. We need to find
    # the assistant's text output that contains our verdict JSON.
    text_parts = []

    for line in raw_output.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if data.get("type") == "assistant":
                content = data.get("message", {}).get("content", [])
                for block in content:
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
        except json.JSONDecodeError:
            continue

    full_text = "\n".join(text_parts)

    # Try to find JSON in the text
    # Look for the classification JSON object
    for attempt in [full_text]:
        # Try to find { ... } containing "classification"
        start = attempt.find("{")
        while start >= 0:
            # Find matching closing brace
            depth = 0
            for i in range(start, len(attempt)):
                if attempt[i] == "{":
                    depth += 1
                elif attempt[i] == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = attempt[start:i + 1]
                        try:
                            parsed = json.loads(candidate)
                            if "classification" in parsed:
                                return parsed
                        except json.JSONDecodeError:
                            pass
                        break
            start = attempt.find("{", start + 1)

    return None


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import sys

    dry_run = "--dry-run" in sys.argv
    test_one = "--test-one" in sys.argv

    print(f"Reading {MANIFEST_FILE}...")
    data = parse_manifest(MANIFEST_FILE)
    scenarios = extract_failed_scenarios(data)
    print(f"Found {len(scenarios)} FAIL scenarios\n")

    if dry_run:
        for i, s in enumerate(scenarios):
            print(f"{i + 1:3d}. [{s.extension_name}] {s.feature_name} > {s.scenario_name}")
            if s.issues:
                for issue in s.issues:
                    print(f"     Issue: {issue}")
            print(f"     Steps: {s.step_count}")
            print()
        print(f"\nTotal: {len(scenarios)} FAIL scenarios ready for triage")
        sys.exit(0)

    if test_one:
        triager = ScenarioTriager(repos_base_path=Path("repos"))
        scenario = scenarios[0]
        print(f"Testing single scenario: {scenario.id}\n")
        verdict = triager.triage_scenario(scenario)
        print(f"\n{'=' * 60}")
        print(f"Classification: {verdict.classification}")
        print(f"Confidence: {verdict.confidence}")
        print(f"Reasoning: {verdict.reasoning}")
        print(f"Evidence: {verdict.evidence_summary}")
        print(f"Duration: {verdict.duration_seconds:.1f}s")
        print(f"Success: {verdict.success}")
        if verdict.error:
            print(f"Error: {verdict.error}")
        sys.exit(0)
