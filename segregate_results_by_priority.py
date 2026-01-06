"""
Segregate *_result folders into priority buckets based on evoq_extensions.csv.

Logic:
  - For each folder in SOURCE that ends with "_result"
  - Extension Name = folder name with trailing "_result" removed
  - Look up "Priority for E2E Testing" in evoq_extensions.csv by matching "Extension Name"
  - Copy (default) or move the whole folder into:
        DEST/<Priority>/<original_folder_name>/

Defaults:
  - source: ./Final Results
  - dest:   ./Final Results By Priority
  - csv:    ./evoq_extensions.csv
  - if dest exists and not --overwrite: use timestamped dest folder name

Examples:
  python segregate_results_by_priority.py --dry-run
  python segregate_results_by_priority.py
  python segregate_results_by_priority.py --move
  python segregate_results_by_priority.py --dest "C:\\DNN\\Evoq.Extensions.Tester\\Final Results By Priority"
  python segregate_results_by_priority.py --priority-column "Priority for E2E Testing"
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Tuple


@dataclass(frozen=True)
class SegregateStats:
    scanned_folders: int
    copied: int
    moved: int
    skipped: int
    errors: int
    per_priority: Dict[str, int]


def _timestamp_suffix() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _sanitize_folder_name(name: str) -> str:
    """
    Windows-safe-ish folder names for priority buckets.
    Keep it simple: replace runs of non [A-Za-z0-9._- ] with underscore and trim.
    """
    name = name.strip()
    if not name:
        return "Unknown"
    name = re.sub(r"[^A-Za-z0-9._\- ]+", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "Unknown"


def _iter_result_dirs(source_dir: Path) -> Iterable[Path]:
    for p in source_dir.iterdir():
        if p.is_dir() and p.name.endswith("_result"):
            yield p


def _load_priority_map(
    csv_path: Path,
    *,
    extension_name_column: str = "Extension Name",
    priority_column: str = "Priority for E2E Testing",
) -> Dict[str, str]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    mapping: Dict[str, str] = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row")

        for row in reader:
            ext = (row.get(extension_name_column) or "").strip()
            pri = (row.get(priority_column) or "").strip()
            if not ext:
                continue
            # Prefer first non-empty priority; keep existing if already set and new is blank.
            if ext not in mapping or (not mapping[ext] and pri):
                mapping[ext] = pri

    return mapping


def segregate_results_by_priority(
    *,
    source_dir: Path,
    dest_dir: Path,
    csv_path: Path,
    extension_name_column: str = "Extension Name",
    priority_column: str = "Priority for E2E Testing",
    dry_run: bool = False,
    overwrite: bool = False,
    move: bool = False,
    verbose: bool = True,
) -> Tuple[Path, SegregateStats]:
    source_dir = source_dir.resolve()
    dest_dir = dest_dir.resolve()
    csv_path = csv_path.resolve()

    if not source_dir.exists() or not source_dir.is_dir():
        raise FileNotFoundError(f"Source folder not found: {source_dir}")

    priority_map = _load_priority_map(
        csv_path,
        extension_name_column=extension_name_column,
        priority_column=priority_column,
    )

    final_dest = dest_dir
    if final_dest.exists() and not overwrite:
        final_dest = final_dest.parent / f"{final_dest.name} {_timestamp_suffix()}"

    scanned_folders = copied = moved_count = skipped = errors = 0
    per_priority_counter: Counter[str] = Counter()

    for src_dir in _iter_result_dirs(source_dir):
        scanned_folders += 1
        extension_name = src_dir.name[: -len("_result")]

        priority = priority_map.get(extension_name, "").strip()
        if not priority or priority.upper() == "N/A":
            priority_bucket = "Unknown"
        else:
            priority_bucket = _sanitize_folder_name(priority)

        per_priority_counter[priority_bucket] += 1

        dest_subdir = final_dest / priority_bucket / src_dir.name
        if dest_subdir.exists() and not overwrite:
            skipped += 1
            if verbose:
                print(f"SKIP (exists): {priority_bucket}\\{src_dir.name}")
            continue

        try:
            if verbose:
                action = "WOULD MOVE" if (dry_run and move) else "MOVE" if move else "WOULD COPY" if dry_run else "COPY"
                if dest_subdir.exists() and overwrite:
                    action = (
                        "WOULD REPLACE+MOVE" if (dry_run and move) else "REPLACE+MOVE"
                        if move
                        else "WOULD REPLACE+COPY"
                        if dry_run
                        else "REPLACE+COPY"
                    )
                print(f"{action}: {src_dir.name} -> {priority_bucket}\\{src_dir.name}")

            if not dry_run:
                dest_subdir.parent.mkdir(parents=True, exist_ok=True)
                if dest_subdir.exists() and overwrite:
                    shutil.rmtree(dest_subdir)

                if move:
                    shutil.move(str(src_dir), str(dest_subdir))
                    moved_count += 1
                else:
                    shutil.copytree(src_dir, dest_subdir)
                    copied += 1
        except Exception as ex:
            errors += 1
            print(f"ERROR processing {src_dir} -> {dest_subdir}: {ex}")

    return final_dest, SegregateStats(
        scanned_folders=scanned_folders,
        copied=copied,
        moved=moved_count,
        skipped=skipped,
        errors=errors,
        per_priority=dict(per_priority_counter),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Segregate *_result folders into priority buckets based on evoq_extensions.csv."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("Final Results"),
        help="Source folder containing *_result folders (default: ./Final Results)",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=Path("Final Results By Priority"),
        help="Destination folder (default: ./Final Results By Priority)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("evoq_extensions.csv"),
        help="CSV path (default: ./evoq_extensions.csv)",
    )
    parser.add_argument(
        "--extension-name-column",
        default="Extension Name",
        help='CSV column for extension name (default: "Extension Name")',
    )
    parser.add_argument(
        "--priority-column",
        default="Priority for E2E Testing",
        help='CSV column for priority (default: "Priority for E2E Testing")',
    )
    parser.add_argument(
        "--move",
        action="store_true",
        help="Move folders instead of copying (default: copy)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without changing files",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace destination folders if they already exist",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Don't print per-folder actions (still prints summary)",
    )
    args = parser.parse_args()

    final_dest, stats = segregate_results_by_priority(
        source_dir=args.source,
        dest_dir=args.dest,
        csv_path=args.csv,
        extension_name_column=args.extension_name_column,
        priority_column=args.priority_column,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
        move=args.move,
        verbose=not args.quiet,
    )

    # Stable-ish ordering for display.
    buckets = sorted(stats.per_priority.items(), key=lambda kv: (kv[0].lower(), kv[0]))

    print(
        "\nSummary:"
        f"\n  destination: {final_dest}"
        f"\n  scanned folders: {stats.scanned_folders}"
        f"\n  copied: {stats.copied}"
        f"\n  moved: {stats.moved}"
        f"\n  skipped: {stats.skipped}"
        f"\n  errors: {stats.errors}"
    )
    if buckets:
        print("\nBy priority:")
        for name, count in buckets:
            print(f"  {name}: {count}")

    return 1 if stats.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())


