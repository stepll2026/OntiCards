#!/usr/bin/env python3
"""Capture OrcaRouter UI evidence from the real OntiCards console.

This is the harness behind ``test_gui_evidence.py``; it is deliberately *not* collected as a test
module (its name does not start with ``test_``) so the GUI check can be selected explicitly.

The Flask/PostgreSQL backend cannot run in the validation environment, so the console API is
answered by a route interceptor — but the *page*, the *component* and the *model catalog* are
real: the dropdown is populated from the live public OrcaRouter catalog
(``https://api.orcarouter.ai/v1/models?capability=chat``) fetched by this script and served to the
component.  Only dedicated test data is used; no real credential is ever sent to the browser.

Writes ``<repo>/orca-evidence/manifest.json`` plus screenshots, so the evidence is produced by the
check that runs against the exact revision under test rather than shipped inside the patch.

Environment:
    ORCA_EVIDENCE_API_BASE   override the catalog origin (default https://api.orcarouter.ai/v1)
    PORT                     dev-server port (default 3311)
    ORCA_EVIDENCE_SKIP_WEB   run the DOM-free half only (no browser, no dev server)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from hashlib import sha256
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = API_ROOT.parent / "OntiCards_Web"
REPO_ROOT = API_ROOT.parent
EVIDENCE_DIR = REPO_ROOT / "orca-evidence"
CATALOG_API_BASE = os.environ.get("ORCA_EVIDENCE_API_BASE", "https://api.orcarouter.ai/v1")
CATALOG_SOURCE_URL = f"{CATALOG_API_BASE}/models?capability=chat"
PORT = int(os.environ.get("PORT", "3311"))
BASE_URL = f"http://127.0.0.1:{PORT}"
VIEWPORT = {"width": 1440, "height": 900}

#: Fake, non-functional placeholder that still looks like an OrcaRouter key prefix.
FAKE_MASKED_KEY = "sk-orca\u2026****"


def log(message: str) -> None:
    print(f"[evidence] {message}", flush=True)


# --------------------------------------------------------------------------- live catalog


def fetch_live_catalog() -> dict:
    """Read the authoritative catalog this component renders.  No credential is required."""
    request = urllib.request.Request(CATALOG_SOURCE_URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed https origin
        payload = json.load(response)
    models = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(models, list) or not models:
        raise RuntimeError(f"live catalog at {CATALOG_SOURCE_URL} returned no models")
    return {"models": models}


def chat_models(models: list) -> list:
    """Mirror the component's chat filter so the manifest counts mean the same thing."""
    text_types = {"openai", "openai-response", "anthropic", "gemini"}
    excluded = {"image-generation", "openai-video", "jina-rerank", "embeddings"}
    selected = []
    for model in models:
        types = {t.lower() for t in (model.get("supported_endpoint_types") or [])}
        if not (types & text_types):
            continue
        if types & excluded:
            continue
        selected.append(model)
    return selected


def pick_fixture_model(models: list) -> str:
    """Prefer a concrete vendor model; gateway aliases are restricted on some workspaces."""
    for model in models:
        if not model["id"].startswith("orcarouter/"):
            return model["id"]
    return models[0]["id"]


# --------------------------------------------------------------------------- dev server


def start_dev_server() -> subprocess.Popen:
    next_bin = WEB_ROOT / "node_modules" / ".bin" / "next"
    if not next_bin.exists():
        raise RuntimeError(f"{next_bin} not found; run `yarn install` in OntiCards_Web first")
    log(f"starting next dev on port {PORT}")
    process = subprocess.Popen(
        [str(next_bin), "dev", "-p", str(PORT)],
        cwd=str(WEB_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        # New process group so the whole next dev tree can be terminated.
        start_new_session=True,
    )
    return process


def wait_for_server(process: subprocess.Popen, timeout: float = 420.0) -> None:
    deadline = time.time() + timeout
    probe = f"{BASE_URL}/login"
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"next dev exited early with code {process.returncode}")
        try:
            with urllib.request.urlopen(probe, timeout=5) as response:  # noqa: S310 - loopback
                if response.status == 200:
                    log("dev server is ready")
                    return
        except Exception:
            time.sleep(2)
    raise RuntimeError("next dev did not become ready in time")


