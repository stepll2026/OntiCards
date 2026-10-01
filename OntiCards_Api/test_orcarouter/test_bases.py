"""Origin, endpoint and stored-URL resolution.

Covers the single most common OrcaRouter integration mistake: deriving one public origin from the
other.  Auth must stay on ``www.orcarouter.ai`` and inference on ``api.orcarouter.ai/v1``.
"""

import pytest

from core.orcarouter.bases import (
    AUTHORIZE_PATH,
    DEFAULT_API_BASE,
    DEFAULT_AUTH_BASE,
    EXCHANGE_PATH,
    OrcaRouterConfigError,
    bases_from_env,
    endpoint_for_model_class,
    is_loopback_url,
    is_orcarouter_model_type,
    resolve_stored_url,
)


def test_defaults_use_the_documented_public_origins():
    bases = bases_from_env({})
    assert bases.auth_base == "https://www.orcarouter.ai"
    assert bases.api_base == "https://api.orcarouter.ai/v1"
    assert bases.authorize_url == "https://www.orcarouter.ai/auth"
    assert bases.exchange_url == "https://www.orcarouter.ai/api/v1/auth/keys"


def test_auth_paths_are_fixed_and_never_live_on_the_inference_origin():
    bases = bases_from_env({})
    # The relay is at /v1; auth endpoints are not.  https://api.orcarouter.ai/v1/auth/keys is a 404.
    assert AUTHORIZE_PATH == "/auth"
    assert EXCHANGE_PATH == "/api/v1/auth/keys"
    assert bases.exchange_url.startswith(DEFAULT_AUTH_BASE)
    # The mistake to guard against is the inference origin with the auth path glued on.
    wrong_path = DEFAULT_API_BASE.rsplit("/v1", 1)[0] + "/v1/auth/keys"
    assert bases.exchange_url != wrong_path
    assert not bases.exchange_url.startswith("https://api.orcarouter.ai")


def test_inference_and_catalog_stay_on_the_api_origin():
    bases = bases_from_env({})
    assert bases.models_url("chat") == "https://api.orcarouter.ai/v1/models?capability=chat"
    assert bases.endpoint_for_class("base") == "https://api.orcarouter.ai/v1/chat/completions"
    assert bases.endpoint_for_class("embedding") == "https://api.orcarouter.ai/v1/embeddings"
    assert bases.endpoint_for_class("rerank") == "https://api.orcarouter.ai/v1/rerank"


def test_explicit_overrides_win_over_the_shared_base():
    bases = bases_from_env(
        {
            "ORCA_BASE_URL": "https://shared.example",
            "ORCA_AUTH_BASE_URL": "https://auth.example",
            "ORCA_API_BASE_URL": "https://api.example/v1",
        }
    )
    assert bases.auth_base == "https://auth.example"
    assert bases.api_base == "https://api.example/v1"


def test_shared_base_is_used_for_both_origins_and_only_gets_one_v1():
    bases = bases_from_env({"ORCA_BASE_URL": "https://one.example"})
    assert bases.auth_base == "https://one.example"
    assert bases.api_base == "https://one.example/v1"
    assert bases.models_url() == "https://one.example/v1/models"

    already_versioned = bases_from_env({"ORCA_BASE_URL": "https://one.example/v1"})
    assert already_versioned.api_base == "https://one.example/v1"


def test_plain_http_is_rejected_for_remote_hosts_but_allowed_for_loopback():
    with pytest.raises(OrcaRouterConfigError):
        bases_from_env({"ORCA_API_BASE_URL": "http://api.example/v1"})
    assert bases_from_env({"ORCA_API_BASE_URL": "http://127.0.0.1:8080/v1"}).api_base == (
        "http://127.0.0.1:8080/v1"
    )
    assert bases_from_env({"ORCA_AUTH_BASE_URL": "http://localhost:3000"}).auth_base == (
        "http://localhost:3000"
    )
    assert is_loopback_url("http://[::1]:9000")
    assert not is_loopback_url("https://api.orcarouter.ai/v1")


def test_unknown_model_class_fails_closed():
    with pytest.raises(OrcaRouterConfigError):
        endpoint_for_model_class("https://api.orcarouter.ai/v1", "not-a-class")


def test_full_endpoint_pasted_instead_of_a_base_is_left_alone():
    assert (
        endpoint_for_model_class("https://api.orcarouter.ai/v1/chat/completions", "base")
        == "https://api.orcarouter.ai/v1/chat/completions"
    )


def test_stored_url_resolution_preserves_other_providers_exactly():
    # Every non-OrcaRouter provider keeps the historical behaviour: url used verbatim.
    assert (
        resolve_stored_url("doubao", "base", "https://ark.example/v3/chat/completions")
        == "https://ark.example/v3/chat/completions"
    )
    assert resolve_stored_url(None, "base", "https://x.example/y") == "https://x.example/y"


def test_stored_url_resolution_derives_endpoints_for_orcarouter_rows():
    assert is_orcarouter_model_type("OrcaRouter")
    assert is_orcarouter_model_type("orcarouter")
    assert not is_orcarouter_model_type("openrouter")
    # A base URL stored on the row is derived into the concrete endpoint.
    assert (
        resolve_stored_url("orcarouter", "base", "https://api.orcarouter.ai/v1")
        == "https://api.orcarouter.ai/v1/chat/completions"
    )
    assert (
        resolve_stored_url("orcarouter", "embedding", "https://api.orcarouter.ai/v1")
        == "https://api.orcarouter.ai/v1/embeddings"
    )
    # A self-hosted override stored on the row wins over the environment default.
    assert (
        resolve_stored_url("orcarouter", "rerank", "https://orca.internal.example/v1")
        == "https://orca.internal.example/v1/rerank"
    )
    # An empty row falls back to the configured default origin.
    assert resolve_stored_url("orcarouter", "base", "") == (
        "https://api.orcarouter.ai/v1/chat/completions"
    )
