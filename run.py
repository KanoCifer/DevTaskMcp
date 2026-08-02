"""Run the DevTaskMcp server.

Convenience entry point so the plugin's .mcp.json can launch the server
without relying on `python -m devtask_mcp.server` (which depends on cwd
and PYTHONPATH when invoked from the plugin cache).
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from devtask_mcp.server import main  # noqa: E402

if __name__ == "__main__":
    main()