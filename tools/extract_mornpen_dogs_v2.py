from __future__ import annotations

import asyncio, hashlib, html, json, re
from pathlib import Path

import simplekml
from playwright.async_api import async_playwright
from pyproj import Transformer

URL = "https://mornpen.spatial.t1cloud.com/spatial/intramaps/ApplicationEngine/frontend/mapbuilder/?liteConfigId=c6bf7b67-3a54-451c-8bb9-45509599e39d&configId=a876603d-3827-4328-b2bc-bad1485f65d7"
OUT = Path("output")
FORM_ID = "71eecbca-f6fa-4347-b0c6-e3f83de380c8"
LAYER = "2d97dfb5-4ad3-49f6-b83a-8c857116f4ff"

TARGETS = [
("Hanns Creek Reserve","Balnarring"),("Stornoway Drive Reserve","Baxter"),("Graham Myers Recreation Reserve Sports Oval","Bittern"),("Lens Street Reserve","Bittern"),("Rosyth Road Reserve","Bittern"),("Camerons Bight","Blairgowrie"),("Stringer Road Reserve","Blairgowrie"),("Truemans Road Reserve","Capel Sound"),("Vern Wright Reserve","Capel Sound"),("Brasser Avenue Bushland Reserve","Dromana"),("Hillview Community Reserve","Dromana"),("Pier Street Reserve","Dromana"),("BA Cairns Reserve Sports Oval","Flinders"),("Flinders Beach","Flinders"),("Cypress Close Reserve","Hastings"),("Fred Smith Reserve","Hastings"),("Kings Creek Reserve","Hastings"),("Lantons Way Reserve","Hastings"),("Villawood Reserve","Hastings"),("Westpark Reserve","Hastings"),("Benbenjie Reserve","McCrae"),("McCrae Beach","McCrae"),("Civic Reserve","Mornington"),("Fosters Beach and Fossil Beach","Mornington"),("Pine Avenue Reserve","Mornington"),("Royal Beach","Mornington"),("S.L Butler Reserve","Mornington"),("Summerfield Reserve","Mornington"),("Cobb Road Reserve","Mount Eliza"),("Daveys Bay Foreshore","Mount Eliza"),("Half Moon Bay Beach","Mount Eliza"),("John Butler Reserve","Mount Eliza"),("Mount Eliza Beach","Mount Eliza"),("Mount Eliza Regional Park","Mount Eliza"),("Balcombe Estuary Reserve","Mount Martha"),("Century Drive Reserve","Mount Martha"),("Citation Recreation Reserve","Mount Martha"),("Community Forest","Mount Martha"),("Dava Beach and Birdrock Beach","Mount Martha"),("Dunns Road Reserve","Mount Martha"),("Harrap Road Reserve","Mount Martha"),("Hawker Beach","Mount Martha"),("Percy Cerutty Oval","Portsea"),("Shelley Beach","Portsea"),("Lawson Park","Rosebud"),("Murrowong Reserve","Rosebud"),("Rosebud Beach","Rosebud"),("Woodvale Grove Reserve","Rosebud"),("Rye Beach","Rye"),("Safety Beach","Safety Beach"),("Tassells Cove Beach","Safety Beach"),("R.W. Stone Reserve","Somers"),("Somers Beach","Somers"),("Clarendon Reserve","Somerville"),("Grant Reserve","Somerville"),("Camerons Bight","Sorrento"),("David MacFarlan Reserve Sports Oval","Sorrento"),("Sorrento Beach","Sorrento"),("Marshall Street Reserve","Tootgarook"),("R.M. Hooper Reserve Sports Oval","Tuerong"),("Bunguyan Reserve","Tyabb")]

ALIASES = {
"Graham Myers Recreation Reserve Sports Oval":["Graham Myers","Graham Myers Reserve"],
"Pier Street Reserve":["Pier Street","Pier St Reserve"],
"BA Cairns Reserve Sports Oval":["B.A. Cairns","BA Cairns"],
"Cypress Close Reserve":["Cypress","Cypress Samuel Reserve"],
"Villawood Reserve":["Villawood"],"Westpark Reserve":["West Park","Westpark"],
"S.L Butler Reserve":["Butler Reserve","S L Butler"],"Summerfield Reserve":["Summerfield"],
"Half Moon Bay Beach":["Half Moon Bay"],"Balcombe Estuary Reserve":["Balcombe Estuary"],
"Century Drive Reserve":["Century Drive"],"Citation Recreation Reserve":["Citation Reserve","Citation"],
"Dunns Road Reserve":["Dunns Road"],"Woodvale Grove Reserve":["Woodvale Reserve","Woodvale"],
"Tassells Cove Beach":["Tassells Cove"],"R.W. Stone Reserve":["R W Stone","Stone Reserve"],
"David MacFarlan Reserve Sports Oval":["David MacFarlan","MacFarlan Reserve"],
"R.M. Hooper Reserve Sports Oval":["R M Hooper","Hooper Reserve"]}

SEASONAL = {"Camerons Bight|Blairgowrie","Camerons Bight|Sorrento","McCrae Beach|McCrae","Daveys Bay Foreshore|Mount Eliza","Half Moon Bay Beach|Mount Eliza","Mount Eliza Beach|Mount Eliza","Dava Beach and Birdrock Beach|Mount Martha","Shelley Beach|Portsea","Rosebud Beach|Rosebud","Rye Beach|Rye","Safety Beach|Safety Beach","Sorrento Beach|Sorrento"}

def norm(s): return re.sub(r"[^a-z0-9]+"," ",s.lower()).strip()

