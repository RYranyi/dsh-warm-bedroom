# -*- coding: utf-8 -*-
"""Bake the user's final bedroom for the live 3D site — v2.

Fixes over the previous bake:
  * keeps the OUTDOOR geometry that is visible through the window
    (window box, garden, hedges, near/mid trees) as its own baked group,
    so the view out of the window has real depth instead of a flat plate
  * keeps the far city silhouettes as flat-coloured geometry (no atlas waste)
  * leaves the sky dome, ground plane and city lights to the viewer, where they
    can change with time and weather
  * 4096 atlases for the surfaces that get close to the camera
"""
import bpy, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

USER_BLEND = paths.blend()
OUT = paths.root("website", "assets")
TEX = os.path.join(OUT, "textures")
os.makedirs(TEX, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=USER_BLEND)
sc = bpy.context.scene

# name, collection, resolution, roughness, extra filter key
GROUPS = [
    ("Architecture", "Architecture", 4096, 0.80, None),
    ("Furniture", "Furniture", 4096, 0.55, None),
    ("Bedding", "Bedding", 2048, 0.90, None),
    ("Decor", "Decor", 2048, 0.62, None),
    ("Plants", "Plants", 2048, 0.70, None),
    ("Window", "Window_and_Curtains", 2048, 0.75, None),
    ("Maid", "Maid", 4096, 0.58, None),
    ("OutdoorNear", "Outdoor", 4096, 0.78, "near"),
]

DROP_ALWAYS = {
    "Window_Glass", "Rain_Glass_Overlay", "Curtain_Sheer", "Frame_Glass",
    "Rain_Curtain_1", "Rain_Curtain_2", "Rain_Curtain_3", "Rain_Haze",
    "Rug_Fibers", "Rug_Tassels",
    # outdoor pieces handled by the viewer instead of the atlas
    "Sky_Dome", "Sun_Disc", "Moon", "Stars", "City_Lights", "Outdoor_Ground",
}
KEEP_SPECIAL = {"TV_Screen", "Frame_Artwork"}
NEAR_MAX_X = 17.0


def remove(objs):
    for o in list(objs):
        if o and o.name in bpy.data.objects:
            bpy.data.objects.remove(o, do_unlink=True)


# ---- strip helper collections -------------------------------------------------
for cname in ("Cameras", "Lights"):
    c = bpy.data.collections.get(cname)
    if c:
        remove(list(c.all_objects))
        bpy.data.collections.remove(c)
remove([bpy.data.objects.get(n) for n in DROP_ALWAYS])
special = {n: bpy.data.objects.get(n) for n in KEEP_SPECIAL}


def is_far_city(o):
    return o.name.startswith("City_")


def convert_and_apply(o):
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    if o.type == "CURVE":
        bpy.ops.object.convert(target="MESH")
    if o.type != "MESH":
        return False
    if o.parent is not None:
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
    if o.data.users > 1:
        o.data = o.data.copy()
    for m in list(o.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=m.name)
        except Exception as e:
            print("MODFAIL", o.name, m.name, e)
    return True


def bake_targets(o, img):
    """Point every material's active image node at the bake image.

    Blender 5.2 cancels the bake unless the target node is BOTH active and
    selected.  Selection must be decided with `==` (data equality) — the Python
    `is` comparison compares wrapper objects, which bpy re-creates on every
    access, so `n is node` silently leaves the node unselected and the bake
    returns CANCELLED with an empty image.
    """
    for slot in o.material_slots:
        mat = slot.material
        if not mat:
            continue
        if not mat.use_nodes:
            mat.use_nodes = True
        nt = mat.node_tree
        node = nt.nodes.get("BakeTarget")
        if node is None:
            node = nt.nodes.new("ShaderNodeTexImage")
            node.name = "BakeTarget"
        node.image = img
        nt.nodes.active = node
        for n in nt.nodes:
            n.select = (n == node)


