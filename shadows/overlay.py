"""
Privacy overlay — the window that appears when screen sharing is detected.

The overlay covers the main window content with a neutral, professional
message indicating that sensitive content has been hidden due to active
screen sharing / recording.
"""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPaintEvent,
    QPalette,
)
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
#  Eye / visibility icons (simple unicode fallback — no asset files needed)
# ---------------------------------------------------------------------------
_ICON_VISIBLE = "👁"
_ICON_HIDDEN = "🔒"
_ICON_SHIELD = "🛡"


# ===================================================================
#  Overlay
# ===================================================================
class PrivacyOverlay(QWidget):
    """
    A semi-transparent overlay that replaces the main window content
    when screen sharing is detected.

    Signals
    -------
    unlock_requested :
        Emitted when the user clicks "Reveal" (requires confirmation).
    """

    unlock_requested = pyqtSignal()

    SHIELD_COLOR = QColor("#1a1a2e")
    ACCENT_COLOR = QColor("#e94560")
    TEXT_COLOR = QColor("#ffffff")
    SUBTITLE_COLOR = QColor("#a0a0b0")

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.hide()

    # ── public API ────────────────────────────────────────────────

    def show_overlay(self, apps: Optional[list[str]] = None) -> None:
        """Show the privacy overlay, optionally listing detected apps."""
        if apps:
            app_list = ", ".join(apps[:5])
            if len(apps) > 3:
                app_list += f" +{len(apps) - 3}"
            self._subtitle.setText(
                f"Compartilhamento de tela detectado via: {app_list}"
            )
        else:
            self._subtitle.setText(
                "Compartilhamento de tela ou gravação detectado"
            )
        # Ensure overlay fills the parent widget
        if self.parentWidget():
            self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()

    def hide_overlay(self) -> None:
        """Hide the overlay and restore normal content."""
        self.hide()

    # ── UI construction ───────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setStyleSheet("""
            PrivacyOverlay {
                background-color: rgba(26, 26, 46, 230);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        # ── shield icon ───────────────────────────────────────────
        self._icon_label = QLabel(_ICON_SHIELD)
        self._icon_label.setAlignment(Qt.AlignCenter)
        icon_font = self._icon_label.font()
        icon_font.setPointSize(48)
        self._icon_label.setFont(icon_font)
        layout.addWidget(self._icon_label)

        # ── title ─────────────────────────────────────────────────
        self._title = QLabel("Conteúdo Protegido")
        self._title.setAlignment(Qt.AlignCenter)
        title_font = self._title.font()
        title_font.setPointSize(22)
        title_font.setBold(True)
        self._title.setFont(title_font)
        self._title.setStyleSheet(f"color: {self.TEXT_COLOR.name()};")
        layout.addWidget(self._title)

        # ── subtitle ──────────────────────────────────────────────
        self._subtitle = QLabel(
            "Compartilhamento de tela ou gravação detectado"
        )
        self._subtitle.setAlignment(Qt.AlignCenter)
        sub_font = self._subtitle.font()
        sub_font.setPointSize(12)
        self._subtitle.setFont(sub_font)
        self._subtitle.setStyleSheet(f"color: {self.SUBTITLE_COLOR.name()};")
        layout.addWidget(self._subtitle)

        # ── spacer ─────────────────────────────────────────────────
        layout.addSpacing(16)

        # ── description ───────────────────────────────────────────
        desc = QLabel(
            "Suas notas e credenciais estão ocultas até que o "
            "compartilhamento de tela seja interrompido.\n"
            "Este aplicativo protege sua privacidade automaticamente."
        )
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        desc.setMaximumWidth(480)
        desc_font = desc.font()
        desc_font.setPointSize(10)
        desc.setFont(desc_font)
        desc.setStyleSheet(
            f"color: {self.SUBTITLE_COLOR.name()}; padding: 0 32px;"
        )
        layout.addWidget(desc)

        # ── reveal button (with guard) ────────────────────────────
        self._reveal_btn = QPushButton("🔓  Revelar conteúdo")
        self._reveal_btn.setCursor(Qt.PointingHandCursor)
        self._reveal_btn.setFixedWidth(260)
        self._reveal_btn.setFixedHeight(42)
        self._reveal_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.ACCENT_COLOR.name()};
                color: white;
                border: none;
                border-radius: 21px;
                font-size: 14px;
                font-weight: bold;
                padding: 0 24px;
            }}
            QPushButton:hover {{
                background-color: #d6384d;
            }}
            QPushButton:pressed {{
                background-color: #c03044;
            }}
        """)
        self._reveal_btn.clicked.connect(self._on_reveal_clicked)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self._reveal_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # ── status indicator ──────────────────────────────────────
        self._status_label = QLabel("🔄  Monitorando...")
        self._status_label.setAlignment(Qt.AlignCenter)
        status_font = self._status_label.font()
        status_font.setPointSize(9)
        self._status_label.setFont(status_font)
        self._status_label.setStyleSheet(
            f"color: {self.SUBTITLE_COLOR.name()}; padding-top: 16px;"
        )
        layout.addWidget(self._status_label)

        self.setLayout(layout)

    # ── event handlers ────────────────────────────────────────────

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Paint a subtle gradient background for the overlay."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0.0, QColor("#1a1a2e"))
        gradient.setColorAt(0.5, QColor("#16213e"))
        gradient.setColorAt(1.0, QColor("#0f3460"))
        painter.fillRect(self.rect(), gradient)

        # Subtle border
        painter.setPen(QColor(self.ACCENT_COLOR))
        painter.drawRect(self.rect().adjusted(2, 2, -2, -2))

        super().paintEvent(event)

    def _on_reveal_clicked(self) -> None:
        """Ask for confirmation before revealing content."""
        from PyQt5.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self,
            "Revelar conteúdo?",
            "Ainda há compartilhamento de tela ativo.\n"
            "Tem certeza de que deseja revelar o conteúdo protegido?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.unlock_requested.emit()

    def set_status(self, text: str) -> None:
        """Update the status text at the bottom of the overlay."""
        self._status_label.setText(text)
