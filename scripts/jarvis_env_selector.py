"""Explicit environment selector; does not start downloads or change source state."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = ("source_download", "raw_repair", "readback_validation", "quality_validation", "indicator_calculation", "pit_research")


def resolve(action: str) -> tuple[str, str]:
    cfg = json.loads((ROOT / "config/python-environments.json").read_text(encoding="utf-8"))
    if action not in cfg["routing"]:
        raise ValueError(f"Unsupported action: {action}")
    env = cfg["routing"][action]
    req = cfg["environments"][env]["requirements"]
    if not (ROOT / req).is_file():
        raise FileNotFoundError(req)
    return env, req


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--action", required=True, choices=ACTIONS)
    p.add_argument("--github-output", default="")
    args = p.parse_args()
    env, req = resolve(args.action)
    print(f"action={args.action}; environment={env}; requirements={req}")
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as f:
            f.write(f"environment={env}\nrequirements={req}\n")


if __name__ == "__main__":
    main()
