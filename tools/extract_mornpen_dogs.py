from __future__ import annotations

import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright

URL = "https://mornpen.spatial.t1cloud.com/spatial/intramaps/ApplicationEngine/frontend/mapbuilder/?liteConfigId=c6bf7b67-3a54-451c-8bb9-45509599e39d&configId=a876603d-3827-4328-b2bc-bad1485f65d7"
OUT = Path("output")
FORM_ID = "71eecbca-f6fa-4347-b0c6-e3f83de380c8"
LAYER = "2d97dfb5-4ad3-49f6-b83a-8c857116f4ff"
TERMS = ["Daveys Bay", "Hanns Creek", "Camerons Bight", "Stornoway Drive"]

async def main():
    OUT.mkdir(exist_ok=True)
    session = {"id": ""}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()
        async def on_response(r):
            if "/Projects/" in r.url:
                session["id"] = r.headers.get("x-intramaps-session", "")
        page.on("response", on_response)
        await page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        await page.wait_for_timeout(25000)
        sid = session["id"]
        result = await page.evaluate("""async ({sid, form, layer, terms}) => {
          const base='/spatial/intramaps/ApplicationEngine';
          async function call(url, options={}) { const r=await fetch(url,options); const t=await r.text(); let b=t; try{b=JSON.parse(t)}catch{} return {status:r.status,body:b}; }
          const searchUrl=`${base}/Search/?infoPanelWidth=0&mode=Refresh&form=${form}&resubmit=false&selectionLayersFilter=${layer}&IntraMapsSession=${sid}`;
          const out={};
          for (const term of terms) {
            out[term]=await call(searchUrl,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fields:[term]})});
          }
          return out;
        }""", {"sid":sid,"form":FORM_ID,"layer":LAYER,"terms":TERMS})
        (OUT/'named_search_probe.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        await context.close(); await browser.close()

if __name__=='__main__': asyncio.run(main())
