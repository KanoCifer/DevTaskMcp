"""Test scaffolding for DevTaskMcp.

Locks current MCP behaviour before the Task Document v3 refactor. The tests
exercise the public surface of src/devtask-mcp (models, helpers, tool bodies)
with a fake HTTP client; they do not need the live kanocifer-chat API.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# Project uses the import name "devtask-mcp" (hyphen) on disk but the package
# is loaded as `devtask_mcp` because hyphens are not valid Python identifiers.
# This helper builds a synthetic module spec that maps the two names so we can
# import the package from any working directory.
_PKG_DIR = Path(__file__).resolve().parent.parent / "src" / "devtask-mcp"


def _load_package() -> None:
    if "devtask_mcp" in sys.modules:
        return
    spec = importlib.util.spec_from_file_location(
        "devtask_mcp",
        _PKG_DIR / "__init__.py",
        submodule_search_locations=[str(_PKG_DIR)],
    )
    if spec is None or spec.loader is None:  # pragma: no cover
        raise RuntimeError("unable to load devtask-mcp package for tests")
    module = importlib.util.module_from_spec(spec)
    sys.modules["devtask_mcp"] = module
    spec.loader.exec_module(module)
    # Hyphen-named submodules still need registering.
    for submodule in ("models", "client", "server"):
        sub_path = _PKG_DIR / f"{submodule}.py"
        sub_spec = importlib.util.spec_from_file_location(
            f"devtask_mcp.{submodule}", sub_path
        )
        if sub_spec is None or sub_spec.loader is None:  # pragma: no cover
            continue
        sub_module = importlib.util.module_from_spec(sub_spec)
        sys.modules[f"devtask_mcp.{submodule}"] = sub_module
        sub_spec.loader.exec_module(sub_module)


_load_package()
