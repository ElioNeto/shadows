"""
Main application window — the primary user interface.

Provides:
  • Login / unlock screen
  • Note list with search
  • Note editor (rich text with Markdown support)
  • System tray integration
  • Privacy overlay integration
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from PyQt5.QtCore import (
    QByteArray,
    QMimeData,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QClipboard,
    QColor,
    QFont,
    QIcon,
    QKeyEvent,
    QKeySequence,
    QPixmap,
    QTextCursor,
    QTextDocument,
    QTextList,
)
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QShortcut,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QStyle,
    QSystemTrayIcon,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .detector import ScreenShareDetector
from .overlay import PrivacyOverlay
from .storage import Note, Vault

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------
APP_NAME = "Shadows"
APP_VERSION = "1.0.0"
ORG_NAME = "Shadows"
WINDOW_MIN_WIDTH = 860
WINDOW_MIN_HEIGHT = 580


# ===================================================================
#  Login Dialog
# ===================================================================
class LoginDialog(QDialog):
    """
    Modal dialog for unlocking the vault.

    On first run the user creates a master password; on subsequent
    launches they provide the existing password.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._password: str = ""
        self._is_first_run = not Vault.exists()
        self._build_ui()

    @property
    def password(self) -> str:
        return self._password

    # ── UI ────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        self.setWindowTitle(f"{APP_NAME} — Autenticação")
        self.setFixedSize(400, 300)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowContextHelpButtonHint
        )
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
            }
            QLabel {
                color: #ffffff;
            }
            QLineEdit {
                background-color: #16213e;
                color: #ffffff;
                border: 1px solid #0f3460;
                border-radius: 6px;
                padding: 10px 14px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #e94560;
            }
            QPushButton {
                background-color: #e94560;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d6384d;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        # App icon / logo area
        icon_label = QLabel("🛡️")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_font = icon_label.font()
        icon_font.setPointSize(40)
        icon_label.setFont(icon_font)
        layout.addWidget(icon_label)

        # Title
        title = QLabel(APP_NAME)
        title.setAlignment(Qt.AlignCenter)
        title_font = title.font()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Subtitle
        if self._is_first_run:
            subtitle = QLabel("Crie sua senha mestra para proteger seus dados")
        else:
            subtitle = QLabel("Digite sua senha mestra para acessar o cofre")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #a0a0b0; font-size: 12px;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # Password field
        self._password_input = QLineEdit()
        self._password_input.setPlaceholderText(
            "Criar senha mestra..." if self._is_first_run
            else "Senha mestra..."
        )
        self._password_input.setEchoMode(QLineEdit.Password)
        self._password_input.setMaxLength(128)
        layout.addWidget(self._password_input)

        # Confirm password (only on first run)
        self._confirm_input: Optional[QLineEdit] = None
        if self._is_first_run:
            self._confirm_input = QLineEdit()
            self._confirm_input.setPlaceholderText("Confirmar senha...")
            self._confirm_input.setEchoMode(QLineEdit.Password)
            self._confirm_input.setMaxLength(128)
            layout.addWidget(self._confirm_input)

        # Unlock button
        self._unlock_btn = QPushButton(
            "🔓  Criar Cofre" if self._is_first_run else "🔓  Desbloquear"
        )
        self._unlock_btn.clicked.connect(self._on_unlock)
        layout.addWidget(self._unlock_btn)

        # Error label
        self._error_label = QLabel("")
        self._error_label.setAlignment(Qt.AlignCenter)
        self._error_label.setStyleSheet("color: #e94560; font-size: 11px;")
        layout.addWidget(self._error_label)

        # Enter key shortcut
        self._password_input.returnPressed.connect(self._on_unlock)
        if self._confirm_input:
            self._confirm_input.returnPressed.connect(self._on_unlock)

        layout.addStretch()

    def _on_unlock(self) -> None:
        password = self._password_input.text().strip()
        if not password:
            self._error_label.setText("A senha não pode estar vazia")
            return

        if self._is_first_run:
            confirm = (
                self._confirm_input.text().strip() if self._confirm_input else ""
            )
            if password != confirm:
                self._error_label.setText("As senhas não coincidem")
                return
            if len(password) < 4:
                self._error_label.setText(
                    "A senha deve ter pelo menos 4 caracteres"
                )
                return

        try:
            # Verify password
            vault = Vault(password)
            self._password = password
            self.accept()
        except ValueError as exc:
            self._error_label.setText(str(exc))
        except Exception as exc:
            logger.exception("Login failed")
            self._error_label.setText(f"Erro: {exc}")


# ===================================================================
#  Note Editor Widget
# ===================================================================
class NoteEditor(QWidget):
    """Rich text editor for a single note."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._current_note: Optional[Note] = None
        self._modified = False
        self._build_ui()

    # ── public API ────────────────────────────────────────────────
    @property
    def current_note(self) -> Optional[Note]:
        return self._current_note

    @property
    def is_modified(self) -> bool:
        return self._modified

    def focus_title(self) -> None:
        """Set keyboard focus to the title field."""
        self._title_edit.setFocus()

    def load_note(self, note: Note) -> None:
        """Load a note for viewing/editing."""
        self._current_note = note
        self._title_edit.setText(note.title)
        self._content_edit.setPlainText(note.content)
        self._modified = False
        self._update_title()

    def clear(self) -> None:
        """Clear the editor."""
        self._current_note = None
        self._title_edit.clear()
        self._content_edit.clear()
        self._modified = False
        self._update_title()

    def get_updated_note(self) -> Optional[Note]:
        """Return the current note with any edits applied, or None."""
        if self._current_note is None:
            return None
        title = self._title_edit.text().strip()
        content = self._content_edit.toPlainText()
        note = Note(
            id=self._current_note.id,
            title=title or "Sem título",
            content=content,
            created=self._current_note.created,
            updated=self._current_note.updated,
        )
        note.touch()
        return note

    # ── UI ────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Title
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Título da nota...")
        self._title_edit.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                border-bottom: 1px solid #2a2a4a;
                color: #ffffff;
                font-size: 20px;
                font-weight: bold;
                padding: 8px 4px;
            }
            QLineEdit:focus {
                border-bottom: 2px solid #e94560;
            }
        """)
        self._title_edit.textChanged.connect(self._mark_modified)
        layout.addWidget(self._title_edit)

        # Content
        self._content_edit = QPlainTextEdit()
        self._content_edit.setPlaceholderText("Digite seu conteúdo aqui...")
        self._content_edit.setStyleSheet("""
            QPlainTextEdit {
                background: transparent;
                border: none;
                color: #d0d0d0;
                font-size: 14px;
                padding: 8px 4px;
                selection-background-color: #e94560;
                selection-color: white;
            }
            QPlainTextEdit:focus {
                background-color: rgba(255, 255, 255, 0.02);
            }
        """)
        content_font = self._content_edit.font()
        content_font.setPointSize(13)
        content_font.setFamily("Inter, SF Mono, Consolas, monospace")
        self._content_edit.setFont(content_font)
        self._content_edit.setTabStopDistance(32)
        self._content_edit.textChanged.connect(self._mark_modified)
        layout.addWidget(self._content_edit)

        # Word / char counter
        self._status_bar_internal = QLabel("")
        self._status_bar_internal.setStyleSheet(
            "color: #666; font-size: 11px; padding: 2px 4px;"
        )
        self._content_edit.textChanged.connect(self._update_stats)
        layout.addWidget(self._status_bar_internal)

        self.setLayout(layout)

    def _mark_modified(self) -> None:
        if self._current_note is not None:
            self._modified = True
            self._update_title()

    def _update_title(self) -> None:
        note = self._current_note
        if note:
            suffix = " *" if self._modified else ""
            self.setWindowTitle(f"{note.title}{suffix}")
        else:
            self.setWindowTitle("")

    def _update_stats(self) -> None:
        text = self._content_edit.toPlainText()
        words = len(text.split()) if text.strip() else 0
        chars = len(text)
        self._status_bar_internal.setText(
            f"{words} palavras  ·  {chars} caracteres"
        )


