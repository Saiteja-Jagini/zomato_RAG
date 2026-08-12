from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from langchain.tools import tool

from tools.plot_security import validate_plot_script


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"
RUNNER_PATH = Path(__file__).with_name("plot_runner.py")
MPL_CONFIG_DIR = PROJECT_ROOT / ".matplotlib"


@tool()
def execute_plot_script(
    python_script: str,
    data: dict[str, Any],
    chart_name: str = "chart",
) -> dict[str, Any] | list[dict[str, Any]]:
    """Execute generated Matplotlib code using structured data from sql_db_query.

    Call this only after sql_db_query returns usable rows. Pass data as a
    dictionary containing `columns` and `rows`. The Python script receives
    `data`, `plt`, `sns`, and `np`; do not include imports, file access,
    plt.show(), savefig(), or external data loading. It must create a figure,
    preferably assigned with `fig, ax = plt.subplots(...)`. This tool validates
    the script, executes it in an isolated child process, saves a PNG, and
    returns its path and the rendered PNG as an image content block.
    """
    if not isinstance(data, dict) or "columns" not in data or "rows" not in data:
        return {"success": False, "error": "data must contain columns and rows."}
    if len(data["rows"]) > 500:
        return {"success": False, "error": "At most 500 rows may be plotted."}

    try:
        validate_plot_script(python_script)
    except (SyntaxError, ValueError) as exc:
        return {"success": False, "error": f"Script validation failed: {exc}"}

    safe_name = "".join(c for c in chart_name.lower() if c.isalnum() or c in "-_")
    safe_name = safe_name.strip("-_") or "chart"
    image_path = OUTPUT_DIR / f"{safe_name}-{uuid.uuid4().hex[:8]}.png"
    OUTPUT_DIR.mkdir(exist_ok=True)
    MPL_CONFIG_DIR.mkdir(exist_ok=True)

    request = {"python_script": python_script, "data": data}
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
            timeout=20,
            check=False,
        )
        if completed.returncode != 0:
            image_path.unlink(missing_ok=True)
            error = (completed.stderr or completed.stdout).strip()
            return {"success": False, "error": error[-2000:]}
        if not image_path.is_file() or image_path.stat().st_size == 0:
            return {"success": False, "error": "No PNG image was generated."}
        relative_path = image_path.relative_to(PROJECT_ROOT).as_posix()
        encoded_image = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "success": True,
                        "image_path": relative_path,
                        "size_bytes": image_path.stat().st_size,
                    }
                ),
            },
            {
                "type": "image",
                "base64": encoded_image,
                "mime_type": "image/png",
            },
        ]
    except subprocess.TimeoutExpired:
        image_path.unlink(missing_ok=True)
        return {"success": False, "error": "Plot execution exceeded 20 seconds."}
    finally:
        if request_file is not None:
            request_file.unlink(missing_ok=True)
