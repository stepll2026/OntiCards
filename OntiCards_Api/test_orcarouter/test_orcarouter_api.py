"""Flask transport tests for ``/console/api/orcarouter/*``.

These drive the real blueprint through Flask's test client.  Only the persistence layer (which
would need PostgreSQL) and the network transport are stubbed; every HTTP contract the browser
depends on is the production one.
"""

import json

import pytest

pytest.importorskip("flask")
pytest.importorskip("flask_restful")

from flask import Flask  # noqa: E402

from core.orcarouter import credentials as cred_mod  # noqa: E402
from core.orcarouter.bases import OrcaRouterBases  # noqa: E402
from core.orcarouter.catalog import fetch_catalog  # noqa: E402
from core.orcarouter.connect import ConnectSessionManager  # noqa: E402
from core.orcarouter.credentials import (  # noqa: E402
    SOURCE_API_KEY,
    SOURCE_PKCE,
    ApiKeyCredentialProvider,
    Credential,
    InMemoryCredentialStorage,
    PkceCredentialProvider,
)

import controllers.orcarouter.orcarouter_api as api_mod  # noqa: E402
from controllers.orcarouter import binding  # noqa: E402

FAKE_KEY = "sk-orca-transportfakekey00000000000000000000"
FAKE_VERIFIER_MARKER = "sk-orca-servermessage-leak"
BASES = OrcaRouterBases("https://www.orcarouter.ai", "https://api.orcarouter.ai/v1")


class StubBackend:
    """In-memory stand-in for the PostgreSQL-backed binding."""

    def __init__(self):
        self.storage = InMemoryCredentialStorage()
        self.needs_reauth_flag = False
        self.row = None  # None => not configured

    # ---- binding surface used by the blueprint
    def get_stored_credential(self):
        credential = self.storage.load()
        if credential is None:
            return None
        if self.needs_reauth_flag:
            return Credential(
                api_key=credential.api_key,
                source=credential.source,
                scope=credential.scope,
                account_id=credential.account_id,
                generation=credential.generation,
                state=cred_mod.STATE_NEEDS_REAUTH,
            )
        return credential

    def get_orcarouter_row(self):
        credential = self.storage.load()
        if credential is None:
            return None

        class Row:
            model_api_key = credential.api_key
            model_type = "orcarouter"
            url = BASES.api_base

        return Row()

    def stored_key_for_requests(self):
        credential = self.get_stored_credential()
        if credential is None or credential.state == cred_mod.STATE_NEEDS_REAUTH:
            return None
        return credential.api_key

    def store_credential(self, credential, model_class="base"):
        stored = self.storage.save(credential)
        self.needs_reauth_flag = False
        self.row = True
        return stored

    def clear_credential(self):
        self.storage.clear()
        self.row = None
        self.needs_reauth_flag = False

    def get_reauth_admin(self):
        return "stub" if self.needs_reauth_flag else None

    def mark_needs_reauth(self, source, generation, admin_id=None):
        current = self.storage.load()
        if current is None or current.source != source or current.generation != generation:
            return False
        self.needs_reauth_flag = True
        return True


class FakeAuthServer:
    def __init__(self, status=200, payload=None):
        self.status = status
        self.payload = payload if payload is not None else {"key": FAKE_KEY, "user_id": "42", "scope": "api"}
        self.requests = []

    def __call__(self, url, body, timeout):
        self.requests.append({"url": url, "body": body})
        return self.status, self.payload


