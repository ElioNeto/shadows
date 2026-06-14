"""
AI-powered features: real-time translation and intelligent note consultation.

Provides:
  • ``Translator``     — Translate note content between languages
  • ``AIAssistant``    — Query notes with natural language (chat / RAG)
  • ``Settings``       — Persist provider preferences and API keys

Supported AI providers
----------------------
  - **Ollama**  (default, free, local) — ``ollama pull llama3.2``
  - **OpenAI**  (GPT-4o / GPT-4o-mini) — requires ``OPENAI_API_KEY``
  - **Gemini**  (Google)                — requires ``GEMINI_API_KEY``

All provider calls are async-friendly but exposed via synchronous wrappers
suitable for use in PyQt5 slots (run in a thread / ``QThreadPool``).
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import ClassVar, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------
_SETTINGS_FILE = Path.home() / ".shadows" / "settings.json"
_DEFAULT_OLLAMA_URL = "http://localhost:11434"
_DEFAULT_OLLAMA_MODEL = "llama3.2"
_DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
_DEFAULT_GEMINI_MODEL = "gemini-2.0-flash-lite"

# Languages supported by the translation feature
SUPPORTED_LANGUAGES: dict[str, str] = {
    "pt-BR": "Português (Brasil)",
    "en-US": "English (US)",
    "en-GB": "English (UK)",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "it": "Italiano",
    "ja": "日本語",
    "zh-CN": "简体中文",
    "ko": "한국어",
    "ru": "Русский",
    "ar": "العربية",
    "nl": "Nederlands",
    "pl": "Polski",
    "sv": "Svenska",
    "pt-PT": "Português (Portugal)",
}


class AIProvider(str, Enum):
    """Supported AI backends."""

    OLLAMA = "ollama"
    OPENAI = "openai"
    GEMINI = "gemini"


# ===================================================================
#  Settings
# ===================================================================
@dataclass
class Settings:
    """Persistent user settings for AI features.

    Stored as JSON in ``~/.shadows/settings.json``.
    """

    provider: AIProvider = AIProvider.OLLAMA

    # Ollama
    ollama_url: str = _DEFAULT_OLLAMA_URL
    ollama_model: str = _DEFAULT_OLLAMA_MODEL

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = _DEFAULT_OPENAI_MODEL

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = _DEFAULT_GEMINI_MODEL

    # Translation defaults
    default_source_lang: str = "pt-BR"
    default_target_lang: str = "en-US"

    # UI
    show_ai_panel_on_start: bool = True

    # ── serialisation ─────────────────────────────────────────────

    def save(self) -> None:
        """Persist settings to disk."""
        _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Mask keys in logs but store them
        data = {
            "provider": self.provider.value,
            "ollama_url": self.ollama_url,
            "ollama_model": self.ollama_model,
            "openai_api_key": self.openai_api_key,
            "openai_model": self.openai_model,
            "gemini_api_key": self.gemini_api_key,
            "gemini_model": self.gemini_model,
            "default_source_lang": self.default_source_lang,
            "default_target_lang": self.default_target_lang,
            "show_ai_panel_on_start": self.show_ai_panel_on_start,
        }
        _SETTINGS_FILE.write_text(json.dumps(data, indent=2))
        logger.info("AI settings saved")

    @classmethod
    def load(cls) -> Settings:
        """Load settings from disk, returning defaults if missing."""
        if not _SETTINGS_FILE.exists():
            return cls()
        try:
            data = json.loads(_SETTINGS_FILE.read_text())
            provider = AIProvider(data.get("provider", AIProvider.OLLAMA.value))
            return cls(
                provider=provider,
                ollama_url=data.get("ollama_url", _DEFAULT_OLLAMA_URL),
                ollama_model=data.get("ollama_model", _DEFAULT_OLLAMA_MODEL),
                openai_api_key=data.get("openai_api_key", ""),
                openai_model=data.get("openai_model", _DEFAULT_OPENAI_MODEL),
                gemini_api_key=data.get("gemini_api_key", ""),
                gemini_model=data.get("gemini_model", _DEFAULT_GEMINI_MODEL),
                default_source_lang=data.get("default_source_lang", "pt-BR"),
                default_target_lang=data.get("default_target_lang", "en-US"),
                show_ai_panel_on_start=data.get("show_ai_panel_on_start", True),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.warning("Failed to load AI settings: %s", exc)
            return cls()


# ===================================================================
#  Provider helpers
# ===================================================================
def _call_ollama(
    url: str,
    model: str,
    messages: list[dict],
    *,
    timeout: int = 60,
) -> str:
    """Call Ollama's chat completion endpoint.

    Parameters
    ----------
    url : str
        Base URL of the Ollama server (e.g. ``http://localhost:11434``).
    model : str
        Model name (e.g. ``llama3.2``, ``mistral``).
    messages : list[dict]
        Chat messages in OpenAI-compatible format.
    timeout : int
        Request timeout in seconds.

    Returns
    -------
    str
        The model's response text.
    """
    import httpx

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(f"{url.rstrip('/')}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "").strip()
    except httpx.HTTPStatusError as exc:
        logger.error("Ollama HTTP error: %s", exc)
        raise RuntimeError(f"Ollama retornou erro {exc.response.status_code}") from exc
    except httpx.RequestError as exc:
        logger.error("Ollama connection error: %s", exc)
        raise RuntimeError(
            "Não foi possível conectar ao Ollama. "
            "Verifique se o servidor está rodando em " + url
        ) from exc


def _call_openai(
    api_key: str,
    model: str,
    messages: list[dict],
    *,
    timeout: int = 60,
) -> str:
    """Call OpenAI's chat completion endpoint.

    Parameters
    ----------
    api_key : str
        OpenAI API key.
    model : str
        Model name (e.g. ``gpt-4o-mini``).
    messages : list[dict]
        Chat messages in OpenAI format.
    timeout : int
        Request timeout in seconds.

    Returns
    -------
    str
        The model's response text.
    """
    import httpx

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except httpx.HTTPStatusError as exc:
        logger.error("OpenAI HTTP error: %s", exc)
        raise RuntimeError(f"OpenAI retornou erro {exc.response.status_code}") from exc
    except httpx.RequestError as exc:
        logger.error("OpenAI connection error: %s", exc)
        raise RuntimeError(
            "Não foi possível conectar à API OpenAI. "
            "Verifique sua conexão com a internet."
        ) from exc


def _call_gemini(
    api_key: str,
    model: str,
    messages: list[dict],
    *,
    timeout: int = 60,
) -> str:
    """Call Google Gemini's chat completion endpoint.

    Parameters
    ----------
    api_key : str
        Gemini API key.
    model : str
        Model name (e.g. ``gemini-2.0-flash-lite``).
    messages : list[dict]
        Chat messages in OpenAI-compatible format (converted internally).
    timeout : int
        Request timeout in seconds.

    Returns
    -------
    str
        The model's response text.
    """
    import httpx

    # Convert OpenAI-format messages to Gemini format
    gemini_contents = []
    system_instruction = None
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            system_instruction = content
        elif role == "user":
            gemini_contents.append({
                "role": "user",
                "parts": [{"text": content}],
            })
        elif role == "assistant":
            gemini_contents.append({
                "role": "model",
                "parts": [{"text": content}],
            })

    payload: dict = {"contents": gemini_contents}
    if system_instruction:
        payload["systemInstruction"] = {
            "role": "user",
            "parts": [{"text": system_instruction}],
        }

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return ""
            parts = candidates[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts).strip()
    except httpx.HTTPStatusError as exc:
        logger.error("Gemini HTTP error: %s", exc)
        raise RuntimeError(f"Gemini retornou erro {exc.response.status_code}") from exc
    except httpx.RequestError as exc:
        logger.error("Gemini connection error: %s", exc)
        raise RuntimeError(
            "Não foi possível conectar à API Gemini. "
            "Verifique sua conexão com a internet."
        ) from exc


# ===================================================================
#  Chat helper
# ===================================================================
def _chat_completion(
    settings: Settings,
    messages: list[dict],
    *,
    timeout: int = 60,
) -> str:
    """Route a chat completion request to the configured provider.

    Parameters
    ----------
    settings : Settings
        Current AI settings (provider, keys, model, …).
    messages : list[dict]
        Chat messages in OpenAI-compatible format.
    timeout : int
        Request timeout in seconds.

    Returns
    -------
    str
        The model's response text.
    """
    provider = settings.provider
    if provider == AIProvider.OLLAMA:
        return _call_ollama(settings.ollama_url, settings.ollama_model, messages, timeout=timeout)
    elif provider == AIProvider.OPENAI:
        return _call_openai(settings.openai_api_key, settings.openai_model, messages, timeout=timeout)
    elif provider == AIProvider.GEMINI:
        return _call_gemini(settings.gemini_api_key, settings.gemini_model, messages, timeout=timeout)
    else:
        raise ValueError(f"Unknown AI provider: {provider}")


# ===================================================================
#  Translator
# ===================================================================
@dataclass
class TranslationResult:
    """Result of a translation request."""

    source_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    duration_ms: float = 0.0


class Translator:
    """Translate note content between languages using the configured AI provider.

    Usage
    -----
    >>> translator = Translator(Settings.load())
    >>> result = translator.translate("Olá, mundo!", target_lang="en-US")
    >>> result.translated_text
    'Hello, world!'
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def translate(
        self,
        text: str,
        target_lang: str,
        source_lang: Optional[str] = None,
        *,
        preserve_formatting: bool = True,
    ) -> TranslationResult:
        """Translate *text* to *target_lang*.

        Parameters
        ----------
        text : str
            The text to translate.
        target_lang : str
            Target language code (e.g. ``"en-US"``, ``"pt-BR"``).
        source_lang : str or None
            Source language code. If ``None``, the provider auto-detects.
        preserve_formatting : bool
            If ``True``, the system prompt instructs the model to preserve
            Markdown, line breaks, and code blocks.

        Returns
        -------
        TranslationResult
            The translation result with metadata.
        """
        t0 = time.time()
        source_lang_name: str = ""
        if source_lang:
            source_lang_name = SUPPORTED_LANGUAGES.get(source_lang, source_lang)
        target_lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        system_prompt = (
            f"Você é um tradutor profissional. Traduza o texto fornecido "
            f"de {'{' + source_lang_name + '}' if source_lang else 'qualquer idioma'} "
            f"para {target_lang_name}.\n"
            f"Responda APENAS com o texto traduzido, sem explicações, sem comentários.\n"
            f"NÃO adicione frases como 'Aqui está a tradução' ou 'Em português'.\n"
        )
        if preserve_formatting:
            system_prompt += (
                "Preserve toda a formatação original: Markdown, quebras de linha, "
                "blocos de código, listas, e espaçamento.\n"
            )

        user_message = f"Traduza o seguinte texto:\n\n{text}"

        try:
            translated = _chat_completion(
                self._settings,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
        except RuntimeError as exc:
            logger.error("Translation failed: %s", exc)
            raise

        duration = (time.time() - t0) * 1000

        return TranslationResult(
            source_text=text,
            translated_text=translated,
            source_lang=source_lang or "auto",
            target_lang=target_lang,
            duration_ms=duration,
        )


# ===================================================================
#  AI Assistant (chat / RAG over notes)
# ===================================================================
@dataclass
class AssistantMessage:
    """A single message in the assistant conversation."""

    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: float = field(default_factory=time.time)


class AIAssistant:
    """Conversational assistant that can answer questions about notes.

    Uses the configured AI provider. When notes are provided as context,
    the assistant performs a form of Retrieval-Augmented Generation (RAG)
    by including relevant note content in the system prompt.

    Usage
    -----
    >>> assistant = AIAssistant(Settings.load())
    >>> assistant.add_note_context("Meeting notes: Q4 plans...")
    >>> reply = assistant.chat("What were the Q4 plans?")
    >>> reply
    'The Q4 plans included...'
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._history: list[AssistantMessage] = []
        self._note_context: list[str] = []
        self._system_prompt = self._build_system_prompt()

    # ── public API ────────────────────────────────────────────────

    @property
    def history(self) -> list[AssistantMessage]:
        """Return the full conversation history."""
        return list(self._history)

    def clear_history(self) -> None:
        """Clear conversation history (keeps note context)."""
        self._history.clear()

    def add_note_context(self, note_text: str) -> None:
        """Add a note's content as context for future queries.

        Parameters
        ----------
        note_text : str
            The full text (title + content) of a note.
        """
        if note_text.strip():
            self._note_context.append(note_text.strip())

    def set_note_context(self, notes: list[str]) -> None:
        """Replace note context with a new set of notes.

        Parameters
        ----------
        notes : list[str]
            List of note texts (each should include title + content).
        """
        self._note_context = [n.strip() for n in notes if n.strip()]

    def clear_note_context(self) -> None:
        """Remove all note context."""
        self._note_context.clear()

    def chat(self, message: str) -> str:
        """Send a message and get the assistant's reply.

        Parameters
        ----------
        message : str
            The user's message / question.

        Returns
        -------
        str
            The assistant's reply text.
        """
        messages = self._build_messages(message)
        try:
            reply = _chat_completion(self._settings, messages)
        except RuntimeError as exc:
            logger.error("Assistant query failed: %s", exc)
            raise

        self._history.append(AssistantMessage(role="user", content=message))
        self._history.append(AssistantMessage(role="assistant", content=reply))

        return reply

    # ── internals ──────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        return (
            "Você é um assistente pessoal de notas e produtividade chamado Shadows AI. "
            "Você ajuda o usuário a organizar, consultar e refletir sobre suas notas.\n\n"
            "Diretrizes:\n"
            "- Responda em português (pt-BR) por padrão, a menos que o usuário pergunte em outro idioma.\n"
            "- Seja conciso e direto.\n"
            "- Se o contexto das notas for fornecido, USE-O para responder.\n"
            "- Se não souber a resposta, diga honestamente.\n"
            "- NÃO invente informações.\n"
            "- NÃO peça para o usuário consultar fontes externas — use apenas as notas fornecidas.\n"
            "- Se o usuário pedir para traduzir algo, use o tradutor interno.\n"
            "- Formate respostas com Markdown simples quando apropriado.\n"
        )

    def _build_messages(self, user_message: str) -> list[dict]:
        """Build the full message list including system prompt, context, and history.

        Parameters
        ----------
        user_message : str
            The user's current message.

        Returns
        -------
        list[dict]
            Messages in OpenAI-compatible format.
        """
        messages: list[dict] = [
            {"role": "system", "content": self._build_system_prompt_with_context()},
        ]

        # Include recent history (last 10 turns to avoid token overflow)
        for msg in self._history[-10:]:
            role = "assistant" if msg.role == "assistant" else "user"
            messages.append({"role": role, "content": msg.content})

        messages.append({"role": "user", "content": user_message})
        return messages

    def _build_system_prompt_with_context(self) -> str:
        """Build system prompt augmented with current note context."""
        prompt = self._system_prompt

        if self._note_context:
            # Truncate context to avoid excessive token usage (max ~8000 chars)
            context_text = "\n\n---\n".join(self._note_context)
            if len(context_text) > 8000:
                context_text = context_text[:8000] + "\n\n[... contexto truncado ...]"

            prompt += (
                "\n\n=== NOTAS DO USUÁRIO (contexto) ===\n"
                f"{context_text}\n"
                "=== FIM DAS NOTAS ===\n\n"
                "Use as notas acima como contexto principal para responder "
                "às perguntas do usuário. Se a pergunta não estiver relacionada "
                "às notas, responda com base no seu conhecimento geral."
            )

        return prompt
