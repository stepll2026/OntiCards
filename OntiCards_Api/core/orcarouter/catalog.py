"""Bounded live model discovery for OrcaRouter, with a verified cold-start fallback.

``GET {api_base}/models`` is the single source of truth for the model list.  The catalog is
filtered per capability before it ever reaches a model selector, so the UI cannot offer a model
the request path cannot speak:

============================  =========================================================
capability                    rule
============================  =========================================================
``chat`` (model_class base)   ``supported_endpoint_types`` contains at least one of
                              ``openai``/``openai-response``/``anthropic``/``gemini`` and
                              declares no non-text-only endpoint type
multimodal understanding      chat **and** ``architecture.input_modalities`` explicitly
                              contains the modality actually being uploaded (fail closed:
                              a model that does not declare the modality is excluded)
``embedding``                 ``?capability=embedding`` or ``supported_endpoint_types``
                              contains ``embeddings``
``image``                     ``?capability=image`` or ``image-generation``
``video``                     ``jina-rerank``'s sibling: strictly ``openai-video``
``rerank``                    strictly ``jina-rerank``
============================  =========================================================

Live discovery always wins.  The verified seed is used **only** when live discovery fails, is
clearly marked as a fallback in the result, and is never mixed into a successful live response.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.orcarouter.bases import OrcaRouterBases

TEXT_ENDPOINT_TYPES = frozenset({"openai", "openai-response", "anthropic", "gemini"})
NON_TEXT_ENDPOINT_TYPES = frozenset(
    {"image-generation", "openai-video", "jina-rerank", "embeddings"}
)
EMBEDDING_ENDPOINT_TYPES = frozenset({"embeddings"})

#: Hard bounds so a catalog response can never consume unbounded memory.
MAX_RESPONSE_BYTES = 512 * 1024
MAX_ITEMS = 300
DEFAULT_TIMEOUT = 12.0

#: Maps an OntiCards model class onto the catalog capability it must be filtered by.
MODEL_CLASS_CAPABILITY = {
    "base": "chat",
    "embedding": "embedding",
    "rerank": "rerank",
}

#: Small, verified cold-start seed.  Used only when live discovery fails.  These ids are present
#: in the default public catalog (verified 2026-10-01) and keep their metadata, notably the
#: GPT-5.5 reasoning-effort ladder, so an outage does not silently downgrade capabilities.
SEED_MODELS: List[Dict[str, object]] = [
    {
        "id": "openai/gpt-5.5",
        "name": "OpenAI: GPT-5.5",
        "context_length": 400000,
        "supported_endpoint_types": ["openai", "openai-response", "anthropic"],
        "architecture": {"input_modalities": ["text", "image"]},
        "reasoning": True,
        "reasoning_efforts": ["low", "medium", "high", "xhigh"],
    },
    {
        "id": "anthropic/claude-opus-4.8",
        "name": "Anthropic: Claude Opus 4.8",
        "context_length": 200000,
        "supported_endpoint_types": ["anthropic", "openai"],
        "architecture": {"input_modalities": ["text", "image"]},
        "reasoning": True,
        "reasoning_efforts": ["low", "medium", "high"],
    },
    {
        "id": "google/gemini-3.5-flash",
        "name": "Google: Gemini 3.5 Flash",
        "context_length": 1000000,
        "supported_endpoint_types": ["gemini", "openai", "openai-response"],
        "architecture": {"input_modalities": ["text", "image"]},
        "reasoning": False,
    },
    {
        "id": "deepseek/deepseek-v4-pro",
        "name": "DeepSeek: DeepSeek V4 Pro",
        "context_length": 1048576,
        "supported_endpoint_types": ["openai", "openai-response", "anthropic"],
        "architecture": {"input_modalities": ["text"]},
        "reasoning": False,
    },
    {
        "id": "orcarouter/auto",
        "name": "OrcaRouter: Auto",
        "context_length": 1000000,
        "supported_endpoint_types": ["openai", "openai-response", "anthropic", "gemini"],
        "architecture": {"input_modalities": ["text"]},
        "reasoning": False,
    },
]


@dataclass(frozen=True)
class CatalogModel:
    """One catalog record, reduced to the metadata the client actually uses."""

    id: str
    name: str
    context_length: Optional[int]
    supported_endpoint_types: tuple
    input_modalities: tuple
    reasoning: bool
    reasoning_efforts: tuple = ()
    raw: Dict[str, object] = field(default_factory=dict, compare=False, repr=False)

    @property
    def vendor(self) -> str:
        return self.id.split("/", 1)[0] if "/" in self.id else ""

    def to_public(self) -> Dict[str, object]:
        """Minimal metadata for the browser — never includes pricing or any credential."""
        payload: Dict[str, object] = {
            "id": self.id,
            "name": self.name or self.id,
            "supported_endpoint_types": list(self.supported_endpoint_types),
            "input_modalities": list(self.input_modalities),
            "reasoning": self.reasoning,
            "reasoning_efforts": list(self.reasoning_efforts),
        }
        if self.context_length:
            payload["context_length"] = self.context_length
        return payload


@dataclass
class CatalogResult:
    """Outcome of a discovery attempt."""

    models: List[CatalogModel]
    source: str  # "live" | "seed"
    degraded: bool
    reason: Optional[str] = None
    total_before_filter: int = 0

    def to_public(self) -> Dict[str, object]:
        return {
            "models": [m.to_public() for m in self.models],
            "source": self.source,
            "degraded": self.degraded,
            "reason": self.reason,
            "count": len(self.models),
            "total_before_filter": self.total_before_filter,
        }


def _as_str_tuple(value: object) -> tuple:
    if isinstance(value, (list, tuple)):
        return tuple(str(v) for v in value if isinstance(v, str))
    return ()


def parse_models(payload: object, max_items: int = MAX_ITEMS) -> List[CatalogModel]:
    """Convert a raw ``/v1/models`` payload into :class:`CatalogModel` records.

    Records that do not have the accepted shape are dropped rather than trusted; the item count
    is bounded.
    """
    if isinstance(payload, dict):
        items = payload.get("data")
    else:
        items = payload
    if not isinstance(items, list):
        return []

    models: List[CatalogModel] = []
    for item in items[: max(0, max_items)]:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        architecture = item.get("architecture")
        modalities = _as_str_tuple(
            architecture.get("input_modalities") if isinstance(architecture, dict) else None
        )
        context_length = item.get("context_length")
        if not isinstance(context_length, int) or context_length <= 0:
            context_length = None
        efforts = _as_str_tuple(item.get("reasoning_efforts"))
        name = item.get("name")
        models.append(
            CatalogModel(
                id=model_id,
                name=name if isinstance(name, str) else model_id,
                context_length=context_length,
                supported_endpoint_types=_as_str_tuple(item.get("supported_endpoint_types")),
                input_modalities=modalities,
                reasoning=bool(item.get("reasoning", False)),
                reasoning_efforts=efforts,
                raw=item,
            )
        )
    return models


def _endpoint_types(model: CatalogModel) -> set:
    return {t.lower() for t in model.supported_endpoint_types}


def filter_models(
    models: Sequence[CatalogModel],
    capability: Optional[str] = None,
    required_modalities: Optional[Iterable[str]] = None,
) -> List[CatalogModel]:
    """Apply the capability rules above.  ``capability=None`` returns the catalog unchanged."""
    required = {m.lower() for m in (required_modalities or []) if m}
    selected: List[CatalogModel] = []

    for model in models:
        types = _endpoint_types(model)
        if capability and capability != "all":
            if capability == "chat":
                if not (types & TEXT_ENDPOINT_TYPES):
                    continue
                # A model dedicated to image/video/rerank/embedding output is not a text chat model.
                if types & NON_TEXT_ENDPOINT_TYPES:
                    continue
            elif capability == "embedding":
                if not (types & EMBEDDING_ENDPOINT_TYPES):
                    continue
            elif capability == "image":
                if "image-generation" not in types:
                    continue
            elif capability == "video":
                if "openai-video" not in types:
                    continue
            elif capability == "rerank":
                if "jina-rerank" not in types:
                    continue
            else:
                continue  # unknown capability: fail closed

        if required:
            declared = {m.lower() for m in model.input_modalities}
            # Fail closed: a model that does not *explicitly* declare the modality is excluded,
            # even if its id suggests it supports it.
            if not required.issubset(declared):
                continue

        selected.append(model)
    return selected


def _default_transport(request: Request, timeout: float) -> bytes:
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https origin
        return response.read(MAX_RESPONSE_BYTES + 1)


def fetch_live_models(
    bases: OrcaRouterBases,
    api_key: Optional[str],
    capability: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
    transport: Optional[Callable[[Request, float], bytes]] = None,
) -> List[CatalogModel]:
    """Fetch and parse the live catalog.  Raises on transport or HTTP failure (caller falls back)."""
    request = Request(
        bases.models_url(capability),
        headers={
            "Accept": "application/json",
            **({"Authorization": f"Bearer {api_key}"} if api_key else {}),
        },
        method="GET",
    )
    raw = (transport or _default_transport)(request, timeout)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("catalog response exceeded the size bound")
    payload = json.loads(raw.decode("utf-8", "replace") or "{}")
    return parse_models(payload)


def fetch_catalog(
    bases: OrcaRouterBases,
    api_key: Optional[str],
    model_class: Optional[str] = None,
    capability: Optional[str] = None,
    required_modalities: Optional[Iterable[str]] = None,
    timeout: float = DEFAULT_TIMEOUT,
    transport: Optional[Callable[[Request, float], bytes]] = None,
) -> CatalogResult:
    """Discover models for a capability, falling back to the verified seed on failure.

    ``model_class`` (``base``/``embedding``/``rerank``) is mapped onto a capability when
    ``capability`` is not given explicitly.
    """
    resolved_capability = capability or MODEL_CLASS_CAPABILITY.get(model_class or "", None)
    if model_class and capability is None and resolved_capability is None:
        # Unknown model class: do not guess a capability filter.
        resolved_capability = None

    try:
        live = fetch_live_models(
            bases, api_key, capability=resolved_capability, timeout=timeout, transport=transport
        )
        filtered = filter_models(live, resolved_capability, required_modalities)
        return CatalogResult(
            models=filtered,
            source="live",
            degraded=False,
            total_before_filter=len(live),
        )
    except (HTTPError, URLError, OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        seed = parse_models({"data": SEED_MODELS})
        filtered = filter_models(seed, resolved_capability, required_modalities)
        return CatalogResult(
            models=filtered,
            source="seed",
            degraded=True,
            reason=f"live model discovery unavailable ({type(exc).__name__})",
            total_before_filter=len(seed),
        )