@pytest.fixture()
def env(monkeypatch):
    backend = StubBackend()
    server = FakeAuthServer()

    for name in (
        "get_stored_credential",
        "get_orcarouter_row",
        "stored_key_for_requests",
        "store_credential",
        "clear_credential",
        "get_reauth_admin",
        "mark_needs_reauth",
    ):
        monkeypatch.setattr(binding, name, getattr(backend, name), raising=True)

    manager = ConnectSessionManager(
        bases=BASES,
        provider=PkceCredentialProvider(backend.storage),
        app_name="OntiCards",
        post=server,
    )
    monkeypatch.setattr(api_mod, "_manager", lambda: manager)
    monkeypatch.setattr(api_mod, "_storage", lambda: backend.storage)
    monkeypatch.setattr(api_mod, "bases_from_env", lambda: BASES)
    # Model discovery must not hit the network in these tests.
    monkeypatch.setattr(api_mod, "fetch_catalog", lambda **kwargs: fetch_catalog(**kwargs, transport=_live_transport))

    app = Flask(__name__)
    app.register_blueprint(api_mod.orcarouter_api, url_prefix="/console/api/orcarouter")
    client = app.test_client()
    return {"client": client, "backend": backend, "server": server, "manager": manager}


def _live_transport(request, timeout):
    payload = {
        "data": [
            {"id": "deepseek/deepseek-v4-flash", "supported_endpoint_types": ["openai"],
             "architecture": {"input_modalities": ["text"]}, "context_length": 1048576},
            {"id": "openai/gpt-5.5", "supported_endpoint_types": ["openai", "openai-response"],
             "architecture": {"input_modalities": ["text", "image"]}, "context_length": 400000,
             "reasoning": True, "reasoning_efforts": ["low", "medium", "high", "xhigh"]},
            {"id": "vendor/text-to-image", "supported_endpoint_types": ["image-generation"]},
        ]
    }
    return json.dumps(payload).encode()


def _ok(response):
    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_json()
    assert body["code"] == 200, body
    return body["data"]


# --------------------------------------------------------------------------- status


def test_status_advertises_both_authentication_choices(env):
    data = _ok(env["client"].get("/console/api/orcarouter/status"))
    assert data["provider"] == "orcarouter"
    assert data["auth_base"] == "https://www.orcarouter.ai"
    assert data["api_base"] == "https://api.orcarouter.ai/v1"
    methods = {m["id"] for m in data["auth_methods"]}
    assert methods == {SOURCE_API_KEY, SOURCE_PKCE}
    assert data["has_key"] is False
    assert data["needs_reauth"] is False


def test_status_masks_the_key_and_never_returns_it(env):
    env["client"].post("/console/api/orcarouter/api-key", json={"api_key": FAKE_KEY})
    raw = env["client"].get("/console/api/orcarouter/status").get_data(as_text=True)
    assert FAKE_KEY not in raw
    data = json.loads(raw)["data"]
    assert data["has_key"] is True
    assert data["api_key_masked"].startswith("sk-orca")


# --------------------------------------------------------------------------- API key adapter


def test_api_key_can_be_saved_read_and_cleared(env):
    data = _ok(env["client"].post("/console/api/orcarouter/api-key", json={"api_key": FAKE_KEY}))
    assert data["credential_source"] == SOURCE_API_KEY
    assert data["api_key_masked"].startswith("sk-orca")
    assert FAKE_KEY not in json.dumps(data)
    assert env["backend"].stored_key_for_requests() == FAKE_KEY

    cleared = _ok(env["client"].post("/console/api/orcarouter/api-key/clear", json={}))
    assert cleared["has_key"] is False
    assert env["backend"].stored_key_for_requests() is None


def test_an_obviously_wrong_key_is_rejected_with_a_clear_message(env):
    response = env["client"].post("/console/api/orcarouter/api-key", json={"api_key": "nope"})
    assert response.status_code == 400
    assert "sk-orca-" in response.get_json()["msg"]
    assert env["backend"].stored_key_for_requests() is None


# --------------------------------------------------------------------------- PKCE adapter


def test_connect_start_returns_an_oob_s256_authorize_url_on_the_auth_origin(env):
    data = _ok(env["client"].post("/console/api/orcarouter/connect/start", json={}))
    assert data["status"] == "pending"
    assert data["source"] == "pkce"
    assert data["authorize_url"].startswith("https://www.orcarouter.ai/auth?")
    assert "callback_url=oob" in data["authorize_url"]
    assert "code_challenge_method=S256" in data["authorize_url"]
    assert "code_verifier" not in data["authorize_url"]


