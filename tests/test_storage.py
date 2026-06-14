"""
Unit tests for the encrypted vault (storage.py).

Uses a temporary directory for each test to avoid clobbering
the real ``~/.shadows`` directory.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
#  Fixtures — redirect vault paths to a temp directory
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def temp_vault_dir(monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ``~/.shadows`` to a temporary directory."""
    tmp = Path(tempfile.mkdtemp(prefix="shadows_test_"))
    monkeypatch.setattr("shadows.storage._VAULT_DIR", tmp / "vault")
    monkeypatch.setattr("shadows.storage._KEY_FILE", tmp / "master.key")
    monkeypatch.setattr("shadows.storage._SALT_FILE", tmp / "salt.bin")
    monkeypatch.setattr("shadows.storage.Path.home", lambda: tmp)
    # Ensure the vault dir exists
    (tmp / "vault").mkdir(parents=True, exist_ok=True)
    return tmp


# ---------------------------------------------------------------------------
#  Tests
# ---------------------------------------------------------------------------

class TestVaultCreation:
    """Creating a vault on first run."""

    def test_create_new_vault(self) -> None:
        from shadows.storage import Vault

        vault = Vault("my-secret-password")
        assert vault is not None
        # Key file should have been created
        from shadows.storage import _KEY_FILE
        assert _KEY_FILE.exists()

    def test_reopen_with_correct_password(self) -> None:
        from shadows.storage import Vault

        Vault("correct-pw")
        # Re-open with the same password
        vault2 = Vault("correct-pw")
        assert vault2 is not None

    def test_reopen_with_wrong_password_raises(self) -> None:
        from shadows.storage import Vault

        Vault("correct-pw")
        with pytest.raises(ValueError, match="Incorrect master password"):
            Vault("wrong-pw")


class TestNoteOperations:
    """Creating, listing, reading, updating, and deleting notes."""

    def test_create_and_list(self) -> None:
        from shadows.storage import Vault

        vault = Vault("pw")
        note = vault.create_note("Hello", "World")
        assert note.id is not None
        assert note.title == "Hello"

        notes = vault.list_notes()
        assert len(notes) == 1
        assert notes[0].title == "Hello"
        assert notes[0].content == ""  # content not decrypted in list

    def test_get_full_note(self) -> None:
        from shadows.storage import Vault

        vault = Vault("pw")
        note = vault.create_note("Title", "Secret content")

        loaded = vault.get_note(note.id)
        assert loaded is not None
        assert loaded.title == "Title"
        assert loaded.content == "Secret content"

    def test_update_note(self) -> None:
        from shadows.storage import Vault, Note

        vault = Vault("pw")
        note = vault.create_note("Original", "Original content")

        note.title = "Updated"
        note.content = "Updated content"
        vault.save_note(note)

        loaded = vault.get_note(note.id)
        assert loaded is not None
        assert loaded.title == "Updated"
        assert loaded.content == "Updated content"

    def test_delete_note(self) -> None:
        from shadows.storage import Vault

        vault = Vault("pw")
        note = vault.create_note("To delete", "bye")
        assert vault.delete(note.id) is True
        assert vault.get_note(note.id) is None
        # Second delete should return False
        assert vault.delete(note.id) is False

    def test_list_notes_empty(self) -> None:
        from shadows.storage import Vault

        vault = Vault("pw")
        assert vault.list_notes() == []


class TestVaultPersistence:
    """Notes survive across vault instances."""

    def test_notes_persist(self) -> None:
        from shadows.storage import Vault

        vault1 = Vault("pw")
        vault1.create_note("Persistent", "I am still here")

        vault2 = Vault("pw")
        notes = vault2.list_notes()
        assert len(notes) == 1
        assert notes[0].title == "Persistent"


class TestCorruptVault:
    """Handling of corrupt vault files."""

    def test_corrupt_note_file_moved_aside(self) -> None:
        from shadows.storage import Vault, _VAULT_DIR

        vault = Vault("pw")
        note = vault.create_note("Good", "data")
        note_path = _VAULT_DIR / f"{note.id}.note.enc"

        # Corrupt the file
        note_path.write_text("not valid json at all")

        # List should skip the corrupt file
        notes = vault.list_notes()
        assert len(notes) == 0

        # The corrupt file should have been renamed
        corrupt_files = list(_VAULT_DIR.glob("*.corrupt"))
        assert len(corrupt_files) >= 1


class TestUtils:
    """Crypto helpers."""

    def test_derive_key_deterministic(self) -> None:
        from shadows.storage import _derive_key

        salt = os.urandom(32)
        k1 = _derive_key("password", salt)
        k2 = _derive_key("password", salt)
        assert k1 == k2

    def test_derive_key_different_salt(self) -> None:
        from shadows.storage import _derive_key

        k1 = _derive_key("password", os.urandom(32))
        k2 = _derive_key("password", os.urandom(32))
        assert k1 != k2

    def test_aes_roundtrip(self) -> None:
        from shadows.storage import _derive_key, _aes_encrypt, _aes_decrypt

        key = _derive_key("test", os.urandom(32))
        ct, nonce, tag = _aes_encrypt(key, "hello world")
        decrypted = _aes_decrypt(key, ct, nonce, tag)
        assert decrypted == "hello world"

    def test_aes_wrong_key_fails(self) -> None:
        from shadows.storage import _derive_key, _aes_encrypt, _aes_decrypt

        key1 = _derive_key("correct", os.urandom(32))
        key2 = _derive_key("wrong", os.urandom(32))
        ct, nonce, tag = _aes_encrypt(key1, "secret")
        with pytest.raises(ValueError, match="Decryption failed"):
            _aes_decrypt(key2, ct, nonce, tag)
