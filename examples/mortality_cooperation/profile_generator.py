"""Generate agent profile JSON files with varying compositions."""

import json
import os

BASE_DIR = os.path.dirname(__file__)
BASE_PROFILES_PATH = os.path.join(BASE_DIR, "profiles.json")


def _load_base_profiles() -> dict[str, list[dict]]:
    with open(BASE_PROFILES_PATH) as f:
        all_profiles = json.load(f)
    grouped: dict[str, list[dict]] = {"high": [], "medium": [], "low": []}
    for p in all_profiles:
        tendency = p.get("cooperation_tendency", "medium")
        grouped[tendency].append(p)
    return grouped


def generate_profiles(
    num_high: int = 10,
    num_medium: int = 10,
    num_low: int = 10,
    initial_resources: float = 100.0,
) -> list[dict]:
    grouped = _load_base_profiles()
    result = []
    id_counter = 1001

    for tendency, count in [("high", num_high), ("medium", num_medium), ("low", num_low)]:
        templates = grouped[tendency]
        for i in range(count):
            template = templates[i % len(templates)].copy()
            template["id"] = id_counter
            template["resource_pool"] = initial_resources
            if i >= len(templates):
                template["name"] = f"{template['name']}_{i // len(templates) + 1}"
            id_counter += 1
            result.append(template)

    return result


def write_profiles(profiles: list[dict], path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(profiles, f, indent=2)