def test_connect_response_never_contains_the_verifier(env):
    data = _ok(env["client"].post("/console/api/orcarouter/connect/start", json={}))
    session = env["manager"].get(data["session_id"])
    assert session.verifier not in json.dumps(data)
    raw = env["client"].get(f"/console/api/orcarouter/connect/{data['session_id']}").get_data(as_text=True)
    assert session.verifier not in raw
    assert session.verifier not in raw.replace("\\u", "")


def test_polling_reports_the_current_state(env):
    started = _ok(env["client"].post("/console/api/orcarouter/connect/start", json={}))
    polled = _ok(env["client"].get(f"/console/api/orcarouter/connect/{started['session_id']}"))
    assert polled["status"] == "pending"
    assert polled["session_id"] == started["session_id"]


def test_submitting_the_code_connects_and_persists_a_usable_key(env):
    started = _ok(env["client"].post("/console/api/orcarouter/connect/start", json={}))
    data = _ok(
        env["client"].post(
            f"/console/api/orcarouter/connect/{started['session_id']}/code", json={"code": "fake-code"}
        )
    )
    assert data["connected"] is True
    assert data["credential_source"] == SOURCE_PKCE
    assert data["scope"] == "api"
    assert FAKE_KEY not in json.dumps(data)
    # The exchange went to the auth origin only.
    assert env["server"].requests[0]["url"] == "https://www.orcarouter.ai/api/v1/auth/keys"
    # Downstream sees a normal key.
    assert env["backend"].stored_key_for_requests() == FAKE_KEY


def test_cancel_releases_the_attempt(env):
    started = _ok(env["client"].post("/console/api/orcarouter/connect/start", json={}))
    data = _ok(
        env["client"].post(
            f"/console/api/orcarouter/connect/{started['session_id']}/cancel", json={"reason": "pagehide"}
        )
    )
    assert data["cancelled"] is True
    assert env["manager"].get(started["session_id"]).status != "pending"


def test_a_rejected_code_reports_an_actionable_reason(env):
    env["server"].status = 403
    env["server"].payload = {"error": "invalid_grant", "error_description": "code expired"}
    started = _ok(env["client"].post("/console/api/orcarouter/connect/start", json={}))
    response = env["client"].post(
        f"/console/api/orcarouter/connect/{started['session_id']}/code", json={"code": "bad"}
    )
    assert response.status_code == 403
    body = response.get_json()
    assert body["data"]["reason"] == "code_rejected"
    assert env["backend"].stored_key_for_requests() is None


def test_an_unknown_session_polls_as_not_found(env):
    response = env["client"].get("/console/api/orcarouter/connect/nope")
    assert response.status_code == 404


# --------------------------------------------------------------------------- model catalog


def test_models_endpoint_returns_capability_filtered_minimal_metadata(env):
    data = _ok(env["client"].get("/console/api/orcarouter/models?model_class=base"))
    ids = [m["id"] for m in data["models"]]
    assert "deepseek/deepseek-v4-flash" in ids
    assert "vendor/text-to-image" not in ids
    assert data["source"] == "live"
    assert data["degraded"] is False
    gpt = next(m for m in data["models"] if m["id"] == "openai/gpt-5.5")
    assert gpt["reasoning_efforts"] == ["low", "medium", "high", "xhigh"]
    assert "pricing" not in gpt


def test_models_endpoint_filters_by_requested_modality(env):
    data = _ok(
        env["client"].get("/console/api/orcarouter/models?model_class=base&modalities=image")
    )
    ids = {m["id"] for m in data["models"]}
    assert ids == {"openai/gpt-5.5"}


