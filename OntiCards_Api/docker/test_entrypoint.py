"""Run with python3 -m unittest discover -s OntiCards_Api/docker -p 'test_*.py' -v.

Requires Bash. Only the image WORKDIR path is relocated to a temporary fixture;
Flask and Gunicorn are stand-ins, so no application or database is started.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which("bash"), "Bash is required")
class EntrypointTest(unittest.TestCase):
    def run_entrypoint(self, variables=None, env_file=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / "onticards_api"
            app.mkdir()
            if env_file is not None:
                (app / ".env").write_text(env_file, encoding="utf-8")
            script = Path(__file__).with_name("entrypoint.sh").read_text(encoding="utf-8")
            # Relocate only the documented image path, leaving a stale path broken.
            entrypoint = root / "entrypoint.sh"
            entrypoint.write_text(script.replace("/onticards_api", str(app)), encoding="utf-8")
            commands = root / "bin"
            commands.mkdir()
            (commands / "gunicorn").write_text(
                '#!/bin/bash\nprintf "%s\\n" "$@" > "$CAPTURE"\n'
                'printf "%s" "${ENV_FILE_MARKER:-}" > "$MARKER"\n',
                encoding="utf-8",
            )
            (commands / "flask").write_text("#!/bin/bash\nexit 97\n", encoding="utf-8")
            for command in commands.iterdir():
                command.chmod(0o755)
            capture = root / "args"
            marker = root / "marker"
            environment = {
                "PATH": str(commands) + os.pathsep + os.environ["PATH"],
                "RUN_DB_MIGRATION": "false",
                "CAPTURE": str(capture),
                "MARKER": str(marker),
            }
            environment.update(variables or {})
            result = subprocess.run(
                ["bash", str(entrypoint)], cwd=app, env=environment,
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            args = capture.read_text().splitlines()
            return args[args.index("--bind") + 1], marker.read_text()

    def test_default_bind_without_env_file(self):
        self.assertEqual(self.run_entrypoint()[0], "0.0.0.0:9103")

    def test_container_environment_controls_bind(self):
        bind, _ = self.run_entrypoint({
            "PORT": "9203", "API_BIND_ADDRESS": "127.0.0.1",
            "DIFY_PORT": "9999", "DIFY_BIND_ADDRESS": "192.0.2.1",
        })
        self.assertEqual(bind, "127.0.0.1:9203")

    def test_image_env_file_is_loaded_and_exported_before_migration(self):
        bind, marker = self.run_entrypoint(
            {"RUN_DB_MIGRATION": "true"},
            "PORT=9303\nAPI_BIND_ADDRESS=127.0.0.2\n"
            "RUN_DB_MIGRATION=false\nENV_FILE_MARKER=loaded\n",
        )
        self.assertEqual(bind, "127.0.0.2:9303")
        self.assertEqual(marker, "loaded")

    def test_empty_bind_values_use_defaults(self):
        self.assertEqual(self.run_entrypoint({
            "PORT": "", "API_BIND_ADDRESS": "",
        })[0], "0.0.0.0:9103")


if __name__ == "__main__":
    unittest.main()
