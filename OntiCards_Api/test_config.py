"""DSN round-trip tests; no application bootstrap or database connection."""
import os
import unittest
from unittest.mock import patch

with patch("dotenv.load_dotenv"):
    from config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url


class DatabaseURLTests(unittest.TestCase):
    def check_url(self, **overrides):
        values = dict(DB_USERNAME="onti", DB_PASSWORD="password", DB_HOST="db",
                      DB_PORT="5432", DB_DATABASE="onticards", DB_CHARSET="")
        values.update(overrides)
        with patch.dict(os.environ, values, clear=True):
            uri = Config().SQLALCHEMY_DATABASE_URI
        from flask import Flask
        from flask_sqlalchemy import SQLAlchemy
        app = Flask(__name__)
        app.config["SQLALCHEMY_DATABASE_URI"] = uri
        db = SQLAlchemy(app)
        with app.app_context():
            self.assertEqual(db.engine.url, make_url(uri))
            db.engine.dispose()
        url = make_url(uri)
        self.assertEqual(url.username, values["DB_USERNAME"])
        self.assertEqual(url.password, values["DB_PASSWORD"])
        self.assertEqual(url.database, values["DB_DATABASE"])
        self.assertEqual(url.host, values["DB_HOST"].strip("[]"))
        self.assertEqual(url.port, int(values["DB_PORT"]))
        engine = create_engine(uri)
        try:
            args, kwargs = engine.dialect.create_connect_args(url)
            self.assertEqual(kwargs.get("user", ""), values["DB_USERNAME"])
            self.assertEqual(kwargs.get("password", ""), values["DB_PASSWORD"])
            self.assertEqual(kwargs["dbname"], values["DB_DATABASE"])
            self.assertEqual(kwargs["host"], values["DB_HOST"].strip("[]"))
            if values["DB_CHARSET"]:
                self.assertEqual(kwargs["client_encoding"], values["DB_CHARSET"])
            else:
                self.assertNotIn("client_encoding", kwargs)
        finally:
            engine.dispose()

    def test_plain_configuration(self):
        self.check_url()

    def test_reserved_characters(self):
        self.check_url(DB_USERNAME="user@:/?#%+", DB_PASSWORD="p@:/?#%+",
                       DB_DATABASE="db@:/?#%+")

    def test_spaces_and_unicode(self):
        self.check_url(DB_USERNAME="用户 name", DB_PASSWORD="密 码+",
                       DB_DATABASE="业务 data")

    def test_ipv4(self):
        self.check_url(DB_HOST="127.0.0.1")

    def test_bracketed_ipv6(self):
        self.check_url(DB_HOST="[::1]")

    def test_query_encoding(self):
        self.check_url(DB_CHARSET="UTF8&application_name=unexpected")

    def test_empty_credentials(self):
        self.check_url(DB_USERNAME="", DB_PASSWORD="")


if __name__ == "__main__":
    unittest.main(verbosity=2)
