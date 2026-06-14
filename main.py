#!/usr/bin/env python3
"""
Shadows — Desktop application that hides sensitive content during screen sharing.

Usage
-----
    python main.py              # Launch the application
    python main.py --detect     # One-shot detection (no GUI)
    python main.py --help       # Show help

Features
--------
    • Real-time screen sharing detection (process + PipeWire + DBus)
    • Encrypted vault for notes and credentials (AES-256-GCM)
    • Auto-hide privacy overlay when sharing is detected
    • System tray integration for discreet operation
    • Password-protected access to the vault

License: MIT
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure the package root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# ---------------------------------------------------------------------------
#  Logging
# ---------------------------------------------------------------------------
def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ---------------------------------------------------------------------------
#  CLI entry points
# ---------------------------------------------------------------------------
def cmd_detect() -> None:
    """Run a one-shot detection and print results."""
    from shadows.detector import quick_detect

    sharing, apps = quick_detect()
    if sharing:
        print(f"🔴 SCREEN SHARING DETECTED — apps: {', '.join(apps)}")
    else:
        print("🟢 No screen sharing detected")
    sys.exit(0)  # 0 = detection completed successfully


def cmd_gui() -> None:
    """Launch the graphical application."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication

    from shadows.detector import ScreenShareDetector
    from shadows.storage import Vault
    from shadows.ui import LoginDialog, MainWindow

    # ── Create application ───────────────────────────────────────
    app = QApplication(sys.argv)
    app.setApplicationName("Shadows")
    app.setOrganizationName("Shadows")
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray

    # Dark palette (Fusion + explicit QPalette for consistent theming)
    app.setStyle("Fusion")
    from PyQt5.QtGui import QColor, QPalette
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#1a1a2e"))
    palette.setColor(QPalette.WindowText, QColor("#ffffff"))
    palette.setColor(QPalette.Base, QColor("#16213e"))
    palette.setColor(QPalette.AlternateBase, QColor("#1e1e3e"))
    palette.setColor(QPalette.ToolTipBase, QColor("#16213e"))
    palette.setColor(QPalette.ToolTipText, QColor("#ffffff"))
    palette.setColor(QPalette.Text, QColor("#ffffff"))
    palette.setColor(QPalette.Button, QColor("#16213e"))
    palette.setColor(QPalette.ButtonText, QColor("#ffffff"))
    palette.setColor(QPalette.BrightText, QColor("#e94560"))
    palette.setColor(QPalette.Link, QColor("#e94560"))
    palette.setColor(QPalette.Highlight, QColor("#e94560"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    # ── Authentication loop ──────────────────────────────────────
    vault: Vault | None = None
    while vault is None:
        login = LoginDialog()
        if login.exec_() != LoginDialog.Accepted:
            sys.exit(0)  # User cancelled

        password = login.password
        try:
            vault = Vault(password)
        except ValueError as exc:
            logging.error("Authentication failed: %s", exc)
            # Loop back to login dialog
            continue
        except Exception as exc:
            logging.exception("Unexpected error during vault open")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Erro", f"Erro ao abrir cofre: {exc}")
            sys.exit(1)

    # ── Main window ──────────────────────────────────────────────
    detector = ScreenShareDetector()
    window = MainWindow(vault, detector)
    window.show()

    sys.exit(app.exec_())


# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Shadows — Protege seu conteúdo durante compartilhamento de tela",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  %(prog)s                  Inicia a aplicação gráfica
  %(prog)s --detect         Detecta compartilhamento (sem GUI)
  %(prog)s --verbose        Modo detalhado para depuração
        """,
    )
    parser.add_argument(
        "--detect",
        action="store_true",
        help="Escaneia uma vez e sai (sem abrir a GUI)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Exibe logs detalhados de depuração",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="Shadows 1.0.0",
    )

    args = parser.parse_args()
    _setup_logging(args.verbose)

    if args.detect:
        cmd_detect()
    else:
        cmd_gui()


if __name__ == "__main__":
    main()
