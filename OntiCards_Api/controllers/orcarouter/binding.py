"""Flask/SQLAlchemy binding for the OrcaRouter credential seam.

Persistence deliberately reuses what the project already has:

* the **key** lives in ``model_config.model_api_key`` on the canonical OrcaRouter row
  (``model_type = 'orcarouter'``, ``model_class = 'base'``) — the same place every other
  provider key is stored, so ``llm_call`` / ``qian_wen_llm`` / embedding / rerank keep working
  with no change;
* the **credential lifecycle** (source, monotonically increasing generation, needs-reauth) lives
  in ``system_configs``, which exists for exactly this kind of small runtime state.

No new secret store is introduced and the raw key is never returned to a browser.
"""

from __future__ import annotations

import json
import uuid
from typing import Optional

from sqlalchemy import func

from core.orcarouter.bases import (
    ORCAROUTER_MODEL_TYPES,
    OrcaRouterBases,
    bases_from_env,
    is_orcarouter_model_type,
    resolve_stored_url,
)
from core.orcarouter.credentials import (
    SOURCE_API_KEY,
    SOURCE_PKCE,
    STATE_ACTIVE,
    STATE_NEEDS_REAUTH,
    Credential,
    CredentialStorage,
)
from core.orcarouter.connect import ConnectSession, SessionStore
from extensions.ext_database import db
from models.model_config import Model_configuration
from models.system_configs import get_config, set_config

#: ``system_configs`` keys owned by this integration.
STATE_KEY = "orcarouter_credential_state"
REAUTH_KEY = "orcarouter_reauth_admin"

#: The canonical OrcaRouter row is the ``base`` class row; embedding/rerank rows follow the same
#: ``model_type`` marker.
CANONICAL_CLASS = "base"


def orcarouter_bases() -> OrcaRouterBases:
    return bases_from_env()


def _orcarouter_rows():
    return Model_configuration.query.filter(
        func.lower(Model_configuration.model_type).in_(ORCAROUTER_MODEL_TYPES)
    )


def get_orcarouter_row(model_class: str = CANONICAL_CLASS) -> Optional[Model_configuration]:
    """Return the OrcaRouter row for *model_class*, preferring the canonical ``base`` row."""
    row = _orcarouter_rows().filter_by(model_class=model_class).first()
    if row is None and model_class == CANONICAL_CLASS:
        row = _orcarouter_rows().first()
    return row


def _load_state() -> dict:
    raw = get_config(STATE_KEY)
    if not raw:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def _save_state(**updates) -> None:
    state = _load_state()
    state.update(updates)
    set_config(STATE_KEY, json.dumps(state), description="OrcaRouter credential lifecycle state")


def get_reauth_admin() -> Optional[str]:
    value = get_config(REAUTH_KEY)
    return value or None


def _set_reauth_admin(admin_id: Optional[str]) -> None:
    set_config(REAUTH_KEY, admin_id or "", description="OrcaRouter account awaiting reauthentication")


def get_stored_credential() -> Optional[Credential]:
    """Read the stored credential **without ever exposing the raw key outside the process**."""
    row = get_orcarouter_row()
    if row is None or not row.model_api_key:
        return None
    state = _load_state()
    needs_reauth = bool(get_reauth_admin())
    return Credential(
        api_key=row.model_api_key,
        source=state.get("source") or SOURCE_API_KEY,
        scope=state.get("scope") or "api",
        account_id=state.get("account_id"),
        generation=int(state.get("generation") or 0),
        state=STATE_NEEDS_REAUTH if needs_reauth else STATE_ACTIVE,
    )


def stored_key_for_requests() -> Optional[str]:
    """The key the inference path must use, or ``None`` when the account needs reauthentication."""
    credential = get_stored_credential()
    if credential is None or credential.state == STATE_NEEDS_REAUTH:
        return None
    return credential.api_key


def store_credential(credential: Credential, model_class: str = CANONICAL_CLASS) -> Credential:
    """Persist a credential from either adapter and bump its generation.

    Only after the new key is safely written is the needs-reauth flag cleared, so a failed
    replacement never destroys the previous credential (the old row value is overwritten in the
    same transaction, and the flag is only cleared once the write succeeded).
    """
    row = get_orcarouter_row(model_class)
    if row is None:
        row = Model_configuration(
            model_name="orcarouter-auto",
            model_type="orcarouter",
            model_api_key=None,
            model_class=model_class,
            url=orcarouter_bases().api_base,
        )
        db.session.add(row)

    row.model_api_key = credential.api_key
    if not row.url or is_orcarouter_model_type(row.model_type) and not row.url.strip():
        row.url = orcarouter_bases().api_base
    if not is_orcarouter_model_type(row.model_type):
        row.model_type = "orcarouter"

    generation = int(_load_state().get("generation") or 0) + 1
    db.session.commit()

    _save_state(
        source=credential.source,
        scope=credential.scope,
        account_id=credential.account_id,
        generation=generation,
    )
    _set_reauth_admin(None)

    return Credential(
        api_key=credential.api_key,
        source=credential.source,
        scope=credential.scope,
        account_id=credential.account_id,
        generation=generation,
        state=STATE_ACTIVE,
    )


