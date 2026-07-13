#!/usr/bin/env bash
# Bootstrap a local venv with dependencies installed — for machines without uv.
#
# Usage:
#   scripts/setup.sh              # create .venv in repo root and install
#   PYTHON=python3.11 scripts/setup.sh   # pick a specific interpreter
#
# After running, use the venv's python to start the MCP server:
#   .venv/bin/python -m devtask_mcp.server
#
# Or paste this into .mcp.json / ~/.claude.json:
#   {
#     "mcpServers": {
#       "devtask": {
#         "command": "<repo>/venv/bin/python",
#         "args": ["-m", "devtask_mcp.server"]
#       }
#     }
#   }

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT}/.venv"
PYTHON="${PYTHON:-python3}"

if [ ! -d "$VENV_DIR" ]; then
    echo "==> Creating venv at ${VENV_DIR} (using ${PYTHON})"
    "$PYTHON" -m venv "$VENV_DIR"
fi

echo "==> Installing dependencies"
"${VENV_DIR}/bin/pip" install --upgrade pip >/dev/null
"${VENV_DIR}/bin/pip" install -e "${ROOT}" >/dev/null

echo "==> Done. Server command:"
echo "    ${VENV_DIR}/bin/python -m devtask_mcp.server"
