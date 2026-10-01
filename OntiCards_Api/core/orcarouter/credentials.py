"""Credential seam for OrcaRouter.

Both authentication choices — a pasted ``sk-orca-…`` API key and an OAuth 2.0 + PKCE login —
are *adapters on the same seam*.  They return one identical :class:`Credential` (a normal
OrcaRouter API key); the provider request path, the model catalog and every AI entry point only
ever consume that object, so no part of the codebase duplicates authentication logic.

A PKCE-issued key is a **durable API key, not a refresh token**.  There is no refresh endpoint and
this module never attempts a refresh grant: a relay ``401`` marks the exact credential generation
that made the rejected request as ``needs_reauth`` and stops, until a new login succeeds.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field, replace
from typing import Callable, Dict, Optional

STATE_ACTIVE = "active"
STATE_NEEDS_REAUTH = "needs_reauth"

SOURCE_API_KEY = "api_key"
SOURCE_PKCE = "pkce"

PROVIDER = "orcarouter"

_KEY_PATTERN = re.compile(r"sk-orca-[A-Za-z0-9._\-]{8,}")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|apikey|authorization|token|secret|password|code_verifier|verifier)"
    r"(\s*[:=]\s*)(\"?)([^\s\"',;}]+)"
)


class CredentialError(RuntimeError):
    """Credential could not be produced or is no longer usable."""


def mask_api_key(key: Optional[str]) -> str:
    """Return a display-safe placeholder.  Never returns any part of a real key."""
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:7] + "…" + "*" * 4


def redact(text: str) -> str:
    """Replace anything that looks like an ``sk-orca-…`` key with a placeholder."""
    return _KEY_PATTERN.sub(lambda m: mask_api_key(m.group(0)), text or "")


def redact_secrets(text: str) -> str:
    """Redact API keys *and* ``key=value`` shaped secrets (verifiers, tokens, passwords)."""
    redacted = redact(text)
    return _SECRET_ASSIGNMENT.sub(lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}<redacted>", redacted)


@dataclass(frozen=True)
class Credential:
    """A usable OrcaRouter credential, independent of how it was obtained."""

    api_key: str
    source: str = SOURCE_API_KEY
    provider: str = PROVIDER
    scope: str = "api"
    account_id: Optional[str] = None
    generation: int = 0
    state: str = STATE_ACTIVE
    created_at: float = field(default_factory=time.time)

    @property
    def is_usable(self) -> bool:
        return bool(self.api_key) and self.state == STATE_ACTIVE

    @property
    def masked_key(self) -> str:
        return mask_api_key(self.api_key)

    def __repr__(self) -> str:  # pragma: no cover - defensive, asserted in tests
        return (
            f"Credential(provider={self.provider!r}, source={self.source!r}, "
            f"api_key={self.masked_key!r}, scope={self.scope!r}, generation={self.generation}, "
            f"state={self.state!r})"
        )


class CredentialStorage:
    """Minimal storage contract.  The Flask adapter persists to the existing ``model_config`` row."""

    def load(self) -> Optional[Credential]:  # pragma: no cover - interface
        raise NotImplementedError

    def save(self, credential: Credential) -> Credential:  # pragma: no cover - interface
        raise NotImplementedError

    def clear(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def mark_needs_reauth(self, provider: str, source: str, generation: int) -> bool:  # pragma: no cover
        raise NotImplementedError


class InMemoryCredentialStorage(CredentialStorage):
    """Generation-safe credential store used by tests and as the reference implementation.

    ``save`` always increments the generation, so a credential has a monotonically increasing
    identity.  ``mark_needs_reauth`` is a compare-and-set: it only affects the credential whose
    ``(provider, source, generation)`` matches exactly.  A late failure reported for an old
    generation therefore cannot mark a freshly re-authorized credential as broken.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._credential: Optional[Credential] = None
        self._generation = 0

    def load(self) -> Optional[Credential]:
        with self._lock:
            return self._credential

    def save(self, credential: Credential) -> Credential:
        with self._lock:
            self._generation += 1
            stored = replace(credential, generation=self._generation, state=STATE_ACTIVE)
            self._credential = stored
            return stored

    def clear(self) -> None:
        with self._lock:
            self._credential = None

    def mark_needs_reauth(self, provider: str, source: str, generation: int) -> bool:
        with self._lock:
            current = self._credential
            if current is None:
                return False
            if (
                current.provider != provider
                or current.source != source
                or current.generation != generation
            ):
                return False
            self._credential = replace(current, state=STATE_NEEDS_REAUTH)
            return True


