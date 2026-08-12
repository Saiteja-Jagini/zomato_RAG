"""SQLite-backed skill definitions and execution tracking."""

from __future__ import annotations

import json
import pathlib
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


PROJECT_ROOT = pathlib.Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "database" / "database.db"
PLOTTING_SKILL_PATH = PROJECT_ROOT / "skills" / "plotting-design" / "SKILL.md"
PLOTTING_SKILL_ID = "plotting-design"

SKILL_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS skills (
    skill_id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL UNIQUE,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    description TEXT NOT NULL,
    prompt_template TEXT NOT NULL,
    configuration_json TEXT NOT NULL DEFAULT '{}',
    input_schema_json TEXT NOT NULL DEFAULT '{}',
    output_schema_json TEXT NOT NULL DEFAULT '{}',
    scope TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('draft', 'active', 'inactive')),
    autonomy_requirements_json TEXT NOT NULL DEFAULT '{}',
    autonomy_level TEXT NOT NULL DEFAULT 'supervised'
        CHECK (autonomy_level IN ('supervised', 'autonomous')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_executions (
    execution_id TEXT PRIMARY KEY NOT NULL,
    skill_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('succeeded', 'failed')),
    input_json TEXT NOT NULL,
    output_json TEXT NOT NULL,
    error_message TEXT,
    duration_ms INTEGER NOT NULL CHECK (duration_ms >= 0),
    created_at TEXT NOT NULL,
    FOREIGN KEY (skill_id) REFERENCES skills(skill_id)
);

CREATE INDEX IF NOT EXISTS idx_skill_executions_skill_created
    ON skill_executions(skill_id, created_at);
"""

DEFAULT_CONFIGURATION = {
    "model": "openai:gpt-5.4-mini-2026-03-17",
    "tool_name": "execute_plot_script",
    "max_rows": 500,
    "max_script_characters": 20_000,
    "timeout_seconds": 20,
    "dpi": 160,
    "allowed_libraries": ["matplotlib", "seaborn", "numpy"],
}

DEFAULT_INPUT_SCHEMA = {
    "type": "object",
    "required": ["python_script", "data", "chart_name"],
    "properties": {
        "python_script": {"type": "string", "minLength": 1},
        "data": {
            "type": "object",
            "required": ["columns", "rows"],
            "properties": {
                "columns": {"type": "array"},
                "rows": {"type": "array"},
            },
        },
        "chart_name": {"type": "string", "minLength": 1},
    },
}

DEFAULT_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["success"],
    "properties": {
        "success": {"type": "boolean"},
        "image_path": {"type": "string"},
        "size_bytes": {"type": "integer"},
        "error": {"type": "string"},
    },
}

DEFAULT_AUTONOMY_REQUIREMENTS = {
    "minimum_executions": 5,
    "minimum_successful_executions": 4,
    "minimum_success_rate": 0.8,
}


@dataclass(frozen=True)
class SkillDefinition:
    skill_id: str
    name: str
    version: int
    description: str
    prompt_template: str
    configuration: dict[str, Any]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    scope: str
    status: str
    autonomy_requirements: dict[str, Any]
    autonomy_level: str


@dataclass(frozen=True)
class ExecutionSummary:
    execution_id: str
    autonomy_level: str
    total_executions: int
    successful_executions: int
    success_rate: float


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _skill_prompt(skill_path: pathlib.Path) -> str:
    content = skill_path.read_text(encoding="utf-8").strip()
    if content.startswith("---"):
        _, separator, remainder = content[3:].partition("---")
        if separator:
            content = remainder.strip()
    return content


def initialize_skill_store(
    db_path: pathlib.Path = DB_PATH,
    skill_path: pathlib.Path = PLOTTING_SKILL_PATH,
) -> None:
    """Create the skill tables and seed plotting-design only when absent.

    SKILL.md is a bootstrap source. After insertion, the database record is the
    runtime source of truth and is not overwritten on application restarts.
    """

    db_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = _utc_now()
    with closing(sqlite3.connect(db_path)) as connection:
        connection.executescript(SKILL_SCHEMA)
        exists = connection.execute(
            "SELECT 1 FROM skills WHERE skill_id = ?",
            (PLOTTING_SKILL_ID,),
        ).fetchone()
        if exists:
            connection.commit()
            return
        connection.execute(
            """
            INSERT OR IGNORE INTO skills (
                skill_id, name, version, description, prompt_template,
                configuration_json, input_schema_json, output_schema_json,
                scope, status, autonomy_requirements_json, autonomy_level,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                PLOTTING_SKILL_ID,
                "Plotting Design",
                1,
                "Create clear Matplotlib and Seaborn charts from tabular data.",
                _skill_prompt(skill_path),
                json.dumps(DEFAULT_CONFIGURATION),
                json.dumps(DEFAULT_INPUT_SCHEMA),
                json.dumps(DEFAULT_OUTPUT_SCHEMA),
                "analytics.visualization",
                "active",
                json.dumps(DEFAULT_AUTONOMY_REQUIREMENTS),
                "supervised",
                timestamp,
                timestamp,
            ),
        )
        connection.commit()


