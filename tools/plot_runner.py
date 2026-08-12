"""Child-process runner for validated Matplotlib scripts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Isolated mode removes project paths. Add the trusted project root only so
# this runner can import its validator; generated code cannot access `sys`.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from tools.plot_security import validate_plot_script


SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}


def main() -> int:
    request_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    request = json.loads(request_path.read_text(encoding="utf-8"))
    script = request["python_script"]
    data = request["data"]
    dpi = int(request.get("configuration", {}).get("dpi", 160))
    if not 72 <= dpi <= 300:
        raise ValueError("Configured DPI must be between 72 and 300.")
    tree = validate_plot_script(script)

    safe_globals = {
        "__builtins__": SAFE_BUILTINS,
        "data": data,
        "np": np,
        "plt": plt,
        "sns": sns,
    }
    namespace: dict = {}
    exec(compile(tree, "<generated-plot>", "exec"), safe_globals, namespace)

    figures = [plt.figure(number) for number in plt.get_fignums()]
    if not figures:
        raise RuntimeError("The script did not create a Matplotlib figure.")
    figure = namespace.get("fig", figures[-1])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, format="png", dpi=dpi, bbox_inches="tight")
    plt.close("all")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
