"""Flask transport for the OrcaRouter provider.

This is a thin adapter: all protocol and credential logic lives in ``core.orcarouter``.  The
blueprint is registered under ``/console/api/orcarouter`` and is reachable from the browser, so it
must never return the PKCE verifier, the raw stored key of an unrelated provider, or a credential
belonging to a different account.

Endpoints (all ``POST`` unless noted):

============================  =========================================================
``GET  /status``              which authentication choices exist and what is stored
``POST /api-key``             save a pasted ``sk-orca-…`` key
``POST /api-key/clear``       remove the stored key
``POST /connect/start``       begin a Flow B attempt and return the authorize URL
``GET  /connect/<id>``        poll attempt state (never returns the verifier)
``POST /connect/<id>/code``   exchange the pasted code
``POST /connect/<id>/cancel`` cancel (explicit, modal close, ``pagehide``)
``GET  /models``              capability-filtered model catalog for a model selector
============================  =========================================================
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, request
from flask_restful import Api, Resource

from core.orcarouter.bases import OrcaRouterConfigError, bases_from_env
from core.orcarouter.catalog import MODEL_CLASS_CAPABILITY, fetch_catalog
from core.orcarouter.connect import ConnectSessionManager
from core.orcarouter.credentials import (
    SOURCE_API_KEY,
    SOURCE_PKCE,
    ApiKeyCredentialProvider,
    CredentialError,
    PkceCredentialProvider,
    classify_relay_status,
    mask_api_key,
)
from controllers.orcarouter import binding

orcarouter_api = Blueprint("orcarouter_api", __name__)
api = Api(orcarouter_api)

#: Restrict catalog requests to the capabilities this project actually speaks.
_ALLOWED_CAPABILITIES = {"chat", "embedding", "image", "video", "rerank"}


def resp(code: int = 200, msg: str = "success", data: Any = None, http_status: int = 200):
    return {"code": code, "msg": msg, "data": data if data is not None else {}}, http_status


def _payload() -> Dict[str, Any]:
    return request.get_json(force=True, silent=True) or {}


def _storage() -> binding.FlaskOrcaRouterStorage:
    return binding.FlaskOrcaRouterStorage()


def _manager() -> ConnectSessionManager:
    return ConnectSessionManager(
        bases=bases_from_env(),
        provider=PkceCredentialProvider(_storage()),
        store=binding.DbSessionStore(),
    )


def _status_payload() -> Dict[str, Any]:
    credential = binding.get_stored_credential()
    row = binding.get_orcarouter_row()
    bases = bases_from_env()
    needs_reauth = bool(binding.get_reauth_admin())
    return {
        "provider": "orcarouter",
        "auth_base": bases.auth_base,
        "api_base": bases.api_base,
        "configured": row is not None,
        "has_key": bool(row and row.model_api_key),
        # The browser only ever learns a masked placeholder.
        "api_key_masked": mask_api_key(row.model_api_key if row else None),
        "credential_source": credential.source if credential else None,
        "scope": credential.scope if credential else None,
        "generation": credential.generation if credential else 0,
        "needs_reauth": needs_reauth,
        "auth_methods": [
            {"id": SOURCE_API_KEY, "label": "OrcaRouter - API", "available": True},
            {"id": SOURCE_PKCE, "label": "OrcaRouter - Auth", "available": True},
        ],
        "key_dashboard_url": "https://www.orcarouter.ai/console/token",
        "connected_apps_url": "https://www.orcarouter.ai/console/authorized-apps",
    }


class OrcaRouterStatusAPI(Resource):
    """``GET /status`` — what the settings UI renders on load."""

    def get(self):
        try:
            return resp(200, "success", _status_payload(), 200)
        except Exception as exc:  # pragma: no cover - defensive
            return resp(500, f"failed to read OrcaRouter status: {exc}", {}, 500)


class OrcaRouterApiKeyAPI(Resource):
    """``POST /api-key`` — adapter #1: paste an existing key."""

    def post(self):
        payload = _payload()
        provider = ApiKeyCredentialProvider(_storage())
        try:
            credential = provider.acquire(payload.get("api_key") or "", payload.get("account_id"))
        except CredentialError as exc:
            return resp(400, str(exc), {}, 400)
        return resp(200, "saved", {
            "configured": True,
            "api_key_masked": mask_api_key(credential.api_key),
            "credential_source": credential.source,
            "generation": credential.generation,
            "needs_reauth": False,
        }, 200)


