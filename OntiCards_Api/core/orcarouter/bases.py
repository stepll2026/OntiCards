"""Origin and endpoint resolution for OrcaRouter.

Authentication and inference live on **different public origins** and the paths must not be
guessed from one another:

* auth / code exchange: ``https://www.orcarouter.ai`` (authorize ``/auth``, exchange
  ``/api/v1/auth/keys``)
* inference and catalog: ``https://api.orcarouter.ai/v1``

``https://api.orcarouter.ai/v1/auth/keys`` is a 404 — see the integration spec.  This module
therefore never derives one origin from the other; each is resolved independently.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Optional

DEFAULT_AUTH_BASE = "https://www.orcarouter.ai"
DEFAULT_API_BASE = "https://api.orcarouter.ai/v1"

AUTHORIZE_PATH = "/auth"
EXCHANGE_PATH = "/api/v1/auth/keys"

# Path appended to the inference base for each OntiCards model class.  OntiCards stores a base
# URL for OrcaRouter rows (the OpenAI-compatible convention) and derives the concrete endpoint,
# exactly like every other OpenAI-compatible client.
MODEL_CLASS_PATHS = {
    "base": "/chat/completions",
    "embedding": "/embeddings",
    "rerank": "/rerank",
}

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1"}


class OrcaRouterConfigError(ValueError):
    """Raised when an explicitly configured origin is unusable (e.g. plain HTTP to a remote host)."""


def _loopback_hostname(hostname: Optional[str]) -> bool:
    if not hostname:
        return False
    return hostname.strip("[]").lower() in {"localhost", "127.0.0.1", "::1"}


def is_loopback_url(url: str) -> bool:
    """True when *url* points at the local machine (``localhost``, ``127.0.0.1`` or ``[::1]``)."""
    from urllib.parse import urlsplit

    try:
        parts = urlsplit(url if "//" in url else f"//{url}")
    except ValueError:
        return False
    return _loopback_hostname(parts.hostname)


def _normalise_base(url: str, label: str) -> str:
    """Validate scheme policy and return the base without a trailing slash."""
    from urllib.parse import urlsplit

    candidate = (url or "").strip()
    if not candidate:
        return ""
    if "://" not in candidate:
        candidate = "https://" + candidate
    parts = urlsplit(candidate)
    if parts.scheme not in ("http", "https"):
        raise OrcaRouterConfigError(f"{label} must use http or https, got {parts.scheme!r}")
    if parts.scheme == "http" and not _loopback_hostname(parts.hostname):
        raise OrcaRouterConfigError(
            f"{label} must use https for non-loopback hosts (got {candidate!r}); "
            "plain http is only permitted for loopback development"
        )
    # Keep the path (a self-hosted deployment may sit under a prefix) but drop trailing slash.
    return candidate.rstrip("/")


@dataclass(frozen=True)
class OrcaRouterBases:
    """Resolved auth and inference origins."""

    auth_base: str
    api_base: str

    @property
    def authorize_url(self) -> str:
        return self.auth_base + AUTHORIZE_PATH

    @property
    def exchange_url(self) -> str:
        return self.auth_base + EXCHANGE_PATH

    def models_url(self, capability: Optional[str] = None) -> str:
        url = self.api_base + "/models"
        if capability:
            url = f"{url}?capability={capability}"
        return url

    def endpoint_for_class(self, model_class: str) -> str:
        return endpoint_for_model_class(self.api_base, model_class)


def bases_from_env(env: Optional[Mapping[str, str]] = None) -> OrcaRouterBases:
    """Resolve origins from the environment.

    Precedence: explicit ``ORCA_AUTH_BASE_URL`` / ``ORCA_API_BASE_URL`` win, then the shared
    ``ORCA_BASE_URL``, then the public defaults.  A shared base is treated as a *shared* origin:
    if the shared value already ends in ``/v1`` the API base keeps it, otherwise ``/v1`` is
    appended once.
    """
    source: Mapping[str, str] = env if env is not None else os.environ

    shared_raw = (source.get("ORCA_BASE_URL") or "").strip()
    auth_raw = (source.get("ORCA_AUTH_BASE_URL") or "").strip()
    api_raw = (source.get("ORCA_API_BASE_URL") or "").strip()

    shared = _normalise_base(shared_raw, "ORCA_BASE_URL") if shared_raw else ""

    if auth_raw:
        auth_base = _normalise_base(auth_raw, "ORCA_AUTH_BASE_URL")
    elif shared:
        auth_base = shared
    else:
        auth_base = DEFAULT_AUTH_BASE

    if api_raw:
        api_base = _normalise_base(api_raw, "ORCA_API_BASE_URL")
    elif shared:
        api_base = shared if shared.endswith("/v1") else shared + "/v1"
    else:
        api_base = DEFAULT_API_BASE

    return OrcaRouterBases(auth_base=auth_base, api_base=api_base)


def endpoint_for_model_class(api_base: str, model_class: str) -> str:
    """Return the concrete endpoint for an OntiCards model class on *api_base*.

    ``model_class`` is one of ``base`` / ``embedding`` / ``rerank``.  Unknown classes raise so a
    typo cannot silently POST to the base URL (which is what the project did before this change).
    """
    path = MODEL_CLASS_PATHS.get(model_class)
    if path is None:
        raise OrcaRouterConfigError(f"unsupported model_class for OrcaRouter: {model_class!r}")
    base = api_base.rstrip("/")
    # Tolerate an admin pasting the full endpoint instead of a base URL.
    if base.endswith(path):
        return base
    return base + path


#: ``model_type`` values that mark a ``model_config`` row as an OrcaRouter entry.  The column is
#: free text in this project, so the marker is matched case-insensitively.
ORCAROUTER_MODEL_TYPES = ("orcarouter", "orca-router", "orca_router")


def is_orcarouter_model_type(model_type: Optional[str]) -> bool:
    return (model_type or "").strip().lower() in ORCAROUTER_MODEL_TYPES


def resolve_stored_url(model_type: Optional[str], model_class: str, url: Optional[str]) -> str:
    """Turn a stored ``model_config.url`` into the URL the request path should POST to.

    Every other provider in this project stores a *full endpoint* and it is used verbatim; that
    behaviour is preserved exactly.  For an OrcaRouter row the stored value is a **base URL**
    (the OpenAI-compatible convention) and the concrete endpoint is derived from the model class,
    because ``https://api.orcarouter.ai/v1`` is not itself a request target.  A self-hosted base
    stored in the row wins over the environment so a per-row override stays possible.
    """
    stored = (url or "").strip()
    if not is_orcarouter_model_type(model_type):
        return stored
    base = stored or bases_from_env().api_base
    return endpoint_for_model_class(base, model_class)