def candidates(name, locality):
    vals=[f"{name} {locality}",name]+ALIASES.get(name,[])
    words=name.split()
    if len(words)>2: vals += [" ".join(words[:3])," ".join(words[:2])]
    return list(dict.fromkeys(v for v in vals if v))

def score(display,name,locality):
    d=norm(display); n=norm(name); l=norm(locality)
    toks=set(n.split())
    return (100 if l in d else 0)+(70 if n in d else 0)+sum(5 for t in toks if t in d)

def transform_coords(coords):
    x=coords
    while isinstance(x,list) and x and isinstance(x[0],list): x=x[0]
    if not x or len(x)<2:return coords
    a,b=float(x[0]),float(x[1]); tr=None
    if abs(a)>1000000 or abs(b)>1000000: tr=Transformer.from_crs(3857,4326,always_xy=True)
    elif 100000<a<1000000 and 5000000<b<7000000: tr=Transformer.from_crs(7855,4326,always_xy=True)
    if tr is None:return coords
    def rec(v):
        if isinstance(v,list) and len(v)>=2 and all(isinstance(q,(int,float)) for q in v[:2]):
            lon,lat=tr.transform(v[0],v[1]); return [lon,lat]+v[2:]
        return [rec(q) for q in v]
    return rec(coords)

def add_geom(folder,name,desc,geom,style):
    typ=geom.get("type"); coords=transform_coords(geom.get("coordinates",[]))
    polys=[coords] if typ=="Polygon" else coords if typ=="MultiPolygon" else []
    for i,poly in enumerate(polys):
        if not poly:continue
        p=folder.newpolygon(name=name if i==0 else f"{name} ({i+1})",description=desc)
        p.outerboundaryis=[(z[0],z[1]) for z in poly[0]]
        if len(poly)>1:p.innerboundaryis=[[(z[0],z[1]) for z in ring] for ring in poly[1:]]
        p.style=style

async def main():
    OUT.mkdir(exist_ok=True); session={"id":""}
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True); context=await browser.new_context(ignore_https_errors=True); page=await context.new_page()
        async def on_response(r):
            if "/Projects/" in r.url:session["id"]=r.headers.get("x-intramaps-session","")
        page.on("response",on_response); await page.goto(URL,wait_until="domcontentloaded",timeout=120000); await page.wait_for_timeout(25000)
        sid=session["id"]; features=[]; report=[]; seen=set()
        for name,locality in TARGETS:
            found=[]; used=""
            for q in candidates(name,locality):
                matches=await page.evaluate("""async ({sid,form,layer,q})=>{const u=`/spatial/intramaps/ApplicationEngine/Search/?infoPanelWidth=0&mode=Refresh&form=${form}&resubmit=false&selectionLayersFilter=${layer}&IntraMapsSession=${sid}`;const r=await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fields:[q]})});const j=await r.json();return j.fullText||[]}""",{"sid":sid,"form":FORM_ID,"layer":LAYER,"q":q})
                if matches:found=matches;used=q;break
            if not found: report.append({"name":name,"locality":locality,"status":"not found","candidates":candidates(name,locality)});continue
            m=max(found,key=lambda x:score(x.get("displayValue",""),name,locality))
            result=await page.evaluate("""async ({sid,m})=>{const b='/spatial/intramaps/ApplicationEngine';await fetch(`${b}/Search/Refine/Set?IntraMapsSession=${sid}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({selectionLayer:m.selectionLayer,mapKey:String(m.mapKey),infoPanelWidth:-350,mode:'Refresh',dbKey:String(m.dbKey),zoomType:'current'})});const r=await fetch(`${b}/Integration/geojson?IntraMapsSession=${sid}`);return await r.json()}""",{"sid":sid,"m":m})
            count=0
            for feat in result.get("features",[]):
                geom=feat.get("geometry");
                if not geom:continue
                key=hashlib.sha1(json.dumps(geom,sort_keys=True).encode()).hexdigest()
                if key in seen:continue
                seen.add(key); props=feat.setdefault("properties",{}); props.update({"Reserve":name,"Locality":locality,"Control type":"Seasonal / mixed" if f"{name}|{locality}" in SEASONAL else "Off leash","Source display":m.get("displayValue",""),"dbKey":m.get("dbKey","")}); features.append(feat);count+=1
            report.append({"name":name,"locality":locality,"status":"ok","search":used,"match":m.get("displayValue"),"dbKey":m.get("dbKey"),"new_features":count})
        await context.close();await browser.close()
    fc={"type":"FeatureCollection","features":features};(OUT/"mornington_peninsula_dog_off_leash_areas.geojson").write_text(json.dumps(fc,indent=2,ensure_ascii=False),encoding="utf-8");(OUT/"extraction_report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    kml=simplekml.Kml(name="Mornington Peninsula Dog Off-Leash Areas"); yr=kml.newfolder(name="Year-round off-leash areas"); seas=kml.newfolder(name="Seasonal or mixed-control areas")
    green=simplekml.Style();green.polystyle.color="7d4caf50";green.linestyle.color="ff1b5e20";green.linestyle.width=3
    orange=simplekml.Style();orange.polystyle.color="7dff9800";orange.linestyle.color="ffe65100";orange.linestyle.width=3
    for feat in features:
        p=feat.get("properties",{}); seasonal=p.get("Control type")=="Seasonal / mixed"; folder=seas if seasonal else yr; style=orange if seasonal else green; name=f"{p.get('Reserve')} — {p.get('Locality')}";desc="<table>"+"".join(f"<tr><th align='left'>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>" for k,v in p.items())+"</table>";add_geom(folder,name,desc,feat.get("geometry",{}),style)
    kml.savekmz(str(OUT/"mornington_peninsula_dog_off_leash_areas.kmz"))

if __name__=="__main__":asyncio.run(main())
