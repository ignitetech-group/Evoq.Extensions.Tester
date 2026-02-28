"""
triage_parallelizer.py - Parallel triage of failed test scenarios.

Extracts all FAIL scenarios from the backup manifest, runs Claude Code
instances in parallel to classify each, and writes results to CSV.

Usage:
    python3 triage_parallelizer.py                  # Full run (all 233 scenarios)
    python3 triage_parallelizer.py --dry-run        # List scenarios without running
    python3 triage_parallelizer.py --test-one       # Run single scenario
    python3 triage_parallelizer.py --workers 20     # Set parallel workers
    python3 triage_parallelizer.py --extension ContentLayout  # Filter by extension
"""

import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from triager import (
    FailedScenario,
    TriageVerdict,
    ScenarioTriager,
    parse_manifest,
    extract_failed_scenarios,
    MANIFEST_FILE,
)
from utils import format_claude_output_line


# ============================================================================
# Parallel Runner
# ============================================================================

class TriageParallelizer:
    """
    Runs triage across all failed scenarios in parallel.

    SCALING GUIDE (same as testing parallelizer):
    - Console provider: 5-10 workers (rate limited)
    - API key provider: 10-20 workers
    - Bedrock provider: 20-50 workers
    """

    def __init__(
        self,
        repos_base_path: Path = Path("repos"),
        max_workers: int = 10,
        extension_filter: Optional[str] = None,
    ) -> None:
        self.repos_base_path = repos_base_path
        self.max_workers = max_workers
        self.extension_filter = extension_filter
        self.triager = ScenarioTriager(repos_base_path=repos_base_path)

        # Load scenarios
        print(f"Reading {MANIFEST_FILE}...")
        data = parse_manifest(MANIFEST_FILE)
        self.all_scenarios = extract_failed_scenarios(data)

        if extension_filter:
            self.scenarios = [
                s for s in self.all_scenarios
                if s.extension_name == extension_filter
            ]
            print(f"Filtered to {len(self.scenarios)} scenarios for '{extension_filter}'")
        else:
            self.scenarios = self.all_scenarios

        print(f"Loaded {len(self.scenarios)} FAIL scenarios for triage\n")

        # Cache directory for raw verdicts
        self.cache_dir = Path("triage_cache")
        self.cache_dir.mkdir(exist_ok=True)

    def run(self) -> List[TriageVerdict]:
        """Run triage on all scenarios in parallel."""
        print(f"Starting triage with {self.max_workers} workers...")
        print(f"Scenarios: {len(self.scenarios)}")
        print(f"{'=' * 60}\n")

        start_time = time.time()
        verdicts: List[TriageVerdict] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_scenario = {
                executor.submit(
                    self._triage_with_cache, scenario
                ): scenario
                for scenario in self.scenarios
            }

            completed = 0
            for future in as_completed(future_to_scenario):
                scenario = future_to_scenario[future]
                completed += 1
                try:
                    verdict = future.result()
                    verdicts.append(verdict)
                    icon = "🐛" if verdict.classification == "LEGITIMATE_BUG" else "🚫"
                    print(
                        f"[{completed}/{len(self.scenarios)}] {icon} "
                        f"{verdict.classification} ({verdict.confidence}) - "
                        f"{scenario.extension_name} > {scenario.scenario_name}"
                    )
                except Exception as e:
                    print(f"[{completed}/{len(self.scenarios)}] ❌ FAILED: {scenario.id}: {e}")
                    verdicts.append(TriageVerdict(
                        scenario=scenario,
                        classification="ERROR",
                        confidence="LOW",
                        reasoning=f"Triage failed: {e}",
                        evidence_summary="",
                        success=False,
                        error=str(e),
                    ))

        total_duration = time.time() - start_time

        # Print summary
        self._print_summary(verdicts, total_duration)

        # Write CSV
        csv_path = self._write_csv(verdicts)
        print(f"\nResults written to: {csv_path}")

        return verdicts

    def _triage_with_cache(self, scenario: FailedScenario) -> TriageVerdict:
        """Triage a scenario, using cache if available."""
        cache_path = self.cache_dir / f"{_safe_id(scenario)}.json"

        # Check cache
        if cache_path.exists():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                print(f"  ♻️  Cache hit: {scenario.scenario_name}")
                return TriageVerdict(
                    scenario=scenario,
                    classification=cached["classification"],
                    confidence=cached["confidence"],
                    reasoning=cached["reasoning"],
                    evidence_summary=cached["evidence_summary"],
                    success=True,
                )
            except (json.JSONDecodeError, KeyError):
                pass  # Re-run if cache is corrupt

        # Run triage
        verdict = self.triager.triage_scenario(scenario)

        # Save to cache
        if verdict.success and verdict.classification != "UNKNOWN":
            cache_data = {
                "classification": verdict.classification,
                "confidence": verdict.confidence,
                "reasoning": verdict.reasoning,
                "evidence_summary": verdict.evidence_summary,
                "scenario_id": scenario.id,
                "timestamp": datetime.now().isoformat(),
            }
            cache_path.write_text(
                json.dumps(cache_data, indent=2), encoding="utf-8"
            )

        return verdict

    def _print_summary(self, verdicts: List[TriageVerdict], duration: float) -> None:
        """Print triage summary statistics."""
        bugs = sum(1 for v in verdicts if v.classification == "LEGITIMATE_BUG")
        invalid = sum(1 for v in verdicts if v.classification == "INVALID_TEST")
        errors = sum(1 for v in verdicts if v.classification in ("UNKNOWN", "ERROR"))
        high_conf = sum(1 for v in verdicts if v.confidence == "HIGH")

        print(f"\n{'=' * 60}")
        print("📊 TRIAGE SUMMARY")
        print(f"{'=' * 60}")
        print(f"  Total scenarios:    {len(verdicts)}")
        print(f"  🐛 Legitimate bugs: {bugs}")
        print(f"  🚫 Invalid tests:   {invalid}")
        print(f"  ❌ Errors:          {errors}")
        print(f"  🎯 High confidence: {high_conf}")
        print(f"  ⏱️  Duration:        {duration:.0f}s ({duration / 60:.1f}m)")

        if bugs + invalid > 0:
            print(f"\n  Bug rate: {bugs / (bugs + invalid) * 100:.1f}% of classifiable failures are real bugs")

    def _write_csv(self, verdicts: List[TriageVerdict]) -> Path:
        """Write triage results to CSV."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = Path(f"triage_results_{timestamp}.csv")

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Extension",
                "Feature",
                "Scenario",
                "Classification",
                "Confidence",
                "Reasoning",
                "Evidence Summary",
                "Issues",
                "Step Count",
                "Duration (s)",
            ])

            for v in sorted(verdicts, key=lambda x: (
                x.classification != "LEGITIMATE_BUG",  # Bugs first
                x.confidence != "HIGH",  # High confidence first
                x.scenario.extension_name,
                x.scenario.feature_name,
            )):
                writer.writerow([
                    v.scenario.extension_name,
                    v.scenario.feature_name,
                    v.scenario.scenario_name,
                    v.classification,
                    v.confidence,
                    v.reasoning,
                    v.evidence_summary,
                    " | ".join(v.scenario.issues),
                    v.scenario.step_count,
                    f"{v.duration_seconds:.1f}",
                ])

        return csv_path


def _safe_id(scenario: FailedScenario) -> str:
    """Create a filesystem-safe ID for caching."""
    from prompts import sanitize_filename
    return sanitize_filename(
        f"{scenario.extension_name}_{scenario.feature_name}_{scenario.scenario_name}"
    )[:200]


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Triage failed test scenarios in parallel")
    parser.add_argument("--dry-run", action="store_true", help="List scenarios without running")
    parser.add_argument("--test-one", action="store_true", help="Run single scenario for testing")
    parser.add_argument("--workers", type=int, default=10, help="Number of parallel workers (default: 10)")
    parser.add_argument("--extension", type=str, default=None, help="Filter by extension name")
    args = parser.parse_args()

    if args.dry_run:
        data = parse_manifest(MANIFEST_FILE)
        scenarios = extract_failed_scenarios(data)
        if args.extension:
            scenarios = [s for s in scenarios if s.extension_name == args.extension]

        # Group by extension
        by_ext: Dict[str, List[FailedScenario]] = {}
        for s in scenarios:
            by_ext.setdefault(s.extension_name, []).append(s)

        for ext_name, ext_scenarios in sorted(by_ext.items()):
            print(f"\n📦 {ext_name} ({len(ext_scenarios)} failures)")
            for s in ext_scenarios:
                print(f"   • {s.feature_name} > {s.scenario_name}")
                if s.issues:
                    for issue in s.issues:
                        print(f"     └─ {issue[:100]}")

        print(f"\nTotal: {len(scenarios)} FAIL scenarios ready for triage")
        return

    if args.test_one:
        runner = TriageParallelizer(
            max_workers=1,
            extension_filter=args.extension,
        )
        if not runner.scenarios:
            print("No scenarios found.")
            return
        scenario = runner.scenarios[0]
        print(f"Testing single scenario: {scenario.id}\n")
        verdict = runner.triager.triage_scenario(scenario)
        print(f"\n{'=' * 60}")
        print(f"Scenario:       {scenario.id}")
        print(f"Classification: {verdict.classification}")
        print(f"Confidence:     {verdict.confidence}")
        print(f"Reasoning:      {verdict.reasoning}")
        print(f"Evidence:       {verdict.evidence_summary}")
        print(f"Duration:       {verdict.duration_seconds:.1f}s")
        print(f"Success:        {verdict.success}")
        if verdict.error:
            print(f"Error:          {verdict.error}")
        return

    # Full run
    runner = TriageParallelizer(
        max_workers=args.workers,
        extension_filter=args.extension,
    )
    runner.run()


if __name__ == "__main__":
    main()
