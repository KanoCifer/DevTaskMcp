"""Test scaffolding for DevTaskMcp.

Locks current MCP behaviour before the Task Document v3 refactor. The tests
exercise the public surface of src/devtask_mcp (models, helpers, tool bodies)
with a fake HTTP client; they do not need the live kanocifer-chat API.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))