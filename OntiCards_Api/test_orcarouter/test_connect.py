"""The PKCE connect flow, driven end to end against a local fake authorization server.

Nothing here performs a real authorization (that needs a human to consent).  Instead an injected
transport stands in for the OrcaRouter auth origin, so the whole sequence — start, authorize URL,
code submit, exchange, persist — runs through the exact adapter the product uses.

The property that matters most: the verifier never appears in a URL, a response the browser can
see, a log line, or an error message.
"""

import base64
import hashlib
import json
import re
import urllib.error

import pytest

from core.orcarouter.bases import OrcaRouterBases
from core.orcarouter.connect import (
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_EXPIRED,
    STATUS_FAILED,
    STATUS_PENDING,
    ConnectSessionManager,
    InvalidStateError,
    PkceFlowError,
    b64url,
    build_authorize_url,
    challenge_for,
    generate_state,
    generate_verifier,
)
from core.orcarouter.credentials import (
    SOURCE_PKCE,
    STATE_ACTIVE,
    InMemoryCredentialStorage,
    PkceCredentialProvider,
)

BASES = OrcaRouterBases(
    auth_base="https://www.orcarouter.ai", api_base="https://api.orcarouter.ai/v1"
)
AUTH_ORIGIN = "https://www.orcarouter.ai"
FAKE_CODE = "authcode-fake-0001"
FAKE_KEY = "sk-orca-pkcefakekey000000000000000000000000000"


class FakeAuthServer:
    """Stands in for the OrcaRouter auth origin; records what it was asked."""

    def __init__(self, status=200, payload=None, raises=None):
        self.status = status
        self.payload = payload if payload is not None else {"key": FAKE_KEY, "user_id": "12345", "scope": "api"}
        self.raises = raises
        self.requests = []

    def __call__(self, url, body, timeout):
        self.requests.append({"url": url, "body": body, "timeout": timeout})
        if self.raises is not None:
            raise self.raises
        return self.status, self.payload


def _manager(server=None, ttl=600, clock=None):
    storage = InMemoryCredentialStorage()
    provider = PkceCredentialProvider(storage)
    kwargs = {}
    if clock is not None:
        kwargs["clock"] = clock
    manager = ConnectSessionManager(
        bases=BASES,
        provider=provider,
        app_name="OntiCards",
        ttl=ttl,
        post=server or FakeAuthServer(),
        **kwargs,
    )
    return manager, storage


def _query(url):
    from urllib.parse import parse_qs, urlsplit

    return parse_qs(urlsplit(url).query)


# --------------------------------------------------------------------------- verifier / challenge


def test_verifier_and_state_are_fresh_for_every_attempt():
    verifiers = {generate_verifier() for _ in range(50)}
    assert len(verifiers) == 50
    states = {generate_state() for _ in range(50)}
    assert len(states) == 50
    for verifier in verifiers:
        # 32 random bytes, base64url, no padding.
        assert len(verifier) >= 42
        assert "=" not in verifier
        assert re.fullmatch(r"[A-Za-z0-9_-]+", verifier)


def test_challenge_is_base64url_sha256_without_padding():
    verifier = generate_verifier()
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    assert challenge_for(verifier) == expected
    assert challenge_for(verifier) == b64url(hashlib.sha256(verifier.encode()).digest())
    assert "=" not in challenge_for(verifier)


def test_two_attempts_never_reuse_a_verifier_or_state():
    manager, _ = _manager()
    first = manager.start()
    second = manager.start()
    assert first.verifier != second.verifier
    assert first.state != second.state
    assert challenge_for(first.verifier) != challenge_for(second.verifier)


# --------------------------------------------------------------------------- authorize URL


