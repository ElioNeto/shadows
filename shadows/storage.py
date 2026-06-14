"""
Encrypted vault for notes and credentials.

Uses AES-256-GCM via the ``cryptography`` library (Fernet-like but with
additional authenticated data for integrity).  Each note is stored as an
individual encrypted file under ``~/.shadows/vault/``.

Schema
------
A vault file is a JSON structure with the following keys:

.. code-block:: json

    {
      "id":       "<uuid>",
      "title":    "<encrypted-bytes-base64>",
      "content":  "<encrypted-bytes-base64>",
      "nonce":    "<base64>",
      "tag":      "<base64>",
      "created":  "<iso-timestamp>",
      "updated":  "<iso-timestamp>"
    }

The *title* and *content* fields are encrypted separately so that the
title can be shown in a list without decrypting the full note body.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------
_VAULT_DIR = Path.home() / ".shadows" / "vault"
_KEY_FILE = Path.home() / ".shadows" / "master.key"
_SALT_FILE = Path.home() / ".shadows" / "salt.bin"

# Key derivation parameters
PBKDF2_ITERATIONS = 600_000
AES_KEY_SIZE = 32  # AES-256


# ===================================================================
#  Notes — domain model
# ===================================================================
@dataclass
class Note:
    """A single encrypted note."""

    id: str
    title: str
    content: str
    created: float  # unix timestamp
    updated: float  # unix timestamp

    @classmethod
    def create(cls, title: str = "", content: str = "") -> Note:
        now = time.time()
        return cls(
            id=str(uuid.uuid4()),
            title=title,
            content=content,
            created=now,
            updated=now,
        )

    def touch(self) -> None:
        self.updated = time.time()


# ===================================================================
#  Crypto helpers
# ===================================================================
def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit AES key from *password* and *salt* using PBKDF2."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=AES_KEY_SIZE,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def _aes_encrypt(key: bytes, plaintext: str) -> tuple[bytes, bytes, bytes]:
    """
    Encrypt *plaintext* with AES-256-GCM.

    Returns ``(ciphertext, nonce, tag)``.
    """
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit IV for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # GCM appends the 16-byte tag at the end of the ciphertext
    tag = ciphertext[-16:]
    ct = ciphertext[:-16]
    return ct, nonce, tag


def _aes_decrypt(key: bytes, ciphertext: bytes, nonce: bytes, tag: bytes) -> str:
    """Decrypt a value previously encrypted with ``_aes_encrypt``."""
    aesgcm = AESGCM(key)
    payload = ciphertext + tag
    try:
        plaintext = aesgcm.decrypt(nonce, payload, None)
    except InvalidTag:
        raise ValueError("Decryption failed — wrong password or corrupted data")
    return plaintext.decode("utf-8")


# ===================================================================
#  Vault
# ===================================================================
class Vault:
    """
    Manages an encrypted vault of notes stored as individual files.

    Usage
    -----
    >>> vault = Vault.open("my password")
    >>> note = vault.create_note("Shopping", "Milk, eggs, bread")
    >>> all_notes = vault.list_notes()
    >>> vault.delete(note.id)
    """

    FILE_EXT: ClassVar[str] = ".note.enc"

    def __init__(self, password: str) -> None:
        self._key: bytes
        self._password = password
        self._ensure_dirs()
        self._key = self._load_or_create_key(password)

    # ── public API ────────────────────────────────────────────────

    @staticmethod
    def exists() -> bool:
        """Return ``True`` if a vault has been initialised."""
        return _KEY_FILE.exists()

    @staticmethod
    def create(password: str) -> Vault:
        """Create a new vault (overwrites any existing key)."""
        if _KEY_FILE.exists():
            _KEY_FILE.unlink()
        if _SALT_FILE.exists():
            _SALT_FILE.unlink()
        return Vault(password)

    def list_notes(self) -> list[Note]:
        """Return all notes (titles decrypted, content empty)."""
        notes: list[Note] = []
        for path in sorted(_VAULT_DIR.glob(f"*{self.FILE_EXT}")):
            if path.name.startswith("."):
                continue
            try:
                note = self._load_note_meta(path)
                notes.append(note)
            except Exception as exc:
                logger.warning("Failed to load %s: %s", path.name, exc)
        return notes

    def get_note(self, note_id: str) -> Optional[Note]:
        """Load a full note (with decrypted content) by ID."""
        path = _VAULT_DIR / f"{note_id}{self.FILE_EXT}"
        if not path.exists():
            return None
        return self._load_note_full(path)

    def save_note(self, note: Note) -> None:
        """Encrypt and save a note (creates or updates)."""
        path = _VAULT_DIR / f"{note.id}{self.FILE_EXT}"
        self._write_note(path, note)

    def create_note(self, title: str = "", content: str = "") -> Note:
        """Create and persist a new note."""
        note = Note.create(title, content)
        self.save_note(note)
        return note

    def delete(self, note_id: str) -> bool:
        """Permanently delete a note.  Returns ``True`` if deleted."""
        path = _VAULT_DIR / f"{note_id}{self.FILE_EXT}"
        if path.exists():
            path.unlink()
            logger.info("Deleted note %s", note_id)
            return True
        return False

    def change_password(self, new_password: str) -> None:
        """Re-encrypt the vault key with a new password."""
        # Re-derive and re-store
        old_key = self._key
        salt = os.urandom(32)
        new_key = _derive_key(new_password, salt)
        # Re-encrypt the current key with the new password
        ct, nonce, tag = _aes_encrypt(new_key, base64.b64encode(old_key).decode())
        _KEY_FILE.write_text(json.dumps({
            "ct": base64.b64encode(ct).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "tag": base64.b64encode(tag).decode(),
            "salt": base64.b64encode(salt).decode(),
        }))
        self._key = new_key
        logger.info("Vault password changed")

    # ── internal helpers ──────────────────────────────────────────

    @staticmethod
    def _ensure_dirs() -> None:
        _VAULT_DIR.mkdir(parents=True, exist_ok=True)

    def _load_or_create_key(self, password: str) -> bytes:
        if not _KEY_FILE.exists():
            # Fresh vault
            salt = os.urandom(32)
            key = _derive_key(password, salt)
            # Store the derived key encrypted with itself as proof
            ct, nonce, tag = _aes_encrypt(key, base64.b64encode(key).decode())
            _KEY_FILE.write_text(json.dumps({
                "ct": base64.b64encode(ct).decode(),
                "nonce": base64.b64encode(nonce).decode(),
                "tag": base64.b64encode(tag).decode(),
                "salt": base64.b64encode(salt).decode(),
            }))
            logger.info("New vault key created")
            return key

        # Existing vault — derive key and verify
        data = json.loads(_KEY_FILE.read_text())
        salt = base64.b64decode(data["salt"])
        key = _derive_key(password, salt)
        # Verify by decrypting the proof
        try:
            _aes_decrypt(
                key,
                base64.b64decode(data["ct"]),
                base64.b64decode(data["nonce"]),
                base64.b64decode(data["tag"]),
            )
        except (InvalidTag, ValueError):
            raise ValueError("Incorrect master password")
        logger.info("Vault unlocked")
        return key

    def _encrypt_field(self, value: str) -> dict:
        ct, nonce, tag = _aes_encrypt(self._key, value)
        return {
            "ct": base64.b64encode(ct).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "tag": base64.b64encode(tag).decode(),
        }

    def _decrypt_field(self, data: dict) -> str:
        return _aes_decrypt(
            self._key,
            base64.b64decode(data["ct"]),
            base64.b64decode(data["nonce"]),
            base64.b64decode(data["tag"]),
        )

    def _write_note(self, path: Path, note: Note) -> None:
        payload = {
            "id": note.id,
            "title": self._encrypt_field(note.title),
            "content": self._encrypt_field(note.content),
            "created": note.created,
            "updated": note.updated,
        }
        path.write_text(json.dumps(payload, indent=2))

    def _load_note_meta(self, path: Path) -> Note:
        """Load note metadata only (title decrypted, content left encrypted)."""
        try:
            data = json.loads(path.read_text())
            return Note(
                id=data["id"],
                title=self._decrypt_field(data["title"]),
                content="",  # not decrypted yet
                created=data["created"],
                updated=data["updated"],
            )
        except (json.JSONDecodeError, KeyError, ValueError, OSError) as exc:
            logger.error("Corrupt vault file %s: %s", path.name, exc)
            # Move corrupt file aside so it doesn't block loading
            backup = path.with_suffix(path.suffix + ".corrupt")
            path.rename(backup)
            logger.info("Moved corrupt file to %s", backup)
            raise ValueError(f"Note file corrupted: {path.name}") from exc

    def _load_note_full(self, path: Path) -> Note:
        try:
            data = json.loads(path.read_text())
            return Note(
                id=data["id"],
                title=self._decrypt_field(data["title"]),
                content=self._decrypt_field(data["content"]),
                created=data["created"],
                updated=data["updated"],
            )
        except (json.JSONDecodeError, KeyError, ValueError, OSError) as exc:
            logger.error("Corrupt vault file %s: %s", path.name, exc)
            backup = path.with_suffix(path.suffix + ".corrupt")
            path.rename(backup)
            logger.info("Moved corrupt file to %s", backup)
            raise ValueError(f"Note file corrupted: {path.name}") from exc