class OrcaRouterApiKeyClearAPI(Resource):
    """``POST /api-key/clear`` — remove the stored credential."""

    def post(self):
        provider = ApiKeyCredentialProvider(_storage())
        provider.clear()
        binding.clear_credential()
        return resp(200, "cleared", _status_payload(), 200)


class OrcaRouterConnectStartAPI(Resource):
    """``POST /connect/start`` — adapter #2: begin the PKCE login."""

    def post(self):
        try:
            manager = _manager()
            session = manager.start()
        except OrcaRouterConfigError as exc:
            return resp(400, str(exc), {}, 400)
        return resp(200, "started", session.public(), 200)


class OrcaRouterConnectSessionAPI(Resource):
    """``GET /connect/<id>`` — poll attempt state."""

    def get(self, session_id: str):
        session = _manager().get(session_id)
        if session is None:
            return resp(404, "authorization attempt not found", {}, 404)
        return resp(200, "success", session.public(), 200)


class OrcaRouterConnectCodeAPI(Resource):
    """``POST /connect/<id>/code`` — exchange the code the user pasted."""

    def post(self, session_id: str):
        payload = _payload()
        manager = _manager()
        try:
            credential = manager.submit_code(
                session_id, payload.get("code") or "", payload.get("state")
            )
        except Exception as exc:  # noqa: BLE001 - PkceFlowError carries the reason
            reason = getattr(exc, "reason", "exchange_failed")
            status = getattr(exc, "status", None) or 400
            return resp(status, str(exc), {"reason": reason}, status)
        return resp(200, "connected", {
            "connected": True,
            "credential_source": credential.source,
            "scope": credential.scope,
            "generation": credential.generation,
            "api_key_masked": credential.masked_key,
        }, 200)


class OrcaRouterConnectCancelAPI(Resource):
    """``POST /connect/<id>/cancel`` — explicit cancel, provider switch, ``pagehide``."""

    def post(self, session_id: str):
        payload = _payload()
        reason = payload.get("reason") or "cancelled"
        cancelled = _manager().cancel(session_id, reason)
        return resp(200, "cancelled" if cancelled else "not_found", {"cancelled": cancelled}, 200)


class OrcaRouterModelsAPI(Resource):
    """``GET /models`` — capability-filtered catalog for a model selector.

    The key is held server-side and only minimal metadata reaches the browser.
    """

    def get(self):
        model_class = (request.args.get("model_class") or "base").strip()
        capability = (request.args.get("capability") or "").strip() or MODEL_CLASS_CAPABILITY.get(model_class)
        if capability not in _ALLOWED_CAPABILITIES:
            return resp(400, f"unsupported capability {capability!r}", {}, 400)
        modalities = [m for m in (request.args.get("modalities") or "").split(",") if m.strip()]
        try:
            result = fetch_catalog(
                bases=bases_from_env(),
                api_key=binding.stored_key_for_requests(),
                model_class=model_class,
                capability=capability,
                required_modalities=modalities or None,
            )
        except OrcaRouterConfigError as exc:
            return resp(400, str(exc), {}, 400)
        return resp(200, "success", result.to_public(), 200)


class OrcaRouterRelayStatusAPI(Resource):
    """``POST /relay-status`` — apply a relay status to the exact credential generation.

    Called by the request path when the inference call fails.  This is a *terminal* transition:
    an OrcaRouter key is durable and there is no refresh grant to attempt.
    """

    def post(self):
        payload = _payload()
        try:
            status_code = int(payload.get("status_code"))
        except (TypeError, ValueError):
            return resp(400, "status_code is required", {}, 400)
        action = classify_relay_status(status_code)
        credential = binding.get_stored_credential()
        marked = False
        if action == "needs_reauth" and credential is not None:
            marked = binding.mark_needs_reauth(credential.source, credential.generation)
        return resp(200, "success", {
            "action": action,
            "marked_needs_reauth": marked,
            "generation": credential.generation if credential else None,
            "refresh_attempted": False,
        }, 200)


api.add_resource(OrcaRouterStatusAPI, "/status")
api.add_resource(OrcaRouterApiKeyAPI, "/api-key")
api.add_resource(OrcaRouterApiKeyClearAPI, "/api-key/clear")
api.add_resource(OrcaRouterConnectStartAPI, "/connect/start")
api.add_resource(OrcaRouterConnectSessionAPI, "/connect/<string:session_id>")
api.add_resource(OrcaRouterConnectCodeAPI, "/connect/<string:session_id>/code")
api.add_resource(OrcaRouterConnectCancelAPI, "/connect/<string:session_id>/cancel")
api.add_resource(OrcaRouterModelsAPI, "/models")
api.add_resource(OrcaRouterRelayStatusAPI, "/relay-status")
