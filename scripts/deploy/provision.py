from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT_DIR = REPO_ROOT / "deployment"
BOOTSTRAP_DIR = REPO_ROOT / "backend" / "database" / "bootstrap"
_ADMIN_PASSWORD_HASH_ENV_KEY = "ADMIN_BOOTSTRAP_PASSWORD_HASH"  # noqa: S105
_ADMIN_PASSWORD_HASH_PLACEHOLDER = "{{ADMIN_BOOTSTRAP_PASSWORD_HASH}}"  # noqa: S105
_BCRYPT_HASH_PATTERN = re.compile(r"^\$2[abxy]\$\d{2}\$[./A-Za-z0-9]{53}$")


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line == "" or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key == "":
            continue
        values[key] = value.strip()
    return values


def _load_compose_env_values(target_env: str) -> dict[str, str]:
    values: dict[str, str] = {}
    values.update(_read_env_file(DEPLOYMENT_DIR / ".env"))
    values.update(_read_env_file(DEPLOYMENT_DIR / target_env / ".env"))
    values.update({key: value for key, value in os.environ.items() if value != ""})
    return values


def _build_sql_replacements(target_env: str, env_values: dict[str, str]) -> dict[str, str]:
    if target_env == "dev":
        return {}

    raw_hash = env_values.get(_ADMIN_PASSWORD_HASH_ENV_KEY, "").strip()
    if raw_hash == "":
        raise ValueError(f"{_ADMIN_PASSWORD_HASH_ENV_KEY} is required for {target_env} bootstrap")
    if not _BCRYPT_HASH_PATTERN.fullmatch(raw_hash):
        raise ValueError(
            f"{_ADMIN_PASSWORD_HASH_ENV_KEY} must be a valid bcrypt hash like $2b$12$..."
        )
    return {_ADMIN_PASSWORD_HASH_PLACEHOLDER: raw_hash}


def _compose_files(target_env: str) -> list[str]:
    if target_env == "dev":
        return ["-f", "dev/compose.yaml"]
    return ["-f", "compose.base.yaml", "-f", f"{target_env}/compose.yaml"]


def _compose_env_files(target_env: str) -> list[str]:
    return ["--env-file", ".env", "--env-file", f"{target_env}/.env"]


def _run_compose(
    env_file_args: list[str],
    compose_file_args: list[str],
    args: list[str],
    *,
    extra_env: dict[str, str] | None = None,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = ["docker", "compose", *env_file_args, *compose_file_args, *args]
    print("+ " + " ".join(shlex.quote(part) for part in command))
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    return subprocess.run(  # noqa: S603
        command,
        cwd=DEPLOYMENT_DIR,
        check=check,
        env=env,
        text=True,
        capture_output=capture_output,
    )


def _wait_for_postgres(env_file_args: list[str], compose_file_args: list[str]) -> None:
    for _ in range(30):
        result = _run_compose(
            env_file_args,
            compose_file_args,
            [
                "exec",
                "-T",
                "postgres",
                "sh",
                "-c",
                'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
            ],
            check=False,
            capture_output=True,
        )
        if result.returncode == 0:
            return
        time.sleep(2)

    raise RuntimeError("postgres did not become ready within 60 seconds")


def _run_sql_file(
    env_file_args: list[str],
    compose_file_args: list[str],
    *,
    sql_file: Path,
    replacements: dict[str, str] | None = None,
) -> None:
    if not sql_file.exists():
        raise FileNotFoundError(f"bootstrap SQL file not found: {sql_file}")

    sql_text = sql_file.read_text(encoding="utf-8")
    if replacements:
        for placeholder, value in replacements.items():
            sql_text = sql_text.replace(placeholder, value)
    args = [
        "exec",
        "-T",
        "postgres",
        "sh",
        "-lc",
        'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
    ]
    command = ["docker", "compose", *env_file_args, *compose_file_args, *args]
    print("+ " + " ".join(shlex.quote(part) for part in command) + f" < {sql_file}")
    env = os.environ.copy()
    subprocess.run(  # noqa: S603
        command,
        cwd=DEPLOYMENT_DIR,
        check=True,
        env=env,
        text=True,
        encoding="utf-8",
        input=sql_text,
    )


def parse_args() -> argparse.Namespace:
    """Parse provisioning CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Provision database and business baseline for target environment."
    )
    parser.add_argument(
        "--env",
        choices=("dev", "staging", "prod"),
        default="dev",
        help="Deployment environment.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Drop existing docker-compose resources for a clean bootstrap.",
    )
    parser.add_argument(
        "--with-fixtures",
        action="store_true",
        help="Apply dev/test fixtures after bootstrap.",
    )
    parser.add_argument(
        "--allow-prod-fresh",
        action="store_true",
        help="Allow --fresh on prod.",
    )
    parser.add_argument(
        "--apply-env-overrides",
        action="store_true",
        help="Apply env-specific SQL overrides even without --fresh.",
    )
    return parser.parse_args()


def main() -> int:
    """Run provisioning workflow."""
    args = parse_args()
    if args.fresh and args.env == "prod" and not args.allow_prod_fresh:
        raise ValueError("--fresh for prod requires --allow-prod-fresh")
    if args.with_fixtures and args.env != "dev":
        raise ValueError("--with-fixtures is supported only in dev environment")

    env_file_args = _compose_env_files(args.env)
    compose_file_args = _compose_files(args.env)
    compose_env_values = _load_compose_env_values(args.env)
    env_sql_replacements = _build_sql_replacements(args.env, compose_env_values)

    if args.fresh:
        _run_compose(env_file_args, compose_file_args, ["down", "-v", "--remove-orphans"])

    _run_compose(env_file_args, compose_file_args, ["up", "-d", "postgres"])
    _wait_for_postgres(env_file_args, compose_file_args)
    _run_compose(
        env_file_args,
        compose_file_args,
        ["exec", "-T", "postgres", "sh", "/docker-entrypoint-initdb.d/init.sh"],
    )
    _run_compose(
        env_file_args,
        compose_file_args,
        ["run", "--rm", "backend", "alembic", "upgrade", "head"],
    )
    _run_sql_file(
        env_file_args,
        compose_file_args,
        sql_file=BOOTSTRAP_DIR / "base.sql",
    )
    if args.fresh or args.apply_env_overrides:
        _run_sql_file(
            env_file_args,
            compose_file_args,
            sql_file=BOOTSTRAP_DIR / "env" / f"{args.env}.sql",
            replacements=env_sql_replacements,
        )
    else:
        print("skip env-specific overrides (use --apply-env-overrides to force)")

    if args.with_fixtures:
        _run_sql_file(
            env_file_args,
            compose_file_args,
            sql_file=BOOTSTRAP_DIR / "seeds" / "dev.sql",
        )

    _run_compose(env_file_args, compose_file_args, ["up", "-d", "backend"])
    print("provision completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
