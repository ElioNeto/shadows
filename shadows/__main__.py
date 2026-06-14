"""
Entry point for ``python -m shadows`` and ``shadows`` CLI command.

Delegates to ``main.py`` at the project root.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is on sys.path (where main.py lives)
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Import the main module dynamically to avoid circular imports
import importlib  # noqa: E402

main_module = importlib.import_module("main")
main_module.main()
