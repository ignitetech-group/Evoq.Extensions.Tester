"""
Copy test result folders out of ./repos into a "Final Results" folder.

Default behavior:
  - Copies ONLY folders under ./repos that end with "_result"
  - Destination defaults to: ./Final Results
  - If destination exists, a timestamped folder name is used unless --overwrite is provided

Examples:
  python copy_repos_results_to_final.py --dry-run
  python copy_repos_results_to_final.py
  python copy_repos_results_to_final.py --overwrite
  python copy_repos_results_to_final.py --all-folders
  python copy_repos_results_to_final.py --dest "C:\\DNN\\Evoq.Extensions.Tester\\Final Results"
"""

from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class CopyStats:
    candidates: int
    copied: int
    skipped: int
    errors: int


def _timestamp_suffix() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _iter_source_dirs(repos_dir: Path, *, all_folders: bool) -> Iterable[Path]:
    for p in repos_dir.iterdir():
        if not p.is_dir():
            continue
        if p.name == ".playwright-mcp":
            continue
        if all_folders or p.name.endswith("_result"):
            yield p


def copy_repos_to_final(
    repos_dir: Path,
    dest_dir: Path,
    *,
    all_folders: bool = False,
    dry_run: bool = False,
    overwrite: bool = False,
    verbose: bool = True,
) -> tuple[Path, CopyStats]:
    repos_dir = repos_dir.resolve()
    dest_dir = dest_dir.resolve()

    if not repos_dir.exists() or not repos_dir.is_dir():
        raise FileNotFoundError(f"Missing repos folder: {repos_dir}")

    final_dest = dest_dir
    if final_dest.exists() and not overwrite:
        final_dest = final_dest.parent / f"{final_dest.name} {_timestamp_suffix()}"

    candidates = copied = skipped = errors = 0

    for src_dir in _iter_source_dirs(repos_dir, all_folders=all_folders):
        candidates += 1
        dest_subdir = final_dest / src_dir.name

        if dest_subdir.exists() and not overwrite:
            skipped += 1
            if verbose:
                print(f"SKIP (exists): {src_dir.name}")
            continue

        try:
            if verbose:
                action = "WOULD COPY" if dry_run else "COPY"
                if dest_subdir.exists() and overwrite:
                    action = "WOULD REPLACE" if dry_run else "REPLACE"
                print(f"{action}: {src_dir.name}")

            if not dry_run:
                final_dest.mkdir(parents=True, exist_ok=True)
                if dest_subdir.exists() and overwrite:
                    shutil.rmtree(dest_subdir)
                shutil.copytree(src_dir, dest_subdir)
                copied += 1
        except Exception as ex:
            errors += 1
            print(f"ERROR copying {src_dir} -> {dest_subdir}: {ex}")

    return final_dest, CopyStats(
        candidates=candidates,
        copied=copied,
        skipped=skipped,
        errors=errors,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy repos result folders into a 'Final Results' folder."
    )
    parser.add_argument(
        "--repos",
        type=Path,
        default=Path("repos"),
        help="Source repos folder (default: ./repos)",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=Path("Final Results"),
        help="Destination folder (default: ./Final Results)",
    )
    parser.add_argument(
        "--all-folders",
        action="store_true",
        help="Copy ALL folders in repos (except .playwright-mcp). Default copies only *_result folders.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be copied, but don't write anything",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace destination subfolders if they already exist",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Don't print per-folder actions (still prints summary)",
    )
    args = parser.parse_args()

    final_dest, stats = copy_repos_to_final(
        repos_dir=args.repos,
        dest_dir=args.dest,
        all_folders=args.all_folders,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
        verbose=not args.quiet,
    )

    print(
        "\nSummary:"
        f"\n  destination: {final_dest}"
        f"\n  folders considered: {stats.candidates}"
        f"\n  copied: {stats.copied}"
        f"\n  skipped: {stats.skipped}"
        f"\n  errors: {stats.errors}"
    )

    return 1 if stats.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())


