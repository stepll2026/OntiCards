"""OrcaRouter provider integration for OntiCards.

This package is deliberately free of Flask, SQLAlchemy and application state so the credential,
catalog and connect logic can be unit tested in isolation.  The Flask layer
(``controllers/orcarouter/orcarouter_api.py``) is a thin transport adapter on top of it.
"""

from core.orcarouter.bases import (
    DEFAULT_API_BASE,
    DEFAULT_AUTH_BASE,
    ORCAROUTER_MODEL_TYPES,
    OrcaRouterBases,
    OrcaRouterConfigError,
    bases_from_env,
    endpoint_for_model_class,
    is_loopback_url,
    is_orcarouter_model_type,
    resolve_stored_url,
)
from core.orcarouter.catalog import (
    CatalogResult,
    CatalogModel,
    SEED_MODELS,
    fetch_catalog,
    filter_models,
    parse_models,
)
from core.orcarouter.credentials import (
    STATE_ACTIVE,
    STATE_NEEDS_REAUTH,
    ApiKeyCredentialProvider,
    Credential,
    CredentialError,
    CredentialStorage,
    InMemoryCredentialStorage,
    PkceCredentialProvider,
    classify_relay_status,
    mask_api_key,
    redact,
    redact_secrets,
)
from core.orcarouter.connect import (
    ConnectSessionManager,
    InvalidStateError,
    PkceFlowError,
)

__all__ = [
    "DEFAULT_API_BASE",
    "DEFAULT_AUTH_BASE",
    "OrcaRouterBases",
    "OrcaRouterConfigError",
    "bases_from_env",
    "endpoint_for_model_class",
    "is_loopback_url",
    "is_orcarouter_model_type",
    "resolve_stored_url",
    "ORCAROUTER_MODEL_TYPES",
    "CatalogResult",
    "CatalogModel",
    "SEED_MODELS",
    "fetch_catalog",
    "filter_models",
    "parse_models",
    "STATE_ACTIVE",
    "STATE_NEEDS_REAUTH",
    "ApiKeyCredentialProvider",
    "Credential",
    "CredentialError",
    "CredentialStorage",
    "InMemoryCredentialStorage",
    "PkceCredentialProvider",
    "classify_relay_status",
    "mask_api_key",
    "redact",
    "redact_secrets",
    "ConnectSessionManager",
    "InvalidStateError",
    "PkceFlowError",
]