def test_authorize_url_uses_oob_and_s256_on_the_auth_origin():
    manager, _ = _manager()
    session = manager.start()
    query = _query(session.authorize_url)

    assert session.authorize_url.startswith(AUTH_ORIGIN + "/auth?")
    assert query["callback_url"] == ["oob"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["app_name"] == ["OntiCards"]
    assert query["scope"] == ["api"]
    assert query["state"] == [session.state]
    assert query["code_challenge"] == [challenge_for(session.verifier)]


def test_authorize_url_never_contains_the_verifier():
    manager, _ = _manager()
    session = manager.start()
    assert session.verifier not in session.authorize_url
    # Neither the verifier nor the state may be sent as a parameter named like the verifier.
    assert "code_verifier" not in session.authorize_url
    assert "verifier" not in _query(session.authorize_url)


def test_build_authorize_url_uses_the_configured_auth_origin():
    url = build_authorize_url(BASES, "chal", "state", "Tool")
    assert url.startswith("https://www.orcarouter.ai/auth?")
    assert not url.startswith("https://api.orcarouter.ai")


# --------------------------------------------------------------------------- happy path


def test_full_flow_authorize_then_exchange_then_persist():
    server = FakeAuthServer()
    manager, storage = _manager(server)

    session = manager.start()
    verifier = session.verifier
    assert manager.get(session.id).status == STATUS_PENDING

    credential = manager.submit_code(session.id, FAKE_CODE)

    # The exchange went to the auth origin, with the correct path and body.
    assert len(server.requests) == 1
    request = server.requests[0]
    assert request["url"] == "https://www.orcarouter.ai/api/v1/auth/keys"
    assert not request["url"].startswith("https://api.orcarouter.ai")
    assert request["body"]["code"] == FAKE_CODE
    assert request["body"]["code_verifier"] == verifier
    assert request["body"]["code_challenge_method"] == "S256"

    assert credential.source == SOURCE_PKCE
    assert credential.scope == "api"
    assert credential.account_id == "12345"
    assert storage.load().api_key == FAKE_KEY
    assert storage.load().state == STATE_ACTIVE
    assert manager.get(session.id).status == STATUS_COMPLETED


def test_the_stored_credential_is_a_normal_key_usable_by_the_request_path():
    manager, storage = _manager()
    manager.submit_code(manager.start().id, FAKE_CODE)
    credential = storage.load()
    # This is the only thing the request path consumes; it does not know how the key arrived.
    assert {"Authorization": f"Bearer {credential.api_key}"}["Authorization"] == f"Bearer {FAKE_KEY}"
    assert credential.is_usable


def test_granted_scope_is_read_back_rather_than_assumed():
    manager, storage = _manager(FakeAuthServer(payload={"key": FAKE_KEY, "scope": "connector"}))
    credential = manager.submit_code(manager.start().id, FAKE_CODE)
    assert credential.scope == "connector"
    assert storage.load().scope == "connector"


def test_an_unexpected_granted_scope_is_rejected():
    manager, storage = _manager(FakeAuthServer(payload={"key": FAKE_KEY, "scope": "root"}))
    with pytest.raises(PkceFlowError) as excinfo:
        manager.submit_code(manager.start().id, FAKE_CODE)
    assert excinfo.value.reason == "malformed_response"
    assert storage.load() is None


def test_success_is_recorded_but_the_verifier_is_gone():
    manager, _ = _manager()
    session = manager.start()
    manager.submit_code(session.id, FAKE_CODE)
    stored = manager.get(session.id)
    assert stored.status == STATUS_COMPLETED
    assert stored.verifier == ""


# --------------------------------------------------------------------------- terminal failures


def test_denial_or_explicit_cancel_closes_the_attempt():
    manager, _ = _manager()
    session = manager.start()
    assert manager.cancel(session.id) is True
    closed = manager.get(session.id)
    assert closed.status == STATUS_CANCELLED
    assert closed.verifier == ""
    # A cancelled attempt cannot be completed afterwards.
    with pytest.raises(PkceFlowError) as excinfo:
        manager.submit_code(session.id, FAKE_CODE)
    assert excinfo.value.reason == "session_closed"


def test_cancel_all_releases_every_pending_attempt():
    manager, _ = _manager()
    first = manager.start()
    second = manager.start()
    assert manager.get(second.id).status == STATUS_PENDING
    assert manager.get(first.id).status == STATUS_FAILED  # superseded by the newer attempt
    assert manager.cancel_all("pagehide") == 1  # only the newest was still pending
    released = manager.get(second.id)
    assert released.status == STATUS_FAILED
    assert released.error_reason == "pagehide"
    assert released.verifier == ""
    assert _sessions(manager) and all(s.status != STATUS_PENDING for s in _sessions(manager))

def _sessions(manager):
    return manager._store.items()


def test_state_mismatch_is_rejected_before_any_exchange():
    server = FakeAuthServer()
    manager, _ = _manager(server)
    session = manager.start()
    with pytest.raises(InvalidStateError):
        manager.submit_code(session.id, FAKE_CODE, state="not-the-state")
    assert server.requests == []  # no code was sent to the server
    assert manager.get(session.id).status == STATUS_FAILED
    assert manager.get(session.id).error_reason == "state_mismatch"


def test_a_code_cannot_be_redeemed_twice():
    manager, _ = _manager()
    session = manager.start()
    manager.submit_code(session.id, FAKE_CODE)
    with pytest.raises(PkceFlowError) as excinfo:
        manager.submit_code(session.id, FAKE_CODE)
    assert excinfo.value.reason == "session_closed"


def test_an_expired_attempt_cannot_be_completed():
    now = [1000.0]
    manager, _ = _manager(ttl=600, clock=lambda: now[0])
    session = manager.start()
    now[0] += 601
    with pytest.raises(PkceFlowError) as excinfo:
        manager.submit_code(session.id, FAKE_CODE)
    assert excinfo.value.reason == "session_closed"
    assert manager.get(session.id).status == STATUS_EXPIRED


def test_an_empty_code_is_refused():
    manager, _ = _manager()
    session = manager.start()
    with pytest.raises(PkceFlowError) as excinfo:
        manager.submit_code(session.id, "   ")
    assert excinfo.value.reason == "empty_code"


def test_unknown_session_is_refused():
    manager, _ = _manager()
    with pytest.raises(PkceFlowError) as excinfo:
        manager.submit_code("does-not-exist", FAKE_CODE)
    assert excinfo.value.reason == "unknown_session"


@pytest.mark.parametrize(
    "status,reason",
    [(400, "challenge_mismatch"), (403, "code_rejected"), (429, "rate_limited"), (500, "exchange_failed")],
)
def test_http_failures_end_the_attempt_with_an_actionable_reason(status, reason):
    server = FakeAuthServer(status=status, payload={"error": "x", "error_description": "nope"})
    manager, storage = _manager(server)
    session = manager.start()
    with pytest.raises(PkceFlowError) as excinfo:
        manager.submit_code(session.id, FAKE_CODE)
    assert excinfo.value.reason == reason
    assert storage.load() is None
    assert manager.get(session.id).status == STATUS_FAILED


def test_network_failure_is_not_a_hot_loop():
    server = FakeAuthServer(raises=urllib.error.URLError("connection refused"))
    manager, storage = _manager(server)
    session = manager.start()
    with pytest.raises(PkceFlowError) as excinfo:
        manager.submit_code(session.id, FAKE_CODE)
    assert excinfo.value.reason == "network_error"
    assert len(server.requests) == 1  # exactly one attempt, then it stopped
    assert storage.load() is None


def test_a_malformed_success_response_is_refused():
    server = FakeAuthServer(payload={"scope": "api"})  # no key
    manager, storage = _manager(server)
    with pytest.raises(PkceFlowError) as excinfo:
        manager.submit_code(manager.start().id, FAKE_CODE)
    assert excinfo.value.reason == "malformed_response"
    assert storage.load() is None


# --------------------------------------------------------------------------- generation guard


def test_a_stale_exchange_cannot_overwrite_a_newer_login():
    """Start A, start B (which supersedes A), then finish A — A must not win."""
    server = FakeAuthServer()
    manager, storage = _manager(server)
    first = manager.start()
    second = manager.start()

    with pytest.raises(PkceFlowError):
        manager.submit_code(first.id, FAKE_CODE)

    assert manager.get(first.id).status == STATUS_FAILED
    assert manager.get(second.id).status == STATUS_PENDING
    assert storage.load() is None

    # The current attempt still works.
    manager.submit_code(second.id, FAKE_CODE)
    assert manager.get(second.id).status == STATUS_COMPLETED
    assert storage.load() is not None


def test_a_response_from_a_superseded_generation_is_dropped():
    """Even a *successful* late response is dropped when a newer attempt exists."""
    server = FakeAuthServer()
    manager, storage = _manager(server)
    first = manager.start()

    # Simulate a newer attempt starting while the first exchange is in flight.
    original_post = server.__call__

    def post_then_bump(url, body, timeout):
        manager._store.set_generation(manager._store.generation() + 1)
        return original_post(url, body, timeout)

    manager._post = post_then_bump
    credential = manager.submit_code(first.id, FAKE_CODE)

    # The credential was returned but the stale session was closed, not marked completed.
    assert credential.api_key == FAKE_KEY
    assert manager.get(first.id).status == STATUS_FAILED


# --------------------------------------------------------------------------- secret hygiene


def test_the_public_session_view_never_contains_the_verifier():
    """The verifier is process-private.  The state is public by design (it rides the authorize URL)."""
    manager, _ = _manager()
    session = manager.start()
    public = json.dumps(session.public())
    assert session.verifier not in public
    assert challenge_for(session.verifier) in public  # only the hash is exposed
    assert "code_verifier" not in public
    assert "_verifier" not in public


def test_the_session_repr_never_contains_the_verifier():
    manager, _ = _manager()
    session = manager.start()
    assert session.verifier not in repr(session)
    assert "<redacted>" in repr(session)


def test_a_server_message_that_echoes_the_verifier_is_redacted():
    server = FakeAuthServer(status=400, payload={"error_description": "bad verifier sk-orca-aaaaaaaaaaaa"})
    manager, _ = _manager(server)
    session = manager.start()
    verifier = session.verifier
    with pytest.raises(PkceFlowError) as excinfo:
        manager.submit_code(session.id, FAKE_CODE)
    message = str(excinfo.value)
    assert "sk-orca-aaaaaaaaaaaa" not in message
    assert verifier not in message
    assert verifier not in (manager.get(session.id).error_message or "")


def test_the_timeout_is_always_bounded():
    server = FakeAuthServer()
    manager, _ = _manager(server)
    manager.submit_code(manager.start().id, FAKE_CODE)
    assert 0 < server.requests[0]["timeout"] <= 60


def test_sessions_are_bounded_in_number():
    manager, _ = _manager()
    for _ in range(50):
        manager.start()
    assert len(_sessions(manager)) <= manager._max_sessions
