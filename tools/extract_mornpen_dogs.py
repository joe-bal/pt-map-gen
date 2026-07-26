from __future__ import annotations

import asyncio
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

URL = (
    "https://mornpen.spatial.t1cloud.com/spatial/intramaps/"
    "ApplicationEngine/frontend/mapbuilder/"
    "?liteConfigId=c6bf7b67-3a54-451c-8bb9-45509599e39d"
    "&configId=a876603d-3827-4328-b2bc-bad1485f65d7"
)
OUT = Path("output")
RESP = OUT / "responses"
FORM_ID = "71eecbca-f6fa-4347-b0c6-e3f83de380c8"
SELECTION_LAYER = "2d97dfb5-4ad3-49f6-b83a-8c857116f4ff"


def safe_name(url: str, suffix: str) -> str:
    parsed = urlparse(url)
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", parsed.path.strip("/") or "root")[-120:]
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    return f"{base}_{digest}{suffix}"


async def main() -> None:
    OUT.mkdir(exist_ok=True)
    RESP.mkdir(exist_ok=True)
    manifest: list[dict] = []
    console: list[str] = []
    session_holder = {"id": ""}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1600, "height": 1100},
            record_har_path=str(OUT / "network.har"),
            record_har_content="embed",
            ignore_https_errors=True,
        )
        page = await context.new_page()
        page.on("console", lambda msg: console.append(f"{msg.type}: {msg.text}"))

        async def capture(response):
            entry = {
                "url": response.url,
                "status": response.status,
                "content_type": response.headers.get("content-type", ""),
                "request_method": response.request.method,
            }
            if "/Projects/" in response.url:
                session_holder["id"] = response.headers.get("x-intramaps-session", "")
            try:
                ctype = entry["content_type"].lower()
                url_l = response.url.lower()
                interesting = any(
                    token in url_l
                    for token in (
                        "applicationengine", "intramaps", "map", "layer", "feature",
                        "selection", "search", "module", "project", "geometry", "spatial"
                    )
                )
                if interesting and (
                    "json" in ctype
                    or "text" in ctype
                    or "xml" in ctype
                    or response.request.resource_type in {"xhr", "fetch"}
                ):
                    body = await response.body()
                    if len(body) <= 15_000_000:
                        suffix = ".json" if "json" in ctype else ".txt"
                        fn = safe_name(response.url, suffix)
                        (RESP / fn).write_bytes(body)
                        entry["file"] = fn
                        entry["size"] = len(body)
            except Exception as exc:
                entry["capture_error"] = repr(exc)
            manifest.append(entry)

        page.on("response", capture)
        await page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
        await page.wait_for_timeout(30_000)

        session_id = session_holder["id"]
        (OUT / "session.txt").write_text(session_id, encoding="utf-8")
        if session_id:
            probe = await page.evaluate(
                """async ({sessionId, formId, layer}) => {
                    const base = '/spatial/intramaps/ApplicationEngine';
                    async function call(url, options={}) {
                        const r = await fetch(url, options);
                        const text = await r.text();
                        let body = text;
                        try { body = JSON.parse(text); } catch (_) {}
                        return {status:r.status, headers:Object.fromEntries(r.headers.entries()), body};
                    }
                    const searchUrl = `${base}/Search/?infoPanelWidth=0&mode=Refresh&form=${formId}&resubmit=false&selectionLayersFilter=${layer}&IntraMapsSession=${sessionId}`;
                    const blankSearch = await call(searchUrl, {
                        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({fields:['']})
                    });
                    const wildcardSearch = await call(searchUrl, {
                        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({fields:['*']})
                    });
                    const geojson = await call(`${base}/Integration/geojson?IntraMapsSession=${sessionId}`);
                    const kml = await call(`${base}/Integration/kml?googleearth=false&IntraMapsSession=${sessionId}`);
                    return {blankSearch, wildcardSearch, geojson, kml};
                }""",
                {"sessionId": session_id, "formId": FORM_ID, "layer": SELECTION_LAYER},
            )
            (OUT / "endpoint_probe.json").write_text(json.dumps(probe, indent=2), encoding="utf-8")

        # Preserve a screenshot and page state for debugging.
        await page.screenshot(path=str(OUT / "map.png"), full_page=True)
        (OUT / "page.html").write_text(await page.content(), encoding="utf-8")
        (OUT / "page_text.txt").write_text(await page.locator("body").inner_text(), encoding="utf-8")
        state = await page.evaluate(
            """() => ({
                url: location.href,
                title: document.title,
                localStorage: Object.fromEntries(Object.entries(localStorage)),
                sessionStorage: Object.fromEntries(Object.entries(sessionStorage)),
                scripts: [...document.scripts].map(s => s.src).filter(Boolean),
                windowKeys: Object.keys(window).filter(k => /map|layer|intra|spatial|config/i.test(k)).sort()
            })"""
        )
        (OUT / "browser_state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
        (OUT / "console.txt").write_text("\n".join(console), encoding="utf-8")
        (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        await context.close()
        await browser.close()

    hits = []
    terms = re.compile(r"dog|leash|reserve|fenced|wkt|geojson|geometry|polygon|coordinates", re.I)
    for path in RESP.iterdir():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        matches = sorted(set(m.group(0).lower() for m in terms.finditer(text)))
        if matches:
            hits.append({"file": path.name, "terms": matches, "size": path.stat().st_size})
    (OUT / "likely_geometry_files.json").write_text(json.dumps(hits, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
