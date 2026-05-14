"""
Experiment matrix runner — 16 parameterized runs to answer:
"What factors enable mortal LLM agents to sustain cooperation?"

Design: 1 baseline + 8 single-factor variations + 1 visibility toggle
        + 6 targeted interactions = 16 runs

Estimated cost: ~$56 total at gpt-4o-mini pricing ($3.50/run average)
Estimated time: ~8-12 hours total (30-45 min per run)
"""

import asyncio
import json
import os
import time
from dataclasses import asdict

from experiment_params import ExperimentParams
from run import run_single

OUTPUT_DIR = os.environ.get("EXPERIMENT_OUTPUT_DIR", "./experiment_results")

# ---------------------------------------------------------------------------
# Experiment matrix
# ---------------------------------------------------------------------------
EXPERIMENT_MATRIX = [
    # === Baseline ===
    ExperimentParams(run_name="baseline"),

    # === Vary cooperation multiplier (core game theory knob) ===
    ExperimentParams(run_name="low_mult", cooperation_multiplier=1.5),
    ExperimentParams(run_name="high_mult", cooperation_multiplier=4.0),

    # === Vary death threshold (urgency/fear) ===
    ExperimentParams(run_name="low_threshold", death_threshold=10.0),
    ExperimentParams(run_name="high_threshold", death_threshold=40.0),

    # === Vary agent composition ===
    ExperimentParams(run_name="defector_heavy", num_high=5, num_medium=10, num_low=15),
    ExperimentParams(run_name="cooperator_heavy", num_high=15, num_medium=10, num_low=5),

    # === Vary shock severity ===
    ExperimentParams(run_name="mild_shock", shock_amount=15.0),
    ExperimentParams(run_name="severe_shock", shock_amount=50.0),

    # === Visibility toggle ===
    ExperimentParams(run_name="blind", show_cooperation_rate=False),

    # === Targeted interactions ===
    ExperimentParams(
        run_name="low_mult_high_pressure",
        cooperation_multiplier=1.5,
        death_threshold=40.0,
    ),
    ExperimentParams(
        run_name="high_mult_low_pressure",
        cooperation_multiplier=4.0,
        death_threshold=10.0,
    ),
    ExperimentParams(
        run_name="low_mult_blind",
        cooperation_multiplier=1.5,
        show_cooperation_rate=False,
    ),
    ExperimentParams(
        run_name="high_mult_coop_heavy",
        cooperation_multiplier=4.0,
        num_high=15,
        num_medium=10,
        num_low=5,
    ),
    ExperimentParams(
        run_name="severe_shock_high_pressure",
        shock_amount=50.0,
        death_threshold=40.0,
    ),
    ExperimentParams(
        run_name="blind_defector_heavy",
        show_cooperation_rate=False,
        num_high=5,
        num_medium=10,
        num_low=15,
    ),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
async def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    manifest_path = os.path.join(OUTPUT_DIR, "manifest.json")

    # Resume support: load existing manifest if present
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)
        completed_names = {entry["run_name"] for entry in manifest}
        print(f"Resuming: {len(completed_names)} runs already completed")
    else:
        manifest = []
        completed_names = set()

    total = len(EXPERIMENT_MATRIX)
    for i, params in enumerate(EXPERIMENT_MATRIX):
        if params.run_name in completed_names:
            print(f"[{i+1}/{total}] {params.run_name} — already completed, skipping")
            continue

        print(f"\n{'='*60}")
        print(f"[{i+1}/{total}] Run: {params.run_name}")
        print(f"{'='*60}")

        start = time.time()
        try:
            exp_id = await run_single(params, output_dir=OUTPUT_DIR)
            elapsed = time.time() - start

            manifest.append({
                "run_name": params.run_name,
                "exp_id": exp_id,
                "params": asdict(params),
                "elapsed_seconds": round(elapsed, 1),
                "status": "completed",
            })
            print(f"  Completed in {elapsed/60:.1f} minutes")

        except Exception as e:
            elapsed = time.time() - start
            manifest.append({
                "run_name": params.run_name,
                "exp_id": None,
                "params": asdict(params),
                "elapsed_seconds": round(elapsed, 1),
                "status": f"failed: {e}",
            })
            print(f"  FAILED after {elapsed/60:.1f} minutes: {e}")

        # Save manifest after each run for crash resilience
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

    # Summary
    completed = sum(1 for m in manifest if m["status"] == "completed")
    failed = sum(1 for m in manifest if m["status"].startswith("failed"))
    total_time = sum(m["elapsed_seconds"] for m in manifest)

    print(f"\n{'='*60}")
    print(f"All runs finished: {completed} completed, {failed} failed")
    print(f"Total time: {total_time/3600:.1f} hours")
    print(f"Results in: {OUTPUT_DIR}")
    print(f"Manifest: {manifest_path}")
    print(f"Next step: python analyze_results.py")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
