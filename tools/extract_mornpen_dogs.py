from __future__ import annotations

import asyncio, hashlib, html, json
from pathlib import Path

import simplekml
from playwright.async_api import async_playwright
from pyproj import Transformer

URL = "https://mornpen.spatial.t1cloud.com/spatial/intramaps/ApplicationEngine/frontend/mapbuilder/?liteConfigId=c6bf7b67-3a54-451c-8bb9-45509599e39d&configId=a876603d-3827-4328-b2bc-bad1485f65d7"
OUT = Path("output")
FORM_ID = "71eecbca-f6fa-4347-b0c6-e3f83de380c8"
LAYER = "2d97dfb5-4ad3-49f6-b83a-8c857116f4ff"
QUERIES = [
"Hanns Creek Reserve Balnarring","Stornoway Drive Reserve Baxter","Graham Myers Recreation Reserve Sports Oval Bittern","Lens Street Reserve Bittern","Rosyth Road Reserve Bittern","Camerons Bight Blairgowrie","Stringer Road Reserve Blairgowrie","Truemans Road Reserve Capel Sound","Vern Wright Reserve Capel Sound","Brasser Avenue Bushland Reserve Dromana","Hillview Community Reserve Dromana","Pier Street Reserve Dromana","BA Cairns Reserve Sports Oval Flinders","Flinders Beach Flinders","Cypress Close Reserve Hastings","Fred Smith Reserve Hastings","Kings Creek Reserve Hastings","Lantons Way Reserve Hastings","Villawood Reserve Hastings","Westpark Reserve Hastings","Benbenjie Reserve McCrae","McCrae Beach McCrae","Civic Reserve Mornington","Fosters Beach and Fossil Beach Mornington","Pine Avenue Reserve Mornington","Royal Beach Mornington","S.L Butler Reserve Mornington","Summerfield Reserve Mornington","Cobb Road Reserve Mount Eliza","Daveys Bay Foreshore Mount Eliza","Half Moon Bay Beach Mount Eliza","John Butler Reserve Mount Eliza","Mount Eliza Beach Mount Eliza","Mount Eliza Regional Park Mount Eliza","Balcombe Estuary Reserve Mount Martha","Century Drive Reserve Mount Martha","Citation Recreation Reserve Mount Martha","Community Forest Mount Martha","Dava Beach and Birdrock Beach Mount Martha","Dunns Road Reserve Mount Martha","Harrap Road Reserve Mount Martha","Hawker Beach Mount Martha","Percy Cerutty Oval Portsea","Shelley Beach Portsea","Lawson Park Rosebud","Murrowong Reserve Rosebud","Rosebud Beach Rosebud","Woodvale Grove Reserve Rosebud","Rye Beach Rye","Safety Beach Safety Beach","Tassells Cove Beach Safety Beach","R.W. Stone Reserve Somers","Somers Beach Somers","Clarendon Reserve Somerville","Grant Reserve Somerville","Camerons Bight Sorrento","David MacFarlan Reserve Sports Oval Sorrento","Sorrento Beach Sorrento","Marshall Street Reserve Tootgarook","R.M. Hooper Reserve Sports Oval Tuerong","Bunguyan Reserve Tyabb"
]


def transform_coords(coords):
    x = coords
    while isinstance(x, list) and x and isinstance(x[0], list):
        x = x[0]
    if not x or len(x) < 2:
        return coords
    a, b = float(x[0]), float(x[1])
    tr = None
    if abs(a) > 1000000 or abs(b) > 1000000:
        tr = Transformer.from_crs(3857, 4326, always_xy=True)
    elif 100000 < a < 1000000 and 5000000 < b < 7000000:
        tr = Transformer.from_crs(7855, 4326, always_xy=True)
    if tr is None:
        return coords
    def rec(v):
        if isinstance(v, list) and len(v) >= 2 and all(isinstance(q, (int, float)) for q in v[:2]):
            lon, lat = tr.transform(v[0], v[1])
            return [lon, lat] + v[2:]
        return [rec(q) for q in v]
    return rec(coords)


