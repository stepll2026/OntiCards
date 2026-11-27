import base64
from contextlib import redirect_stderr, redirect_stdout
import hashlib
from io import StringIO
import os
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core.connect_info_encryptor import ConnectInfoEncryptor


class ConnectInfoKeyTests(unittest.TestCase):
    def test_missing_public_and_weak_values_fail_without_output(self):
        captured = StringIO()
        for value in ("", "onticards-dev-connect-key", "your-32-byte-base64-encoded-key-here", "z" * 44):
            with self.subTest(kind="missing" if not value else "invalid"):
                with patch.object(ConnectInfoEncryptor, "_instance", None), patch.dict(
                    os.environ, {"CONNECT_INFO_MASTER_KEY": value}
                ), redirect_stdout(captured), redirect_stderr(captured):
                    with self.assertRaisesRegex(ValueError, "CONNECT_INFO_MASTER_KEY") as error:
                        ConnectInfoEncryptor()
                    if value:
                        self.assertNotIn(value, str(error.exception))
        self.assertEqual(captured.getvalue(), "")

    def test_valid_legacy_data_remains_decryptable(self):
        material = bytes(range(1, 33))
        legacy_text = "synthetic-existing-key!x"
        with self.assertRaises(ValueError):
            base64.b64decode(legacy_text)
        cases = (
            (base64.b64encode(material).decode(), material),
            (base64.b64encode(material[:24]).decode(), material[:24]),
            (legacy_text, hashlib.sha256(legacy_text.encode()).digest()),
        )
        for configured, original in cases:
            nonce = os.urandom(12)
            ciphertext = AESGCM(original).encrypt(nonce, b"synthetic-connection", None)
            encrypted = "ENC$" + base64.b64encode(nonce + ciphertext).decode()
            with patch.object(ConnectInfoEncryptor, "_instance", None), patch.dict(
                os.environ, {"CONNECT_INFO_MASTER_KEY": configured}
            ):
                self.assertEqual(ConnectInfoEncryptor().decrypt(encrypted), "synthetic-connection")

    def test_new_key_survives_reinitialization(self):
        configured = base64.b64encode(os.urandom(32)).decode()
        with patch.dict(os.environ, {"CONNECT_INFO_MASTER_KEY": configured}):
            with patch.object(ConnectInfoEncryptor, "_instance", None):
                encrypted = ConnectInfoEncryptor().encrypt("synthetic-connection")
            with patch.object(ConnectInfoEncryptor, "_instance", None):
                self.assertEqual(ConnectInfoEncryptor().decrypt(encrypted), "synthetic-connection")
