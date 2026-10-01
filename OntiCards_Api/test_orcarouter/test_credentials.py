"""The credential seam: two adapters, one credential, one transport contract.

The point of these tests is that the API-key adapter and the PKCE adapter are interchangeable.
Nothing downstream (provider request path, model discovery) may care which one produced the
credential.
"""

import datetime

import pytest

from core.orcarouter.credentials import (
    SOURCE_API_KEY,
    SOURCE_PKCE,
    STATE_ACTIVE,
    STATE_NEEDS_REAUTH,
    ApiKeyCredentialProvider,
    Credential,
    CredentialError,
    InMemoryCredentialStorage,
    PkceCredentialProvider,
    classify_relay_status,
    mask_api_key,
    provider_for_source,
    redact,
    redact_secrets,
)

FAKE_KEY = "sk-orca-fakeabcdefghijklmnopqrstuvwxyz0123456789"


def test_api_key_adapter_saves_and_reads_a_credential():
    storage = InMemoryCredentialStorage()
    provider = ApiKeyCredentialProvider(storage)
    credential = provider.acquire(FAKE_KEY, account_id="acct-1")

    assert credential.api_key == FAKE_KEY
    assert credential.source == SOURCE_API_KEY
    assert credential.provider == "orcarouter"
    assert credential.state == STATE_ACTIVE
    assert credential.is_usable
    assert storage.load() == credential


def test_api_key_adapter_rejects_obviously_wrong_input():
    storage = InMemoryCredentialStorage()
    provider = ApiKeyCredentialProvider(storage)
    with pytest.raises(CredentialError):
        provider.acquire("")
    with pytest.raises(CredentialError):
        provider.acquire("not-an-orcarouter-key")
    assert storage.load() is None


def test_clearing_removes_the_credential():
    storage = InMemoryCredentialStorage()
    provider = ApiKeyCredentialProvider(storage)
    provider.acquire(FAKE_KEY)
    provider.clear()
    assert storage.load() is None
    assert not provider.is_usable()


@pytest.mark.parametrize("source", [SOURCE_API_KEY, SOURCE_PKCE])
def test_both_adapters_produce_the_same_credential_shape(source):
    """The seam is only real if downstream code cannot tell the adapters apart."""
    storage = InMemoryCredentialStorage()
    if source == SOURCE_API_KEY:
        credential = ApiKeyCredentialProvider(storage).acquire(FAKE_KEY, account_id="acct-1")
    else:
        credential = PkceCredentialProvider(storage).commit(
            FAKE_KEY, granted_scope="api", account_id="acct-1"
        )

    assert isinstance(credential, Credential)
    assert credential.source == source
    assert credential.provider == "orcarouter"
    assert credential.api_key == FAKE_KEY
    assert credential.scope == "api"
    assert credential.is_usable


def test_downstream_consumers_only_read_the_common_fields():
    """A fake downstream consumer must behave identically for both credential sources."""
    def downstream_request_headers(credential: Credential) -> dict:
        # This is exactly what the request path does; it never asks where the key came from.
        return {"Authorization": f"Bearer {credential.api_key}"}

    api_key_credential = ApiKeyCredentialProvider(InMemoryCredentialStorage()).acquire(FAKE_KEY)
    pkce_credential = PkceCredentialProvider(InMemoryCredentialStorage()).commit(FAKE_KEY, "api")

    assert downstream_request_headers(api_key_credential) == downstream_request_headers(pkce_credential)
    assert api_key_credential.masked_key == pkce_credential.masked_key


def test_pkce_adapter_validates_the_granted_scope_not_the_requested_one():
    storage = InMemoryCredentialStorage()
    provider = PkceCredentialProvider(storage)
    # Granted 'api' although 'connector' may have been requested: that is what we store.
    assert provider.commit(FAKE_KEY, granted_scope="api").scope == "api"
    assert provider.commit(FAKE_KEY, granted_scope=None).scope == "api"
    with pytest.raises(CredentialError):
        provider.commit(FAKE_KEY, granted_scope="root")
    with pytest.raises(CredentialError):
        provider.commit("", granted_scope="api")