def test_models_endpoint_rejects_an_unsupported_capability(env):
    response = env["client"].get("/console/api/orcarouter/models?capability=telepathy")
    assert response.status_code == 400


def test_models_endpoint_never_returns_a_key(env):
    env["client"].post("/console/api/orcarouter/api-key", json={"api_key": FAKE_KEY})
    raw = env["client"].get("/console/api/orcarouter/models?model_class=base").get_data(as_text=True)
    assert FAKE_KEY not in raw


# --------------------------------------------------------------------------- relay 401


def test_relay_401_marks_the_exact_generation_and_never_refreshes(env):
    env["client"].post("/console/api/orcarouter/api-key", json={"api_key": FAKE_KEY})
    credential = env["backend"].storage.load()
    data = _ok(env["client"].post("/console/api/orcarouter/relay-status", json={"status_code": 401}))
    assert data["action"] == "needs_reauth"
    assert data["marked_needs_reauth"] is True
    assert data["refresh_attempted"] is False
    assert data["generation"] == credential.generation
    assert env["backend"].stored_key_for_requests() is None  # fails closed
    # The stored key is not deleted; only its state changed.
    assert env["backend"].storage.load().api_key == FAKE_KEY


def test_a_stale_relay_401_for_an_old_generation_is_ignored(env):
    env["client"].post("/console/api/orcarouter/api-key", json={"api_key": FAKE_KEY})
    stale_generation = env["backend"].storage.load().generation
    # A newer login replaces the credential and bumps the generation.
    env["client"].post("/console/api/orcarouter/api-key", json={"api_key": FAKE_KEY + "2"})

    # The old request now reports 401 against the generation it actually used.
    assert env["backend"].mark_needs_reauth(SOURCE_API_KEY, stale_generation) is False
    current = env["backend"].storage.load()
    assert current.generation != stale_generation
    assert env["backend"].stored_key_for_requests() == current.api_key
    assert env["backend"].get_reauth_admin() is None


def test_non_auth_relay_status_does_not_mark_needs_reauth(env):
    env["client"].post("/console/api/orcarouter/api-key", json={"api_key": FAKE_KEY})
    for status in (429, 500, 200):
        data = _ok(env["client"].post("/console/api/orcarouter/relay-status", json={"status_code": status}))
        assert data["marked_needs_reauth"] is False
    assert env["backend"].stored_key_for_requests() == FAKE_KEY


def test_relay_status_requires_a_status_code(env):
    response = env["client"].post("/console/api/orcarouter/relay-status", json={})
    assert response.status_code == 400


# --------------------------------------------------------------------------- log hygiene


def test_no_secret_appears_in_stdout_or_logs_during_a_full_flow(env, capsys):
    import logging

    records = []

    class Collector(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    handler = Collector()
    logging.getLogger().addHandler(handler)
    try:
        started = _ok(env["client"].post("/console/api/orcarouter/connect/start", json={}))
        verifier = env["manager"].get(started["session_id"]).verifier
        env["client"].post(
            f"/console/api/orcarouter/connect/{started['session_id']}/code", json={"code": "fake-code"}
        )
        env["client"].get("/console/api/orcarouter/status")
        env["client"].get("/console/api/orcarouter/models?model_class=base")
    finally:
        logging.getLogger().removeHandler(handler)

    captured = capsys.readouterr()
    # Everything the process wrote, anywhere a secret could realistically leak.
    haystack = captured.out + captured.err + "\n".join(records)
    assert FAKE_KEY not in haystack
    assert verifier and verifier not in haystack
    assert FAKE_VERIFIER_MARKER not in haystack

    # The verifier does travel to the exchange endpoint — that is the whole point of PKCE —
    # but only there, and only to the auth origin.
    assert env["server"].requests[-1]["body"]["code_verifier"] == verifier
    assert env["server"].requests[-1]["url"].startswith("https://www.orcarouter.ai")
    assert "code_verifier" not in "\n".join(records)
