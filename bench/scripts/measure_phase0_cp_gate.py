"""Measure the Phase 0 exit gate that requires real-API CP runs.

The v2 evidence-locked design's Phase 0 gate requires:
    thin_block_full_skopus_score >= 0.95 * pre_slim_full_skopus_score

This script:
  1. Checks out commit 77c2d94^ (the commit just BEFORE the slim block
     shipped) into a temporary git worktree.
  2. Runs `skopus bench run cp --driver anthropic --lens full` against
     that worktree to get the pre-slim baseline.
  3. Runs the same against current HEAD to get the thin-block score.
  4. Compares and reports pass/fail against the 95% threshold.

Cost: ~$5-15 per full sweep (120 scenarios * 2 runs). Use --limit N
for cheap dry runs (start with --limit 5 to estimate cost before
committing to the full run).

Requires:
  * ANTHROPIC_API_KEY in environment
  * git worktree support (Git 2.5+)
  * the anthropic SDK installed
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Pre-slim reference: the commit IMMEDIATELY BEFORE the slim block shipped.
# `77c2d94` is "phase0: slim Skopus adapter context"; its parent is the
# pre-slim state we want to measure against.
PRE_SLIM_REF = "77c2d94^"

REPO_ROOT = Path(__file__).resolve().parents[2]


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> str:
    """Run a command, raise on non-zero, return stdout.

    Captures stdout/stderr — use only for fast commands (git plumbing, etc.).
    For long-running streams (the harness invocation), use `run_streaming`.
    """
    result = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.stderr.write(f"\n[command failed] {' '.join(cmd)}\n")
        if result.stdout:
            sys.stderr.write(f"[stdout]\n{result.stdout}\n")
        sys.stderr.write(f"[stderr]\n{result.stderr}\n")
        raise SystemExit(result.returncode)
    return result.stdout


def run_streaming(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> None:
    """Run a command with stdout/stderr streamed to the terminal.

    Use for long-running invocations where realtime progress matters and
    capturing buffers would hide all output until exit.
    """
    result = subprocess.run(cmd, cwd=cwd, env=env, check=False)
    if result.returncode != 0:
        sys.stderr.write(f"\n[command failed] {' '.join(cmd)}\n")
        raise SystemExit(result.returncode)


def measure_one(label: str, repo: Path, lens: str, limit: int | None) -> dict:
    """Run CP against a repo at <repo> and return parsed result."""
    cmd = [
        sys.executable,
        "-m",
        "skopus",
        "bench",
        "run",
        "cp",
        "--driver",
        "anthropic",
        "--lens",
        lens,
    ]
    if limit:
        cmd.extend(["--limit", str(limit)])
    print(f"\n[{label}] {' '.join(cmd)}")
    print(f"[{label}] cwd = {repo}")

    env = os.environ.copy()
    # Make sure the worktree's skopus is the one the harness imports.
    env["PYTHONPATH"] = str(repo)

    # Stream output: a real run is 5-10+ minutes and the user needs progress.
    run_streaming(cmd, cwd=repo, env=env)

    # The harness saves to bench/results/skopus-bench-YYYYMMDD-HHMMSS.json
    # under the repo it ran in. Find the most recent one.
    results_dir = repo / "bench" / "results"
    candidates = sorted(results_dir.glob("skopus-bench-*.json"))
    if not candidates:
        raise SystemExit(f"[{label}] no result file found in {results_dir}")
    latest = candidates[-1]
    data = json.loads(latest.read_text())
    return {"label": label, "result_file": str(latest), "data": data}


def extract_full_skopus_accuracy(measurement: dict) -> float | None:
    """Find the `full skopus` accuracy in the measurement payload.

    The harness emits one of two shapes:
      * --ablation: {"ablation": {"vanilla": {...}, "full": {...}, ...}}
      * --lens single: a flat dict with `lens` and `accuracy` at top level

    We always invoke with --lens full (not --ablation), so the second shape
    is the primary path. Falls back to the ablation shape if present, and
    a generic recursive search as a last resort.
    """
    data = measurement["data"]

    # Single-lens shape (what --lens full produces).
    if data.get("lens") == "full" and "accuracy" in data:
        return float(data["accuracy"])

    # Ablation shape (in case someone runs --ablation).
    if "ablation" in data and "full" in data["ablation"]:
        full = data["ablation"]["full"]
        if "accuracy" in full:
            return float(full["accuracy"])

    # Generic recursive walk — defensive.
    def walk(obj):
        if isinstance(obj, dict):
            if obj.get("lens") == "full" and "accuracy" in obj:
                return float(obj["accuracy"])
            for v in obj.values():
                hit = walk(v)
                if hit is not None:
                    return hit
        if isinstance(obj, list):
            for v in obj:
                hit = walk(v)
                if hit is not None:
                    return hit
        return None

    return walk(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run only N scenarios (cheap dry run). Default: all 120.",
    )
    parser.add_argument(
        "--lens",
        default="full",
        help="Lens to compare. Default 'full'. Supports the same values as `skopus bench run cp --lens`.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.95,
        help="Required ratio: thin / pre-slim. Default 0.95 per v2 evidence-locked gate.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "docs" / "proposals" / "skopus-v1" / "phase0-real-api-gate.json",
        help="Where to write the comparison report JSON.",
    )
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.stderr.write("ERROR: ANTHROPIC_API_KEY not set in environment.\n")
        return 1

    # Set up a git worktree for the pre-slim reference.
    with tempfile.TemporaryDirectory(prefix="skopus-pre-slim-") as wt_parent:
        wt = Path(wt_parent) / "pre-slim"
        print(f"\nSetting up worktree for {PRE_SLIM_REF} at {wt}")
        run(["git", "worktree", "add", str(wt), PRE_SLIM_REF], cwd=REPO_ROOT)

        try:
            pre_slim = measure_one("pre-slim", wt, args.lens, args.limit)
            # Copy the pre-slim result into REPO_ROOT/bench/results/ so the
            # report's pre_slim_result_file path survives worktree cleanup.
            pre_slim_src = Path(pre_slim["result_file"])
            pre_slim_dst = REPO_ROOT / "bench" / "results" / f"pre-slim-{pre_slim_src.name}"
            pre_slim_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pre_slim_src, pre_slim_dst)
            pre_slim["result_file"] = str(pre_slim_dst)

            thin_block = measure_one("thin-block", REPO_ROOT, args.lens, args.limit)
        finally:
            run(["git", "worktree", "remove", "--force", str(wt)], cwd=REPO_ROOT)

    pre_acc = extract_full_skopus_accuracy(pre_slim)
    thin_acc = extract_full_skopus_accuracy(thin_block)

    if pre_acc is None or thin_acc is None:
        sys.stderr.write("ERROR: could not extract full-skopus accuracy from one or both runs\n")
        sys.stderr.write(f"  pre_slim file: {pre_slim['result_file']}\n")
        sys.stderr.write(f"  thin_block file: {thin_block['result_file']}\n")
        return 1

    ratio = thin_acc / pre_acc if pre_acc > 0 else float("inf")
    passed = ratio >= args.threshold

    report = {
        "measured_at": datetime.now().isoformat(timespec="seconds"),
        "pre_slim_ref": PRE_SLIM_REF,
        "pre_slim_result_file": pre_slim["result_file"],
        "thin_block_result_file": thin_block["result_file"],
        "pre_slim_full_skopus_accuracy": pre_acc,
        "thin_block_full_skopus_accuracy": thin_acc,
        "ratio": ratio,
        "threshold": args.threshold,
        "passed": passed,
        "limit": args.limit,
        "lens": args.lens,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print("\n=== Phase 0 real-API gate ===")
    print(f"pre-slim full-skopus accuracy:   {pre_acc:.4f}")
    print(f"thin-block full-skopus accuracy: {thin_acc:.4f}")
    print(f"ratio: {ratio:.4f}  (threshold {args.threshold})")
    print(f"verdict: {'PASS' if passed else 'FAIL'}")
    print(f"report:  {args.out}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
