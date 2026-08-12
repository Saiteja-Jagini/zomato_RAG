"""Validation shared by the plotting tool and its isolated runner."""

from __future__ import annotations

import ast


BLOCKED_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.Global,
    ast.Nonlocal,
    ast.Lambda,
    ast.ClassDef,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.Raise,
    ast.Delete,
)

BLOCKED_NAMES = {
    "__builtins__",
    "breakpoint",
    "compile",
    "eval",
    "exec",
    "globals",
    "help",
    "input",
    "locals",
    "memoryview",
    "open",
    "os",
    "pathlib",
    "shutil",
    "socket",
    "subprocess",
    "sys",
    "vars",
}

ALLOWED_DIRECT_CALLS = {
    "abs",
    "all",
    "any",
    "bool",
    "dict",
    "enumerate",
    "float",
    "int",
    "len",
    "list",
    "max",
    "min",
    "range",
    "reversed",
    "round",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
    "zip",
}

ALLOWED_METHODS = {
    # Matplotlib axes and figure methods.
    "annotate",
    "axhline",
    "axvline",
    "bar",
    "bar_label",
    "boxplot",
    "figure",
    "fill_between",
    "get_height",
    "get_legend",
    "get_width",
    "get_x",
    "grid",
    "hist",
    "legend",
    "lineplot",
    "plot",
    "scatter",
    "set",
    "set_facecolor",
    "set_title",
    "set_xlabel",
    "set_xlim",
    "set_xscale",
    "set_xticklabels",
    "set_xticks",
    "set_ylabel",
    "set_ylim",
    "set_yscale",
    "set_yticklabels",
    "set_yticks",
    "subplots_adjust",
    "suptitle",
    "text",
    "tick_params",
    "tight_layout",
    "violinplot",
    # Safe pyplot, seaborn, and numpy operations.
    "arange",
    "array",
    "barplot",
    "boxplot",
    "close",
    "color_palette",
    "heatmap",
    "histplot",
    "linspace",
    "mean",
    "median",
    "pie",
    "scatterplot",
    "set_theme",
    "subplots",
    "xlabel",
    "ylabel",
    "violinplot",
    "xticks",
    "yticks",
    # Local container/string operations used to prepare labels.
    "append",
    "capitalize",
    "get",
    "items",
    "join",
    "keys",
    "lower",
    "replace",
    "sort",
    "strip",
    "title",
    "upper",
    "values",
}


def validate_plot_script(script: str) -> ast.Module:
    if not script.strip():
        raise ValueError("The plotting script is empty.")
    if len(script) > 20_000:
        raise ValueError("The plotting script exceeds the 20,000 character limit.")

    tree = ast.parse(script, mode="exec")
    for node in ast.walk(tree):
        if isinstance(node, BLOCKED_NODES):
            raise ValueError(f"{type(node).__name__} is not allowed in plotting scripts.")
        if isinstance(node, ast.Name) and node.id in BLOCKED_NAMES:
            raise ValueError(f"Name '{node.id}' is not allowed in plotting scripts.")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise ValueError("Private and dunder attributes are not allowed.")
        if isinstance(node, ast.While):
            raise ValueError("While loops are not allowed in plotting scripts.")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id not in ALLOWED_DIRECT_CALLS:
                    raise ValueError(f"Call to '{node.func.id}' is not allowed.")
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr not in ALLOWED_METHODS:
                    raise ValueError(f"Method '{node.func.attr}' is not allowed.")
            else:
                raise ValueError("Dynamic function calls are not allowed.")
    return tree