def flat_mat(name, color, rough):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (300, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (0, 0)
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = 0.0
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def bake_group(name, coll_name, res, rough, key):
    coll = bpy.data.collections.get(coll_name)
    if not coll:
        print("NO COLLECTION", coll_name)
        return None
    objs = []
    for o in coll.all_objects:
        if o.type not in {"MESH", "CURVE"} or o.name in KEEP_SPECIAL or o.name in DROP_ALWAYS:
            continue
        if key == "near":
            if is_far_city(o):
                continue
            bb = [o.matrix_world @ __import__("mathutils").Vector(c) for c in o.bound_box]
            if max(v.x for v in bb) > NEAR_MAX_X:
                continue
        objs.append(o)
    objs = [o for o in objs if convert_and_apply(o)]
    if not objs:
        print("NO OBJECTS", name)
        return None
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = "Baked_" + name
    obj.data.name = "Baked_" + name
    if name == "Maid":
        mod = obj.modifiers.new("web_decimate", "DECIMATE")
        mod.ratio = 0.20
        bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    try:
        bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.006)
    except Exception as e:
        print("UVFAIL", name, e)
    bpy.ops.object.mode_set(mode="OBJECT")

    img = bpy.data.images.new("bake_" + name, width=res, height=res, alpha=False)
    img.colorspace_settings.name = "sRGB"
    bake_targets(obj, img)
    sc.render.engine = "CYCLES"
    sc.cycles.device = "GPU"
    sc.cycles.samples = 1
    rb = sc.render.bake
    rb.use_pass_direct = False
    rb.use_pass_indirect = False
    rb.use_pass_color = True
    rb.margin = 6
    rb.use_clear = True
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    t = time.time()
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, target="IMAGE_TEXTURES", use_clear=True)
    print("BAKE", name, "faces", len(obj.data.polygons), "seconds", round(time.time() - t, 2))
    img.filepath_raw = os.path.join(TEX, name.lower() + ".jpg")
    img.file_format = "JPEG"
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 90
    img.save()

    obj.data.materials.clear()
    obj.data.materials.append(flat_mat("Baked_" + name, (0.8, 0.8, 0.8), rough))
    obj["web_texture"] = name
    return obj


results = []
for gname, coll, res, rough, key in GROUPS:
    o = bake_group(gname, coll, res, rough, key)
    if o:
        results.append((gname, len(o.data.polygons), len(o.data.vertices)))
        print("GROUP_DONE", gname, len(o.data.polygons))

# ---- far city: flat colours, no atlas ----------------------------------------
city = [o for o in bpy.data.collections["Outdoor"].all_objects
        if o.type == "MESH" and is_far_city(o)]
city = [o for o in city if convert_and_apply(o)]
if city:
    bpy.ops.object.select_all(action="DESELECT")
    for o in city:
        o.select_set(True)
    bpy.context.view_layer.objects.active = city[0]
    bpy.ops.object.join()
    cobj = bpy.context.view_layer.objects.active
    cobj.name = "City_Far"
    cobj.data.name = "City_Far"
    # two flat tones: cool matte blocks and the warmer lit ones
    cobj.data.materials.clear()
    cobj.data.materials.append(flat_mat("City_Matte", (0.055, 0.062, 0.075), 0.92))
    cobj.data.materials.append(flat_mat("City_Warm", (0.16, 0.115, 0.092), 0.92))
    cobj["web_texture"] = "City"
    print("CITY_FAR faces", len(cobj.data.polygons))

# ---- special surfaces: keep the original images ------------------------------
for n, o in special.items():
    if not o:
        continue
    if n == "TV_Screen":
        o.data.materials.clear()
        o.data.materials.append(flat_mat("TV_Media", (1.0, 1.0, 1.0), 0.4))
    else:
        o.data.materials.clear()
        o.data.materials.append(flat_mat("Art_Media", (1.0, 1.0, 1.0), 0.38))
    o["web_texture"] = "TV" if n == "TV_Screen" else "Art"

# ---- strip everything that is not part of the web scene ----------------------
keep = {"Baked_" + g[0] for g in GROUPS} | KEEP_SPECIAL | {"City_Far"}
for o in list(bpy.data.objects):
    if o.type in {"MESH", "CURVE"} and o.name not in keep:
        bpy.data.objects.remove(o, do_unlink=True)
    elif o.type not in {"MESH", "CURVE"}:
        bpy.data.objects.remove(o, do_unlink=True)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "web_export.blend"))
bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(
    filepath=os.path.join(OUT, "scene.glb"),
    export_format="GLB", use_selection=False, export_apply=False,
    export_materials="EXPORT", export_cameras=False, export_lights=False, export_yup=True,
)
print("RESULTS", results)
print("GLB", os.path.getsize(os.path.join(OUT, "scene.glb")))