# ===================================================================
#  Main Application Window
# ===================================================================
class MainWindow(QMainWindow):
    """Primary application window with sidebar, editor, and tray icon."""

    def __init__(
        self,
        vault: Vault,
        detector: ScreenShareDetector,
    ) -> None:
        super().__init__()
        self._vault = vault
        self._detector = detector
        self._notes: list[Note] = []
        self._sharing = False

        self._build_ui()
        self._setup_tray()
        self._connect_signals()

        # Load notes
        self._refresh_notes()
        self._detector.start()

        # Status
        self.statusBar().showMessage("Pronto  ·  Proteção ativa", 3000)

    # ── UI Construction ───────────────────────────────────────────
    def _build_ui(self) -> None:
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.resize(1024, 700)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a2e;
            }
            QWidget {
                background-color: #1a1a2e;
                color: #ffffff;
            }
            QSplitter::handle {
                background-color: #2a2a4a;
                width: 1px;
            }
        """)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Toolbar ──────────────────────────────────────────────
        self._toolbar = QToolBar()
        self._toolbar.setMovable(False)
        self._toolbar.setStyleSheet("""
            QToolBar {
                background-color: #16213e;
                border-bottom: 1px solid #2a2a4a;
                padding: 4px 8px;
                spacing: 6px;
            }
            QToolButton {
                background: transparent;
                border: none;
                color: #a0a0b0;
                padding: 6px 10px;
                border-radius: 4px;
                font-size: 13px;
            }
            QToolButton:hover {
                background-color: #2a2a4a;
                color: white;
            }
            QToolButton:pressed {
                background-color: #e94560;
                color: white;
            }
        """)

        # New note
        self._new_btn = QToolButton()
        self._new_btn.setText("＋  Nova")
        self._new_btn.clicked.connect(self._on_new_note)
        self._toolbar.addWidget(self._new_btn)

        # Save
        self._save_btn = QToolButton()
        self._save_btn.setText("💾  Salvar")
        self._save_btn.clicked.connect(self._on_save_note)
        self._toolbar.addWidget(self._save_btn)

        self._toolbar.addSeparator()

        # Delete
        self._delete_btn = QToolButton()
        self._delete_btn.setText("🗑  Excluir")
        self._delete_btn.clicked.connect(self._on_delete_note)
        self._toolbar.addWidget(self._delete_btn)

        # Export
        self._export_btn = QToolButton()
        self._export_btn.setText("📤  Exportar")
        self._export_btn.clicked.connect(self._on_export)
        self._toolbar.addWidget(self._export_btn)

        self._toolbar.addSeparator()

        # Sharing indicator
        self._sharing_indicator = QToolButton()
        self._sharing_indicator.setText("🛡  Protegido")
        self._sharing_indicator.setEnabled(False)
        self._sharing_indicator.setStyleSheet("""
            QToolButton {
                background-color: #2d4a2e;
                color: #4caf50;
                border: 1px solid #4caf50;
                border-radius: 12px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: bold;
            }
        """)
        self._toolbar.addWidget(self._sharing_indicator)

        # Spacer + tray controls on the right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        spacer.setStyleSheet("background: transparent;")
        self._toolbar.addWidget(spacer)

        # Hide to tray
        self._minimize_to_tray_btn = QToolButton()
        self._minimize_to_tray_btn.setText("➖  Minimizar")
        self._minimize_to_tray_btn.clicked.connect(self._on_minimize_to_tray)
        self._toolbar.addWidget(self._minimize_to_tray_btn)

        main_layout.addWidget(self._toolbar)

        # ── Splitter: sidebar + editor ───────────────────────────
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setHandleWidth(1)

        # Sidebar
        self._sidebar = QWidget()
        sidebar_layout = QVBoxLayout(self._sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Search
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍  Buscar notas...")
        self._search_input.setStyleSheet("""
            QLineEdit {
                background-color: #16213e;
                border: none;
                border-bottom: 1px solid #2a2a4a;
                color: #ffffff;
                padding: 12px 16px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-bottom: 2px solid #e94560;
            }
        """)
        self._search_input.textChanged.connect(self._on_search)
        sidebar_layout.addWidget(self._search_input)

        # Note list
        self._note_list = QListWidget()
        self._note_list.setStyleSheet("""
            QListWidget {
                background-color: #16213e;
                border: none;
                outline: none;
            }
            QListWidget::item {
                color: #d0d0d0;
                padding: 12px 16px;
                border-bottom: 1px solid #1e1e3e;
                font-size: 13px;
            }
            QListWidget::item:selected {
                background-color: #2a2a4a;
                color: white;
                border-left: 3px solid #e94560;
            }
            QListWidget::item:hover {
                background-color: #1e1e3e;
            }
        """)
        self._note_list.currentItemChanged.connect(self._on_note_selected)
        sidebar_layout.addWidget(self._note_list)

        self._sidebar.setMinimumWidth(220)
        self._sidebar.setMaximumWidth(400)
        self._splitter.addWidget(self._sidebar)

        # Editor container (with overlay)
        self._editor_container = QWidget()
        editor_layout = QVBoxLayout(self._editor_container)
        editor_layout.setContentsMargins(16, 8, 16, 8)

        self._editor = NoteEditor()
        editor_layout.addWidget(self._editor)

        # Privacy overlay
        self._overlay = PrivacyOverlay(self._editor_container)
        self._overlay.hide()

        self._splitter.addWidget(self._editor_container)
        self._splitter.setSizes([280, 744])
        self._splitter.splitterMoved.connect(self._on_splitter_moved)

        main_layout.addWidget(self._splitter)

        # ── Keyboard shortcuts ───────────────────────────────────
        QShortcut(QKeySequence("Ctrl+N"), self, self._on_new_note)
        QShortcut(QKeySequence("Ctrl+S"), self, self._on_save_note)
        QShortcut(QKeySequence("Delete"), self, self._on_delete_note)
        QShortcut(QKeySequence("Ctrl+F"), self, self._search_input.setFocus)
        QShortcut(QKeySequence("Escape"), self, self._on_escape)

        # ── Status bar ───────────────────────────────────────────
        self._status_bar = StatusBar(self)
        self.setStatusBar(self._status_bar)

    # ── System Tray ───────────────────────────────────────────────
    def _setup_tray(self) -> None:
        self._tray_icon = QSystemTrayIcon(self)
        # Create a simple shield icon programmatically (no asset files needed)
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        from PyQt5.QtGui import QPainter, QPen, QBrush, QPainterPath
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        # Draw a shield shape
        path = QPainterPath()
        path.moveTo(32, 4)
        path.lineTo(56, 14)
        path.lineTo(56, 32)
        path.cubicTo(56, 48, 32, 60, 32, 60)
        path.cubicTo(32, 60, 8, 48, 8, 32)
        path.lineTo(8, 14)
        path.closeSubpath()
        painter.fillPath(path, QBrush(QColor("#e94560")))
        # Draw a checkmark inside
        pen = QPen(QColor("#ffffff"), 3)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(22, 32, 30, 40)
        painter.drawLine(30, 40, 44, 24)
        painter.end()
        self._tray_icon.setIcon(QIcon(pixmap))
        self._tray_icon.setToolTip(APP_NAME)

        tray_menu = QMenu()

        show_action = tray_menu.addAction("🪟  Mostrar")
        show_action.triggered.connect(self._on_show_from_tray)

        lock_action = tray_menu.addAction("🔒  Bloquear")
        lock_action.triggered.connect(self._on_lock)

        tray_menu.addSeparator()

        quit_action = tray_menu.addAction("🚪  Sair")
        quit_action.triggered.connect(self._on_quit)

        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _on_tray_activated(
        self, reason: QSystemTrayIcon.ActivationReason
    ) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self._on_show_from_tray()

    def _on_minimize_to_tray(self) -> None:
        self.hide()
        self._tray_icon.showMessage(
            APP_NAME,
            "O aplicativo continua protegendo sua privacidade em segundo plano.",
            QSystemTrayIcon.Information,
            2000,
        )

    def _on_show_from_tray(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_escape(self) -> None:
        if self.isVisible():
            self._on_minimize_to_tray()

    # ── Signal Connections ────────────────────────────────────────
    def _connect_signals(self) -> None:
        self._detector.state_changed.connect(self._on_sharing_state_changed)
        self._overlay.unlock_requested.connect(self._on_overlay_unlock)

    def _on_sharing_state_changed(self, is_sharing: bool) -> None:
        self._sharing = is_sharing
        if is_sharing:
            apps = self._detector.active_apps
            self._overlay.show_overlay(apps)
            self._sharing_indicator.setText("🔴  Compartilhando")
            self._sharing_indicator.setStyleSheet("""
                QToolButton {
                    background-color: #4a2e2e;
                    color: #f44336;
                    border: 1px solid #f44336;
                    border-radius: 12px;
                    padding: 4px 12px;
                    font-size: 12px;
                    font-weight: bold;
                }
            """)
            self._status_bar.show_sharing_detected(apps)
            self._tray_icon.showMessage(
                "🔴 Compartilhamento Detectado",
                "Conteúdo protegido ocultado automaticamente.",
                QSystemTrayIcon.Warning,
                3000,
            )
        else:
            self._overlay.hide_overlay()
            self._sharing_indicator.setText("🛡  Protegido")
            self._sharing_indicator.setStyleSheet("""
                QToolButton {
                    background-color: #2d4a2e;
                    color: #4caf50;
                    border: 1px solid #4caf50;
                    border-radius: 12px;
                    padding: 4px 12px;
                    font-size: 12px;
                    font-weight: bold;
                }
            """)
            self._status_bar.show_clear()

    def _on_overlay_unlock(self) -> None:
        """User clicked reveal on the overlay — force-show content."""
        self._overlay.hide_overlay()

    # ── Note Operations ───────────────────────────────────────────
    def _refresh_notes(self, search: str = "") -> None:
        self._notes = self._vault.list_notes()
        if search:
            search_lower = search.lower()
            self._notes = [
                n for n in self._notes if search_lower in n.title.lower()
            ]

        self._note_list.clear()
        for note in self._notes:
            item = QListWidgetItem()
            # Truncate title for display
            title = note.title if note.title else "Sem título"
            if len(title) > 42:
                title = title[:40] + "…"
            item.setText(title)
            item.setData(Qt.UserRole, note.id)
            self._note_list.addItem(item)

        self._status_bar.show_note_count(len(self._notes))
        if not self._notes:
            self._editor.clear()

    def _on_search(self, text: str) -> None:
        self._refresh_notes(text)

    def _on_note_selected(
        self, current: QListWidgetItem, previous: QListWidgetItem
    ) -> None:
        if current is None:
            return
        note_id = current.data(Qt.UserRole)
        note = self._vault.get_note(note_id)
        if note:
            self._editor.load_note(note)

    def _on_new_note(self) -> None:
        note = self._vault.create_note()
        self._refresh_notes()
        # Select the new note in the list
        for i in range(self._note_list.count()):
            item = self._note_list.item(i)
            if item.data(Qt.UserRole) == note.id:
                self._note_list.setCurrentItem(item)
                break
        self._editor.load_note(note)
        self._editor.focus_title()
        self.statusBar().showMessage("Nova nota criada", 2000)

    def _on_save_note(self) -> None:
        if self._sharing:
            QMessageBox.warning(
                self,
                "Compartilhamento Ativo",
                "Não é possível salvar enquanto o compartilhamento "
                "de tela estiver ativo por questões de segurança.",
            )
            return

        updated = self._editor.get_updated_note()
        if updated:
            self._vault.save_note(updated)
            self._refresh_notes(self._search_input.text())
            self.statusBar().showMessage("Nota salva ✅", 2000)

    def _on_delete_note(self) -> None:
        note = self._editor.current_note
        if note is None:
            return

        reply = QMessageBox.question(
            self,
            "Excluir nota?",
            f'Tem certeza que deseja excluir "{note.title}"?\n'
            "Esta ação não pode ser desfeita.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._vault.delete(note.id)
            self._editor.clear()
            self._refresh_notes(self._search_input.text())
            self.statusBar().showMessage("Nota excluída", 2000)

    def _on_export(self) -> None:
        note = self._editor.current_note
        if note is None:
            QMessageBox.information(
                self, "Exportar", "Selecione uma nota para exportar."
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar nota",
            f"{note.title}.txt",
            "Arquivo de texto (*.txt);;Markdown (*.md);;Todos (*)",
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(f"# {note.title}\n\n{note.content}")
                self.statusBar().showMessage(
                    f"Nota exportada para {path}", 3000
                )
            except OSError as exc:
                QMessageBox.critical(
                    self, "Erro", f"Não foi possível exportar: {exc}"
                )

    def _on_lock(self) -> None:
        """Lock the vault and return to login."""
        self._detector.stop()
        self._overlay.hide_overlay()
        self.hide()
        self._tray_icon.hide()

        # Show login dialog again — loop until authenticated or cancelled
        from .storage import Vault  # already imported at top, but keep explicit

        app = QApplication.instance()
        if app is None:
            return

        vault: Vault | None = None
        while vault is None:
            login = LoginDialog()
            if login.exec_() != LoginDialog.Accepted:
                self._on_quit()
                return

            password = login.password
            try:
                vault = Vault(password)
            except ValueError as exc:
                logging.error("Authentication failed: %s", exc)
                continue
            except Exception as exc:
                logging.exception("Unexpected error during vault open")
                QMessageBox.critical(
                    None, "Erro", f"Erro ao abrir cofre: {exc}"
                )
                self._on_quit()
                return

        self._vault = vault
        self._refresh_notes()
        self._detector.start()
        self._tray_icon.show()
        self.show()
        self.statusBar().showMessage("Cofre desbloqueado", 2000)

    def _on_quit(self) -> None:
        self._detector.stop()
        QApplication.instance().quit()

    # ── Event Overrides ───────────────────────────────────────────
    def closeEvent(self, event) -> None:  # noqa: N802
        """Override close to minimize to tray instead of quitting."""
        self._on_minimize_to_tray()
        event.ignore()

    def _on_splitter_moved(self, pos: int, index: int) -> None:
        """Ensure overlay matches editor container size after splitter move."""
        self._update_overlay_geometry()

    def _update_overlay_geometry(self) -> None:
        """Sync overlay geometry with the editor container."""
        if hasattr(self, "_overlay") and self._overlay.isVisible():
            self._overlay.setGeometry(self._editor_container.rect())

    def resizeEvent(self, event) -> None:  # noqa: N802
        """Ensure overlay matches editor container size."""
        super().resizeEvent(event)
        self._update_overlay_geometry()


# ===================================================================
#  Custom Status Bar
# ===================================================================
class StatusBar(QStatusBar):
    """Enhanced status bar with sharing state indicators."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("""
            QStatusBar {
                background-color: #0f0f23;
                color: #888;
                border-top: 1px solid #2a2a4a;
                font-size: 12px;
                padding: 2px 8px;
            }
            QStatusBar::item {
                border: none;
            }
        """)

        self._note_count = QLabel("0 notas")
        self.addPermanentWidget(self._note_count)

        self._sharing_label = QLabel("")
        self.addPermanentWidget(self._sharing_label)

    def show_note_count(self, count: int) -> None:
        self._note_count.setText(f"{count} nota{'s' if count != 1 else ''}")

    def show_sharing_detected(self, apps: list[str]) -> None:
        app_str = ", ".join(apps[:3])
        if len(apps) > 3:
            app_str += f" +{len(apps) - 3}"
        self._sharing_label.setText(f"🔴 Compartilhando: {app_str}")
        self._sharing_label.setStyleSheet(
            "color: #f44336; font-weight: bold; padding: 0 8px;"
        )

    def show_clear(self) -> None:
        self._sharing_label.setText("🛡 Protegido")
        self._sharing_label.setStyleSheet(
            "color: #4caf50; padding: 0 8px;"
        )
