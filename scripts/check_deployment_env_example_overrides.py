from __future__ import annotations

import re
import sys
from pathlib import Path


_DOTENV_KEY_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")


def _extract_dotenv_keys(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    keys: set[str] = set()

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        match = _DOTENV_KEY_RE.match(line)
        if not match:
            continue

        keys.add(match.group(1))

    return keys


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    deployment_dir = repo_root / "deployment"
    baseline_path = deployment_dir / ".env.example"

    if not baseline_path.is_file():
        print(f"ERROR: Baseline env example not found: {baseline_path}")
        return 2

    override_paths = sorted(
        p for p in deployment_dir.glob("*/.env.example") if p.is_file()
    )
    if not override_paths:
        return 0

    baseline_keys = _extract_dotenv_keys(baseline_path)
    invalid: list[tuple[Path, list[str]]] = []

    for override_path in override_paths:
        override_keys = _extract_dotenv_keys(override_path)
        extra_keys = sorted(k for k in override_keys if k not in baseline_keys)
        if extra_keys:
            invalid.append((override_path, extra_keys))

    if not invalid:
        return 0

    print("ERROR: deployment/<env>/.env.example contains keys not present in deployment/.env.example")
    print("This makes env overrides drift from the baseline inventory.")
    print("")
    for override_path, extra_keys in invalid:
        rel_path = override_path.relative_to(repo_root)
        print(f"- {rel_path}:")
        for key in extra_keys:
            print(f"  - {key}")
    print("")
    print("Fix: add the missing keys to deployment/.env.example (inventory), then keep values in the override files.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
