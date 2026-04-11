"""Generate schema artifacts from Alembic-applied database schema.

Single source of truth:
- Alembic migrations (`backend/alembic/versions/*.py`)

Pipeline:
1) Apply migrations (`alembic upgrade head`) unless skipped.
2) Export init SQL to `01_schema.sql` unless skipped.
3) Reflect live schema and generate data-dict TSV files.
"""

from __future__ import annotations

import argparse
import importlib
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL, make_url


@dataclass(frozen=True)
class ColumnRecord:
    """Normalized row for schema.columns.tsv."""

    table: str
    name: str
    data_type: str
    nullable: bool
    default: str
    is_primary_key: bool
    is_unique: bool
    foreign_key: str
    enum_hint: str
    comment: str


@dataclass(frozen=True)
class TableRecord:
    """Normalized row for schema.tables.tsv."""

    table: str
    primary_key: str
    model: str
    comment: str


@dataclass(frozen=True)
class ConstraintRecord:
    """Normalized row for schema.constraints.tsv."""

    table: str
    kind: str
    name: str
    expression: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize_sync_database_url(raw_url: str) -> str:
    if raw_url.startswith("postgresql+asyncpg://"):
        return raw_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if raw_url.startswith("postgresql+psycopg://"):
        return raw_url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
    return raw_url


