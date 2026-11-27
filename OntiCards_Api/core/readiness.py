"""Bounded, read-only checks for serving account traffic."""

from threading import Lock
from time import monotonic

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from core.admin_bootstrap import AdminBootstrapError, read_bootstrap_collection_for_readiness
from core.admin_collection import check_weaviate_ready, verify_admin_collection


class ReadinessProbe:
    def __init__(self, database_url, users, weaviate_url):
        self.engine = create_engine(
            database_url, pool_size=1, max_overflow=0, pool_timeout=1,
            pool_pre_ping=True, hide_parameters=True,
            connect_args={"connect_timeout": 2, "tcp_user_timeout": 2000,
                          "options": "-c statement_timeout=1500"},
        )
        self.users = users
        self.weaviate_url = weaviate_url
        self.lock = Lock()
        self.until = 0
        self.result = ({"status": "not_ready", "check": "initializing"}, 503)

    def __call__(self):
        if monotonic() < self.until:
            return self.result
        if not self.lock.acquire(blocking=False):
            return {"status": "not_ready", "check": "checking"}, 503
        try:
            if monotonic() >= self.until:
                self.result = self._check()
                self.until = monotonic() + 2
            return self.result
        finally:
            self.lock.release()

    def _check(self):
        try:
            with self.engine.connect() as connection:
                binding = read_bootstrap_collection_for_readiness(connection, self.users)
        except SQLAlchemyError:
            return {"status": "not_ready", "check": "postgresql"}, 503
        except AdminBootstrapError:
            return {"status": "not_ready", "check": "collection_binding"}, 503

        try:
            check_weaviate_ready(self.weaviate_url, timeout=1.5)
        except AdminBootstrapError:
            return {"status": "not_ready", "check": "weaviate"}, 503

        if binding is not None:
            try:
                verify_admin_collection(self.weaviate_url, *binding, timeout=1.5)
            except AdminBootstrapError:
                return {"status": "not_ready", "check": "collection"}, 503
        return {"status": "ready"}, 200