def mark_needs_reauth(source: str, generation: int, admin_id: Optional[str] = None) -> bool:
    """Generation-safe transition to ``needs_reauth``.

    Only the credential whose stored generation matches the rejected request's generation is
    flagged, so a late failure from an older request cannot poison a freshly re-authorized key.
    """
    state = _load_state()
    current_generation = int(state.get("generation") or 0)
    current_source = state.get("source") or SOURCE_API_KEY
    if generation != current_generation or source != current_source:
        return False
    _set_reauth_admin(admin_id or "unknown")
    return True


def clear_credential() -> None:
    """Clear the stored key but keep the lifecycle row so the UI can show an explicit empty state."""
    row = get_orcarouter_row()
    if row is not None:
        row.model_api_key = None
        db.session.commit()
    _save_state(source=None, scope=None, account_id=None)
    _set_reauth_admin(None)


def request_target(model_class: str) -> tuple:
    """``(url, key)`` the inference path should use for *model_class*.

    Returns an empty key when the account needs reauthentication so the caller fails closed
    instead of sending a dead credential.
    """
    row = Model_configuration.query.filter_by(model_class=model_class).first()
    if row is None:
        return "", None
    return resolve_model_config(row)


def resolve_model_config(model_config) -> tuple:
    """``(api_url, api_key)`` for a ``model_config`` row.

    Non-OrcaRouter rows keep the project's established behaviour exactly: the stored ``url`` is
    used verbatim and the stored key is used as-is.  OrcaRouter rows store a *base* URL, so the
    concrete endpoint is derived from the row's ``model_class`` and the key comes from the
    credential seam (which returns ``None`` when the account needs reauthentication).
    """
    if model_config is None:
        return "", None
    model_type = getattr(model_config, "model_type", None)
    model_class = getattr(model_config, "model_class", "base") or "base"
    url = resolve_stored_url(model_type, model_class, getattr(model_config, "url", ""))
    if is_orcarouter_model_type(model_type):
        return url, stored_key_for_requests()
    return url, model_config.model_api_key


class FlaskOrcaRouterStorage(CredentialStorage):
    """Adapter that lets :class:`~core.orcarouter.connect.ConnectSessionManager` persist a key."""

    def load(self) -> Optional[Credential]:
        return get_stored_credential()

    def save(self, credential: Credential) -> Credential:
        return store_credential(credential)

    def clear(self) -> None:
        clear_credential()

    def mark_needs_reauth(self, provider: str, source: str, generation: int) -> bool:
        if provider != "orcarouter":
            return False
        return mark_needs_reauth(source, generation)


#: ``system_configs`` keys backing the pending PKCE sessions.
SESSIONS_KEY = "orcarouter_connect_sessions"
SESSIONS_GENERATION_KEY = "orcarouter_connect_generation"


def _read_sessions() -> list:
    raw = get_config(SESSIONS_KEY)
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return value if isinstance(value, list) else []


def _write_sessions(records: list) -> None:
    set_config(SESSIONS_KEY, json.dumps(records), description="OrcaRouter pending PKCE sessions")


class DbSessionStore(SessionStore):
    """Pending PKCE sessions in ``system_configs``.

    The verifier must stay server-side and survive across gunicorn workers, so sessions are
    persisted in the project's existing key/value table rather than in worker memory.
    """

    def put(self, session: ConnectSession) -> None:
        records = [r for r in _read_sessions() if r.get("id") != session.id]
        records.append(session.to_record())
        _write_sessions(records)

    def get(self, session_id: str) -> Optional[ConnectSession]:
        for record in _read_sessions():
            if record.get("id") == session_id:
                return ConnectSession.from_record(record)
        return None

    def items(self) -> list:
        return [ConnectSession.from_record(r) for r in _read_sessions()]

    def delete(self, session_id: str) -> None:
        _write_sessions([r for r in _read_sessions() if r.get("id") != session_id])

    def generation(self) -> int:
        try:
            return int(get_config(SESSIONS_GENERATION_KEY) or 0)
        except (TypeError, ValueError):
            return 0

    def set_generation(self, value: int) -> None:
        set_config(
            SESSIONS_GENERATION_KEY,
            str(value),
            description="OrcaRouter connect attempt generation",
        )


def new_session_id() -> str:
    return uuid.uuid4().hex