def _parse_env_file(env_file: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not env_file.exists():
        return result
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        result[key.strip()] = raw_value.strip().strip("'").strip('"')
    return result


def _load_deployment_env() -> dict[str, str]:
    repo_root = _repo_root()
    merged: dict[str, str] = {}
    for env_file in [repo_root / "deployment/.env", repo_root / "deployment/dev/.env"]:
        merged.update(_parse_env_file(env_file))
    return merged


def _build_database_url(
    *,
    host: str,
    port: str,
    user: str,
    password: str,
    database: str,
) -> str:
    user_encoded = quote_plus(user)
    password_encoded = quote_plus(password)
    return f"postgresql+psycopg2://{user_encoded}:{password_encoded}@{host}:{port}/{database}"


def _resolve_database_url(cli_database_url: str | None) -> str:
    if cli_database_url:
        return _normalize_sync_database_url(cli_database_url)

    backend_dir = _repo_root() / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    try:
        config_module = importlib.import_module("app.core.config")
        get_settings = config_module.get_settings
        return _normalize_sync_database_url(get_settings().database_url)
    except Exception:
        env_values = _load_deployment_env()
        host = env_values.get("DB_HOST", "").strip()
        port = env_values.get("DB_PORT", "5432").strip() or "5432"
        user = env_values.get("DB_USER", "").strip()
        password = env_values.get("DB_PASSWORD", "").strip()
        database = env_values.get("DB_NAME", "").strip()
        if host and user and database:
            return _build_database_url(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
            )
        raise RuntimeError(
            "Failed to resolve database URL from backend settings and deployment env files. "
            "Please provide --database-url explicitly."
        ) from None


def _build_alembic_env_overrides(database_url: str) -> dict[str, str]:
    env_values = _load_deployment_env()
    parsed: URL = make_url(database_url)
    db_name = parsed.database or ""
    if db_name.startswith("/"):
        db_name = db_name[1:]
    env_values.update(
        {
            "DB_HOST": parsed.host or "",
            "DB_PORT": str(parsed.port or 5432),
            "DB_USER": parsed.username or "",
            "DB_PASSWORD": parsed.password or "",
            "DB_NAME": db_name,
        }
    )
    return env_values


def _run_alembic_command(
    *,
    python_executable: str,
    backend_dir: Path,
    alembic_ini: Path,
    db_env_overrides: dict[str, str],
    args: list[str],
    capture_stdout: bool = False,
) -> str:
    env = os.environ.copy()
    env.update(db_env_overrides)
    command = [python_executable, "-m", "alembic", "-c", str(alembic_ini), *args]
    completed = subprocess.run(  # noqa: S603
        command,
        cwd=str(backend_dir),
        env=env,
        check=True,
        capture_output=capture_stdout,
        text=True,
    )
    return completed.stdout if capture_stdout else ""


def _export_sql_via_pg_dump_docker(
    *,
    sql_output: Path,
    database_url: str,
    postgres_container: str,
    restrict_key: str,
) -> None:
    if shutil.which("docker") is None:
        raise RuntimeError("Cannot export SQL via pg_dump: `docker` command not found.")

    parsed: URL = make_url(database_url)
    username = parsed.username or ""
    password = parsed.password or ""
    database = parsed.database or ""
    if database.startswith("/"):
        database = database[1:]
    if not username or not database:
        raise RuntimeError(
            "Cannot export SQL via pg_dump: missing database username or database name."
        )

    command = [
        "docker",
        "exec",
        "-e",
        f"PGPASSWORD={password}",
        postgres_container,
        "pg_dump",
        "-U",
        username,
        "-d",
        database,
        "--schema-only",
        "--no-owner",
        "--no-privileges",
        f"--restrict-key={restrict_key}",
    ]
    completed = subprocess.run(  # noqa: S603
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        raise RuntimeError(f"pg_dump export failed: {stderr}")
    sql_output.parent.mkdir(parents=True, exist_ok=True)
    sql_output.write_text(completed.stdout, encoding="utf-8")


def _extract_enum_hint(comment: str | None) -> str:
    if not comment:
        return ""
    enum_match = re.search(r"enum:\s*([A-Za-z0-9_]+)", comment, flags=re.IGNORECASE)
    if enum_match:
        return enum_match.group(1)
    app_enum_match = re.search(r"app\.enums\.([A-Za-z0-9_]+)", comment)
    if app_enum_match:
        return app_enum_match.group(1)
    return ""


def _load_model_index() -> dict[str, str]:
    backend_dir = _repo_root() / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    models_module = importlib.import_module("app.models")
    base_model = models_module.Base
    model_index: dict[str, str] = {}
    for mapper in base_model.registry.mappers:
        table_name = mapper.local_table.name
        model_index[table_name] = f"{mapper.class_.__module__}.{mapper.class_.__name__}"
    return model_index


def _reflect_schema_records(
    *,
    database_url: str,
    schema_name: str | None,
    model_index: dict[str, str],
) -> tuple[list[TableRecord], list[ColumnRecord], list[ConstraintRecord]]:
    engine = create_engine(database_url)
    inspector = inspect(engine)
    dialect = engine.dialect

    table_records: list[TableRecord] = []
    column_records: list[ColumnRecord] = []
    constraint_records: list[ConstraintRecord] = []

    for table_name in sorted(inspector.get_table_names(schema=schema_name)):
        pk = inspector.get_pk_constraint(table_name, schema=schema_name) or {}
        pk_columns = list(pk.get("constrained_columns") or [])
        table_comment_obj = inspector.get_table_comment(table_name, schema=schema_name)
        table_comment = str(table_comment_obj.get("text") or "")
        table_records.append(
            TableRecord(
                table=table_name,
                primary_key=",".join(pk_columns),
                model=model_index.get(table_name, ""),
                comment=table_comment,
            )
        )

        unique_single_columns: set[str] = set()
        for unique in inspector.get_unique_constraints(table_name, schema=schema_name):
            cols = [name for name in list(unique.get("column_names") or []) if name]
            if len(cols) == 1:
                unique_single_columns.add(cols[0])

        indexes = inspector.get_indexes(table_name, schema=schema_name)
        for index in indexes:
            cols = [name for name in list(index.get("column_names") or []) if name]
            if index.get("unique") and len(cols) == 1:
                unique_single_columns.add(cols[0])

        foreign_key_map: dict[str, list[str]] = {}
        for fk in inspector.get_foreign_keys(table_name, schema=schema_name):
            local_cols = list(fk.get("constrained_columns") or [])
            referred_schema = fk.get("referred_schema")
            referred_table = fk.get("referred_table")
            referred_cols = list(fk.get("referred_columns") or [])
            if not referred_table:
                continue
            schema_prefix = f"{referred_schema}." if referred_schema else ""
            for local_col, remote_col in zip(local_cols, referred_cols, strict=False):
                foreign_key_map.setdefault(local_col, []).append(
                    f"{schema_prefix}{referred_table}.{remote_col}"
                )

        for column in inspector.get_columns(table_name, schema=schema_name):
            column_name = str(column["name"])
            column_comment = str(column.get("comment") or "")
            default_value = column.get("default")
            column_records.append(
                ColumnRecord(
                    table=table_name,
                    name=column_name,
                    data_type=str(column["type"].compile(dialect=dialect)),
                    nullable=bool(column.get("nullable", True)),
                    default="" if default_value is None else str(default_value),
                    is_primary_key=column_name in pk_columns,
                    is_unique=column_name in unique_single_columns,
                    foreign_key=",".join(sorted(foreign_key_map.get(column_name, []))),
                    enum_hint=_extract_enum_hint(column_comment),
                    comment=column_comment,
                )
            )

        if pk_columns:
            constraint_records.append(
                ConstraintRecord(
                    table=table_name,
                    kind="primary_key",
                    name=str(pk.get("name") or f"pk_{table_name}"),
                    expression=f"({','.join(pk_columns)})",
                )
            )

        for unique in inspector.get_unique_constraints(table_name, schema=schema_name):
            cols = [name for name in list(unique.get("column_names") or []) if name]
            constraint_records.append(
                ConstraintRecord(
                    table=table_name,
                    kind="unique",
                    name=str(unique.get("name") or ""),
                    expression=f"({','.join(cols)})",
                )
            )

        for fk in inspector.get_foreign_keys(table_name, schema=schema_name):
            local_cols = [name for name in list(fk.get("constrained_columns") or []) if name]
            referred_schema = fk.get("referred_schema")
            referred_table = fk.get("referred_table")
            referred_cols = [name for name in list(fk.get("referred_columns") or []) if name]
            if not referred_table:
                continue
            schema_prefix = f"{referred_schema}." if referred_schema else ""
            remote_cols = [f"{schema_prefix}{referred_table}.{col}" for col in referred_cols]
            constraint_records.append(
                ConstraintRecord(
                    table=table_name,
                    kind="foreign_key",
                    name=str(fk.get("name") or ""),
                    expression=f"({','.join(local_cols)})->({','.join(remote_cols)})",
                )
            )

        for check in inspector.get_check_constraints(table_name, schema=schema_name):
            constraint_records.append(
                ConstraintRecord(
                    table=table_name,
                    kind="check",
                    name=str(check.get("name") or ""),
                    expression=str(check.get("sqltext") or ""),
                )
            )

        for index in indexes:
            cols = [name for name in list(index.get("column_names") or []) if name]
            expression = ",".join(cols) if cols else str(index.get("name") or "")
            options = index.get("dialect_options")
            if isinstance(options, dict):
                where_clause = options.get("postgresql_where")
                if where_clause:
                    expression = f"{expression} WHERE {where_clause}"
            constraint_records.append(
                ConstraintRecord(
                    table=table_name,
                    kind="index_unique" if bool(index.get("unique")) else "index",
                    name=str(index.get("name") or ""),
                    expression=expression,
                )
            )

    engine.dispose()
    return table_records, column_records, constraint_records


def _write_data_dict_tsv(
    *,
    output_dir: Path,
    table_records: list[TableRecord],
    column_records: list[ColumnRecord],
    constraint_records: list[ConstraintRecord],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    tables_path = output_dir / "schema.tables.tsv"
    columns_path = output_dir / "schema.columns.tsv"
    constraints_path = output_dir / "schema.constraints.tsv"

    table_lines = ["table\tprimary_key\tmodel\tcomment"]
    for item in table_records:
        table_lines.append(f"{item.table}\t{item.primary_key}\t{item.model}\t{item.comment}")
    tables_path.write_text("\n".join(table_lines) + "\n", encoding="utf-8")

    column_lines = [
        "table\tname\tdata_type\tnullable\tdefault\tis_primary_key\tis_unique\tforeign_key\tenum_hint\tcomment"
    ]
    for item in column_records:
        column_lines.append(
            "\t".join(
                [
                    item.table,
                    item.name,
                    item.data_type,
                    str(item.nullable).lower(),
                    item.default,
                    str(item.is_primary_key).lower(),
                    str(item.is_unique).lower(),
                    item.foreign_key,
                    item.enum_hint,
                    item.comment,
                ]
            )
        )
    columns_path.write_text("\n".join(column_lines) + "\n", encoding="utf-8")

    constraint_lines = ["table\tkind\tname\texpression"]
    for item in constraint_records:
        constraint_lines.append(f"{item.table}\t{item.kind}\t{item.name}\t{item.expression}")
    constraints_path.write_text("\n".join(constraint_lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Generate schema artifacts from Alembic-applied database schema."
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help=(
            "Target database URL. If omitted, try backend settings and then "
            "deployment env files."
        ),
    )
    parser.add_argument(
        "--data-dict-dir",
        default="docs/data-dict",
        help=(
            "Output directory for schema.tables.tsv / "
            "schema.columns.tsv / schema.constraints.tsv."
        ),
    )
    parser.add_argument(
        "--sql-output",
        default="backend/database/init/sql/01_schema.sql",
        help="Output SQL path.",
    )
    parser.add_argument(
        "--sql-export-mode",
        default="pg_dump_docker",
        choices=["pg_dump_docker", "alembic"],
        help=(
            "SQL export mode: use `pg_dump_docker` by default for better compatibility; "
            "`alembic` uses `alembic upgrade head --sql`."
        ),
    )
    parser.add_argument(
        "--postgres-container",
        default="postgres",
        help="Postgres container name for pg_dump export mode.",
    )
    parser.add_argument(
        "--pg-dump-restrict-key",
        default="says123",
        help="Fixed pg_dump restrict key for stable SQL output.",
    )
    parser.add_argument(
        "--skip-migrate",
        action="store_true",
        help="Skip running `alembic upgrade head`.",
    )
    parser.add_argument(
        "--skip-sql-export",
        action="store_true",
        help="Skip SQL export step.",
    )
    parser.add_argument(
        "--schema",
        default=None,
        help="Database schema name for reflection (default: connection default schema).",
    )
    parser.add_argument(
        "--backend-dir",
        default="backend",
        help="Backend directory containing alembic.ini.",
    )
    parser.add_argument(
        "--alembic-config",
        default="alembic.ini",
        help="Alembic config path relative to backend-dir.",
    )
    parser.add_argument(
        "--python-executable",
        default=sys.executable,
        help="Python executable for Alembic commands.",
    )
    return parser.parse_args()


def main() -> int:
    """Execute generation pipeline."""
    args = parse_args()
    repo_root = _repo_root()

    database_url = _resolve_database_url(args.database_url)
    db_env_overrides = _build_alembic_env_overrides(database_url)
    backend_dir = (repo_root / args.backend_dir).resolve()
    alembic_ini = (backend_dir / args.alembic_config).resolve()
    data_dict_dir = (repo_root / args.data_dict_dir).resolve()
    sql_output = (repo_root / args.sql_output).resolve()

    if not alembic_ini.exists():
        raise FileNotFoundError(f"Alembic config not found: {alembic_ini}")

    if not args.skip_migrate:
        _run_alembic_command(
            python_executable=args.python_executable,
            backend_dir=backend_dir,
            alembic_ini=alembic_ini,
            db_env_overrides=db_env_overrides,
            args=["upgrade", "head"],
        )

    if not args.skip_sql_export:
        if args.sql_export_mode == "alembic":
            sql_text = _run_alembic_command(
                python_executable=args.python_executable,
                backend_dir=backend_dir,
                alembic_ini=alembic_ini,
                db_env_overrides=db_env_overrides,
                args=["upgrade", "head", "--sql"],
                capture_stdout=True,
            )
            sql_output.parent.mkdir(parents=True, exist_ok=True)
            sql_output.write_text(sql_text, encoding="utf-8")
        else:
            _export_sql_via_pg_dump_docker(
                sql_output=sql_output,
                database_url=database_url,
                postgres_container=args.postgres_container,
                restrict_key=args.pg_dump_restrict_key,
            )

    model_index = _load_model_index()
    table_records, column_records, constraint_records = _reflect_schema_records(
        database_url=database_url,
        schema_name=args.schema,
        model_index=model_index,
    )
    _write_data_dict_tsv(
        output_dir=data_dict_dir,
        table_records=table_records,
        column_records=column_records,
        constraint_records=constraint_records,
    )

    print(f"database_url={database_url}")
    print(f"data_dict_dir={data_dict_dir}")
    if not args.skip_sql_export:
        print(f"sql_output={sql_output}")
    print("Schema artifacts generated from Alembic-applied database schema.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
