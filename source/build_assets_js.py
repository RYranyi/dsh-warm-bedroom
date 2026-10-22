# Rebuild the single-file offline asset bundle used by website/index.html.
# Reads website/assets/scene.glb + textures + art/tv images and writes assets.js.
import base64, json, os

ROOT = r"E:\dsh\bedroom_scene\website"
TEX = os.path.join(ROOT, "assets", "textures")

def b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")

keys = {
    "Baked_Architecture": "architecture.jpg",
    "Baked_Bedding": "bedding.jpg",
    "Baked_Decor": "decor.jpg",
    "Baked_Furniture": "furniture.jpg",
    "Baked_Maid": "maid.jpg",
    "Baked_Plants": "plants.jpg",
    "Baked_Window": "window.jpg",
    "Baked_OutdoorNear": "outdoornear.jpg",
}
data = {
    "glb": b64(os.path.join(ROOT, "assets", "scene.glb")),
    "textures": {
        k: "data:image/jpeg;base64," + b64(os.path.join(TEX, v))
        for k, v in keys.items()
    },
    "art": "data:image/png;base64," + b64(os.path.join(ROOT, "assets", "art.png")),
    "tv": "data:image/png;base64," + b64(os.path.join(ROOT, "assets", "tv.png")),
}
out = os.path.join(ROOT, "assets.js")
with open(out, "w", encoding="utf-8") as f:
    f.write("window.SITE_ASSETS=" + json.dumps(data, separators=(",", ":")) + ";\n")
print("wrote", out, os.path.getsize(out), "bytes")
