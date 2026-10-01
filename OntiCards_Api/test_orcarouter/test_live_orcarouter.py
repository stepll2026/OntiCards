"""Live OrcaRouter checks through the code paths this integration added.

These are the only tests that need a real credential.  They are skipped unless
``ORCAROUTER_API_KEY`` is present, and they never print the key or any response that could
contain one.

    ORCAROUTER_API_KEY=sk-orca-… python -m pytest OntiCards_Api/test_orcarouter/test_live_orcarouter.py -v

What they prove:

* model discovery runs through :func:`core.orcarouter.catalog.fetch_catalog` against the real
  configured origin, and every returned model is text-capable;
* the capability filter is applied for the classes this project speaks;
* inference runs against the endpoint the integration derives for an OrcaRouter row
  (``…/v1/chat/completions``) with the same Bearer header the request path builds.
"""

import json
import os
import urllib.error
import urllib.request

import pytest

from core.orcarouter.bases import bases_from_env, endpoint_for_model_class, resolve_stored_url
from core.orcarouter.catalog import TEXT_ENDPOINT_TYPES, fetch_catalog
from core.orcarouter.credentials import ApiKeyCredentialProvider, InMemoryCredentialStorage

RAW_KEY = os.environ.get("ORCAROUTER_API_KEY")
pytestmark = pytest.mark.skipif(
    not RAW_KEY, reason="ORCAROUTER_API_KEY is required for the live checks"
)

#: Models that are gateway aliases rather than upstream models; prefer a concrete one when a
#: workspace restricts access to the aliases.
PREFERRED = ("deepseek/deepseek-v4-flash", "deepseek/deepseek-v4-pro")


@pytest.fixture(scope="module")
def credential():
    # The live key goes through the same adapter a user's pasted key goes through.
    return ApiKeyCredentialProvider(InMemoryCredentialStorage()).acquire(RAW_KEY)


@pytest.fixture(scope="module")
def catalog(credential):
    return fetch_catalog(bases_from_env(), credential.api_key, model_class="base")


def test_live_model_discovery_is_authoritative(credential, catalog):
    assert catalog.source == "live", f"live discovery failed: {catalog.reason}"
    assert catalog.degraded is False
    ids = [m.id for m in catalog.models]
    assert ids, "the live catalog returned no chat models"
    # Namespaced ids must survive verbatim.
    assert all("/" in model_id for model_id in ids)


def test_every_live_chat_model_is_text_capable(catalog):
    for model in catalog.models:
        types = {t.lower() for t in model.supported_endpoint_types}
        assert types & TEXT_ENDPOINT_TYPES, f"{model.id} has no text endpoint type: {types}"


def test_live_embedding_and_rerank_filters_only_keep_exact_matches(credential):
    for model_class, required in (("embedding", "embeddings"), ("rerank", "jina-rerank")):
        result = fetch_catalog(bases_from_env(), credential.api_key, model_class=model_class)
        for model in result.models:
            types = {t.lower() for t in model.supported_endpoint_types}
            assert required in types, f"{model.id} does not declare {required}: {types}"
        print(f"[live] {model_class}: {len(result.models)} model(s) from source={result.source}")


def test_reasoning_metadata_survives_live_discovery(catalog):
    """Metadata must not be dropped when live discovery replaces the seed."""
    for model in catalog.models:
        if model.reasoning_efforts:
            assert all(isinstance(effort, str) for effort in model.reasoning_efforts)


def test_live_chat_through_the_endpoint_the_integration_derives(credential, catalog):
    bases = bases_from_env()
    # This is the exact URL an OrcaRouter row resolves to in the request path.
    url = resolve_stored_url("orcarouter", "base", bases.api_base)
    assert url == endpoint_for_model_class(bases.api_base, "base")
    assert url.endswith("/chat/completions")
    assert url.startswith("https://api.orcarouter.ai/v1")

    live_ids = {m.id for m in catalog.models}
    candidates = [m for m in PREFERRED if m in live_ids] + [
        m.id for m in catalog.models if not m.id.startswith("orcarouter/")
    ]
    assert candidates, "no live chat model is available to call"

    last_error = None
    for model_id in candidates:
        request = urllib.request.Request(
            url,
            data=json.dumps(
                {
                    "model": model_id,
                    "messages": [{"role": "user", "content": "Reply with the single word: pong"}],
                    "max_tokens": 16,
                }
            ).encode(),
            headers={
                # Identical to the header the request path builds.
                "Authorization": f"Bearer {credential.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            last_error = f"{model_id}: HTTP {exc.code}"
            if exc.code in (401, 403):
                continue  # this key cannot use this model; try the next one
            raise
        content = (payload.get("choices") or [{}])[0].get("message", {}).get("content")
        usage = payload.get("usage") or {}
        assert content, f"empty completion from {model_id}"
        assert usage.get("total_tokens", 0) > 0
        print(f"[live] {model_id} -> {content!r} (total_tokens={usage.get('total_tokens')})")
        return

    pytest.fail(f"no callable live chat model for this key ({last_error})")
