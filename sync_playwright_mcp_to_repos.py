"""
Ensure all files under `repos/.playwright-mcp` also exist under `repos/`.

This mirrors the `.playwright-mcp` directory tree into the parent `repos` folder:
  - For every file in `repos/.playwright-mcp/**`, ensure `repos/**` contains the same relative file.
  - By default, it does NOT overwrite existing files (use --overwrite if you want that).

Example:
  python sync_playwright_mcp_to_repos.py --dry-run
  python sync_playwright_mcp_to_repos.py
  python sync_playwright_mcp_to_repos.py --overwrite
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class SyncStats:
    scanned: int
    missing: int
    copied: int
    skipped_existing: int
    identical: int
    mismatched: int
    overwritten: int
    errors: int


def _iter_files(root: Path):
    # pathlib.Path.rglob is simple and works well on Windows.
    for p in root.rglob("*"):
        if p.is_file():
            yield p


def _sha256(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


VerifyMode = Literal["none", "size", "sha256"]


def _files_match(src: Path, dest: Path, verify: VerifyMode) -> bool:
    if verify == "none":
        return True
    if verify == "size":
        return src.stat().st_size == dest.stat().st_size
    if verify == "sha256":
        # Quick reject: if size differs, hash can't match.
        if src.stat().st_size != dest.stat().st_size:
            return False
        return _sha256(src) == _sha256(dest)
    raise ValueError(f"Unknown verify mode: {verify}")


def sync_playwright_mcp_to_repos(
    repos_root: Path,
    mcp_root: Path,
    *,
    dry_run: bool = False,
    overwrite: bool = False,
    verify: VerifyMode = "size",
    verbose: bool = True,
) -> SyncStats:
    repos_root = repos_root.resolve()
    mcp_root = mcp_root.resolve()

    if not mcp_root.exists() or not mcp_root.is_dir():
        raise FileNotFoundError(f"Missing source folder: {mcp_root}")
    if not repos_root.exists() or not repos_root.is_dir():
        raise FileNotFoundError(f"Missing destination folder: {repos_root}")

    scanned = missing = copied = skipped_existing = identical = mismatched = overwritten = errors = 0

    for src in _iter_files(mcp_root):
        scanned += 1
        rel = src.relative_to(mcp_root)
        dest = repos_root / rel

        if dest.exists():
            try:
                matches = _files_match(src, dest, verify)
            except Exception as ex:
                errors += 1
                print(f"ERROR verifying {rel}: {ex}")
                continue

            if matches:
                identical += 1
                skipped_existing += 1
                continue

            # Exists but doesn't match.
            mismatched += 1
            if not overwrite:
                if verbose:
                    print(f"MISMATCH (skipping): {rel}")
                continue

        # Track "missing" as "didn't exist before copy"; if overwrite, it may exist.
        if not dest.exists():
            missing += 1

        try:
            if verbose:
                action = "WOULD COPY" if dry_run else "COPY"
                if dest.exists() and overwrite:
                    action = "WOULD OVERWRITE" if dry_run else "OVERWRITE"
                print(f"{action}: {rel}")

            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                copied += 1
                if dest.exists() and overwrite:
                    overwritten += 1
        except Exception as ex:
            errors += 1
            print(f"ERROR copying {src} -> {dest}: {ex}")

    return SyncStats(
        scanned=scanned,
        missing=missing,
        copied=copied,
        skipped_existing=skipped_existing,
        identical=identical,
        mismatched=mismatched,
        overwritten=overwritten,
        errors=errors,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mirror repos/.playwright-mcp files into repos so nothing is missing."
    )
    parser.add_argument(
        "--repos",
        type=Path,
        default=Path("repos"),
        help="Destination repos folder (default: ./repos)",
    )
    parser.add_argument(
        "--mcp",
        type=Path,
        default=Path("repos") / ".playwright-mcp",
        help="Source .playwright-mcp folder (default: ./repos/.playwright-mcp)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be copied, but don't write anything",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files in repos (default: skip existing)",
    )
    parser.add_argument(
        "--verify",
        choices=["none", "size", "sha256"],
        default="size",
        help="How to verify existing files match: none|size|sha256 (default: size)",
    )
    parser.add_argument(
        "--fail-on-mismatch",
        action="store_true",
        help="Exit non-zero if any existing files differ (even if not copying/overwriting)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Don't print per-file actions (still prints final summary)",
    )

    args = parser.parse_args()

    stats = sync_playwright_mcp_to_repos(
        repos_root=args.repos,
        mcp_root=args.mcp,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
        verify=args.verify,
        verbose=not args.quiet,
    )

    print(
        "\nSummary:"
        f"\n  scanned files: {stats.scanned}"
        f"\n  missing in repos: {stats.missing}"
        f"\n  copied: {stats.copied}"
        f"\n  skipped (already existed): {stats.skipped_existing}"
        f"\n  identical (per --verify): {stats.identical}"
        f"\n  mismatched (per --verify): {stats.mismatched}"
        f"\n  overwritten: {stats.overwritten}"
        f"\n  errors: {stats.errors}"
    )

    if stats.errors:
        return 1
    if args.fail_on_mismatch and stats.mismatched:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