def load_skill(
    skill_id: str,
    *,
    db_path: pathlib.Path = DB_PATH,
    require_active: bool = True,
) -> SkillDefinition:
    initialize_skill_store(db_path=db_path)
    query = "SELECT * FROM skills WHERE skill_id = ?"
    parameters: tuple[Any, ...] = (skill_id,)
    if require_active:
        query += " AND status = 'active'"

    with closing(sqlite3.connect(db_path)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(query, parameters).fetchone()

    if row is None:
        qualifier = "active " if require_active else ""
        raise LookupError(f"No {qualifier}skill exists with id '{skill_id}'.")

    try:
        return SkillDefinition(
            skill_id=row["skill_id"],
            name=row["name"],
            version=row["version"],
            description=row["description"],
            prompt_template=row["prompt_template"],
            configuration=json.loads(row["configuration_json"]),
            input_schema=json.loads(row["input_schema_json"]),
            output_schema=json.loads(row["output_schema_json"]),
            scope=row["scope"],
            status=row["status"],
            autonomy_requirements=json.loads(row["autonomy_requirements_json"]),
            autonomy_level=row["autonomy_level"],
        )
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"Skill '{skill_id}' contains invalid JSON metadata.") from exc


def _matches_type(value: Any, expected: str) -> bool:
    mappings = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
    }
    checker = mappings.get(expected)
    return True if checker is None else checker(value)


def _validate_value(value: Any, schema: dict[str, Any], path: str) -> None:
    expected = schema.get("type")
    if isinstance(expected, str) and not _matches_type(value, expected):
        raise ValueError(f"{path} must be of type {expected}.")

    if isinstance(value, str) and len(value) < schema.get("minLength", 0):
        raise ValueError(f"{path} is shorter than the allowed minimum.")

    if isinstance(value, dict):
        for field in schema.get("required", []):
            if field not in value:
                raise ValueError(f"{path}.{field} is required.")
        for field, field_schema in schema.get("properties", {}).items():
            if field in value and isinstance(field_schema, dict):
                _validate_value(value[field], field_schema, f"{path}.{field}")


def validate_payload(payload: dict[str, Any], schema: dict[str, Any], label: str) -> None:
    """Validate the JSON-schema subset used by stored skill contracts."""

    _validate_value(payload, schema, label)


def record_skill_execution(
    skill: SkillDefinition,
    *,
    input_payload: dict[str, Any],
    output_payload: dict[str, Any],
    duration_ms: int,
    db_path: pathlib.Path = DB_PATH,
    validate_contracts: bool = True,
) -> ExecutionSummary:
    if validate_contracts:
        validate_payload(input_payload, skill.input_schema, "skill_input")
        validate_payload(output_payload, skill.output_schema, "skill_output")

    succeeded = output_payload.get("success") is True
    execution_id = str(uuid.uuid4())
    created_at = _utc_now()
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            INSERT INTO skill_executions (
                execution_id, skill_id, status, input_json, output_json,
                error_message, duration_ms, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                execution_id,
                skill.skill_id,
                "succeeded" if succeeded else "failed",
                json.dumps(input_payload, ensure_ascii=False, default=str),
                json.dumps(output_payload, ensure_ascii=False, default=str),
                None if succeeded else str(output_payload.get("error", "Unknown error")),
                max(0, int(duration_ms)),
                created_at,
            ),
        )
        total, successful = connection.execute(
            """
            SELECT COUNT(*),
                   SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END)
            FROM skill_executions
            WHERE skill_id = ?
            """,
            (skill.skill_id,),
        ).fetchone()
        successful = int(successful or 0)
        total = int(total)
        success_rate = successful / total if total else 0.0
        requirements = skill.autonomy_requirements
        autonomous = (
            total >= int(requirements.get("minimum_executions", 0))
            and successful
            >= int(requirements.get("minimum_successful_executions", 0))
            and success_rate >= float(requirements.get("minimum_success_rate", 1.0))
        )
        autonomy_level = "autonomous" if autonomous else "supervised"
        connection.execute(
            """
            UPDATE skills
            SET autonomy_level = ?, updated_at = ?
            WHERE skill_id = ?
            """,
            (autonomy_level, created_at, skill.skill_id),
        )
        connection.commit()

    return ExecutionSummary(
        execution_id=execution_id,
        autonomy_level=autonomy_level,
        total_executions=total,
        successful_executions=successful,
        success_rate=success_rate,
    )
