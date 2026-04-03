"""Generate schema artifacts from SQLAlchemy models.

This script reads SQLAlchemy metadata from ``app.models`` and writes:
1) AI-oriented data-dict TSV files
2) Optional SQL preview snapshot (DDL + indexes + comments)

By default this script is used for preview output directories, so existing
runtime/init schema files are not overwritten unless an explicit target path
is passed.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable, MetaData


@dataclass(frozen=True)
class ColumnRecord:
    """Machine-readable column metadata."""

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
    """Machine-readable table metadata."""

    table: str
    primary_key: str
    model: str
    comment: str


@dataclass(frozen=True)
class ConstraintRecord:
    """Machine-readable constraint/index metadata."""

    table: str
    kind: str
    name: str
    expression: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _escape_sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _extract_enum_hint(comment: str | None) -> str:
    if not comment:
        return ""
    enum_pattern = re.compile(r"enum:\s*([A-Za-z0-9_]+)", re.IGNORECASE)
    match = enum_pattern.search(comment)
    if match:
        return match.group(1)

    app_enum_pattern = re.compile(r"app\.enums\.([A-Za-z0-9_]+)")
    app_match = app_enum_pattern.search(comment)
    if app_match:
        return app_match.group(1)

    return ""


def _column_default_string(column: Any) -> str:
    if column.server_default is not None and getattr(column.server_default, "arg", None) is not None:
        return str(column.server_default.arg)
    if column.default is not None and getattr(column.default, "arg", None) is not None:
        return str(column.default.arg)
    return ""


def _is_single_column_unique(table: Any, column_name: str) -> bool:
    if getattr(table.c[column_name], "unique", False):
        return True
    for constraint in table.constraints:
        if isinstance(constraint, UniqueConstraint):
            names = [col.name for col in constraint.columns]
            if len(names) == 1 and names[0] == column_name:
                return True
    return False


def _column_foreign_key(column: Any) -> str:
    if not column.foreign_keys:
        return ""
    refs = sorted(str(fk.target_fullname) for fk in column.foreign_keys)
    return ",".join(refs)


def load_metadata_and_model_index() -> tuple[MetaData, dict[str, str]]:
    """Load SQLAlchemy metadata and table->model mapping from app.models."""

    backend_dir = _repo_root() / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    from app.models import Base  # noqa: WPS433

    model_index: dict[str, str] = {}
    for mapper in Base.registry.mappers:
        table_name = mapper.local_table.name
        model_index[table_name] = f"{mapper.class_.__module__}.{mapper.class_.__name__}"

    return Base.metadata, model_index


def build_records(metadata: MetaData, model_index: dict[str, str]) -> tuple[
    list[TableRecord],
    list[ColumnRecord],
    list[ConstraintRecord],
]:
    """Build normalized records for tables, columns, and constraints/indexes."""

    dialect = postgresql.dialect()
    table_records: list[TableRecord] = []
    column_records: list[ColumnRecord] = []
    constraint_records: list[ConstraintRecord] = []

    sorted_tables = sorted(metadata.tables.values(), key=lambda item: item.name)
    for table in sorted_tables:
        pk_columns = [col.name for col in table.primary_key.columns]
        table_records.append(
            TableRecord(
                table=table.name,
                primary_key=",".join(pk_columns),
                model=model_index.get(table.name, ""),
                comment=table.comment or "",
            )
        )

        for column in table.columns:
            column_records.append(
                ColumnRecord(
                    table=table.name,
                    name=column.name,
                    data_type=str(column.type.compile(dialect=dialect)),
                    nullable=bool(column.nullable),
                    default=_column_default_string(column),
                    is_primary_key=bool(column.primary_key),
                    is_unique=_is_single_column_unique(table, column.name),
                    foreign_key=_column_foreign_key(column),
                    enum_hint=_extract_enum_hint(column.comment),
                    comment=column.comment or "",
                )
            )

        if pk_columns:
            pk_name = table.primary_key.name or f"pk_{table.name}"
            constraint_records.append(
                ConstraintRecord(
                    table=table.name,
                    kind="primary_key",
                    name=pk_name,
                    expression=f"({','.join(pk_columns)})",
                )
            )

        for constraint in sorted(
            table.constraints,
            key=lambda item: item.name or item.__class__.__name__,
        ):
            if isinstance(constraint, UniqueConstraint):
                cols = ",".join(col.name for col in constraint.columns)
                constraint_records.append(
                    ConstraintRecord(
                        table=table.name,
                        kind="unique",
                        name=constraint.name or "",
                        expression=f"({cols})",
                    )
                )
            elif isinstance(constraint, ForeignKeyConstraint):
                local_cols = ",".join(element.parent.name for element in constraint.elements)
                remote_cols = ",".join(element.target_fullname for element in constraint.elements)
                constraint_records.append(
                    ConstraintRecord(
                        table=table.name,
                        kind="foreign_key",
                        name=constraint.name or "",
                        expression=f"({local_cols})->({remote_cols})",
                    )
                )
            elif isinstance(constraint, CheckConstraint):
                constraint_records.append(
                    ConstraintRecord(
                        table=table.name,
                        kind="check",
                        name=constraint.name or "",
                        expression=str(constraint.sqltext),
                    )
                )

        for index in sorted(table.indexes, key=lambda item: item.name or ""):
            expressions = ",".join(str(expr) for expr in index.expressions)
            where_clause = index.dialect_options.get("postgresql", {}).get("where")
            if where_clause is not None:
                expressions = f"{expressions} WHERE {where_clause}"
            constraint_records.append(
                ConstraintRecord(
                    table=table.name,
                    kind="index_unique" if index.unique else "index",
                    name=index.name or "",
                    expression=expressions,
                )
            )

    return table_records, column_records, constraint_records


def write_data_dict_tsv(
    output_dir: Path,
    table_records: list[TableRecord],
    column_records: list[ColumnRecord],
    constraint_records: list[ConstraintRecord],
) -> None:
    tables_path = output_dir / "schema.tables.tsv"
    columns_path = output_dir / "schema.columns.tsv"
    constraints_path = output_dir / "schema.constraints.tsv"

    table_lines = ["table\tprimary_key\tmodel\tcomment"]
    for item in table_records:
        table_lines.append(
            f"{item.table}\t{item.primary_key}\t{item.model}\t{item.comment}"
        )
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


def write_sql_preview(metadata: MetaData, output_dir: Path, sql_filename: str) -> None:
    sql_path = output_dir / sql_filename
    dialect = postgresql.dialect()

    lines: list[str] = []
    lines.append("-- ==========================================================================")
    lines.append("-- AUTO-GENERATED SQL PREVIEW FROM SQLALCHEMY METADATA")
    lines.append("-- Source of truth: SQLAlchemy models")
    lines.append("-- This file is generated for review and should not be edited manually.")
    lines.append("-- ==========================================================================")
    lines.append("")

    for table in sorted(metadata.tables.values(), key=lambda item: item.name):
        create_table_sql = str(CreateTable(table).compile(dialect=dialect)).rstrip()
        lines.append(f"{create_table_sql};")
        lines.append("")

    for table in sorted(metadata.tables.values(), key=lambda item: item.name):
        for index in sorted(table.indexes, key=lambda item: item.name or ""):
            create_index_sql = str(CreateIndex(index).compile(dialect=dialect)).rstrip()
            lines.append(f"{create_index_sql};")
        if table.indexes:
            lines.append("")

    for table in sorted(metadata.tables.values(), key=lambda item: item.name):
        if table.comment:
            escaped_table_comment = _escape_sql_literal(table.comment)
            lines.append(f"COMMENT ON TABLE {table.name} IS '{escaped_table_comment}';")
        for column in table.columns:
            if column.comment:
                escaped_column_comment = _escape_sql_literal(column.comment)
                lines.append(
                    f"COMMENT ON COLUMN {table.name}.{column.name} IS '{escaped_column_comment}';"
                )
    lines.append("")

    sql_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate schema artifacts from SQLAlchemy metadata.")
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory for generated artifacts (preview-safe by default).",
    )
    parser.add_argument(
        "--sql-filename",
        default="01_schema.preview.sql",
        help="SQL preview filename.",
    )
    parser.add_argument(
        "--no-sql-preview",
        action="store_true",
        help="Generate TSV files only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata, model_index = load_metadata_and_model_index()
    table_records, column_records, constraint_records = build_records(metadata, model_index)

    write_data_dict_tsv(
        output_dir=output_dir,
        table_records=table_records,
        column_records=column_records,
        constraint_records=constraint_records,
    )
    if not args.no_sql_preview:
        write_sql_preview(
            metadata=metadata,
            output_dir=output_dir,
            sql_filename=args.sql_filename,
        )

    print(f"Generated schema artifacts in: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
