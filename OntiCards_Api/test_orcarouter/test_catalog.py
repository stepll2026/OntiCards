"""Live model discovery, capability filtering and the verified fallback seed.

The selector must never offer a model the request path cannot speak, and a catalog outage must not
silently erase capability metadata.  ``?capability=chat`` is the authoritative filter; when the
relay does not implement a capability filter the contract is "strictly compatible with what the
relay returned".
"""

import json

import pytest

from core.orcarouter.bases import OrcaRouterBases
from core.orcarouter.catalog import (
    MAX_ITEMS,
    MAX_RESPONSE_BYTES,
    SEED_MODELS,
    CatalogResult,
    fetch_catalog,
    fetch_live_models,
    filter_models,
    parse_models,
)

BASES = OrcaRouterBases(
    auth_base="https://www.orcarouter.ai", api_base="https://api.orcarouter.ai/v1"
)


def _model(model_id, endpoints, modalities=None, **extra):
    item = {"id": model_id, "object": "model", "supported_endpoint_types": endpoints}
    if modalities is not None:
        item["architecture"] = {"input_modalities": modalities}
    item.update(extra)
    return item


LIVE_PAYLOAD = {
    "data": [
        _model("deepseek/deepseek-v4-flash", ["openai", "openai-response"], ["text"], context_length=1048576),
        _model("deepseek/deepseek-v4.1-flash", ["openai", "anthropic"], ["text", "image"], context_length=1048576),
        _model("anthropic/claude-opus-4.8", ["anthropic", "openai"], ["text", "image"], context_length=200000),
        _model("openai/gpt-5.5", ["openai", "openai-response"], ["text", "image"], context_length=400000,
               reasoning=True, reasoning_efforts=["low", "medium", "high", "xhigh"]),
        _model("orcarouter/auto", ["openai", "openai-response", "anthropic", "gemini"], ["text"]),
        _model("vendor/text-to-image", ["image-generation"], []),
        _model("vendor/video-maker", ["openai-video"], []),
        _model("vendor/reranker", ["jina-rerank"], []),
        _model("vendor/embedder", ["embeddings"], []),
    ]
}


def _live_result(model_class="base", required_modalities=None):
    parsed = parse_models(LIVE_PAYLOAD)

    def transport(request, timeout):
        return json.dumps(LIVE_PAYLOAD).encode()

    return fetch_catalog(
        BASES,
        "sk-orca-fake",
        model_class=model_class,
        required_modalities=required_modalities,
        transport=transport,
    )


# --------------------------------------------------------------------------- parsing


def test_parsing_drops_records_that_do_not_have_the_accepted_shape():
    parsed = parse_models(
        {
            "data": [
                {"id": "good/model", "supported_endpoint_types": ["openai"]},
                {"id": ""},                        # empty id
                {"no_id": True},                   # missing id
                "not-a-dict",                      # wrong type
                {"id": "bad/context", "context_length": -5},
            ]
        }
    )
    assert [m.id for m in parsed] == ["good/model", "bad/context"]
    assert parsed[1].context_length is None


def test_parsing_bounds_the_item_count():
    payload = {"data": [{"id": f"v/m{i}"} for i in range(MAX_ITEMS + 50)]}
    assert len(parse_models(payload)) == MAX_ITEMS


def test_parsing_tolerates_a_missing_data_key():
    assert parse_models({}) == []
    assert parse_models({"data": "nope"}) == []


# --------------------------------------------------------------------------- filtering


def test_chat_filter_keeps_only_text_capable_models():
    models = parse_models(LIVE_PAYLOAD)
    ids = {m.id for m in filter_models(models, "chat")}
    assert "deepseek/deepseek-v4-flash" in ids
    assert "orcarouter/auto" in ids
    # Non-text dedicated endpoint types are excluded even though they are OpenAI-compatible.
    assert "vendor/text-to-image" not in ids
    assert "vendor/video-maker" not in ids
    assert "vendor/reranker" not in ids
    assert "vendor/embedder" not in ids


def test_multimodal_filter_is_fail_closed():
    models = parse_models(LIVE_PAYLOAD)
    ids = {m.id for m in filter_models(models, "chat", required_modalities=["image"])}
    # Only models that explicitly declare image input survive.
    assert ids == {"anthropic/claude-opus-4.8", "deepseek/deepseek-v4.1-flash", "openai/gpt-5.5"}
    # A model with no declared architecture cannot slip in.
    assert "orcarouter/auto" not in ids
    assert "deepseek/deepseek-v4-flash" not in ids


