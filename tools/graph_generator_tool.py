from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from langchain.tools import tool

from skill_store import (
    PLOTTING_SKILL_ID,
    SkillDefinition,
    load_skill,
    record_skill_execution,
    validate_payload,
)
from tools.plot_security import validate_plot_script


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"
RUNNER_PATH = Path(__file__).with_name("plot_runner.py")
MPL_CONFIG_DIR = PROJECT_ROOT / ".matplotlib"


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((time.perf_counter() - started_at) * 1000))


def _track_outcome(
    skill: SkillDefinition,
    input_payload: dict[str, Any],
    output_payload: dict[str, Any],
    started_at: float,
    *,
    validate_contracts: bool = True,
) -> dict[str, Any]:
    """Persist an outcome and add non-binary execution metadata to the result."""

    result = dict(output_payload)
    result["skill_id"] = skill.skill_id
    try:
        execution = record_skill_execution(
            skill,
            input_payload=input_payload,
            output_payload=output_payload,
            duration_ms=_elapsed_ms(started_at),
            validate_contracts=validate_contracts,
        )
        result.update(
            {
                "skill_execution_id": execution.execution_id,
                "autonomy_level": execution.autonomy_level,
                "total_skill_executions": execution.total_executions,
                "skill_success_rate": round(execution.success_rate, 4),
            }
        )
    except Exception as exc:  # Plot output should survive a telemetry failure.
        result["tracking_error"] = str(exc)
    return result


@tool()
def execute_plot_script(
    python_script: str,
    data: dict[str, Any],
    chart_name: str = "chart",
) -> dict[str, Any] | list[dict[str, Any]]:
    """Run the active database-backed plotting skill on structured SQL data.

    The skill's prompt, configuration, input/output schemas, scope, status, and
    autonomy requirements are loaded from SQLite. Each call is recorded as a
    success or failure, and its success history updates the autonomy level.
    """

    started_at = time.perf_counter()
    try:
        skill = load_skill(PLOTTING_SKILL_ID)
    except Exception as exc:
        return {"success": False, "error": f"Plotting skill unavailable: {exc}"}

    input_payload = {
        "python_script": python_script,
        "data": data,
        "chart_name": chart_name,
    }

    try:
        validate_payload(input_payload, skill.input_schema, "skill_input")
    except ValueError as exc:
        return _track_outcome(
            skill,
            input_payload,
            {"success": False, "error": f"Input contract failed: {exc}"},
            started_at,
            validate_contracts=False,
        )

    configuration = skill.configuration
    try:
        max_rows = max(1, min(int(configuration.get("max_rows", 500)), 5000))
        max_script_characters = max(
            1, min(int(configuration.get("max_script_characters", 20_000)), 20_000)
        )
        timeout_seconds = max(
            1, min(int(configuration.get("timeout_seconds", 20)), 60)
        )
        dpi = max(72, min(int(configuration.get("dpi", 160)), 300))
    except (TypeError, ValueError) as exc:
        return _track_outcome(
            skill,
            input_payload,
            {"success": False, "error": f"Invalid skill configuration: {exc}"},
            started_at,
        )

    if len(data["rows"]) > max_rows:
        return _track_outcome(
            skill,
            input_payload,
            {"success": False, "error": f"At most {max_rows} rows may be plotted."},
            started_at,
        )
    if not data["columns"] or not data["rows"]:
        return _track_outcome(
            skill,
            input_payload,
            {"success": False, "error": "Plot data must have columns and rows."},
            started_at,
        )
    if len(python_script) > max_script_characters:
        return _track_outcome(
            skill,
            input_payload,
            {
                "success": False,
                "error": (
                    "Plotting script exceeds the configured "
                    f"{max_script_characters} character limit."
                ),
            },
            started_at,
        )

    try:
        validate_plot_script(python_script)
    except (SyntaxError, ValueError) as exc:
        return _track_outcome(
            skill,
            input_payload,
            {"success": False, "error": f"Script validation failed: {exc}"},
            started_at,
        )

    safe_name = "".join(c for c in chart_name.lower() if c.isalnum() or c in "-_")
    safe_name = safe_name.strip("-_") or "chart"
    image_path = OUTPUT_DIR / f"{safe_name}-{uuid.uuid4().hex[:8]}.png"
    OUTPUT_DIR.mkdir(exist_ok=True)
    MPL_CONFIG_DIR.mkdir(exist_ok=True)

    request = {
        "python_script": python_script,
        "data": data,
        "configuration": {"dpi": dpi},
    }
    request_file: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            prefix="plot-request-",
            dir=OUTPUT_DIR,
            encoding="utf-8",
            delete=False,
        ) as handle:
            json.dump(request, handle, ensure_ascii=False)
            request_file = Path(handle.name)

        environment = {
            "PATH": os.environ.get("PATH", ""),
            "MPLCONFIGDIR": str(MPL_CONFIG_DIR),
            "PYTHONIOENCODING": "utf-8",
        }
        completed = subprocess.run(
            [sys.executable, "-I", str(RUNNER_PATH), str(request_file), str(image_path)],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            image_path.unlink(missing_ok=True)
            error = (completed.stderr or completed.stdout).strip()
            return _track_outcome(
                skill,
                input_payload,
                {"success": False, "error": error[-2000:]},
                started_at,
            )
        if not image_path.is_file() or image_path.stat().st_size == 0:
            return _track_outcome(
                skill,
                input_payload,
                {"success": False, "error": "No PNG image was generated."},
                started_at,
            )

        relative_path = image_path.relative_to(PROJECT_ROOT).as_posix()
        output_payload = {
            "success": True,
            "image_path": relative_path,
            "size_bytes": image_path.stat().st_size,
        }
        validate_payload(output_payload, skill.output_schema, "skill_output")
        tracked_output = _track_outcome(
            skill, input_payload, output_payload, started_at
        )
        encoded_image = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return [
            {"type": "text", "text": json.dumps(tracked_output)},
            {
                "type": "image",
                "base64": encoded_image,
                "mime_type": "image/png",
            },
        ]
    except subprocess.TimeoutExpired:
        image_path.unlink(missing_ok=True)
        return _track_outcome(
            skill,
            input_payload,
            {
                "success": False,
                "error": f"Plot execution exceeded {timeout_seconds} seconds.",
            },
            started_at,
        )
    except Exception as exc:
        image_path.unlink(missing_ok=True)
        return _track_outcome(
            skill,
            input_payload,
            {"success": False, "error": str(exc)},
            started_at,
        )
    finally:
        if request_file is not None:
            request_file.unlink(missing_ok=True)