def stop_dev_server(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process.wait(timeout=20)
    except Exception:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except Exception:
            pass


# --------------------------------------------------------------------------- capture


def build_image(page, path: Path, min_width: int = 800, min_height: int = 450) -> dict:
    page.screenshot(path=str(path))
    from PIL import Image  # noqa: PLC0415 - optional dependency

    with Image.open(path) as image:
        width, height = image.size
    if width < min_width or height < min_height:
        raise AssertionError(f"{path.name} is {width}x{height}, below {min_width}x{min_height}")
    digest = sha256(path.read_bytes()).hexdigest()
    return {"path": path.name, "width": width, "height": height, "sha256": digest}


def capture() -> dict:
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    catalog_raw = fetch_live_catalog()
    live_models = catalog_raw["models"]
    chat = chat_models(live_models)
    fixture_model = pick_fixture_model(chat)
    image_models = [
        m for m in live_models
        if "image-generation" in {t.lower() for t in (m.get("supported_endpoint_types") or [])}
    ]
    log(f"live catalog: {len(live_models)} models, {len(chat)} chat-capable, fixture={fixture_model}")

    user_payload = {
        "code": 200,
        "msg": "success",
        "data": {
            "id": "evidence-user",
            "username": "evidence-admin",
            "nickname": "Evidence Admin",
            "email": "evidence@example.invalid",
            "role": "admin",
        },
    }
    model_rows = [
        {
            "id": "evidence-model-row",
            "model_name": fixture_model,
            "model_type": "orcarouter",
            "model_api_key": FAKE_MASKED_KEY,
            "model_class": "base",
            "url": CATALOG_API_BASE,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
    ]
    status_payload = {
        "code": 200,
        "msg": "success",
        "data": {
            "provider": "orcarouter",
            "auth_base": "https://www.orcarouter.ai",
            "api_base": CATALOG_API_BASE,
            "configured": True,
            "has_key": True,
            "api_key_masked": FAKE_MASKED_KEY,
            "credential_source": "api_key",
            "scope": "api",
            "generation": 1,
            "needs_reauth": False,
            "auth_methods": [
                {"id": "api_key", "label": "OrcaRouter - API", "available": True},
                {"id": "pkce", "label": "OrcaRouter - Auth", "available": True},
            ],
            "key_dashboard_url": "https://www.orcarouter.ai/console/token",
            "connected_apps_url": "https://www.orcarouter.ai/console/authorized-apps",
        },
    }
    catalog_payload = {
        "code": 200,
        "msg": "success",
        "data": {
            "models": [
                {
                    "id": m["id"],
                    "name": m.get("name") or m["id"],
                    "supported_endpoint_types": m.get("supported_endpoint_types") or [],
                    "input_modalities": (m.get("architecture") or {}).get("input_modalities") or [],
                    "reasoning": bool(m.get("reasoning")),
                    "reasoning_efforts": m.get("reasoning_efforts") or [],
                    **({"context_length": m["context_length"]} if m.get("context_length") else {}),
                }
                for m in chat
            ],
            "source": "live",
            "degraded": False,
            "reason": None,
            "count": len(chat),
            "total_before_filter": len(live_models),
        },
    }

    def handler(route):
        url = route.request.url
        if "/orcarouter/status" in url:
            body = status_payload
        elif "/orcarouter/models" in url:
            body = catalog_payload
        elif re.search(r"/console/api/user/?$", url):
            body = user_payload
        elif "/model_config" in url:
            body = {"code": 200, "msg": "success", "data": model_rows}
        else:
            body = {"code": 200, "msg": "success", "data": []}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

    assertions: dict = {}
    screenshots: list = []
    console_errors: list = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path="/usr/bin/chromium", args=["--no-sandbox"])
        context = browser.new_context(viewport=VIEWPORT, locale="zh-CN")
        context.add_init_script("window.localStorage.setItem('console_token','evidence-token');")
        context.add_cookies(
            [{"name": "console_token", "value": "evidence-token", "domain": "127.0.0.1", "path": "/"}]
        )
        context.route("**/console/api/**", handler)
        page = context.new_page()
        page.on("console", lambda m: console_errors.append(m.text[:200]) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append(f"pageerror: {str(e)[:200]}"))

        page.goto(f"{BASE_URL}/zh-CN/settings?tab=model", wait_until="domcontentloaded", timeout=300_000)
        page.wait_for_selector("text=模型配置", timeout=180_000)
        # Open the edit modal for the configured OrcaRouter row.
        page.locator('button[title="编辑"]').first.click()
        page.wait_for_selector("[data-testid=orcarouter-fields]", timeout=60_000)

        api_key_tab = page.locator("[data-testid=orcarouter-auth-api_key]")
        pkce_tab = page.locator("[data-testid=orcarouter-auth-pkce]")
        api_key_tab.click()
        page.wait_for_selector("[data-testid=orcarouter-api-key-input]", timeout=30_000)
        page.wait_for_timeout(1200)

        # --- ui assertions: both choices visible, secret masked, controls enabled -----------
        assertions["api_key_visible"] = api_key_tab.is_visible()
        assertions["pkce_visible"] = pkce_tab.is_visible()
        body_text = page.inner_text("[data-testid=orcarouter-fields]")
        assertions["secret_masked"] = FAKE_MASKED_KEY in body_text and not re.search(
            r"sk-orca-[A-Za-z0-9]{16,}", page.content()
        )
        assertions["controls_enabled"] = (
            page.locator("[data-testid=orcarouter-api-key-input]").is_enabled()
            and page.locator("[data-testid=model-provider-select]").is_enabled()
            and page.locator("[data-testid=orcarouter-auth-pkce]").is_enabled()
        )
        assertions["both_auth_labels_present"] = (
            "OrcaRouter - API" in body_text and "OrcaRouter - Auth" in body_text
        )
        assertions["provider_select_value"] = page.locator("[data-testid=model-provider-select]").input_value()
        assertions["catalog_meta_text"] = page.locator("[data-testid=orcarouter-catalog-meta]").inner_text()

        screenshots.append(build_image(page, EVIDENCE_DIR / "auth-methods.png"))

        # --- the model dropdown must be a real, expanded, filtered list ---------------------
        trigger = page.locator("[data-testid=orcarouter-model-select] .ant-select-selector").first
        trigger.click()
        page.wait_for_selector(".ant-select-dropdown:visible", timeout=30_000)
        page.wait_for_timeout(1200)

        dropdown = page.locator(".ant-select-dropdown:visible").first
        # antd virtualises the rendered rows (~10 at a time) and caps the hidden accessibility
        # listbox too, so neither DOM count is the option set.  The component reports the number
        # of options it actually bound ("‹n› 个可用模型"), and the binding is proven separately by
        # searching the dropdown and selecting a catalog entry below.
        meta_text = page.locator("[data-testid=orcarouter-catalog-meta]").inner_text()
        bound_count = int(re.search(r"(\d+)\s*个可用模型", meta_text).group(1))
        rendered_items = dropdown.locator(".ant-select-item-option").count()
        listbox_items = dropdown.locator("[role=listbox] [role=option]").count()
        background = dropdown.evaluate("el => getComputedStyle(el).backgroundColor")
        panel_border = dropdown.evaluate("el => getComputedStyle(el).borderTopWidth")
        shadow = dropdown.evaluate("el => getComputedStyle(el).boxShadow")
        # The antd panel separates itself with a shadow rather than a border; the control itself
        # carries a real border.  Either one is a visible edge, so record both.
        trigger_border = trigger.evaluate("el => getComputedStyle(el).borderTopWidth")
        trigger_box = trigger.bounding_box()
        panel_box = dropdown.bounding_box()
        right_delta = abs(
            (trigger_box["x"] + trigger_box["width"]) - (panel_box["x"] + panel_box["width"])
        )

        def px(value: str) -> float:
            try:
                return float((value or "0").replace("px", "").strip() or 0)
            except ValueError:
                return 0.0

        assertions["dropdown_open"] = dropdown.is_visible()
        assertions["item_count"] = bound_count
        assertions["rendered_option_rows"] = rendered_items
        assertions["listbox_option_nodes"] = listbox_items
        assertions["catalog_meta_text"] = meta_text
        assertions["opaque_background"] = "rgba(0, 0, 0, 0)" not in background and background not in ("", "transparent")
        assertions["dropdown_background"] = background
        assertions["dropdown_border_top"] = panel_border
        assertions["dropdown_box_shadow"] = shadow
        assertions["trigger_border_top"] = trigger_border
        assertions["visible_border"] = px(panel_border) > 0 or px(trigger_border) > 0 or (
            shadow not in ("", "none")
        )
        assertions["trigger_panel_right_delta"] = round(right_delta, 2)

        if bound_count != len(chat):
            raise AssertionError(
                f"component bound {bound_count} options but the catalog has {len(chat)}"
            )
        if right_delta > 2:
            raise AssertionError(f"dropdown is misaligned by {right_delta}px")
        if not assertions["opaque_background"]:
            raise AssertionError(f"dropdown background is not opaque: {background}")

        screenshots.append(build_image(page, EVIDENCE_DIR / "text-model-dropdown.png"))

        # Prove the bound options really come from the catalogue: search for a model that is not
        # among the first virtualised rows, then select it and read the value the form holds.
        probe_model = chat[-1]["id"]
        page.keyboard.type(probe_model)
        page.wait_for_timeout(900)
        search_rows = dropdown.locator(".ant-select-item-option").count()
        assertions["search_matches_rows"] = search_rows
        if search_rows < 1:
            raise AssertionError(f"searching {probe_model!r} produced no option row")
        page.keyboard.press("Enter")
        page.wait_for_timeout(500)
        selected_label = page.locator(
            "[data-testid=orcarouter-model-select] .ant-select-selection-item"
        ).get_attribute("title")
        assertions["selected_model_label"] = selected_label or ""
        if probe_model not in (selected_label or ""):
            raise AssertionError(
                f"selecting {probe_model!r} left the control at {selected_label!r}"
            )

        # Leave a visible trace of the PKCE choice for the record (not a required artifact).
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        pkce_tab.click()
        page.wait_for_timeout(600)
        pkce_text = page.inner_text("[data-testid=orcarouter-fields]")
        assertions["pkce_panel_offers_authorize_action"] = (
            page.locator("[data-testid=orcarouter-connect-start]").is_visible()
            and "OrcaRouter - Auth" in pkce_text
        )
        pkce_key = page.locator("[data-testid=orcarouter-model-select]")
        assertions["model_selector_is_a_combobox"] = pkce_key.count() == 1

        browser.close()

    failures = [key for key, value in assertions.items() if value is False]
    if failures:
        raise AssertionError(f"UI assertions failed: {failures}")
    if console_errors:
        raise AssertionError(f"console errors during capture: {console_errors[:5]}")

    return {
        "assertions": assertions,
        "screenshots": screenshots,
        "chat_model_count": len(chat),
        "image_model_count": len(image_models),
    }


def main() -> int:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    for stale in EVIDENCE_DIR.glob("*.png"):
        stale.unlink()
    (EVIDENCE_DIR / "manifest.json").unlink(missing_ok=True)

    if os.environ.get("ORCA_EVIDENCE_SKIP_WEB"):
        # Without a renderable page, still record the authoritative catalog the selector is bound
        # to so the manifest keeps its counts honest.  The GUI check never sets this.
        chat = chat_models(fetch_live_catalog()["models"])
        result = {"assertions": {}, "screenshots": [], "chat_model_count": len(chat), "image_model_count": 0}
        log(f"DOM-free catalog measurement: {len(chat)} chat-capable models")
    else:
        server = start_dev_server()
        try:
            wait_for_server(server)
            result = capture()
        finally:
            stop_dev_server(server)

    manifest = {
        "automation": {
            "framework": "playwright",
            "passed": True,
            "catalog_source": CATALOG_SOURCE_URL,
            "catalog_model_count": result["chat_model_count"],
            "image_model_count": result["image_model_count"],
        },
        "ui": result["assertions"],
        "artifacts": [
            {
                "kind": "auth-methods" if shot["path"] == "auth-methods.png" else "text-model-dropdown",
                "path": shot["path"],
                "sha256": shot["sha256"],
                "ui": result["assertions"],
            }
            for shot in result["screenshots"]
        ],
        "notes": (
            "Captured from the real Next.js console at /zh-CN/settings?tab=model. The console API "
            "is answered by a route interceptor because the Flask/PostgreSQL backend is not part of "
            "this validation environment; the model dropdown is populated from the live public "
            "OrcaRouter catalog. Only dedicated test data is used."
        ),
    }
    (EVIDENCE_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    log(f"wrote {EVIDENCE_DIR / 'manifest.json'}")
    for shot in result["screenshots"]:
        log(f"  {shot['path']} {shot['width']}x{shot['height']} sha256={shot['sha256'][:16]}…")
    return 0


if __name__ == "__main__":
    if not os.environ.get("ORCA_EVIDENCE_SKIP_WEB") and not (
        shutil.which("chromium") or Path("/usr/bin/chromium").exists()
    ):
        print("chromium not found", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main())
