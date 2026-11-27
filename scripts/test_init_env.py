import ast
import base64
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import tempfile
from threading import Barrier
import unittest
from unittest.mock import patch

from init_env import existing_config_warnings, initialize, ROOT


class InitializeEnvTests(unittest.TestCase):
    def test_both_templates_pass_the_application_sso_check(self):
        source = ROOT / "OntiCards_Api/controllers/sso/sso_api.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        validate = next(node for node in tree.body if getattr(node, "name", None) == "get_sso_secret_key")
        scope = {"os": os}
        exec(compile(ast.Module(body=[validate], type_ignores=[]), str(source), "exec"), scope)
        generated = []
        for template in (ROOT / ".env.prod", ROOT / "OntiCards_Api/.env.prod"):
            with self.subTest(template=template), tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp)
                (folder / ".env.prod").write_bytes(template.read_bytes())
                self.assertTrue(initialize(folder))
                data = (folder / ".env").read_text(encoding="utf-8")
                env = dict(line.split("=", 1) for line in data.splitlines() if "=" in line and not line.lstrip().startswith("#"))
                with patch.dict(os.environ, {"SSO_SECRET_KEY": env["SSO_SECRET_KEY"]}):
                    self.assertTrue(scope["get_sso_secret_key"]() == env["SSO_SECRET_KEY"])
                self.assertTrue(len(env["SECRET_KEY"]) == 64)
                self.assertTrue(env["SECRET_KEY"] != env["SSO_SECRET_KEY"])
                self.assertTrue(len(base64.b64decode(env["CONNECT_INFO_MASTER_KEY"], validate=True)) == 32)
                generated.append(env["SSO_SECRET_KEY"])
        self.assertTrue(generated[0] != generated[1])

    def test_existing_configuration_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            target = folder / ".env"
            original = b"# local overrides\r\nAPP_PORT=9220\r\n"
            target.write_bytes(original)
            self.assertFalse(initialize(folder))
            self.assertEqual(target.read_bytes(), original)

    def test_compose_initialization_keeps_private_signing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / ".env.prod").write_text("", encoding="utf-8")
            self.assertTrue(initialize(folder, signing_files=True))
            directory = folder / ".secrets"
            original = {p.name: p.read_bytes() for p in directory.iterdir()}
            self.assertEqual(len(original), 2)
            self.assertEqual(len(set(original.values())), 2)
            if os.name == "posix":
                self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
                for path in (*directory.iterdir(), folder / ".env"):
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertFalse(initialize(folder, signing_files=True))
            self.assertEqual({p.name: p.read_bytes() for p in directory.iterdir()}, original)
            self.assertEqual(existing_config_warnings(folder / ".env", signing_files=True), [])

    def test_public_data_key_warns_without_printing_or_replacing_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / ".env"
            original = b"CONNECT_INFO_MASTER_KEY=onticards-dev-connect-key\r\n"
            target.write_bytes(original)
            self.assertFalse(initialize(target.parent))
            warnings = "\n".join(existing_config_warnings(target))
            self.assertIn("public template value", warnings)
            self.assertNotIn("onticards-dev-connect-key", warnings)
            self.assertEqual(target.read_bytes(), original)

    def test_interrupted_flush_leaves_no_partial_env_and_retry_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / ".env.prod").write_text("APP_PORT=9107\n", encoding="utf-8")
            with patch("init_env.os.fsync", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    initialize(folder)
            self.assertEqual(sorted(p.name for p in folder.iterdir()), [".env.prod"])
            self.assertTrue(initialize(folder))
            self.assertFalse(initialize(folder))
            self.assertEqual(existing_config_warnings(folder / ".env"), [])

    def test_publish_error_removes_temp_and_leaves_no_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / ".env.prod").write_text("APP_PORT=9107\n", encoding="utf-8")
            with patch("init_env.os.link", side_effect=PermissionError):
                with self.assertRaises(PermissionError):
                    initialize(folder)
            self.assertEqual(sorted(p.name for p in folder.iterdir()), [".env.prod"])

    def test_publish_preserves_a_concurrent_winner(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / ".env.prod").write_text("APP_PORT=9107\n", encoding="utf-8")
            target = folder / ".env"
            original = b"APP_PORT=9220\n"

            def publish(_source, destination):
                destination.write_bytes(original)
                raise FileExistsError

            with patch("init_env.os.link", side_effect=publish):
                self.assertFalse(initialize(folder))
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(sorted(p.name for p in folder.iterdir()), [".env", ".env.prod"])

    def test_compose_concurrent_initialization_publishes_one_complete_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / ".env.prod").write_text("APP_PORT=9107\n", encoding="utf-8")
            begin = Barrier(4)

            def attempt():
                begin.wait(timeout=5)
                return initialize(folder, signing_files=True)

            with ThreadPoolExecutor(max_workers=4) as pool:
                jobs = [pool.submit(attempt) for _ in range(4)]
                results = [job.result(timeout=10) for job in jobs]

            self.assertEqual(results.count(True), 1)
            keys = [file.read_bytes() for file in (folder / ".secrets").iterdir()]
            self.assertEqual(len(keys), 2)
            self.assertEqual(len(set(keys)), 2)
            self.assertTrue(all(len(key.strip()) == 64 for key in keys))
            self.assertEqual(existing_config_warnings(folder / ".env", signing_files=True), [])

    def test_config_diagnostics_do_not_reveal_invalid_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / ".env"
            sample = "sensitive-local-placeholder"
            target.write_text(f'SSO_SECRET_KEY="{sample}"\nSECRET_KEY=${{SITE_SECRET}}\n', encoding="utf-8")
            output = "\n".join(existing_config_warnings(target))
            self.assertNotIn(sample, output)
            self.assertNotIn("SITE_SECRET", output)
            self.assertIn("fewer than 32", output)
            self.assertIn("contains interpolation", output)
            self.assertIn("CONNECT_INFO_MASTER_KEY is missing", output)


if __name__ == "__main__":
    unittest.main()