def classify_relay_status(status_code: int) -> str:
    """Map a relay/inference HTTP status onto an action.

    ``401`` is terminal: re-authenticate.  It is never a refresh trigger — an OrcaRouter key is
    durable and has no refresh grant.
    """
    if status_code == 401:
        return "needs_reauth"
    if status_code == 429:
        return "rate_limited"
    if 400 <= status_code < 500:
        return "client_error"
    if status_code >= 500:
        return "server_error"
    return "ok"


def _validate_scope(scope: Optional[str]) -> str:
    granted = (scope or "api").strip() or "api"
    if granted not in ("api", "connector"):
        raise CredentialError(f"unexpected authorization scope {granted!r}")
    return granted


class _BaseCredentialProvider:
    """Shared behaviour for the two authentication adapters."""

    source = ""

    def __init__(self, storage: CredentialStorage) -> None:
        self._storage = storage

    def current(self) -> Optional[Credential]:
        return self._storage.load()

    def clear(self) -> None:
        self._storage.clear()

    def is_usable(self) -> bool:
        credential = self._storage.load()
        return bool(credential and credential.is_usable and credential.source == self.source)

    def handle_relay_status(self, status_code: int) -> str:
        """Apply relay status semantics to the credential this provider owns.

        Marking is generation-safe: only the credential that is *currently* stored and still
        matches its generation is transitioned, so an in-flight request issued under an older
        generation cannot poison a newer credential.
        """
        action = classify_relay_status(status_code)
        if action == "needs_reauth":
            credential = self._storage.load()
            if credential is not None:
                self._storage.mark_needs_reauth(
                    credential.provider, credential.source, credential.generation
                )
        return action


class ApiKeyCredentialProvider(_BaseCredentialProvider):
    """Adapter #1 — the user pastes an existing ``sk-orca-…`` key.

    The key is stored wherever the project already keeps provider secrets; nothing here invents a
    second credential store.  This path never opens a browser and never starts a PKCE login.
    """

    source = SOURCE_API_KEY

    def acquire(self, raw_key: str, account_id: Optional[str] = None) -> Credential:
        key = (raw_key or "").strip()
        if not key:
            raise CredentialError("empty OrcaRouter API key")
        if not key.startswith("sk-orca-"):
            # A prefix check only catches obvious input mistakes; it is not proof of validity.
            raise CredentialError("an OrcaRouter API key starts with 'sk-orca-'")
        return self._storage.save(
            Credential(api_key=key, source=self.source, account_id=account_id)
        )


class PkceCredentialProvider(_BaseCredentialProvider):
    """Adapter #2 — OAuth 2.0 + PKCE login issues the same kind of key.

    The exchange response is the only input; :meth:`commit` validates the *granted* scope
    (not the requested one) and persists the resulting durable key.
    """

    source = SOURCE_PKCE

    def commit(
        self,
        api_key: str,
        granted_scope: Optional[str],
        account_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Credential:
        key = (api_key or "").strip()
        if not key:
            raise CredentialError("authorization exchange returned no key")
        scope = _validate_scope(granted_scope)
        return self._storage.save(
            Credential(
                api_key=key,
                source=self.source,
                scope=scope,
                account_id=account_id or user_id,
            )
        )


def provider_for_source(storage: CredentialStorage, source: str) -> _BaseCredentialProvider:
    """Return the adapter that owns *source* (``api_key`` or ``pkce``)."""
    if source == SOURCE_PKCE:
        return PkceCredentialProvider(storage)
    if source == SOURCE_API_KEY:
        return ApiKeyCredentialProvider(storage)
    raise CredentialError(f"unknown credential source {source!r}")