def add_geom(folder, name, desc, geom, style):
    typ = geom.get("type")
    coords = transform_coords(geom.get("coordinates", []))
    polygons = [coords] if typ == "Polygon" else coords if typ == "MultiPolygon" else []
    for i, poly in enumerate(polygons):
        if not poly:
            continue
        p = folder.newpolygon(name=name if i == 0 else f"{name} ({i+1})", description=desc)
        p.outerboundaryis = [(z[0], z[1]) for z in poly[0]]
        if len(poly) > 1:
            p.innerboundaryis = [[(z[0], z[1]) for z in ring] for ring in poly[1:]]
        p.style = style


async def main():
    OUT.mkdir(exist_ok=True)
    session = {"id": ""}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()
        async def on_response(r):
            if "/Projects/" in r.url:
                session["id"] = r.headers.get("x-intramaps-session", "")
        page.on("response", on_response)
        await page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        await page.wait_for_timeout(25000)
        sid = session["id"]
        all_features, report, seen = [], [], set()
        for query in QUERIES:
            result = await page.evaluate("""async ({sid, form, layer, query}) => {
              const base='/spatial/intramaps/ApplicationEngine';
              const searchUrl=`${base}/Search/?infoPanelWidth=0&mode=Refresh&form=${form}&resubmit=false&selectionLayersFilter=${layer}&IntraMapsSession=${sid}`;
              const sr=await fetch(searchUrl,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fields:[query]})});
              const sj=await sr.json(); const matches=sj.fullText||[];
              if(!matches.length) return {query,status:'not found'};
              const locality=query.split(' ').slice(-1)[0].toLowerCase();
              const m=matches.find(x=>(x.displayValue||'').toLowerCase().includes(locality))||matches[0];
              const setr=await fetch(`${base}/Search/Refine/Set?IntraMapsSession=${sid}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({selectionLayer:m.selectionLayer,mapKey:String(m.mapKey),infoPanelWidth:-350,mode:'Refresh',dbKey:String(m.dbKey),zoomType:'current'})});
              let setBody=await setr.text(); try{setBody=JSON.parse(setBody)}catch{}
              const gr=await fetch(`${base}/Integration/geojson?IntraMapsSession=${sid}`); let gj=await gr.text(); try{gj=JSON.parse(gj)}catch{}
              return {query,status:'ok',match:m,setBody,geojson:gj};
            }""", {"sid": sid, "form": FORM_ID, "layer": LAYER, "query": query})
            report.append({k:v for k,v in result.items() if k != "geojson"})
            gj = result.get("geojson") if isinstance(result.get("geojson"), dict) else {}
            for feat in gj.get("features", []):
                geom = feat.get("geometry")
                if not geom:
                    continue
                key = hashlib.sha1(json.dumps(geom, sort_keys=True).encode()).hexdigest()
                if key in seen:
                    continue
                seen.add(key)
                props = feat.setdefault("properties", {})
                props["query"] = query
                props["displayValue"] = result.get("match", {}).get("displayValue", "")
                props["dbKey"] = result.get("match", {}).get("dbKey", "")
                all_features.append(feat)
        await context.close(); await browser.close()

    fc = {"type":"FeatureCollection","features":all_features}
    (OUT/"mornington_peninsula_dog_off_leash_areas.geojson").write_text(json.dumps(fc, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT/"extraction_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    kml = simplekml.Kml(name="Mornington Peninsula Dog Off-Leash Areas")
    folder = kml.newfolder(name="Off-leash and seasonal dog-control areas")
    green = simplekml.Style(); green.polystyle.color="7d4caf50"; green.linestyle.color="ff1b5e20"; green.linestyle.width=3
    orange = simplekml.Style(); orange.polystyle.color="7dff9800"; orange.linestyle.color="ffe65100"; orange.linestyle.width=3
    for feat in all_features:
        props = feat.get("properties", {})
        text = json.dumps(props, ensure_ascii=False).lower()
        seasonal = any(s in text for s in ["1 december", "26 december", "summertime", "seasonal", "prohibited 10am"])
        style = orange if seasonal else green
        name = props.get("displayValue") or props.get("query") or "Dog-control area"
        desc = "<table>" + "".join(f"<tr><th align='left'>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>" for k,v in props.items()) + "</table>"
        add_geom(folder, name, desc, feat.get("geometry", {}), style)
    kml.savekmz(str(OUT/"mornington_peninsula_dog_off_leash_areas.kmz"))

if __name__ == "__main__":
    asyncio.run(main())
