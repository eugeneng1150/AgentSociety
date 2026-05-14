"""
Comparative analysis of mortality-cooperation experiment results.

Reads the manifest.json and per-run artifacts to produce:
1. Cooperation rate trajectories (per run)
2. Survival curves (per run)
3. Factor effect summary table
4. Per-tendency breakdown

Usage:
    python analyze_results.py [--output-dir ./experiment_results]
"""

import argparse
import json
import os
import sys
from collections import defaultdict

try:
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    print("Install analysis dependencies: pip install pandas matplotlib")
    sys.exit(1)


def load_manifest(output_dir: str) -> list[dict]:
    path = os.path.join(output_dir, "manifest.json")
    with open(path) as f:
        return [m for m in json.load(f) if m["status"] == "completed"]


def load_artifacts(output_dir: str, exp_id: str) -> dict:
    """Try common artifact paths used by the framework."""
    candidates = [
        os.path.join(output_dir, "exps", exp_id, "artifacts.json"),
        os.path.join(output_dir, "exps", "", exp_id, "artifacts.json"),
    ]
    # Also search recursively for the exp_id directory
    for root, dirs, files in os.walk(os.path.join(output_dir, "exps")):
        if "artifacts.json" in files and exp_id in root:
            candidates.insert(0, os.path.join(root, "artifacts.json"))

    for path in candidates:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)

    print(f"  Warning: artifacts not found for exp_id={exp_id}")
    return {}


def extract_timeseries(entry: dict, artifacts: dict) -> list[dict]:
    """Extract per-day metrics from SAVE_CONTEXT artifacts."""
    params = entry["params"]
    num_days = params["num_days"]
    rows = []

    for day in range(1, num_days + 1):
        coop_key = f"cooperation_score_day{day}"
        resource_key = f"resource_pool_day{day}"

        if coop_key not in artifacts or resource_key not in artifacts:
            continue

        coop_scores = artifacts[coop_key]
        resource_pools = artifacts[resource_key]

        if not coop_scores:
            continue

        threshold = params["death_threshold"]
        num_agents = len(coop_scores)
        alive = sum(1 for r in resource_pools.values() if r >= threshold)

        # Cooperation score at day N = cumulative cooperations up to day N
        # Day-over-day cooperation rate = agents whose score increased
        if day == 1:
            day_cooperators = sum(1 for v in coop_scores.values() if v > 0)
        else:
            prev_key = f"cooperation_score_day{day-1}"
            if prev_key in artifacts:
                prev_scores = artifacts[prev_key]
                day_cooperators = sum(
                    1 for aid, v in coop_scores.items()
                    if v > prev_scores.get(aid, 0)
                )
            else:
                day_cooperators = 0

        resources = list(resource_pools.values())
        rows.append({
            "day": day,
            "alive_count": alive,
            "total_agents": num_agents,
            "survival_rate": alive / num_agents if num_agents > 0 else 0,
            "day_cooperators": day_cooperators,
            "day_cooperation_rate": day_cooperators / alive if alive > 0 else 0,
            "mean_resources": sum(resources) / len(resources) if resources else 0,
            "min_resources": min(resources) if resources else 0,
            "mean_cooperation_score": (
                sum(coop_scores.values()) / len(coop_scores) if coop_scores else 0
            ),
        })

    return rows


def plot_cooperation_trajectories(all_data: dict[str, list[dict]], output_dir: str):
    """Line plot: daily cooperation rate per run."""
    fig, ax = plt.subplots(figsize=(12, 6))
    for run_name, rows in all_data.items():
        if not rows:
            continue
        days = [r["day"] for r in rows]
        rates = [r["day_cooperation_rate"] * 100 for r in rows]
        ax.plot(days, rates, marker="o", markersize=3, label=run_name)

    ax.set_xlabel("Day")
    ax.set_ylabel("Daily Cooperation Rate (%)")
    ax.set_title("Cooperation Rate Trajectories Across Conditions")
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=7)
    ax.set_ylim(-5, 105)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "cooperation_trajectories.png"), dpi=150)
    plt.close()
    print("  Saved: cooperation_trajectories.png")


def plot_survival_curves(all_data: dict[str, list[dict]], output_dir: str):
    """Line plot: survival rate per run."""
    fig, ax = plt.subplots(figsize=(12, 6))
    for run_name, rows in all_data.items():
        if not rows:
            continue
        days = [r["day"] for r in rows]
        survival = [r["survival_rate"] * 100 for r in rows]
        ax.plot(days, survival, marker="o", markersize=3, label=run_name)

    ax.set_xlabel("Day")
    ax.set_ylabel("Survival Rate (%)")
    ax.set_title("Survival Curves Across Conditions")
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=7)
    ax.set_ylim(-5, 105)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "survival_curves.png"), dpi=150)
    plt.close()
    print("  Saved: survival_curves.png")