def test_capability_filters_are_exact_for_non_chat_capabilities():
    models = parse_models(LIVE_PAYLOAD)
    assert [m.id for m in filter_models(models, "embedding")] == ["vendor/embedder"]
    assert [m.id for m in filter_models(models, "image")] == ["vendor/text-to-image"]
    assert [m.id for m in filter_models(models, "video")] == ["vendor/video-maker"]
    assert [m.id for m in filter_models(models, "rerank")] == ["vendor/reranker"]


def test_unknown_capability_fails_closed():
    models = parse_models(LIVE_PAYLOAD)
    assert filter_models(models, "telepathy") == []


def test_filtering_preserves_reasoning_and_context_metadata():
    models = parse_models(LIVE_PAYLOAD)
    gpt = next(m for m in filter_models(models, "chat") if m.id == "openai/gpt-5.5")
    assert gpt.reasoning is True
    assert gpt.reasoning_efforts == ("low", "medium", "high", "xhigh")
    assert gpt.context_length == 400000
    public = gpt.to_public()
    assert public["reasoning_efforts"] == ["low", "medium", "high", "xhigh"]
    assert "pricing" not in public


# --------------------------------------------------------------------------- live fetch


def test_live_fetch_sends_the_capability_query_and_bearer_auth():
    seen = {}

    def transport(request, timeout):
        seen["url"] = request.full_url
        seen["auth"] = request.get_header("Authorization")
        seen["timeout"] = timeout
        return json.dumps(LIVE_PAYLOAD).encode()

    fetch_live_models(BASES, "sk-orca-secret", capability="chat", transport=transport)
    assert seen["url"] == "https://api.orcarouter.ai/v1/models?capability=chat"
    assert seen["auth"] == "Bearer sk-orca-secret"


def test_live_fetch_enforces_the_response_size_bound():
    def transport(request, timeout):
        return b"x" * (MAX_RESPONSE_BYTES + 10)

    with pytest.raises(ValueError):
        fetch_live_models(BASES, "sk-orca-secret", transport=transport)


def test_live_fetch_rejects_a_body_that_is_not_json():
    def transport(request, timeout):
        return b"<html>not json</html>"

    with pytest.raises(json.JSONDecodeError):
        fetch_live_models(BASES, "sk-orca-secret", transport=transport)


# --------------------------------------------------------------------------- fallback


def test_live_discovery_is_authoritative_and_not_mixed_with_the_seed():
    result = _live_result()
    assert result.source == "live"
    assert result.degraded is False
    ids = {m.id for m in result.models}
    # Seed-only ids must not appear when live discovery succeeded.
    assert "google/gemini-3.5-flash" not in ids
    assert "orcarouter/auto" in ids  # present live


def test_model_class_is_mapped_onto_a_capability():
    result = _live_result(model_class="embedding")
    assert [m.id for m in result.models] == ["vendor/embedder"]
    assert result.models[0].id == "vendor/embedder"


def test_catalog_falls_back_to_the_verified_seed_on_transport_failure():
    import urllib.error

    def transport(request, timeout):
        raise urllib.error.URLError("dns failure")

    result = fetch_catalog(BASES, "sk-orca-fake", model_class="base", transport=transport)
    assert result.source == "seed"
    assert result.degraded is True
    assert result.reason and "unavailable" in result.reason
    ids = {m.id for m in result.models}
    assert ids == {m["id"] for m in SEED_MODELS}


def test_seed_fallback_keeps_reasoning_effort_and_modality_metadata():
    import urllib.error

    def transport(request, timeout):
        raise urllib.error.URLError("offline")

    result = fetch_catalog(BASES, None, model_class="base", transport=transport)
    gpt = next(m for m in result.models if m.id == "openai/gpt-5.5")
    assert gpt.reasoning is True
    assert gpt.reasoning_efforts == ("low", "medium", "high", "xhigh")
    assert "image" in gpt.input_modalities
    # Every seed model is a text chat model.
    assert all(m.supported_endpoint_types for m in result.models)


def test_seed_fallback_still_applies_capability_filtering():
    import urllib.error

    def transport(request, timeout):
        raise urllib.error.URLError("offline")

    result = fetch_catalog(BASES, None, model_class="embedding", transport=transport)
    assert result.source == "seed"
    assert result.models == []  # no embedding model is claimed in the seed


def test_hardcoded_seed_is_small_and_sourced():
    assert len(SEED_MODELS) == 5
    assert {m["id"] for m in SEED_MODELS} == {
        "openai/gpt-5.5",
        "anthropic/claude-opus-4.8",
        "google/gemini-3.5-flash",
        "deepseek/deepseek-v4-pro",
        "orcarouter/auto",
    }


def test_public_payload_never_leaks_pricing_or_key_material():
    result = _live_result()
    public = result.to_public()
    assert public["source"] == "live"
    assert public["count"] == len(result.models)
    for model in public["models"]:
        assert "pricing" not in model
        assert "sk-orca" not in json.dumps(model)
