import os
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest.mock import patch

from core.signing_keys import application_signing_key, signing_key_value


class SigningKeyTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)

    def test_bad_inputs_fail_without_printing_values(self):
        cases = (None, "", "public-template-value", "a" * 64, bytes(range(32)).hex())
        for value in cases:
            with self.subTest(kind=type(value).__name__, length=len(value or "")):
                os.environ.pop("SECRET_KEY", None)
                if value is not None:
                    os.environ["SECRET_KEY"] = value
                with self.assertRaisesRegex(RuntimeError, "SECRET_KEY") as error:
                    application_signing_key()
                if value:
                    self.assertNotIn(value, str(error.exception))

    def test_same_key_is_rejected_without_exposing_it(self):
        key = secrets.token_hex(32)
        os.environ.update(SECRET_KEY=key, SSO_SECRET_KEY=key)
        with self.assertRaisesRegex(RuntimeError, "independent") as error:
            application_signing_key()
        self.assertNotIn(key, str(error.exception))

    def test_generated_and_mounted_keys_stay_byte_compatible(self):
        key, sso = secrets.token_hex(32), " " + secrets.token_hex(32) + " "
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "key"
            path.write_text(key + "\n", encoding="utf-8")
            path.chmod(0o600)
            os.environ.update(SECRET_KEY_FILE=str(path), SSO_SECRET_KEY=sso)
            self.assertTrue(application_signing_key() == key)
            self.assertTrue(signing_key_value("SSO_SECRET_KEY") == sso)
            os.environ["SECRET_KEY"] = key
            with self.assertRaisesRegex(RuntimeError, "either"):
                application_signing_key()

    @unittest.skipUnless(os.name == "posix", "requires POSIX file permissions")
    def test_insecure_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "key"
            path.write_text(secrets.token_hex(32), encoding="utf-8")
            path.chmod(0o644)
            os.environ["SECRET_KEY_FILE"] = str(path)
            with self.assertRaisesRegex(RuntimeError, "private"):
                application_signing_key()
            path.chmod(0o600)
            link = path.with_name("link")
            link.symlink_to(path)
            os.environ["SECRET_KEY_FILE"] = str(link)
            with self.assertRaisesRegex(RuntimeError, "private"):
                application_signing_key()
