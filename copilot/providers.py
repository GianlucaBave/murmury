"""The AI services Murmury can answer through, including local OpenAI-compatible servers.

Anthropic is reached through its own SDK (prompt caching, the separate question check). Every other service
speaks the OpenAI chat format at its own address, so one client covers them all (openai_copilot.py).

The model list always comes from the service itself, so a new model shows up without an app update. Which
model to suggest comes from models.json on the site (RECOMMENDED_URL), read at most once a day, with the
patterns below as the fallback when the site cannot be reached.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass, field, replace
from urllib.parse import urlsplit, urlunsplit

RECOMMENDED_URL = "https://murmury.pages.dev/models.json"


@dataclass(frozen=True)
class Provider:
    id: str
    name: str
    base_url: str | None                 # None: Anthropic's own API
    key_hint: str                        # what a key looks like, for the placeholder
    key_url: str                         # where to create a key
    env: tuple[str, ...] = ()            # environment variables that may hold the key
    free: str = ""                       # what the free tier costs you, shown next to the connection
    prefer: tuple[str, ...] = ()         # fallback suggestion: patterns, best first
    hide: tuple[str, ...] = ()           # models that cannot write a chat answer
    options: dict = field(default_factory=dict)  # extra request fields this service accepts
    key_required: bool = True            # False: a server on this Mac (Ollama, LM Studio), no key


COMMON_HIDE = (r"embed", r"whisper", r"tts", r"transcribe", r"audio", r"realtime", r"image", r"dall-e",
               r"moderation", r"guard", r"rerank", r"ocr", r"search", r"vision", r"imagen", r"veo", r"live")

# local servers often start with a short context: documents longer than it are cut without a warning
LOCAL_HINT = "a server you run yourself: set a long context length in it so your documents fit"
LOCAL_PREFER = (r"llama", r"qwen", r"mistral", r"gemma")

PROVIDERS: list[Provider] = [
    Provider("anthropic", "Anthropic · Claude", None, "sk-ant-…", "https://console.anthropic.com/settings/keys",
             env=("MURMURY_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
             prefer=(r"claude-sonnet-\d", r"claude-haiku-\d")),
    Provider("openai", "OpenAI", "https://api.openai.com/v1", "sk-…", "https://platform.openai.com/api-keys",
             env=("OPENAI_API_KEY",), prefer=(r"gpt-\d+(\.\d+)?-mini$", r"gpt-\d+(\.\d+)?$"),
             hide=COMMON_HIDE + (r"^o\d", r"codex", r"instruct", r"babbage", r"davinci", r"gpt-3"),
             options={"prompt_cache_key": "murmury"}),
    Provider("gemini", "Google · Gemini", "https://generativelanguage.googleapis.com/v1beta/openai/", "AIza…",
             "https://aistudio.google.com/apikey", env=("GEMINI_API_KEY", "GOOGLE_API_KEY"),
             free="free tier: Google may use what you send to improve its products",
             prefer=(r"gemini-[\d.]+-flash$", r"gemini-[\d.]+-flash", r"gemini"),
             hide=COMMON_HIDE + (r"aqa", r"gemma", r"learnlm", r"thinking", r"exp")),
    Provider("xai", "xAI · Grok", "https://api.x.ai/v1", "xai-…", "https://console.x.ai",
             env=("XAI_API_KEY",), prefer=(r"grok-[\d.]+-fast", r"grok-\d")),
    Provider("groq", "Groq", "https://api.groq.com/openai/v1", "gsk_…", "https://console.groq.com/keys",
             env=("GROQ_API_KEY",), free="free tier with rate limits",
             prefer=(r"openai/gpt-oss-120b", r"llama-3\.3-70b", r"llama"),
             hide=COMMON_HIDE + (r"playai", r"distil", r"compound", r"allam")),
    Provider("mistral", "Mistral", "https://api.mistral.ai/v1", "your Mistral key", "https://console.mistral.ai/api-keys",
             env=("MISTRAL_API_KEY",), prefer=(r"mistral-medium-latest", r"mistral-small-latest", r"mistral-large"),
             hide=COMMON_HIDE + (r"codestral", r"devstral", r"voxtral", r"pixtral")),
    Provider("openrouter", "OpenRouter · many models", "https://openrouter.ai/api/v1", "sk-or-…",
             "https://openrouter.ai/keys", env=("OPENROUTER_API_KEY",),
             free="models ending in :free cost nothing, are rate-limited, and their hosts may log what you send",
             prefer=(r"^anthropic/claude-sonnet", r"^openai/gpt-[\d.]+-mini$", r"^google/gemini-[\d.]+-flash$", r":free$"),
             hide=COMMON_HIDE),
    Provider("ollama", "Ollama · local", "http://localhost:11434/v1", "No key required", "",
             key_required=False, free=LOCAL_HINT, prefer=LOCAL_PREFER, hide=COMMON_HIDE),
    Provider("lm-studio", "LM Studio · local", "http://localhost:1234/v1", "No key required", "",
             key_required=False, free=LOCAL_HINT, prefer=LOCAL_PREFER, hide=COMMON_HIDE),
]
BY_ID = {p.id: p for p in PROVIDERS}
DEFAULT = "anthropic"


def provider(provider_id: str | None) -> Provider:
    return BY_ID.get(provider_id or DEFAULT, BY_ID[DEFAULT])


# local servers: Ollama or LM Studio, on this Mac by default, or on another computer you trust
ADDRESS_ERROR = "Use an address that starts with http:// or https://, like http://mac-mini.local:11434"


def normalize_address(text: str | None, default: str) -> str:
    """The base address to talk to. Empty gives the default (localhost). Only http:// and https:// are accepted;
    a trailing slash is dropped and /v1 is added when missing, so http://mac-mini.local:11434 and
    http://mac-mini.local:11434/v1/ both work. Raises ValueError for anything else."""
    text = (text or "").strip()
    if not text:
        return default
    parts = urlsplit(text)
    try:
        valid = (parts.scheme.lower() in ("http", "https") and bool(parts.hostname)
                 and not any(c.isspace() for c in text))
        parts.port  # a port that is not a number raises ValueError
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(ADDRESS_ERROR)
    path = parts.path.rstrip("/")
    if not path.endswith("/v1"):
        path += "/v1"
    return urlunsplit((parts.scheme.lower(), parts.netloc, path, "", ""))


