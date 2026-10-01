"""OAuth 2.0 + PKCE connect flow (Flow B — out-of-band code).

Flow choice is documented in ``integration-map.md``: OntiCards is self-hosted software whose
install address differs on every deployment, and the consent screen is opened in the
*administrator's* browser, which is frequently not the machine running the API container.  A
loopback listener inside that container would be unreachable, so the out-of-band flow is the
correct shape; there is no callback server the host does not otherwise need.

Every property the protocol depends on is enforced here:

* a fresh 32-byte verifier and 16-byte state from :mod:`secrets` for **every** attempt;
* ``code_challenge = base64url(sha256(verifier))`` with no padding, S256 always;
* the verifier is never placed in a URL, never serialised into any response the browser receives
  and is redacted from every error message;
* state is compared with :func:`hmac.compare_digest` when it is presented;
* exchange targets the auth origin only (never the inference origin);
* denial, state mismatch, expiry, code reuse, 400/403/429 and transport failures all terminate
  the session safely with an actionable message — no hung poll and no hot loop.

The project runs gunicorn with more than one worker, so sessions are held in a pluggable
:class:`SessionStore`; the Flask adapter backs it with the project's existing ``system_configs``
table.  Either way the verifier stays on the server.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.orcarouter.bases import OrcaRouterBases
from core.orcarouter.credentials import (
    Credential,
    CredentialError,
    PkceCredentialProvider,
    redact_secrets,
)

#: Auth codes are single-use with a 10 minute TTL; keep our own deadline slightly under it.
DEFAULT_SESSION_TTL = 600
#: Bound the number of simultaneously-pending authorizations held.
DEFAULT_MAX_SESSIONS = 16
DEFAULT_TIMEOUT = 30.0

STATUS_PENDING = "pending"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"
STATUS_EXPIRED = "expired"

#: Injection point so tests can drive a local fake authorization server.
PostJson = Callable[[str, Dict[str, object], float], "tuple[int, object]"]


class PkceFlowError(RuntimeError):
    """A terminal, user-actionable failure of the PKCE flow."""

    def __init__(self, reason: str, message: str, status: Optional[int] = None) -> None:
        super().__init__(redact_secrets(message))
        self.reason = reason
        self.status = status


class InvalidStateError(PkceFlowError):
    def __init__(self, message: str = "state mismatch") -> None:
        super().__init__("state_mismatch", message)


def b64url(raw: bytes) -> str:
    """Base64url without padding — the encoding the OrcaRouter endpoints expect."""
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def generate_verifier() -> str:
    """A fresh high-entropy verifier.  Must never be logged, printed or put in a URL."""
    return b64url(secrets.token_bytes(32))


def challenge_for(verifier: str) -> str:
    """``base64url(sha256(verifier))`` with no padding."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return b64url(digest)


def generate_state() -> str:
    return b64url(secrets.token_bytes(16))


def build_authorize_url(bases: OrcaRouterBases, challenge: str, state: str, app_name: str) -> str:
    """Build the Flow B authorize URL.

    ``callback_url=oob`` is spelled out rather than omitted so the mode is asked for rather than
    guessed at, and ``code_challenge_method=S256`` is mandatory for a displayed code.
    """
    from urllib.parse import urlencode

    params = {
        "callback_url": "oob",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "app_name": app_name,
        "scope": "api",
    }
    return f"{bases.authorize_url}?{urlencode(params)}"


def post_json_urllib(url: str, payload: Dict[str, object], timeout: float) -> "tuple[int, object]":
    """Default transport.  Reads the body even on an error status so the caller can branch on it."""
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https origins
            raw = response.read().decode("utf-8", "replace")
            return response.status, _loads(raw)
    except HTTPError as exc:  # 4xx/5xx are expected control flow, not crashes
        raw = exc.read().decode("utf-8", "replace")
        return exc.code, _loads(raw)


def _loads(raw: str) -> object:
    try:
        return json.loads(raw) if raw else {}
    except ValueError:
        return {"raw": raw[:500]}


@dataclass
class ConnectSession:
    """A pending authorization attempt.  ``verifier`` is server-side only."""

    id: str
    verifier: str
    state: str
    authorize_url: str
    generation: int
    created_at: float
    expires_at: float
    status: str = STATUS_PENDING
    credential: Optional[Credential] = None
    error_reason: Optional[str] = None
    error_message: Optional[str] = None

    def public(self) -> Dict[str, object]:
        """Serialisable view for the browser — never contains the verifier or the state."""
        return {
            "session_id": self.id,
            "authorize_url": self.authorize_url,
            "status": self.status,
            "generation": self.generation,
            "expires_in": max(0, int(self.expires_at - time.time())),
            "error_reason": self.error_reason,
            "error_message": self.error_message,
            "source": "pkce",
        }

    def to_record(self) -> Dict[str, object]:
        """Full record **including the verifier** — server-side persistence only."""
        return {
            "id": self.id,
            "verifier": self.verifier,
            "state": self.state,
            "authorize_url": self.authorize_url,
            "generation": self.generation,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "status": self.status,
            "error_reason": self.error_reason,
            "error_message": self.error_message,
        }

    @classmethod
    def from_record(cls, record: Dict[str, object]) -> "ConnectSession":
        return cls(
            id=str(record.get("id") or ""),
            verifier=str(record.get("verifier") or ""),
            state=str(record.get("state") or ""),
            authorize_url=str(record.get("authorize_url") or ""),
            generation=int(record.get("generation") or 0),
            created_at=float(record.get("created_at") or 0.0),
            expires_at=float(record.get("expires_at") or 0.0),
            status=str(record.get("status") or STATUS_PENDING),
            error_reason=record.get("error_reason"),
            error_message=record.get("error_message"),
        )

    def __repr__(self) -> str:  # pragma: no cover - defensive, asserted in tests
        return (
            f"ConnectSession(id={self.id!r}, status={self.status!r}, generation={self.generation}, "
            f"verifier=<redacted>, state=<redacted>)"
        )


