"""Isolated SSO configuration and HTTP regressions (no database/model access).

Run: python -m unittest discover -s controllers/sso -p 'test_sso_api.py' -v
"""
import importlib.util
import os
from pathlib import Path
import secrets
import sys
import types
import unittest
from unittest.mock import Mock, patch

import flask
import jwt

HERE = Path(__file__).resolve().parent
API = HERE.parents[1]
LEGACY_KEY = "onticards_sso_secret_key_for_step2"


def load_controller():
    # Only persistence/collection integrations are replaced; Flask and JWT are real.
    replacements = {}
    for name, attrs in {
        "extensions.ext_database": {"db": Mock()},
        "models.users": {"User": Mock()},
        "controllers.weaviate_db_tool.weaviate_api": {
            "ensure_user_collection_exists": Mock()
        },
    }.items():
        module = types.ModuleType(name)
        module.__dict__.update(attrs)
        replacements[name] = module
    spec = importlib.util.spec_from_file_location("isolated_sso_api", HERE / "sso_api.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, replacements):
        spec.loader.exec_module(module)
    return module


class SSOTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"SSO_RATE_LIMIT_ENABLED": "0"}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.module = load_controller()
        self.key = secrets.token_urlsafe(48)

    def app(self):
        app = flask.Flask(__name__)
        app.register_blueprint(self.module.sso_bp)
        return app

    def test_invalid_keys_rejected_before_serving_requests(self):
        for value in (None, "", " " * 64, "x" * 31, LEGACY_KEY):
            with self.subTest(value=value):
                if value is None:
                    os.environ.pop("SSO_SECRET_KEY", None)
                else:
                    os.environ["SSO_SECRET_KEY"] = value
                with self.assertRaisesRegex(RuntimeError, "SSO_SECRET_KEY"):
                    self.app()

    def test_runtime_validation_still_fails_closed(self):
        os.environ["SSO_SECRET_KEY"] = self.key
        client = self.app().test_client()
        os.environ.pop("SSO_SECRET_KEY")
        token = jwt.encode(
            {"username": "alice", "user_id": "external-1"},
            LEGACY_KEY, algorithm="HS256"
        )
        with patch.object(self.module, "_get_or_create_user") as lookup:
            self.assertEqual(client.get("/sso/login", query_string={
                "token": token
            }).status_code, 500)
            lookup.assert_not_called()

    def test_valid_key_preserved_exactly(self):
        for value in (self.key, " " + self.key + " "):
            os.environ["SSO_SECRET_KEY"] = value
            self.app()
            self.assertEqual(self.module.get_sso_secret_key(), value)

    def test_32_character_boundary(self):
        os.environ["SSO_SECRET_KEY"] = secrets.token_hex(16)
        self.app()

    def test_errors_do_not_disclose_configured_key(self):
        os.environ["SSO_SECRET_KEY"] = "sensitive-short-value"
        with self.assertRaises(RuntimeError) as result:
            self.module.get_sso_secret_key()
        self.assertNotIn(os.environ["SSO_SECRET_KEY"], str(result.exception))

    def test_login_and_signature_controls(self):
        os.environ["SSO_SECRET_KEY"] = self.key
        app = self.app()
        user = types.SimpleNamespace(
            id="test-user", username="alice", nickname="Alice", role="normal"
        )
        payload = {"username": "alice", "user_id": "external-1", "exp": 4102444800}
        passport = types.ModuleType("core.passport")
        passport.PassportService = Mock()
        passport.PassportService.get_account_jwt_token.return_value = "local-session"
        with patch.object(self.module, "_get_or_create_user", return_value=user) as lookup, \
                patch.object(self.module, "login_user"), \
                patch.dict(sys.modules, {"core.passport": passport}):
            client = app.test_client()
            self.assertEqual(client.get("/sso/login").status_code, 400)
            for key in (LEGACY_KEY, secrets.token_urlsafe(48)):
                response = client.get("/sso/login", query_string={
                    "token": jwt.encode(payload, key, algorithm="HS256")
                })
                self.assertEqual(response.status_code, 401)
            lookup.assert_not_called()
            token = jwt.encode(payload, self.key, algorithm="HS256")
            response = client.get("/sso/login", query_string={"token": token})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["data"]["token"], "local-session")
            response = client.get("/sso/login", query_string={
                "token": token, "redirect_url": "/callback"
            })
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.location, "/callback#access_token=local-session")
            expired = jwt.encode(dict(payload, exp=1), self.key, algorithm="HS256")
            self.assertEqual(client.get("/sso/login", query_string={
                "token": expired
            }).status_code, 401)
            incomplete = jwt.encode({"exp": 4102444800}, self.key, algorithm="HS256")
            self.assertEqual(client.get("/sso/login", query_string={
                "token": incomplete
            }).status_code, 400)


if __name__ == "__main__":
    sys.path.insert(0, str(API))
    unittest.main()