def test_provider_for_source_routes_to_the_right_adapter():
    storage = InMemoryCredentialStorage()
    assert isinstance(provider_for_source(storage, SOURCE_API_KEY), ApiKeyCredentialProvider)
    assert isinstance(provider_for_source(storage, SOURCE_PKCE), PkceCredentialProvider)
    with pytest.raises(CredentialError):
        provider_for_source(storage, "nope")


def test_generation_increases_on_every_save():
    storage = InMemoryCredentialStorage()
    provider = ApiKeyCredentialProvider(storage)
    first = provider.acquire(FAKE_KEY)
    second = provider.acquire(FAKE_KEY + "x")
    assert second.generation == first.generation + 1


def test_mark_needs_reauth_is_generation_safe():
    storage = InMemoryCredentialStorage()
    provider = ApiKeyCredentialProvider(storage)
    old = provider.acquire(FAKE_KEY)

    # A stale failure for the old generation must not touch a newer credential.
    provider.acquire(FAKE_KEY + "x")
    assert storage.mark_needs_reauth("orcarouter", SOURCE_API_KEY, old.generation) is False
    assert storage.load().state == STATE_ACTIVE

    # The current generation transitions, and nothing about it is deleted.
    current = storage.load()
    assert storage.mark_needs_reauth("orcarouter", SOURCE_API_KEY, current.generation) is True
    assert storage.load().state == STATE_NEEDS_REAUTH
    assert storage.load().api_key == current.api_key


def test_mark_needs_reauth_ignores_a_different_source():
    storage = InMemoryCredentialStorage()
    pkce = PkceCredentialProvider(storage)
    credential = pkce.commit(FAKE_KEY, "api")
    assert storage.mark_needs_reauth("orcarouter", SOURCE_API_KEY, credential.generation) is False
    assert storage.load().state == STATE_ACTIVE


def test_relay_401_marks_needs_reauth_without_any_refresh_attempt():
    storage = InMemoryCredentialStorage()
    provider = PkceCredentialProvider(storage)
    credential = provider.commit(FAKE_KEY, "api")

    action = provider.handle_relay_status(401)

    assert action == "needs_reauth"
    stored = storage.load()
    assert stored.state == STATE_NEEDS_REAUTH
    # A durable key is never replaced by a refresh; only a new login replaces it.
    assert stored.api_key == credential.api_key
    assert not stored.is_usable


def test_a_late_failure_does_not_poison_a_freshly_reauthorized_credential():
    storage = InMemoryCredentialStorage()
    provider = PkceCredentialProvider(storage)
    rejected = provider.commit(FAKE_KEY, "api")

    # The user reauthorizes; a new generation is stored.
    replacement = provider.commit(FAKE_KEY + "new", "api")
    assert replacement.generation > rejected.generation

    # The old request now fails with 401 and reports the generation it used.
    assert storage.mark_needs_reauth("orcarouter", SOURCE_PKCE, rejected.generation) is False
    assert storage.load().state == STATE_ACTIVE
    assert storage.load().api_key == replacement.api_key


def test_classify_relay_status_never_treats_401_as_retryable():
    assert classify_relay_status(401) == "needs_reauth"
    assert classify_relay_status(403) == "client_error"
    assert classify_relay_status(429) == "rate_limited"
    assert classify_relay_status(500) == "server_error"
    assert classify_relay_status(200) == "ok"


def test_mask_and_redaction_never_leak_a_key():
    assert mask_api_key(None) == ""
    assert mask_api_key("short") == "*****"
    masked = mask_api_key(FAKE_KEY)
    assert FAKE_KEY not in masked
    assert masked.startswith("sk-orca")

    # Redaction must survive being embedded in arbitrary text.
    text = f"request failed for Authorization: Bearer {FAKE_KEY} at 2026-10-01"
    redacted = redact(text)
    assert FAKE_KEY not in redacted
    assert "sk-orca…" in redacted

    structured = f"code_verifier={FAKE_KEY} api_key: {FAKE_KEY} token='{FAKE_KEY}'"
    safe = redact_secrets(structured)
    assert FAKE_KEY not in safe
    assert "<redacted>" in safe


def test_repr_never_contains_the_raw_key():
    credential = Credential(api_key=FAKE_KEY, source=SOURCE_PKCE, generation=3)
    assert FAKE_KEY not in repr(credential)
    assert "sk-orca…" in repr(credential)