def plot_resource_trajectories(all_data: dict[str, list[dict]], output_dir: str):
    """Line plot: mean resources per run."""
    fig, ax = plt.subplots(figsize=(12, 6))
    for run_name, rows in all_data.items():
        if not rows:
            continue
        days = [r["day"] for r in rows]
        resources = [r["mean_resources"] for r in rows]
        ax.plot(days, resources, marker="o", markersize=3, label=run_name)

    ax.set_xlabel("Day")
    ax.set_ylabel("Mean Resources")
    ax.set_title("Resource Trajectories Across Conditions")
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=7)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "resource_trajectories.png"), dpi=150)
    plt.close()
    print("  Saved: resource_trajectories.png")


def generate_summary_table(
    manifest: list[dict], all_data: dict[str, list[dict]], output_dir: str
):
    """Summary table comparing all runs on key metrics."""
    rows = []
    for entry in manifest:
        name = entry["run_name"]
        data = all_data.get(name, [])
        params = entry["params"]

        if not data:
            continue

        final = data[-1]
        # Find cooperation rate right after shock day
        shock_day = params["shock_day"]
        post_shock = [r for r in data if r["day"] == shock_day + 1]
        post_shock_rate = post_shock[0]["day_cooperation_rate"] if post_shock else None

        rows.append({
            "Run": name,
            "Multiplier": params["cooperation_multiplier"],
            "Threshold": params["death_threshold"],
            "Composition": f"{params['num_high']}H/{params['num_medium']}M/{params['num_low']}L",
            "Shock": params["shock_amount"],
            "Visible": params["show_cooperation_rate"],
            "Final Survival %": f"{final['survival_rate']*100:.0f}",
            "Final Coop Rate %": f"{final['day_cooperation_rate']*100:.0f}",
            "Final Mean Resources": f"{final['mean_resources']:.1f}",
            "Post-Shock Coop %": (
                f"{post_shock_rate*100:.0f}" if post_shock_rate is not None else "N/A"
            ),
            "Time (min)": f"{entry['elapsed_seconds']/60:.1f}",
        })

    df = pd.DataFrame(rows)
    csv_path = os.path.join(output_dir, "summary.csv")
    df.to_csv(csv_path, index=False)
    print(f"  Saved: summary.csv")

    # Print to console
    print("\n" + "=" * 100)
    print("EXPERIMENT SUMMARY")
    print("=" * 100)
    print(df.to_string(index=False))
    print()

    return df


def generate_factor_effects(df: pd.DataFrame, output_dir: str):
    """Compare each factor's levels against baseline."""
    if df.empty:
        return

    baseline = df[df["Run"] == "baseline"]
    if baseline.empty:
        print("  No baseline run found for factor comparison")
        return

    lines = []
    lines.append("=" * 80)
    lines.append("FACTOR EFFECTS (compared to baseline)")
    lines.append("=" * 80)

    factor_groups = {
        "Cooperation Multiplier": ["low_mult", "baseline", "high_mult"],
        "Death Threshold": ["low_threshold", "baseline", "high_threshold"],
        "Agent Composition": ["defector_heavy", "baseline", "cooperator_heavy"],
        "Shock Severity": ["mild_shock", "baseline", "severe_shock"],
        "Visibility": ["baseline", "blind"],
    }

    for factor_name, run_names in factor_groups.items():
        lines.append(f"\n--- {factor_name} ---")
        for name in run_names:
            row = df[df["Run"] == name]
            if row.empty:
                lines.append(f"  {name}: [not found]")
                continue
            r = row.iloc[0]
            lines.append(
                f"  {name:30s} | Survival: {r['Final Survival %']:>3s}% | "
                f"Coop: {r['Final Coop Rate %']:>3s}% | "
                f"Resources: {r['Final Mean Resources']:>6s}"
            )

    report = "\n".join(lines)
    print(report)

    with open(os.path.join(output_dir, "factor_effects.txt"), "w") as f:
        f.write(report)
    print("  Saved: factor_effects.txt")


def main():
    parser = argparse.ArgumentParser(description="Analyze experiment results")
    parser.add_argument(
        "--output-dir", default="./experiment_results",
        help="Directory containing manifest.json and run artifacts",
    )
    args = parser.parse_args()

    print(f"Loading results from: {args.output_dir}")
    manifest = load_manifest(args.output_dir)
    if not manifest:
        print("No completed runs found in manifest.json")
        sys.exit(1)

    print(f"Found {len(manifest)} completed runs\n")

    # Extract timeseries for each run
    all_data: dict[str, list[dict]] = {}
    for entry in manifest:
        name = entry["run_name"]
        artifacts = load_artifacts(args.output_dir, entry["exp_id"])
        ts = extract_timeseries(entry, artifacts)
        all_data[name] = ts
        print(f"  {name}: {len(ts)} days of data")

    print("\nGenerating plots...")
    plot_cooperation_trajectories(all_data, args.output_dir)
    plot_survival_curves(all_data, args.output_dir)
    plot_resource_trajectories(all_data, args.output_dir)

    print("\nGenerating summary...")
    df = generate_summary_table(manifest, all_data, args.output_dir)
    generate_factor_effects(df, args.output_dir)

    print(f"\nAnalysis complete. All outputs in: {args.output_dir}")


if __name__ == "__main__":
    main()
