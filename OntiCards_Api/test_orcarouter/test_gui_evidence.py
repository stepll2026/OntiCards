"""GUI evidence check: drive the real console and write ``orca-evidence/``.

    python -m pytest OntiCards_Api/test_orcarouter/test_gui_evidence.py -v

Skipped when the browser or the freshly installed front-end dependencies are absent, so the
headless and pure-logic suites stay runnable on their own.
"""

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
WEB_ROOT = Path(__file__).resolve().parents[2] / "OntiCards_Web"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

HAS_BROWSER = Path("/usr/bin/chromium").exists() or bool(shutil.which("chromium"))
HAS_DEV_SERVER = (WEB_ROOT / "node_modules" / ".bin" / "next").exists()

pytestmark = pytest.mark.skipif(
    not HAS_BROWSER, reason="the GUI evidence check needs a Chromium build"
)


@pytest.mark.skipif(
    not (HAS_BROWSER and HAS_DEV_SERVER),
    reason="needs Chromium and the installed Next.js dev server",
)
def test_console_shows_both_auth_methods_and_a_live_model_dropdown():
    # Imported lazily: the harness needs Playwright, which only this check uses.
    import capture_orcarouter_evidence as harness

    assert harness.main() == 0

    manifest_path = harness.EVIDENCE_DIR / "manifest.json"
    assert manifest_path.is_file(), "the harness did not write the evidence manifest"
    manifest = json.loads(manifest_path.read_text())

    assert manifest["automation"]["passed"] is True
    assert manifest["automation"]["catalog_source"].startswith("https://api.orcarouter.ai/v1/models")
    assert manifest["automation"]["catalog_model_count"] > 0

    kinds = {item["kind"] for item in manifest["artifacts"]}
    assert kinds == {"auth-methods", "text-model-dropdown"}
    for item in manifest["artifacts"]:
        shot = harness.EVIDENCE_DIR / item["path"]
        assert shot.stat().st_size > 10_000, f"{shot} is too small to be a real screenshot"

    ui = manifest["ui"]
    assert ui["api_key_visible"] and ui["pkce_visible"] and ui["controls_enabled"]
    assert ui["secret_masked"] is True
    assert ui["dropdown_open"] is True
    assert ui["item_count"] == manifest["automation"]["catalog_model_count"]
    assert ui["opaque_background"] is True and ui["visible_border"] is True
    assert abs(ui["trigger_panel_right_delta"]) <= 2