def with_address(p: Provider, address: str | None) -> Provider:
    """The same service at another address. Only the local servers take one; for the others it is ignored."""
    if p.key_required or p.base_url is None:
        return p
    return replace(p, base_url=normalize_address(address, p.base_url))


# keys: the environment first, then the Keychain (saved on the setup screen)
KEYCHAIN_SERVICE = "Murmury"


def _account(p: Provider) -> str:
    return f"{p.id}-api-key"


_keychain_cache: dict[str, str | None] = {}  # one Keychain read per service per launch: each read can ask macOS


def api_key(provider_id: str) -> tuple[str | None, str]:
    """The key for this service and where it came from."""
    p = provider(provider_id)
    if not p.key_required:
        return None, ""
    for name in p.env:
        if os.environ.get(name):
            return os.environ[name], name
    if p.id in _keychain_cache:
        stored = _keychain_cache[p.id]
        return (stored, "Keychain") if stored else (None, "")
    try:
        import keyring
        stored = keyring.get_password(KEYCHAIN_SERVICE, _account(p))
        if not stored and p.id == "anthropic":  # saved under the app's earlier name
            stored = keyring.get_password("call-copilot", "anthropic-api-key")
    except Exception:
        stored = None
    _keychain_cache[p.id] = stored
    return (stored, "Keychain") if stored else (None, "")


def save_api_key(provider_id: str, key: str | None) -> None:
    import keyring
    account = _account(provider(provider_id))
    _keychain_cache[provider(provider_id).id] = key or None
    if key:
        keyring.set_password(KEYCHAIN_SERVICE, account, key)
    else:
        try:
            keyring.delete_password(KEYCHAIN_SERVICE, account)
        except Exception:
            pass


# models
def list_models(provider_id: str, key: str | None = None, address: str | None = None) -> list[str]:
    """List chat models exposed by the provider; local OpenAI-compatible servers need no key and may
    be reached at another address."""
    p = with_address(provider(provider_id), address)
    if p.base_url is None:
        import anthropic
        ids = [m.id for m in anthropic.Anthropic(api_key=key).models.list(limit=100)]
    else:
        from openai import OpenAI
        ids = [m.id for m in OpenAI(api_key=key or "local", base_url=p.base_url, timeout=20).models.list()]
    ids = [i.removeprefix("models/") for i in ids]  # Gemini names them models/<id>
    return sorted({i for i in ids if not any(re.search(h, i) for h in p.hide)})


_recommended: tuple[float, dict] = (0.0, {})


def recommended() -> dict[str, list[str]]:
    """{provider id: [model ids or patterns, best first]} from the site, at most one fetch a day."""
    global _recommended
    fetched, data = _recommended
    if time.time() - fetched < 86400:
        return data
    try:
        request = urllib.request.Request(RECOMMENDED_URL, headers={"User-Agent": "Murmury"})  # the site blocks Python's default
        with urllib.request.urlopen(request, timeout=3) as response:
            data = json.load(response).get("recommended", {})
    except Exception:
        data = {}
    _recommended = (time.time(), data)
    return data


def _version(model_id: str) -> tuple:
    """Numbers in a model id, for 'newest first' (claude-sonnet-5-5 > claude-sonnet-4-6)."""
    return tuple(int(n) for n in re.findall(r"\d+", model_id) if len(n) < 8)  # not the date in ...-20250929


def suggest(provider_id: str, models: list[str]) -> str | None:
    """The model to preselect: the site's recommendation if the key has it, else the newest model that
    matches the built-in preferences, else the first one."""
    if not models:
        return None
    p = provider(provider_id)
    for wanted in (recommended().get(p.id, []) if p.key_required else []):
        if wanted in models:
            return wanted
        matches = [m for m in models if re.search(wanted, m)]
        if matches:
            return max(matches, key=_version)
    for pattern in p.prefer:
        matches = [m for m in models if re.search(pattern, m)]
        if matches:
            return max(matches, key=_version)
    return models[0]
