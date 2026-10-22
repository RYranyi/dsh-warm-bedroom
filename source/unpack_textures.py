import bpy, json, os

# Restore textures/ from the images packed inside the final .blend.
# Blender image datablock names sometimes lack the extension (TV_Screen_Result),
# while build_bedroom_v2.py expects the on-disk name to keep ".png".
BLEND = r"E:\dsh\bedroom_scene\warm_bedroom_v2.blend"
TEX = r"E:\dsh\bedroom_scene\textures"

bpy.ops.wm.open_mainfile(filepath=BLEND)
os.makedirs(TEX, exist_ok=True)

written = []
for im in bpy.data.images:
    if im.name in ("Render Result", "Viewer Node"):
        continue
    if im.packed_file is None:
        written.append([im.name, "NOT_PACKED", 0])
        continue
    fname = im.name
    if not fname.lower().endswith((".png", ".jpg", ".jpeg")):
        fname += ".png"
    data = bytes(im.packed_file.data)
    dest = os.path.join(TEX, fname)
    with open(dest, "wb") as f:
        f.write(data)
    written.append([fname, data[:8].hex(), os.path.getsize(dest), list(im.size)])

print("HEADLESS " + json.dumps({"written": written}, ensure_ascii=False))