class SessionStore:
    """Where pending attempts live.  Swap in the Flask/DB implementation for multi-worker runs."""

    def put(self, session: ConnectSession) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def get(self, session_id: str) -> Optional[ConnectSession]:  # pragma: no cover - interface
        raise NotImplementedError

    def items(self) -> List[ConnectSession]:  # pragma: no cover - interface
        raise NotImplementedError

    def delete(self, session_id: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def generation(self) -> int:  # pragma: no cover - interface
        raise NotImplementedError

    def set_generation(self, value: int) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class InMemorySessionStore(SessionStore):
    """Thread-safe in-process store.  Used by tests and by single-worker deployments."""

    def __init__(self, generation: int = 0) -> None:
        self._lock = threading.RLock()
        self._sessions: Dict[str, ConnectSession] = {}
        self._generation = generation

    def put(self, session: ConnectSession) -> None:
        with self._lock:
            self._sessions[session.id] = session

    def get(self, session_id: str) -> Optional[ConnectSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def items(self) -> List[ConnectSession]:
        with self._lock:
            return list(self._sessions.values())

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def generation(self) -> int:
        with self._lock:
            return self._generation

    def set_generation(self, value: int) -> None:
        with self._lock:
            self._generation = value


class ConnectSessionManager:
    """Single-flight, generation-guarded PKCE session manager.

    One outstanding *current* attempt keeps the 'login already in progress' lock honest; starting
    a new attempt invalidates the previous generation so a late exchange response can never
    overwrite newer credentials.
    """

    def __init__(
        self,
        bases: OrcaRouterBases,
        provider: PkceCredentialProvider,
        store: Optional[SessionStore] = None,
        app_name: str = "OntiCards",
        ttl: int = DEFAULT_SESSION_TTL,
        max_sessions: int = DEFAULT_MAX_SESSIONS,
        post: Optional[PostJson] = None,
        timeout: float = DEFAULT_TIMEOUT,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._bases = bases
        self._provider = provider
        self._store = store if store is not None else InMemorySessionStore()
        self._app_name = app_name
        self._ttl = ttl
        self._max_sessions = max_sessions
        self._post = post or post_json_urllib
        self._timeout = timeout
        self._clock = clock
        self._lock = threading.RLock()

    # ---------------------------------------------------------------- lifecycle

    def start(self) -> ConnectSession:
        """Begin a new attempt, invalidating any previous generation."""
        with self._lock:
            generation = self._store.generation() + 1
            self._store.set_generation(generation)
            now = self._clock()
            verifier = generate_verifier()
            state = generate_state()
            session_id = secrets.token_hex(16)
            session = ConnectSession(
                id=session_id,
                verifier=verifier,
                state=state,
                authorize_url=build_authorize_url(
                    self._bases, challenge_for(verifier), state, self._app_name
                ),
                generation=generation,
                created_at=now,
                expires_at=now + self._ttl,
            )
            self._invalidate_except(session_id, "superseded")
            self._store.put(session)
            self._evict()
            return session

    def get(self, session_id: str) -> Optional[ConnectSession]:
        with self._lock:
            session = self._store.get(session_id)
            if session is None:
                return None
            if self._expire(session):
                self._store.put(session)
            return session

    def cancel(self, session_id: str, reason: str = "cancelled") -> bool:
        """Explicit cancellation, modal close, provider switch, reload and ``pagehide`` land here.

        Returns ``True`` only when a still-pending attempt was actually released, so the UI can
        tell "cancelled now" from "already finished".
        """
        with self._lock:
            session = self._store.get(session_id)
            if session is None:
                return False
            if session.status != STATUS_PENDING:
                return False
            session.status = STATUS_CANCELLED if reason == "cancelled" else STATUS_FAILED
            session.error_reason = reason
            session.error_message = "authorization cancelled"
            session.verifier = ""  # drop the secret as soon as the attempt is dead
            self._store.put(session)
            return True

    def cancel_all(self, reason: str = "cancelled") -> int:
        with self._lock:
            return sum(1 for session in self._store.items() if self.cancel(session.id, reason))

    def submit_code(self, session_id: str, code: str, state: Optional[str] = None) -> Credential:
        """Exchange the pasted code and persist the resulting durable key.

        Raises :class:`PkceFlowError` on every terminal failure; the session is closed either way,
        so a code can never be redeemed twice through this manager.
        """
        with self._lock:
            session = self._store.get(session_id)
            if session is None:
                raise PkceFlowError("unknown_session", "this authorization attempt no longer exists")
            if self._expire(session):
                self._store.put(session)
            if session.status != STATUS_PENDING:
                raise PkceFlowError(
                    "session_closed",
                    f"this authorization attempt already ended ({session.status})",
                )
            if state is not None and not hmac.compare_digest(session.state, state):
                session.status = STATUS_FAILED
                session.error_reason = "state_mismatch"
                session.error_message = "state mismatch"
                session.verifier = ""
                self._store.put(session)
                raise InvalidStateError()

            verifier = session.verifier
            code_value = (code or "").strip()
            if not code_value:
                raise PkceFlowError("empty_code", "no authorization code was provided")

        # Network I/O happens outside the lock so a slow exchange cannot block status polling.
        try:
            status, payload = self._post(
                self._bases.exchange_url,
                {
                    "code": code_value,
                    "code_verifier": verifier,
                    "code_challenge_method": "S256",
                },
                self._timeout,
            )
        except (URLError, OSError, TimeoutError) as exc:
            self._fail(session_id, "network_error", "could not reach the authorization server")
            raise PkceFlowError("network_error", f"network failure: {exc}") from None

        data = payload if isinstance(payload, dict) else {}
        if status == 400:
            self._fail(session_id, "challenge_mismatch", "the server rejected the PKCE challenge")
            raise PkceFlowError("challenge_mismatch", _server_message(data, "invalid request"), 400)
        if status == 403:
            self._fail(session_id, "code_rejected", "the code is unknown, expired or already used")
            raise PkceFlowError("code_rejected", _server_message(data, "code rejected"), 403)
        if status == 429:
            self._fail(session_id, "rate_limited", "too many authorizations; try again later")
            raise PkceFlowError("rate_limited", "rate limited by the authorization server", 429)
        if status >= 400:
            self._fail(session_id, "exchange_failed", f"authorization failed (HTTP {status})")
            raise PkceFlowError("exchange_failed", _server_message(data, "exchange failed"), status)

        api_key = data.get("key")
        if not api_key:
            self._fail(session_id, "malformed_response", "the server returned no key")
            raise PkceFlowError("malformed_response", "authorization response contained no key")
        try:
            credential = self._provider.commit(
                api_key=str(api_key),
                granted_scope=data.get("scope"),
                account_id=data.get("user_id"),
            )
        except CredentialError as exc:
            self._fail(session_id, "malformed_response", str(exc))
            raise PkceFlowError("malformed_response", str(exc)) from None

        with self._lock:
            session = self._store.get(session_id)
            if session is not None:
                if session.generation == self._store.generation():
                    session.status = STATUS_COMPLETED
                    session.credential = credential
                else:
                    # A newer attempt started while this exchange was in flight: drop the result
                    # rather than letting a stale success overwrite newer state.
                    session.status = STATUS_FAILED
                session.verifier = ""
                self._store.put(session)
        return credential

    # ---------------------------------------------------------------- internals

    def _fail(self, session_id: str, reason: str, message: str) -> None:
        with self._lock:
            session = self._store.get(session_id)
            if session is not None and session.status == STATUS_PENDING:
                session.status = STATUS_FAILED
                session.error_reason = reason
                session.error_message = redact_secrets(message)
                session.verifier = ""
                self._store.put(session)

    def _expire(self, session: ConnectSession) -> bool:
        if session.status == STATUS_PENDING and self._clock() >= session.expires_at:
            session.status = STATUS_EXPIRED
            session.error_reason = "expired"
            session.error_message = "the authorization window closed; start again"
            session.verifier = ""
            return True
        return False

    def _invalidate_except(self, except_id: str, reason: str) -> None:
        for session in self._store.items():
            if session.id == except_id or session.status != STATUS_PENDING:
                continue
            session.status = STATUS_FAILED
            session.error_reason = reason
            session.error_message = "superseded by a newer authorization attempt"
            session.verifier = ""
            self._store.put(session)

    def _evict(self) -> None:
        sessions = sorted(self._store.items(), key=lambda s: s.created_at)
        while len(sessions) > self._max_sessions:
            oldest = sessions.pop(0)
            if oldest.status == STATUS_PENDING:
                oldest.status = STATUS_FAILED
                oldest.error_reason = "superseded"
                oldest.verifier = ""
                self._store.put(oldest)
            self._store.delete(oldest.id)


def _server_message(data: Dict[str, object], fallback: str) -> str:
    """Extract a human message without ever echoing a credential."""
    for key in ("error_description", "message", "error", "msg"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return redact_secrets(value)[:300]
    return fallback
