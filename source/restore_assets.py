# -*- coding: utf-8 -*-
"""Restore the build inputs the pipeline needs, from data we still have.

  website/assets/{art.png, tv.png, scene.glb, textures/*.jpg}
        <- decoded from website/assets.js base64 (lossless, byte-identical)
  textures/{Frame_Artwork.png, TV_Screen_Result.png}
        <- unpacked from warm_bedroom_v2.blend's packed images

No re-encoding: the PNG/JPEG bytes come out exactly as they went in.

Note: the .blend side of this (unpacking) lives in the Blender script
`snippet_unpack_textures.py`; this file handles the assets.js side only.
Blender image datablock names can drop the ".png" extension, so that script
appends it when writing TV_Screen_Result.png.
"""
import base64, json, os, re, sys

ROOT = r"E:\dsh\bedroom_scene"
ASSETS_JS = os.path.join(ROOT, "website", "assets.js")
WEB_ASSETS = os.path.join(ROOT, "website", "assets")
TEX = os.path.join(ROOT, "textures")
BLEND = os.path.join(ROOT, "warm_bedroom_v2.blend")

os.makedirs(WEB_ASSETS, exist_ok=True)
os.makedirs(TEX, exist_ok=True)

# ---- 1. art.png / tv.png out of assets.js --------------------------------
txt = open(ASSETS_JS, encoding="utf-8").read()
m = re.match(r"window\.SITE_ASSETS=(\{.*\});\s*$", txt, re.S)
if not m:
    sys.exit("assets.js does not match the expected shape")
data = json.loads(m.group(1))
print("keys:", sorted(data.keys()))

written = []
for key, fname in (("art", "art.png"), ("tv", "tv.png")):
    v = data.get(key)
    if not isinstance(v, str) or "base64," not in v:
        sys.exit("assets.js has no usable '%s' entry" % key)
    raw = base64.b64decode(v.split("base64,", 1)[1])
    p = os.path.join(WEB_ASSETS, fname)
    with open(p, "wb") as f:
        f.write(raw)
    written.append([fname, len(raw), raw[:8].hex()])

# ---- 2. scene.glb + the 8 baked atlases, also out of assets.js -----------
TEXOUT = os.path.join(WEB_ASSETS, "textures")
os.makedirs(TEXOUT, exist_ok=True)

glb = data.get("glb")
if isinstance(glb, str):
    raw = base64.b64decode(glb)
    p = os.path.join(WEB_ASSETS, "scene.glb")
    with open(p, "wb") as f:
        f.write(raw)
    written.append(["scene.glb", len(raw), raw[:4].hex()])

# group key -> file name, same map as app.js / build_assets_js.py
GROUPS = {
    "Baked_Architecture": "architecture",
    "Baked_Bedding": "bedding",
    "Baked_Decor": "decor",
    "Baked_Furniture": "furniture",
    "Baked_Maid": "maid",
    "Baked_OutdoorNear": "outdoornear",
    "Baked_Plants": "plants",
    "Baked_Window": "window",
}
tex = data.get("textures") or {}
for gkey, fname in GROUPS.items():
    v = tex.get(gkey)
    if not isinstance(v, str) or "base64," not in v:
        print("MISSING texture group: %s" % gkey)
        continue
    raw = base64.b64decode(v.split("base64,", 1)[1])
    p = os.path.join(TEXOUT, fname + ".jpg")
    with open(p, "wb") as f:
        f.write(raw)
    written.append(["textures/%s.jpg" % fname, len(raw), raw[:2].hex()])

for w in written:
    print("WROTE website/assets/%-22s %9d bytes  magic=%s" % (w[0], w[1], w[2]))
print("HEADLESS " + json.dumps({"written": written}, ensure_ascii=False))
