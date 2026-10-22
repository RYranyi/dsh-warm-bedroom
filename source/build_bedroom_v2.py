# -*- coding: utf-8 -*-
"""
Build a detailed, warm, photoreal bedroom in Blender 5.x.

Run headless:
    blender -b --factory-startup -P build_bedroom.py

The scene is built at real-world scale (4.1 x 5.0 x 2.8 m), saved as
warm_bedroom.blend, and initialised to a dusk / sunny look.
"""

import bpy
import bmesh
import math
import os
import sys
import random
from mathutils import Vector, Euler, Matrix
from mathutils import noise as mnoise

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

# ---------------------------------------------------------------------------
# Paths / constants
# ---------------------------------------------------------------------------
ROOT = paths.ROOT
TEX_DIR = os.path.join(ROOT, "textures")
RENDER_DIR = os.path.join(ROOT, "renders")
BLEND_PATH = os.path.join(ROOT, "warm_bedroom_v2.blend")
CONTROLLER_PATH = os.path.join(ROOT, "scene_controller.py")
ARTWORK_PATH = os.path.join(TEX_DIR, "Frame_Artwork.png")
TV_IMAGE_PATH = os.path.join(TEX_DIR, "TV_Screen_Result.png")
os.makedirs(RENDER_DIR, exist_ok=True)
os.makedirs(TEX_DIR, exist_ok=True)
random.seed(1729)

# geometry constants --------------------------------------------------------
ROOM_X = 4.6            # width  (x: -2.3 .. 2.3), widened for the new desk
ROOM_Y = 5.0            # depth  (y: -2.5 .. 2.5)
ROOM_Z = 2.8            # height
WALL_T = 0.14
WIN_Y0, WIN_Y1 = 0.55, 2.35      # 1.8 m wide
WIN_Z0, WIN_Z1 = 0.85, 2.35      # 1.5 m high
BED_CX = 0.00
BED_Y0, BED_Y1 = 0.34, 2.38
BED_HW = 0.80                   # 1.6 m double bed, centred on the wall
WALL_ART_Y = 2.492

# ---------------------------------------------------------------------------
# Scene reset and collections
# ---------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.name = "Warm_Bedroom"
scene.unit_settings.system = "METRIC"
scene.unit_settings.length_unit = "METERS"
scene.render.fps = 24
scene.frame_start = 1
scene.frame_end = 1


def make_collection(name, parent=None):
    c = bpy.data.collections.new(name)
    if parent is None:
        scene.collection.children.link(c)
    else:
        parent.children.link(c)
    return c


COL_ARCH = make_collection("Architecture")
COL_WINDOW = make_collection("Window_and_Curtains")
COL_FURN = make_collection("Furniture")
COL_BED = make_collection("Bedding")
COL_DECOR = make_collection("Decor")
COL_PLANTS = make_collection("Plants")
COL_OUT = make_collection("Outdoor")
COL_LIGHT = make_collection("Lights")
COL_CAM = make_collection("Cameras")

# ---------------------------------------------------------------------------
# Generic mesh helpers
# ---------------------------------------------------------------------------
def mesh_object(name, verts, faces, collection, materials=None, smooth=False,
                uvs=None, location=(0, 0, 0), rotation=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate(verbose=False)
    me.update()
    if uvs is not None:
        uv_layer = me.uv_layers.new(name="UVMap")
        for poly in me.polygons:
            for li in poly.loop_indices:
                vi = me.loops[li].vertex_index
                uv_layer.data[li].uv = uvs[vi]
    obj = bpy.data.objects.new(name, me)
    collection.objects.link(obj)
    if materials:
        if not isinstance(materials, (list, tuple)):
            materials = [materials]
        for m in materials:
            if m is not None:
                me.materials.append(m)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    obj.location = location
    obj.rotation_euler = Euler(rotation, "XYZ")
    return obj


def add_bevel(obj, width=0.004, segments=2, smooth=True, split_angle=35.0,
              apply_scale=False):
    if apply_scale:
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.select_set(False)
    if width > 0:
        mod = obj.modifiers.new("Soft_Edges", "BEVEL")
        mod.width = width
        mod.segments = segments
        mod.limit_method = "ANGLE"
        mod.angle_limit = math.radians(30.0)
        mod.use_clamp_overlap = True
        mod.harden_normals = False
    if smooth:
        for p in obj.data.polygons:
            p.use_smooth = True
        es = obj.modifiers.new("Angle_Normals", "EDGE_SPLIT")
        es.use_edge_angle = True
        es.split_angle = math.radians(split_angle)
    return obj


def add_solidify(obj, thickness=0.01, offset=-1.0):
    mod = obj.modifiers.new("Cloth_Thickness", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = offset
    mod.use_rim = True
    return mod


def make_box(name, size, loc, collection, mat=None, rotation=(0, 0, 0),
             bevel=0.004, segments=2, smooth=True):
    sx, sy, sz = size
    hx, hy, hz = sx / 2.0, sy / 2.0, sz / 2.0
    verts = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
             (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    obj = mesh_object(name, verts, faces, collection, mat, smooth=smooth,
                      location=loc, rotation=rotation)
    add_bevel(obj, bevel, segments, smooth=smooth)
    return obj


def make_cylinder(name, radius, depth, loc, collection, mat=None,
                  rotation=(0, 0, 0), segments=40, r_top=None, caps=True,
                  smooth=True):
    if r_top is None:
        r_top = radius
    verts, faces = [], []
    for z, r in ((-depth / 2, radius), (depth / 2, r_top)):
        for i in range(segments):
            a = 2 * math.pi * i / segments
            verts.append((r * math.cos(a), r * math.sin(a), z))
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((i, j, segments + j, segments + i))
    if caps:
        faces.append(tuple(reversed(range(segments))))
        faces.append(tuple(range(segments, 2 * segments)))
    obj = mesh_object(name, verts, faces, collection, mat, smooth=False,
                      location=loc, rotation=rotation)
    for i, p in enumerate(obj.data.polygons):
        if i < segments:
            p.use_smooth = smooth
    return obj


def make_lathe(name, profile, loc, collection, mat=None, segments=64,
               rotation=(0, 0, 0), caps=True, smooth=True):
    """profile: list of (radius, z) from bottom to top."""
    verts = []
    for r, z in profile:
        for i in range(segments):
            a = 2 * math.pi * i / segments
            verts.append((r * math.cos(a), r * math.sin(a), z))
    faces = []
    for k in range(len(profile) - 1):
        base = k * segments
        nxt = (k + 1) * segments
        for i in range(segments):
            j = (i + 1) % segments
            faces.append((base + i, base + j, nxt + j, nxt + i))
    if caps:
        faces.append(tuple(reversed(range(segments))))
        top = (len(profile) - 1) * segments
        faces.append(tuple(range(top, top + segments)))
    obj = mesh_object(name, verts, faces, collection, mat, smooth=False,
                      location=loc, rotation=rotation)
    for i, p in enumerate(obj.data.polygons):
        if i < segments * (len(profile) - 1):
            p.use_smooth = smooth
    return obj


def make_superellipsoid(name, dims, loc, collection, mat, segments=56,
                        rings=32, exponent=0.62, rotation=(0, 0, 0),
                        wrinkle=0.0):
    """A soft, boxy cushion/pillow volume."""
    sx, sy, sz = dims[0] / 2, dims[1] / 2, dims[2] / 2
    verts = []
    for j in range(rings + 1):
        theta = -math.pi / 2 + math.pi * j / rings
        ct, st = math.cos(theta), math.sin(theta)
        for i in range(segments):
            phi = 2 * math.pi * i / segments
            cp, sp = math.cos(phi), math.sin(phi)
            x = math.copysign(abs(ct) ** exponent * abs(cp) ** exponent, cp)
            y = math.copysign(abs(ct) ** exponent * abs(sp) ** exponent, sp)
            z = math.copysign(abs(st) ** exponent, st)
            if wrinkle:
                # a little relaxed hollow in the middle of the broad faces
                hollow = math.exp(-(x * x / 0.17 + z * z / 0.38))
                y *= (1.0 - 0.10 * hollow)
                n = mnoise.noise(Vector((x * 3.0 + 1.7, y * 4.0, z * 3.5 + 3.1)))
                n2 = mnoise.noise(Vector((x * 9.0, y * 8.0 + 2.0, z * 7.0)))
                fac = wrinkle * (0.65 * n + 0.35 * n2)
                x += fac * 0.15
                y += fac * 0.55
                z += fac * 0.15
                # soft creases radiating from the pressed centre
                rim = min(1.0, (abs(x) * 1.15) ** 2)
                z += 0.006 * rim * math.sin(5.0 * x + 2.2 * y)
            verts.append((x * sx, y * sy, z * sz))
    faces = []
    for j in range(rings):
        for i in range(segments):
            j2 = (i + 1) % segments
            a = j * segments + i
            b = j * segments + j2
            c = (j + 1) * segments + j2
            d = (j + 1) * segments + i
            if j == 0:
                faces.append((a, c, d))
            elif j == rings - 1:
                faces.append((a, b, c))
            else:
                faces.append((a, b, c, d))
    obj = mesh_object(name, verts, faces, collection, mat, smooth=True,
                      location=loc, rotation=rotation)
    return obj


def make_uv_sphere(name, radius, loc, collection, mat, segments=64, rings=32,
                   scale=(1, 1, 1), rotation=(0, 0, 0)):
    verts = []
    verts.append((0, 0, radius))
    for j in range(1, rings):
        phi = math.pi * j / rings
        for i in range(segments):
            theta = 2 * math.pi * i / segments
            verts.append((radius * math.sin(phi) * math.cos(theta),
                          radius * math.sin(phi) * math.sin(theta),
                          radius * math.cos(phi)))
    verts.append((0, 0, -radius))
    faces = []
    # top cap
    for i in range(segments):
        faces.append((0, 1 + i, 1 + (i + 1) % segments))
    for j in range(rings - 2):
        base = 1 + j * segments
        nxt = base + segments
        for i in range(segments):
            j2 = (i + 1) % segments
            faces.append((base + i, base + j2, nxt + j2, nxt + i))
    base = 1 + (rings - 2) * segments
    last = len(verts) - 1
    for i in range(segments):
        faces.append((base + i, last, base + (i + 1) % segments))
    obj = mesh_object(name, verts, faces, collection, mat, smooth=True,
                      location=loc, rotation=rotation)
    obj.scale = scale
    return obj


def make_torus(name, major, minor, loc, collection, mat, rotation=(0, 0, 0),
               major_segments=48, minor_segments=10):
    verts, faces = [], []
    for i in range(major_segments):
        a = 2 * math.pi * i / major_segments
        for j in range(minor_segments):
            b = 2 * math.pi * j / minor_segments
            r = major + minor * math.cos(b)
            verts.append((r * math.cos(a), r * math.sin(a), minor * math.sin(b)))
    for i in range(major_segments):
        i2 = (i + 1) % major_segments
        for j in range(minor_segments):
            j2 = (j + 1) % minor_segments
            faces.append((i * minor_segments + j,
                          i2 * minor_segments + j,
                          i2 * minor_segments + j2,
                          i * minor_segments + j2))
    obj = mesh_object(name, verts, faces, collection, mat, smooth=True,
                      location=loc, rotation=rotation)
    return obj


def make_curve(name, paths, bevel_depth, collection, mat, resolution=2,
               bevel_resolution=1, cyclic=False):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.resolution_u = resolution
    cu.bevel_depth = bevel_depth
    cu.bevel_resolution = bevel_resolution
    cu.use_fill_caps = True
    for pts in paths:
        if len(pts) < 2:
            continue
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for i, p in enumerate(pts):
            sp.points[i].co = (p[0], p[1], p[2], 1.0)
        sp.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, cu)
    collection.objects.link(obj)
    cu.materials.append(mat)
    return obj


def make_rect(name, center, width, height, axis, collection, mat=None,
              uvs=True, rotation=0.0):
    cx, cy, cz = center
    if axis == "XZ":       # fixed y
        verts = [(cx - width / 2, cy, cz - height / 2),
                 (cx + width / 2, cy, cz - height / 2),
                 (cx + width / 2, cy, cz + height / 2),
                 (cx - width / 2, cy, cz + height / 2)]
    elif axis == "YZ":     # fixed x
        verts = [(cx, cy - width / 2, cz - height / 2),
                 (cx, cy + width / 2, cz - height / 2),
                 (cx, cy + width / 2, cz + height / 2),
                 (cx, cy - width / 2, cz + height / 2)]
    else:
        verts = [(cx - width / 2, cy - height / 2, cz),
                 (cx + width / 2, cy - height / 2, cz),
                 (cx + width / 2, cy + height / 2, cz),
                 (cx - width / 2, cy + height / 2, cz)]
    faces = [(0, 1, 2, 3)]
    uvl = [(0, 0), (1, 0), (1, 1), (0, 1)] if uvs else None
    obj = mesh_object(name, verts, faces, collection, mat, smooth=False,
                      uvs=uvl, rotation=(0, 0, rotation))
    return obj


def rounded_rect_points(w, h, radius=0.12, segments=128, power=8.0):
    pts = []
    for i in range(segments):
        t = 2 * math.pi * i / segments
        c, s = math.cos(t), math.sin(t)
        x = (w / 2) * math.copysign(abs(c) ** (2.0 / power), c)
        y = (h / 2) * math.copysign(abs(s) ** (2.0 / power), s)
        pts.append((x, y))
    return pts


def make_rounded_plane(name, center, width, height, radius, z, collection, mat,
                       segments=128, thickness=0.0, bevel=0.0):
    pts = rounded_rect_points(width, height, radius, segments)
    verts = [(center[0] + x, center[1] + y, z) for x, y in pts]
    faces = [tuple(range(len(verts)))]
    uvs = [((x + width / 2) / width, (y + height / 2) / height) for x, y in pts]
    obj = mesh_object(name, verts, faces, collection, mat, smooth=False,
                      uvs=uvs)
    if thickness:
        add_solidify(obj, thickness, offset=-1.0)
        add_bevel(obj, bevel, 2, smooth=True)
    return obj


def make_border_ring(name, center, w_out, h_out, w_in, h_in, z, collection,
                     mat, segments=128):
    outer = rounded_rect_points(w_out, h_out, 0.12, segments)
    inner = rounded_rect_points(w_in, h_in, 0.09, segments)
    verts = [(center[0] + x, center[1] + y, z) for x, y in outer]
    verts += [(center[0] + x, center[1] + y, z) for x, y in inner]
    faces = []
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((i, j, segments + j, segments + i))
    obj = mesh_object(name, verts, faces, collection, mat, smooth=False)
    return obj


# ---------------------------------------------------------------------------
# Material helpers
# ---------------------------------------------------------------------------
def new_material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.name = "Material_Output"
    out.location = (800, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.name = "Principled_BSDF"
    bsdf.location = (480, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat, nt, bsdf


def link_nodes(nt, a, b):
    nt.links.new(a, b)


def set_in(bsdf, name, value):
    s = bsdf.inputs.get(name)
    if s is not None:
        try:
            s.default_value = value
        except Exception:
            pass


def rgb_to_linear(hexstr):
    h = hexstr.lstrip("#")
    vals = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in vals)


def hexrgba(hexstr, alpha=1.0):
    return (*rgb_to_linear(hexstr), alpha)


def mat_plaster(name, base_hex, roughness=0.9, bump=0.12):
    mat, nt, bsdf = new_material(name)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-900, 100)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.location = (-650, 180)
    noise.inputs["Scale"].default_value = 7.0
    noise.inputs["Detail"].default_value = 5.0
    noise.inputs["Roughness"].default_value = 0.62
    noise2 = nt.nodes.new("ShaderNodeTexNoise")
    noise2.location = (-650, -100)
    noise2.inputs["Scale"].default_value = 85.0
    noise2.inputs["Detail"].default_value = 3.0
    noise2.inputs["Roughness"].default_value = 0.7
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    nt.links.new(tc.outputs["Object"], noise2.inputs["Vector"])
    base = rgb_to_linear(base_hex)
    dark = tuple(c * 0.82 for c in base)
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-380, 180)
    ramp.color_ramp.elements[0].position = 0.22
    ramp.color_ramp.elements[0].color = (*dark, 1)
    ramp.color_ramp.elements[1].position = 0.78
    ramp.color_ramp.elements[1].color = (*base, 1)
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    rough_ramp = nt.nodes.new("ShaderNodeValToRGB")
    rough_ramp.location = (-380, -100)
    rough_ramp.color_ramp.elements[0].position = 0.2
    rough_ramp.color_ramp.elements[0].color = (roughness - 0.06,) * 3 + (1,)
    rough_ramp.color_ramp.elements[1].position = 0.8
    rough_ramp.color_ramp.elements[1].color = (min(1.0, roughness + 0.03),) * 3 + (1,)
    nt.links.new(noise2.outputs["Fac"], rough_ramp.inputs["Fac"])
    nt.links.new(rough_ramp.outputs["Color"], bsdf.inputs["Roughness"])
    bump_node = nt.nodes.new("ShaderNodeBump")
    bump_node.location = (220, -160)
    bump_node.inputs["Strength"].default_value = bump
    bump_node.inputs["Distance"].default_value = 0.006
    nt.links.new(noise2.outputs["Fac"], bump_node.inputs["Height"])
    nt.links.new(bump_node.outputs["Normal"], bsdf.inputs["Normal"])
    set_in(bsdf, "Specular IOR Level", 0.32)
    return mat


def mat_wood(name, dark_hex, light_hex, grain=True, coarse=8.0, fine=38.0,
             roughness=0.4, coats=0.05, direction="X", distortion=2.4):
    mat, nt, bsdf = new_material(name)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-1000, 180)
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.location = (-800, 180)
    mp.inputs["Scale"].default_value = (1.0, 1.0, 0.55)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.location = (-580, 300)
    wave.wave_type = "BANDS"
    wave.bands_direction = direction
    wave.inputs["Scale"].default_value = coarse
    wave.inputs["Distortion"].default_value = distortion
    wave.inputs["Detail"].default_value = 2.0
    wave.inputs["Detail Scale"].default_value = 1.2
    nt.links.new(mp.outputs["Vector"], wave.inputs["Vector"])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.location = (-580, 40)
    noise.inputs["Scale"].default_value = 2.4
    noise.inputs["Detail"].default_value = 6.0
    noise.inputs["Roughness"].default_value = 0.6
    nt.links.new(mp.outputs["Vector"], noise.inputs["Vector"])
    wave2 = nt.nodes.new("ShaderNodeTexWave")
    wave2.location = (-580, -220)
    wave2.wave_type = "BANDS"
    wave2.bands_direction = direction
    wave2.inputs["Scale"].default_value = fine
    wave2.inputs["Distortion"].default_value = min(1.1, distortion * 0.5)
    wave2.inputs["Detail"].default_value = 1.0
    nt.links.new(mp.outputs["Vector"], wave2.inputs["Vector"])
    mixw = nt.nodes.new("ShaderNodeMixRGB")
    mixw.location = (-350, 190)
    mixw.blend_type = "MIX"
    mixw.inputs["Fac"].default_value = 0.30
    nt.links.new(wave.outputs["Fac"], mixw.inputs["Color1"])
    nt.links.new(wave2.outputs["Fac"], mixw.inputs["Color2"])
    darkc = rgb_to_linear(dark_hex)
    lightc = rgb_to_linear(light_hex)
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-140, 250)
    ramp.color_ramp.elements[0].position = 0.20
    ramp.color_ramp.elements[0].color = (*darkc, 1)
    ramp.color_ramp.elements[1].position = 0.82
    ramp.color_ramp.elements[1].color = (*lightc, 1)
    nt.links.new(mixw.outputs["Color"], ramp.inputs["Fac"])
    # subtle per-board colour variation
    objinfo = nt.nodes.new("ShaderNodeObjectInfo")
    objinfo.location = (-360, -20)
    rnd = nt.nodes.new("ShaderNodeMapRange")
    rnd.location = (-160, -30)
    rnd.inputs["From Min"].default_value = 0.0
    rnd.inputs["From Max"].default_value = 1.0
    rnd.inputs["To Min"].default_value = 0.88
    rnd.inputs["To Max"].default_value = 1.06
    nt.links.new(objinfo.outputs["Random"], rnd.inputs["Value"])
    tint = nt.nodes.new("ShaderNodeMixRGB")
    tint.location = (110, 220)
    tint.blend_type = "MULTIPLY"
    tint.inputs["Fac"].default_value = 0.55
    tint.inputs["Color2"].default_value = (1, 1, 1, 1)
    nt.links.new(ramp.outputs["Color"], tint.inputs["Color1"])
    nt.links.new(rnd.outputs["Result"], tint.inputs["Color2"])
    nt.links.new(tint.outputs["Color"], bsdf.inputs["Base Color"])
    rough_n = nt.nodes.new("ShaderNodeTexNoise")
    rough_n.location = (-350, -320)
    rough_n.inputs["Scale"].default_value = 14.0
    rough_n.inputs["Detail"].default_value = 4.0
    nt.links.new(mp.outputs["Vector"], rough_n.inputs["Vector"])
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.location = (-100, -320)
    rr.inputs["To Min"].default_value = max(0.12, roughness - 0.08)
    rr.inputs["To Max"].default_value = min(0.9, roughness + 0.10)
    nt.links.new(rough_n.outputs["Fac"], rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"], bsdf.inputs["Roughness"])
    # layered bump: grain + pores
    bump1 = nt.nodes.new("ShaderNodeBump")
    bump1.location = (160, -280)
    bump1.inputs["Strength"].default_value = 0.10
    bump1.inputs["Distance"].default_value = 0.0025
    nt.links.new(noise.outputs["Fac"], bump1.inputs["Height"])
    bump2 = nt.nodes.new("ShaderNodeBump")
    bump2.location = (330, -280)
    bump2.inputs["Strength"].default_value = 0.055
    bump2.inputs["Distance"].default_value = 0.0012
    nt.links.new(wave2.outputs["Fac"], bump2.inputs["Height"])
    nt.links.new(bump1.outputs["Normal"], bump2.inputs["Normal"])
    nt.links.new(bump2.outputs["Normal"], bsdf.inputs["Normal"])
    set_in(bsdf, "Metallic", 0.0)
    set_in(bsdf, "Coat Weight", coats)
    set_in(bsdf, "Coat Roughness", 0.32)
    set_in(bsdf, "Specular IOR Level", 0.42)
    return mat


def mat_linen(name, base_hex, rough=0.86, sheen=0.35, transmission=0.0,
              weave_scale=240.0, wrinkle_scale=8.0, bump=0.22,
              darker_hex=None):
    mat, nt, bsdf = new_material(name)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-1000, 140)
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.location = (-800, 140)
    mp.inputs["Scale"].default_value = (1, 1, 1)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    base = rgb_to_linear(base_hex)
    dark = rgb_to_linear(darker_hex) if darker_hex else tuple(c * 0.86 for c in base)
    broad = nt.nodes.new("ShaderNodeTexNoise")
    broad.location = (-580, 280)
    broad.inputs["Scale"].default_value = wrinkle_scale
    broad.inputs["Detail"].default_value = 5.0
    broad.inputs["Roughness"].default_value = 0.65
    nt.links.new(mp.outputs["Vector"], broad.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-340, 240)
    ramp.color_ramp.elements[0].position = 0.2
    ramp.color_ramp.elements[0].color = (*dark, 1)
    ramp.color_ramp.elements[1].position = 0.8
    ramp.color_ramp.elements[1].color = (*base, 1)
    nt.links.new(broad.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    # weave: two perpendicular wave textures
    wx = nt.nodes.new("ShaderNodeTexWave")
    wx.location = (-580, -80)
    wx.wave_type = "BANDS"
    wx.bands_direction = "X"
    wx.inputs["Scale"].default_value = weave_scale
    wx.inputs["Distortion"].default_value = 0.6
    nt.links.new(mp.outputs["Vector"], wx.inputs["Vector"])
    wy = nt.nodes.new("ShaderNodeTexWave")
    wy.location = (-580, -300)
    wy.wave_type = "BANDS"
    wy.bands_direction = "Z"
    wy.inputs["Scale"].default_value = weave_scale * 0.85
    wy.inputs["Distortion"].default_value = 0.6
    nt.links.new(mp.outputs["Vector"], wy.inputs["Vector"])
    weave = nt.nodes.new("ShaderNodeMath")
    weave.location = (-340, -160)
    weave.operation = "ADD"
    weave.inputs[1].default_value = 0.0
    nt.links.new(wx.outputs["Fac"], weave.inputs[0])
    nt.links.new(wy.outputs["Fac"], weave.inputs[1])
    weave2 = nt.nodes.new("ShaderNodeMath")
    weave2.location = (-150, -160)
    weave2.operation = "MULTIPLY"
    weave2.inputs[1].default_value = 0.5
    nt.links.new(weave.outputs["Value"], weave2.inputs[0])
    # bump: broad soft folds + fine weave
    b1 = nt.nodes.new("ShaderNodeBump")
    b1.location = (120, -180)
    b1.inputs["Strength"].default_value = bump * 1.55
    b1.inputs["Distance"].default_value = 0.013
    nt.links.new(broad.outputs["Fac"], b1.inputs["Height"])
    b2 = nt.nodes.new("ShaderNodeBump")
    b2.location = (300, -180)
    b2.inputs["Strength"].default_value = bump * 0.85
    b2.inputs["Distance"].default_value = 0.0018
    nt.links.new(weave2.outputs["Value"], b2.inputs["Height"])
    nt.links.new(b1.outputs["Normal"], b2.inputs["Normal"])
    nt.links.new(b2.outputs["Normal"], bsdf.inputs["Normal"])
    set_in(bsdf, "Sheen Weight", sheen)
    set_in(bsdf, "Sheen Roughness", 0.42)
    set_in(bsdf, "Roughness", rough)
    set_in(bsdf, "Transmission Weight", transmission)
    set_in(bsdf, "IOR", 1.32)
    set_in(bsdf, "Specular IOR Level", 0.26)
    if transmission > 0:
        set_in(bsdf, "Thin Wall", True)
    return mat


def mat_knit(name, base_hex):
    mat, nt, bsdf = new_material(name)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0, 1.0, 1.0)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    base = rgb_to_linear(base_hex)
    dark = tuple(c * 0.68 for c in base)
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "X"
    wave.inputs["Scale"].default_value = 46.0
    wave.inputs["Distortion"].default_value = 1.8
    wave.inputs["Detail"].default_value = 2.5
    nt.links.new(mp.outputs["Vector"], wave.inputs["Vector"])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 25.0
    noise.inputs["Detail"].default_value = 5.0
    nt.links.new(mp.outputs["Vector"], noise.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.18
    ramp.color_ramp.elements[0].color = (*dark, 1)
    ramp.color_ramp.elements[1].position = 0.82
    ramp.color_ramp.elements[1].color = (*base, 1)
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.5
    bump.inputs["Distance"].default_value = 0.012
    bumpsum = nt.nodes.new("ShaderNodeMath")
    bumpsum.operation = "MULTIPLY"
    nt.links.new(wave.outputs["Fac"], bumpsum.inputs[0])
    nt.links.new(noise.outputs["Fac"], bumpsum.inputs[1])
    nt.links.new(bumpsum.outputs["Value"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    set_in(bsdf, "Roughness", 0.96)
    set_in(bsdf, "Sheen Weight", 0.12)
    set_in(bsdf, "Sheen Roughness", 0.68)
    set_in(bsdf, "Specular IOR Level", 0.16)
    return mat


def mat_metal(name, base_hex, rough=0.3, noise_bump=0.05):
    mat, nt, bsdf = new_material(name)
    base = rgb_to_linear(base_hex)
    bsdf.inputs["Base Color"].default_value = (*base, 1)
    set_in(bsdf, "Metallic", 1.0)
    set_in(bsdf, "Roughness", rough)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 18.0
    noise.inputs["Detail"].default_value = 4.0
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = max(0.05, rough - 0.07)
    mr.inputs["To Max"].default_value = min(0.8, rough + 0.07)
    nt.links.new(noise.outputs["Fac"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], bsdf.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = noise_bump
    bump.inputs["Distance"].default_value = 0.001
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def mat_ceramic(name, base_hex, rough=0.25, coat=0.3):
    mat, nt, bsdf = new_material(name)
    base = rgb_to_linear(base_hex)
    bsdf.inputs["Base Color"].default_value = (*base, 1)
    set_in(bsdf, "Roughness", rough)
    set_in(bsdf, "Coat Weight", coat)
    set_in(bsdf, "Coat Roughness", 0.12)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 20.0
    noise.inputs["Detail"].default_value = 4.0
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    bump.inputs["Distance"].default_value = 0.002
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def mat_glass(name, tint_hex="#E8F4FF", rough=0.025):
    mat, nt, bsdf = new_material(name)
    tint = rgb_to_linear(tint_hex)
    bsdf.inputs["Base Color"].default_value = (*tint, 1)
    set_in(bsdf, "Transmission Weight", 1.0)
    set_in(bsdf, "Roughness", rough)
    set_in(bsdf, "IOR", 1.45)
    mat.use_backface_culling = False
    return mat


def mat_window_glass(name):
    """Mostly transparent glass with a restrained reflection.

    A physically correct thick glass plane reflects too much of the dark room
    when viewed at this oblique angle.  For architectural visualisation we keep
    the transmission and dial the Fresnel reflection down, so the dusk sky and
    garden remain legible while the pane still catches highlights.
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (500, 0)
    transparent = nt.nodes.new("ShaderNodeBsdfTransparent")
    transparent.location = (-50, -120)
    transparent.inputs["Color"].default_value = (0.96, 0.985, 1.0, 1.0)
    gloss = nt.nodes.new("ShaderNodeBsdfGlossy")
    gloss.location = (-50, 100)
    gloss.inputs["Color"].default_value = (0.82, 0.9, 1.0, 1.0)
    gloss.inputs["Roughness"].default_value = 0.035
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.location = (-520, 100)
    lw.inputs["Blend"].default_value = 0.38
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.location = (-320, 120)
    mr.inputs["From Min"].default_value = 0.0
    mr.inputs["From Max"].default_value = 1.0
    mr.inputs["To Min"].default_value = 0.008
    mr.inputs["To Max"].default_value = 0.075
    nt.links.new(lw.outputs["Fresnel"], mr.inputs["Value"])
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.location = (220, 0)
    nt.links.new(mr.outputs["Result"], mix.inputs["Fac"])
    nt.links.new(transparent.outputs["BSDF"], mix.inputs[1])
    nt.links.new(gloss.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    mat.use_backface_culling = False
    return mat


def mat_leaf(name, dark_hex="#1E3A19", light_hex="#5D7A2C", outdoor=False):
    mat, nt, bsdf = new_material(name)
    dark = rgb_to_linear(dark_hex)
    light = rgb_to_linear(light_hex)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 16.0
    noise.inputs["Detail"].default_value = 5.0
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.18
    ramp.color_ramp.elements[0].color = (*dark, 1)
    ramp.color_ramp.elements[1].position = 0.84
    ramp.color_ramp.elements[1].color = (*light, 1)
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    set_in(bsdf, "Roughness", 0.48)
    set_in(bsdf, "Specular IOR Level", 0.34)
    set_in(bsdf, "Subsurface Weight", 0.05)
    set_in(bsdf, "Subsurface Radius", (0.08, 0.16, 0.04))
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "Z"
    wave.inputs["Scale"].default_value = 45.0
    wave.inputs["Distortion"].default_value = 2.0
    nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.16
    bump.inputs["Distance"].default_value = 0.0012
    nt.links.new(wave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    mat.use_backface_culling = False
    return mat


def mat_simple(name, base_hex, rough=0.7, metallic=0.0, coat=0.0):
    mat, nt, bsdf = new_material(name)
    base = rgb_to_linear(base_hex)
    bsdf.inputs["Base Color"].default_value = (*base, 1)
    set_in(bsdf, "Roughness", rough)
    set_in(bsdf, "Metallic", metallic)
    set_in(bsdf, "Coat Weight", coat)
    return mat


def mat_emission(name, color_hex, strength=1.0, node_name="Emission"):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.name = node_name
    em.inputs["Color"].default_value = hexrgba(color_hex)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat


# ---------------------------------------------------------------------------
# Materials library
# ---------------------------------------------------------------------------
M_WALL = mat_plaster("Wall_Warm_Plaster", "#E2D6C7", roughness=0.9, bump=0.08)
M_CEIL = mat_plaster("Ceiling_Warm_White", "#ECE4D9", roughness=0.93, bump=0.03)
M_TRIM = mat_simple("Trim_Cream_Paint", "#EFE8DD", rough=0.45, coat=0.06)

M_OAK_FLOOR = mat_wood("Wood_Floor_Natural_Oak", "#7B5B3E", "#B99066",
                       coarse=26.0, fine=120.0, roughness=0.43, coats=0.06)
M_OAK = mat_wood("Wood_Light_Oak", "#9A7B5C", "#C4A783",
                 coarse=24.0, fine=100.0, roughness=0.46, coats=0.04)
M_OAK_DARK = mat_wood("Wood_Smoked_Oak", "#78583E", "#A17B58",
                      coarse=22.0, fine=95.0, roughness=0.47, coats=0.05)
M_WALNUT = mat_wood("Wood_Walnut_Frame", "#2B1B12", "#5A3A27",
                    coarse=28.0, fine=125.0, roughness=0.38, coats=0.1)
M_WALNUT_LEG = mat_wood("Wood_Walnut_Legs", "#332117", "#674A32",
                        coarse=26.0, fine=110.0, roughness=0.4, coats=0.08)
# vertical grain for the door slab and wardrobe fronts (local Y = width)
M_DOOR_WOOD = mat_wood("Wood_Light_Walnut_Door", "#A48664", "#B69775",
                       coarse=1.2, fine=3.2, roughness=0.47, coats=0.05,
                       direction="Y", distortion=0.3)
M_WARDROBE_WOOD = mat_wood("Wood_Wardrobe_Light", "#BC9C78", "#C9AA86",
                           coarse=1.0, fine=3.0, roughness=0.5, coats=0.03,
                           direction="Y", distortion=0.25)
M_DESK_WOOD = mat_wood("Wood_Desk_Honey_Oak", "#B39470", "#C3A37F",
                       coarse=1.2, fine=3.5, roughness=0.5, coats=0.03,
                       direction="X", distortion=0.3)
M_CONSOLE_WOOD = mat_wood("Wood_TV_Console", "#8C6F53", "#9C805F",
                          coarse=1.3, fine=3.5, roughness=0.5, coats=0.04,
                          direction="X", distortion=0.25)
M_RATTAN = mat_linen("Rattan_Natural_Woven", "#B58B5E", darker_hex="#8E673F",
                     rough=0.82, sheen=0.12, weave_scale=55, bump=0.38)
M_TV_BLACK = mat_simple("TV_Matte_Black", "#101113", rough=0.52)
M_TV_ALLOY = mat_metal("TV_Alloy_Edge", "#4A4C4F", rough=0.32)
M_GAME_WHITE = mat_simple("Game_Console_Warm_White", "#D9D2C4", rough=0.46, coat=0.1)
M_GAME_DARK = mat_simple("Game_Console_Matte_Dark", "#222426", rough=0.5)
M_SCREEN_PRINT = mat_simple("TV_UI_Print", "#E6DCCB", rough=0.65)
M_CANDLE_WAX = mat_simple("Candle_Wax_Cream", "#EADBC4", rough=0.72)
M_LAMP_SHADE_DESK = mat_linen("Lamp_Shade_Desk", "#DFC7A4", darker_hex="#C3A682",
                             rough=0.76, sheen=0.3, transmission=0.25,
                             weave_scale=190, bump=0.18)
_desk_shade_bsdf = M_LAMP_SHADE_DESK.node_tree.nodes.get("Principled_BSDF")
if _desk_shade_bsdf:
    _desk_shade_bsdf.name = "Shade_Principled"
    set_in(_desk_shade_bsdf, "Emission Color", hexrgba("#FFC27D"))
M_BULB_DESK = mat_emission("Bulb_Desk_Mat", "#FFD3A0", strength=0.0,
                           node_name="Desk_Bulb_Emission")
M_TV_UI = mat_emission("TV_UI_Mat", "#F7E5C9", strength=0.9,
                       node_name="TV_UI_Emission")

# The television screen has its own named material and an accessible Emission
# node so the time-of-day controller can dim it independently.
def make_tv_screen_material():
    """Screen material: the supplied game-results capture, emissive.

    The image is packed into the .blend so the scene stays self-contained.  The
    named TV_Emission node is still the single control exposed to the controller.
    """
    mat = bpy.data.materials.new("TV_Screen")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (520, 0)
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.name = "TV_Emission"
    emit.label = "TV screen emission"
    emit.location = (260, 0)
    emit.inputs["Strength"].default_value = 3.0
    if os.path.exists(TV_IMAGE_PATH):
        img = bpy.data.images.load(TV_IMAGE_PATH, check_existing=False)
        img.name = "TV_Screen_Result"
        img.colorspace_settings.name = "sRGB"
        img.pack()
        img.use_fake_user = True
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.name = "TV_Image"
        tex.label = "Game results screen"
        tex.image = img
        tex.interpolation = "Linear"
        tex.extension = "CLIP"
        tex.location = (-60, 40)
        tc = nt.nodes.new("ShaderNodeTexCoord")
        tc.location = (-540, 0)
        mapp = nt.nodes.new("ShaderNodeMapping")
        mapp.location = (-330, 0)
        # The TV plane's front face is UV-mirrored in U; flip the image back so
        # the results screen is not a mirror image.
        mapp.inputs["Scale"].default_value = (-1.0, 1.0, 1.0)
        mapp.inputs["Location"].default_value = (1.0, 0.0, 0.0)
        nt.links.new(tc.outputs["UV"], mapp.inputs["Vector"])
        nt.links.new(mapp.outputs["Vector"], tex.inputs["Vector"])
        nt.links.new(tex.outputs["Color"], emit.inputs["Color"])
    else:
        emit.inputs["Color"].default_value = (*rgb_to_linear("#24100E"), 1)
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    mat.diffuse_color = (0.20, 0.025, 0.02, 1)
    mat.use_fake_user = True
    return mat


M_TV_SCREEN = make_tv_screen_material()

M_LINEN_CREAM = mat_linen("Linen_Cream", "#EDE3D2", darker_hex="#D8C9B4",
                          rough=0.88, sheen=0.32, weave_scale=280, bump=0.24)
M_SHEET_WHITE = mat_linen("Cotton_Sheet_Ivory", "#F1E9DC", darker_hex="#E3D8C8",
                          rough=0.9, sheen=0.25, weave_scale=310, bump=0.19)
M_DUVET = mat_linen("Linen_Duvet_Warm_White", "#E9DFCF", darker_hex="#D9CBB8",
                    rough=0.87, sheen=0.38, weave_scale=220, bump=0.22)
M_DUVET_BAND = mat_linen("Linen_Duvet_Border_Oatmeal", "#B8A084",
                         darker_hex="#9C8368", rough=0.9, sheen=0.34,
                         weave_scale=190, bump=0.26)
M_PILLOW = mat_linen("Cotton_Pillow_Cream", "#E7DCCB", darker_hex="#D5C6B2",
                     rough=0.9, sheen=0.4, weave_scale=260, bump=0.24)
M_PILLOW_TAUPE = mat_linen("Cotton_Pillow_Taupe", "#AD9780", darker_hex="#917B66",
                           rough=0.88, sheen=0.45, weave_scale=250, bump=0.24)
M_PILLOW_CAMEL = mat_linen("Cotton_Pillow_Camel", "#936A4E", darker_hex="#775036",
                           rough=0.88, sheen=0.45, weave_scale=250, bump=0.24)
M_PIPING = mat_simple("Pillow_Piping_Cream", "#CDBAA3", rough=0.8)
M_THROW = mat_knit("Knit_Throw_Caramel", "#96613D")
M_CURTAIN = mat_linen("Linen_Curtain_Beige", "#CDB69E", darker_hex="#B29B81",
                      rough=0.9, sheen=0.3, transmission=0.12,
                      weave_scale=180, bump=0.26)
M_SHEER = mat_linen("Linen_Sheer_Ivory", "#F2E8DA", darker_hex="#E0D3C1",
                    rough=0.9, sheen=0.15, transmission=0.78,
                    weave_scale=200, bump=0.14)
M_RUG = mat_linen("Rug_Cream_Long_Pile", "#C8B69C", darker_hex="#B29D81",
                  rough=0.94, sheen=0.5, weave_scale=120, wrinkle_scale=5.0,
                  bump=0.36)
M_RUG_BORDER = mat_linen("Rug_Border_Taupe", "#9E866D", darker_hex="#826B54",
                         rough=0.95, sheen=0.45, weave_scale=100, bump=0.32)
M_RUG_FIBER = mat_simple("Rug_Fiber_Cream", "#D7C7B0", rough=0.95)
M_SLIPPER = mat_simple("Slipper_Suede_Caramel", "#8A5A39", rough=0.74)
M_SLIPPER_LINING = mat_linen("Slipper_Sheepskin", "#E8DDCB", rough=0.96, sheen=0.4)

M_BRASS = mat_metal("Metal_Aged_Brass", "#B18A55", rough=0.28)
M_BRASS_DARK = mat_metal("Metal_Dark_Bronze", "#6A4D30", rough=0.34)
M_IRON = mat_metal("Metal_Blackened_Iron", "#2C2925", rough=0.38)
M_CERAMIC = mat_ceramic("Ceramic_Warm_White", "#E8DECC", rough=0.22)
M_CERAMIC_TERRA = mat_ceramic("Ceramic_Terracotta", "#A96B4C", rough=0.46, coat=0.08)
M_SOIL = mat_simple("Soil_Dark", "#3B2B20", rough=0.98)
M_BARK = mat_simple("Bark_Fiddle_Fig", "#584333", rough=0.9)
M_PAPER = mat_linen("Paper_Pages", "#E6D8BB", darker_hex="#D3C5A8", rough=0.95,
                    sheen=0.0, weave_scale=350, bump=0.08)
M_BOOK_CLOTH = mat_linen("Book_Cloth_Terracotta", "#8D4F3B", darker_hex="#713C2C",
                         rough=0.84, sheen=0.1, weave_scale=140, bump=0.1)
M_BOOK_GREEN = mat_linen("Book_Cloth_Sage", "#5A6853", darker_hex="#46513F",
                         rough=0.84, sheen=0.1, weave_scale=140, bump=0.1)
M_BOOK_NAVY = mat_linen("Book_Cloth_Navy", "#374255", darker_hex="#293343",
                        rough=0.84, sheen=0.12, weave_scale=140, bump=0.1)
M_COFFEE = mat_simple("Coffee_Liquid", "#2B160D", rough=0.16)
M_GLASS = mat_window_glass("Window_Glass_Clear")
M_GLASS_ART = mat_glass("Artwork_Glass", "#EAF6FF", rough=0.01)
M_LEAF = mat_leaf("Leaf_Fiddle_Fig", "#1F3A18", "#6C8433")
M_LEAF_POTHOS = mat_leaf("Leaf_Pothos", "#365A24", "#88A445")
M_LEAF_VEIN = mat_simple("Leaf_Midrib_Veins", "#8FA45A", rough=0.72)
M_LEAF_SUCCULENT = mat_leaf("Leaf_Succulent_Sage", "#5E7561", "#A6B29A")
M_LEAF_OUT = mat_leaf("Leaf_Outdoor_Tree", "#263D22", "#5A6F35", outdoor=True)
M_LEAF_OUT_DARK = mat_leaf("Leaf_Outdoor_Tree_Dark", "#182A18", "#435A2D", outdoor=True)
M_LEAF_OUT_LIGHT = mat_leaf("Leaf_Outdoor_Tree_Light", "#3B502A", "#7C8E45", outdoor=True)
M_GROUND = mat_plaster("Outdoor_Lawn_Garden", "#4F5B3D", roughness=0.97, bump=0.30)
M_CITY = mat_simple("City_Silhouette_Matte", "#77777A", rough=0.86)
M_CITY_WARM = mat_simple("City_Silhouette_Warm", "#817870", rough=0.86)
# A touch of atmospheric self-lighting keeps the distant skyline from going
# pitch black when the low sun is behind it.
for _cm in (M_CITY, M_CITY_WARM):
    _cbs = _cm.node_tree.nodes.get("Principled_BSDF")
    if _cbs is not None:
        set_in(_cbs, "Emission Color", hexrgba("#8A7378"))
        set_in(_cbs, "Emission Strength", 0.18)
M_HAZE = None  # built below
M_RAIN_GLASS_MOD = None
M_RAIN_GLASS_STORM = None
M_RAIN_CURTAIN_MOD = None
M_RAIN_CURTAIN_STORM = None
M_CITY_LIGHTS = mat_emission("City_Lights_Mat", "#FFC078", strength=0.0,
                             node_name="City_Emission")

M_LAMP_SHADE_BEDSIDE = mat_linen("Lamp_Shade_Bedside", "#E5D4BA",
                                 darker_hex="#CDBA9E", rough=0.74, sheen=0.35,
                                 transmission=0.22, weave_scale=190, bump=0.2)
M_LAMP_SHADE_FLOOR = mat_linen("Lamp_Shade_Floor", "#E4D2B7",
                               darker_hex="#C9B596", rough=0.75, sheen=0.32,
                               transmission=0.22, weave_scale=190, bump=0.2)
# make the lamp shade controllable by controller
for _m in (M_LAMP_SHADE_BEDSIDE, M_LAMP_SHADE_FLOOR):
    _bsdf = _m.node_tree.nodes.get("Principled_BSDF")
    if _bsdf:
        _bsdf.name = "Shade_Principled"
        set_in(_bsdf, "Emission Color", hexrgba("#FFC27D"))
        set_in(_bsdf, "Emission Strength", 0.0)

M_BULB_BEDSIDE = mat_emission("Bulb_Bedside_Mat", "#FFD6A0", strength=0.0,
                              node_name="Bulb_Emission")
M_BULB_FLOOR = mat_emission("Bulb_Floor_Mat", "#FFD19A", strength=0.0,
                            node_name="Bulb_Emission")
M_MOON = mat_emission("Moon_Mat", "#EAF3FF", strength=0.0, node_name="Moon_Emission")
M_SUN_DISC = mat_emission("Sun_Disc_Mat", "#FFD5A1", strength=0.0,
                          node_name="Sun_Disc_Emission")


# --- artwork material ------------------------------------------------------
M_ART = bpy.data.materials.new("Frame_Artwork")
M_ART.use_nodes = True
nt = M_ART.node_tree
nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputMaterial")
out.location = (500, 0)
bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
bsdf.name = "Artwork_BSDF"
bsdf.location = (240, 0)
tex = nt.nodes.new("ShaderNodeTexImage")
tex.name = "Artwork_Image"
tex.location = (-200, 80)
if os.path.exists(ARTWORK_PATH):
    img = bpy.data.images.load(ARTWORK_PATH, check_existing=True)
    img.colorspace_settings.name = "sRGB"
    try:
        img.pack()
    except Exception:
        pass
    tex.image = img
    tex.interpolation = "Cubic"
    tex.extension = "EXTEND"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
set_in(bsdf, "Roughness", 0.5)
set_in(bsdf, "Specular IOR Level", 0.26)
set_in(bsdf, "Coat Weight", 0.08)
set_in(bsdf, "Coat Roughness", 0.18)
nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])


# ---------------------------------------------------------------------------
# Special weather materials
# ---------------------------------------------------------------------------
def make_haze_material():
    mat, nt, bsdf = new_material("Rain_Haze_Mat")
    nt.nodes.remove(bsdf)
    out = nt.nodes.get("Material_Output")
    em = nt.nodes.new("ShaderNodeEmission")
    em.name = "Haze_Emission"
    em.inputs["Color"].default_value = hexrgba("#8DA0A8")
    em.inputs["Strength"].default_value = 0.2
    transparent = nt.nodes.new("ShaderNodeBsdfTransparent")
    transparent.location = (-100, -120)
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.location = (300, 0)
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.location = (-500, -120)
    n.inputs["Scale"].default_value = 2.8
    n.inputs["Detail"].default_value = 3.0
    n.inputs["Roughness"].default_value = 0.5
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-700, -100)
    nt.links.new(tc.outputs["UV"], n.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-280, -100)
    ramp.color_ramp.elements[0].position = 0.2
    ramp.color_ramp.elements[0].color = (0.35, 0.35, 0.35, 1)
    ramp.color_ramp.elements[1].position = 0.8
    ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    nt.links.new(n.outputs["Fac"], ramp.inputs["Fac"])
    op = nt.nodes.new("ShaderNodeValue")
    op.name = "Haze_Opacity"
    op.outputs[0].default_value = 0.0
    op.location = (-280, -300)
    mul = nt.nodes.new("ShaderNodeMath")
    mul.location = (0, -220)
    mul.operation = "MULTIPLY"
    nt.links.new(ramp.outputs["Color"], mul.inputs[0])
    nt.links.new(op.outputs[0], mul.inputs[1])
    nt.links.new(mul.outputs["Value"], mix.inputs["Fac"])
    # emission should be mixed after transparency, with transparent first
    nt.links.new(transparent.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


M_HAZE = make_haze_material()


def make_rain_glass_material(name, dense=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-1000, 0)
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.location = (-820, 0)
    mp.inputs["Scale"].default_value = (4.0, 4.0, 1.0) if not dense else (6.5, 6.5, 1.0)
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.location = (-600, 150)
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = 22.0 if not dense else 30.0
    vor.inputs["Randomness"].default_value = 0.9
    nt.links.new(mp.outputs["Vector"], vor.inputs["Vector"])
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.location = (-600, -150)
    n.inputs["Scale"].default_value = 4.0
    n.inputs["Detail"].default_value = 5.0
    n.inputs["Roughness"].default_value = 0.6
    n2 = nt.nodes.new("ShaderNodeTexNoise")
    n2.location = (-600, -420)
    n2.inputs["Scale"].default_value = 2.0
    n2.inputs["Detail"].default_value = 3.0
    nt.links.new(mp.outputs["Vector"], n.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], n2.inputs["Vector"])
    # drop mask: voronoi edges thin -> invert and clamp
    inv = nt.nodes.new("ShaderNodeMath")
    inv.location = (-380, 160)
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(vor.outputs["Distance"], inv.inputs[1])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-180, 170)
    ramp.color_ramp.elements[0].position = 0.94 if not dense else 0.88
    ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    ramp.color_ramp.elements[1].position = 0.998
    ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    nt.links.new(inv.outputs["Value"], ramp.inputs["Fac"])
    # running streaks
    streak_map = nt.nodes.new("ShaderNodeMapping")
    streak_map.location = (-820, -450)
    streak_map.inputs["Scale"].default_value = (40.0, 0.6, 1.0)
    nt.links.new(tc.outputs["UV"], streak_map.inputs["Vector"])
    streak = nt.nodes.new("ShaderNodeTexNoise")
    streak.location = (-600, -650)
    streak.inputs["Scale"].default_value = 2.2
    streak.inputs["Detail"].default_value = 4.0
    streak.inputs["Distortion"].default_value = 2.3
    nt.links.new(streak_map.outputs["Vector"], streak.inputs["Vector"])
    streak_ramp = nt.nodes.new("ShaderNodeValToRGB")
    streak_ramp.location = (-360, -650)
    streak_ramp.color_ramp.elements[0].position = 0.54
    streak_ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    streak_ramp.color_ramp.elements[1].position = 0.66
    streak_ramp.color_ramp.elements[1].color = (0.7, 0.7, 0.7, 1)
    nt.links.new(streak.outputs["Fac"], streak_ramp.inputs["Fac"])
    addmask = nt.nodes.new("ShaderNodeMath")
    addmask.operation = "MAXIMUM"
    addmask.location = (20, -220)
    nt.links.new(ramp.outputs["Color"], addmask.inputs[0])
    nt.links.new(streak_ramp.outputs["Color"], addmask.inputs[1])
    soften = nt.nodes.new("ShaderNodeMath")
    soften.location = (190, -230)
    soften.operation = "MULTIPLY"
    soften.inputs[1].default_value = 0.28 if not dense else 0.42
    nt.links.new(addmask.outputs["Value"], soften.inputs[0])
    # use blend instead of actual geometry: sparse drops plus a few runs
    glass = nt.nodes.new("ShaderNodeBsdfPrincipled")
    glass.location = (150, 120)
    glass.inputs["Base Color"].default_value = (0.9, 0.96, 1.0, 1)
    set_in(glass, "Transmission Weight", 1.0)
    set_in(glass, "Roughness", 0.10)
    set_in(glass, "IOR", 1.33)
    bump = nt.nodes.new("ShaderNodeBump")
    bump.location = (-80, -430)
    bump.inputs["Strength"].default_value = 0.26 if not dense else 0.38
    bump.inputs["Distance"].default_value = 0.004
    nt.links.new(addmask.outputs["Value"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], glass.inputs["Normal"])
    transparent = nt.nodes.new("ShaderNodeBsdfTransparent")
    transparent.location = (150, -120)
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.location = (400, 0)
    nt.links.new(soften.outputs["Value"], mix.inputs["Fac"])
    nt.links.new(transparent.outputs["BSDF"], mix.inputs[1])
    nt.links.new(glass.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    mat.use_backface_culling = False
    return mat


M_RAIN_GLASS_MOD = make_rain_glass_material("Window_Rain_Moderate", dense=False)
M_RAIN_GLASS_STORM = make_rain_glass_material("Window_Rain_Storm", dense=True)


def make_rain_curtain_mat(name, storm=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-900, 0)
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.location = (-720, 0)
    mp.inputs["Scale"].default_value = (9.0, 0.8, 1.0)
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.location = (-500, 0)
    n.inputs["Scale"].default_value = 3.0
    n.inputs["Detail"].default_value = 5.0
    n.inputs["Roughness"].default_value = 0.55
    n.inputs["Distortion"].default_value = 1.8
    nt.links.new(mp.outputs["Vector"], n.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-280, 0)
    ramp.color_ramp.elements[0].position = 0.54 if not storm else 0.42
    ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    ramp.color_ramp.elements[1].position = 0.66 if not storm else 0.56
    ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    nt.links.new(n.outputs["Fac"], ramp.inputs["Fac"])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.location = (-50, 0)
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = 0.34 if not storm else 0.58
    nt.links.new(ramp.outputs["Color"], mul.inputs[0])
    em = nt.nodes.new("ShaderNodeEmission")
    em.location = (160, 100)
    em.inputs["Color"].default_value = hexrgba("#A8C2CE")
    em.inputs["Strength"].default_value = 0.35 if not storm else 0.2
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    tr.location = (160, -100)
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.location = (390, 0)
    nt.links.new(mul.outputs["Value"], mix.inputs["Fac"])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    mat.use_backface_culling = False
    return mat


M_RAIN_CURTAIN_MOD = make_rain_curtain_mat("Rain_Curtain_Moderate", storm=False)
M_RAIN_CURTAIN_STORM = make_rain_curtain_mat("Rain_Curtain_Storm", storm=True)


def make_sky_material(name, cloud_cover_lo, cloud_cover_hi, cloud_scale, strength):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (900, 0)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-1100, 100)
    norm = nt.nodes.new("ShaderNodeVectorMath")
    norm.location = (-900, 250)
    norm.operation = "NORMALIZE"
    nt.links.new(tc.outputs["Object"], norm.inputs[0])
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-720, 300)
    nt.links.new(norm.outputs["Vector"], sep.inputs["Vector"])
    maprange = nt.nodes.new("ShaderNodeMapRange")
    maprange.location = (-540, 300)
    maprange.inputs["From Min"].default_value = -0.05
    maprange.inputs["From Max"].default_value = 0.72
    maprange.inputs["To Min"].default_value = 0.0
    maprange.inputs["To Max"].default_value = 1.0
    nt.links.new(sep.outputs["Z"], maprange.inputs["Value"])
    gradient = nt.nodes.new("ShaderNodeValToRGB")
    gradient.name = "Sky_Gradient"
    gradient.location = (-320, 320)
    gradient.color_ramp.interpolation = "EASE"
    els = gradient.color_ramp.elements
    els[0].position = 0.0
    els[0].color = hexrgba("#E7F2FB")
    els[1].position = 0.18
    els[1].color = hexrgba("#B5D5ED")
    e2 = els.new(0.52)
    e2.color = hexrgba("#5D95CE")
    e3 = els.new(0.88)
    e3.color = hexrgba("#2C68B0")
    nt.links.new(maprange.outputs["Result"], gradient.inputs["Fac"])
    # cloud base mask
    cmap = nt.nodes.new("ShaderNodeMapping")
    cmap.location = (-900, -60)
    cmap.inputs["Scale"].default_value = cloud_scale
    nt.links.new(norm.outputs["Vector"], cmap.inputs["Vector"])
    cn = nt.nodes.new("ShaderNodeTexNoise")
    cn.location = (-700, -60)
    cn.inputs["Scale"].default_value = 3.2
    cn.inputs["Detail"].default_value = 9.0
    cn.inputs["Roughness"].default_value = 0.62
    cn.inputs["Distortion"].default_value = 0.25
    nt.links.new(cmap.outputs["Vector"], cn.inputs["Vector"])
    cramp = nt.nodes.new("ShaderNodeValToRGB")
    cramp.name = "Cloud_Ramp"
    cramp.location = (-470, -80)
    cramp.color_ramp.interpolation = "EASE"
    cramp.color_ramp.elements[0].position = cloud_cover_lo
    cramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    cramp.color_ramp.elements[1].position = cloud_cover_hi
    cramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    nt.links.new(cn.outputs["Fac"], cramp.inputs["Fac"])
    # cloud shade variation
    cn2 = nt.nodes.new("ShaderNodeTexNoise")
    cn2.location = (-700, -380)
    cn2.inputs["Scale"].default_value = 9.0
    cn2.inputs["Detail"].default_value = 5.0
    cn2.inputs["Roughness"].default_value = 0.5
    nt.links.new(cmap.outputs["Vector"], cn2.inputs["Vector"])
    shade = nt.nodes.new("ShaderNodeValToRGB")
    shade.location = (-470, -390)
    shade.color_ramp.elements[0].position = 0.25
    shade.color_ramp.elements[0].color = (0, 0, 0, 1)
    shade.color_ramp.elements[1].position = 0.78
    shade.color_ramp.elements[1].color = (1, 1, 1, 1)
    nt.links.new(cn2.outputs["Fac"], shade.inputs["Fac"])
    cdl = nt.nodes.new("ShaderNodeRGB")
    cdl.name = "Cloud_Color_Dark"
    cdl.location = (-470, -620)
    cdl.outputs[0].default_value = hexrgba("#AABACB")
    cl = nt.nodes.new("ShaderNodeRGB")
    cl.name = "Cloud_Color_Light"
    cl.location = (-470, -800)
    cl.outputs[0].default_value = hexrgba("#FFFFFF")
    cloudcol = nt.nodes.new("ShaderNodeMixRGB")
    cloudcol.location = (-210, -480)
    nt.links.new(shade.outputs["Color"], cloudcol.inputs["Fac"])
    nt.links.new(cdl.outputs[0], cloudcol.inputs["Color1"])
    nt.links.new(cl.outputs[0], cloudcol.inputs["Color2"])
    skymix = nt.nodes.new("ShaderNodeMixRGB")
    skymix.name = "Sky_Cloud_Mix"
    skymix.location = (50, 180)
    nt.links.new(cramp.outputs["Color"], skymix.inputs["Fac"])
    nt.links.new(gradient.outputs["Color"], skymix.inputs["Color1"])
    nt.links.new(cloudcol.outputs["Color"], skymix.inputs["Color2"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.name = "Sky_Emission"
    em.location = (360, 100)
    em.inputs["Strength"].default_value = strength
    nt.links.new(skymix.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    mat.use_backface_culling = False
    return mat


M_SKY_SUNNY = make_sky_material("Sky_Sunny", 0.63, 0.74, (2.2, 2.2, 1.2), 1.5)
M_SKY_CLOUDY = make_sky_material("Sky_Cloudy", 0.39, 0.58, (2.6, 2.6, 1.4), 1.1)
M_SKY_RAINY = make_sky_material("Sky_Rainy", 0.27, 0.50, (3.2, 3.2, 1.7), 0.85)
M_SKY_STORM = make_sky_material("Sky_Storm", 0.18, 0.42, (3.8, 3.8, 2.0), 0.55)

# Weather variants are not all assigned to an object at once, so mark them as
# fake users.  Without this Blender would purge them on save and the
# controller's weather switch would silently have nothing to switch to.
for _weather_mat in (M_SKY_SUNNY, M_SKY_CLOUDY, M_SKY_RAINY, M_SKY_STORM,
                     M_RAIN_GLASS_MOD, M_RAIN_GLASS_STORM,
                     M_RAIN_CURTAIN_MOD, M_RAIN_CURTAIN_STORM):
    _weather_mat.use_fake_user = True


# ---------------------------------------------------------------------------
# Architecture
# ---------------------------------------------------------------------------
# subfloor
make_box("Subfloor", (ROOM_X + 0.2, ROOM_Y + 0.2, 0.06), (0, 0, -0.045),
         COL_ARCH, M_OAK_FLOOR, bevel=0.0, smooth=False)

# oak planks
x = -ROOM_X / 2 - 0.01
row = 0
while x < ROOM_X / 2:
    w = random.uniform(0.15, 0.205)
    x0 = x + 0.0018
    x1 = min(ROOM_X / 2, x + w - 0.0018)
    if x1 - x0 < 0.04:
        break
    y = -ROOM_Y / 2 - 0.015
    offset = random.uniform(0.0, 0.75) * (row % 2)
    if offset:
        first_len = random.uniform(0.5, 1.1)
        make_box("FloorBoard_%02d_00" % row,
                 (x1 - x0, first_len, 0.024),
                 ((x0 + x1) / 2, -ROOM_Y / 2 + first_len / 2 - 0.015, -0.012),
                 COL_ARCH, M_OAK_FLOOR, bevel=0.0016, segments=1, smooth=True)
        y = -ROOM_Y / 2 + first_len - 0.015
    seg = 1
    while y < ROOM_Y / 2:
        ln = random.uniform(1.1, 2.2)
        ya = max(-ROOM_Y / 2, y)
        yb = min(ROOM_Y / 2, y + ln)
        if yb - ya > 0.05:
            make_box("FloorBoard_%02d_%02d" % (row, seg),
                     (x1 - x0, yb - ya - 0.004, 0.024),
                     ((x0 + x1) / 2, (ya + yb) / 2, -0.012),
                     COL_ARCH, M_OAK_FLOOR, bevel=0.0016, segments=1, smooth=True)
            seg += 1
        y += ln
    x += w
    row += 1

# walls
make_box("Wall_Back", (ROOM_X + 0.3, WALL_T, ROOM_Z), (0, ROOM_Y / 2 + WALL_T / 2, ROOM_Z / 2),
         COL_ARCH, M_WALL, bevel=0.001, smooth=False)
make_box("Wall_Left", (WALL_T, ROOM_Y + 0.3, ROOM_Z), (-ROOM_X / 2 - WALL_T / 2, 0, ROOM_Z / 2),
         COL_ARCH, M_WALL, bevel=0.001, smooth=False)
make_box("Wall_Front", (ROOM_X + 0.3, WALL_T, ROOM_Z), (0, -ROOM_Y / 2 - WALL_T / 2, ROOM_Z / 2),
         COL_ARCH, M_WALL, bevel=0.001, smooth=False)
# right wall split around the window
make_box("Wall_Right_Front", (WALL_T, WIN_Y0 + ROOM_Y / 2, ROOM_Z),
         (ROOM_X / 2 + WALL_T / 2, (-ROOM_Y / 2 + WIN_Y0) / 2, ROOM_Z / 2),
         COL_ARCH, M_WALL, bevel=0.001, smooth=False)
make_box("Wall_Right_Back", (WALL_T, ROOM_Y / 2 - WIN_Y1, ROOM_Z),
         (ROOM_X / 2 + WALL_T / 2, (WIN_Y1 + ROOM_Y / 2) / 2, ROOM_Z / 2),
         COL_ARCH, M_WALL, bevel=0.001, smooth=False)
make_box("Wall_Right_Below", (WALL_T, WIN_Y1 - WIN_Y0, WIN_Z0),
         (ROOM_X / 2 + WALL_T / 2, (WIN_Y0 + WIN_Y1) / 2, WIN_Z0 / 2),
         COL_ARCH, M_WALL, bevel=0.001, smooth=False)
make_box("Wall_Right_Above", (WALL_T, WIN_Y1 - WIN_Y0, ROOM_Z - WIN_Z1),
         (ROOM_X / 2 + WALL_T / 2, (WIN_Y0 + WIN_Y1) / 2, (WIN_Z1 + ROOM_Z) / 2),
         COL_ARCH, M_WALL, bevel=0.001, smooth=False)

# ceiling
make_box("Ceiling", (ROOM_X + 0.3, ROOM_Y + 0.3, 0.12), (0, 0, ROOM_Z + 0.06),
         COL_ARCH, M_CEIL, bevel=0.0, smooth=False)

# baseboards
def baseboard(name, center, size, rot=0):
    make_box(name, size, center, COL_ARCH, M_TRIM, rotation=(0, 0, rot),
             bevel=0.003, segments=2, smooth=True)
    # top cap
    sx, sy, sz = size
    make_box(name + "_Cap", (sx + 0.008, sy + 0.012, 0.012),
             (center[0], center[1] - (0.01 if sy < sx else 0), center[2] + sz / 2),
             COL_ARCH, M_TRIM, rotation=(0, 0, rot), bevel=0.004, segments=2,
             smooth=True)

baseboard("Baseboard_Back", (0, ROOM_Y / 2 - 0.012, 0.045), (ROOM_X, 0.024, 0.09))
baseboard("Baseboard_Front", (0, -ROOM_Y / 2 + 0.012, 0.045), (ROOM_X, 0.024, 0.09))
baseboard("Baseboard_Left", (-ROOM_X / 2 + 0.012, 0, 0.045), (0.024, ROOM_Y, 0.09), rot=math.pi / 2)
baseboard("Baseboard_Right_F", (ROOM_X / 2 - 0.012, (-ROOM_Y / 2 + WIN_Y0) / 2, 0.045),
          (0.024, WIN_Y0 + ROOM_Y / 2, 0.09), rot=math.pi / 2)
baseboard("Baseboard_Right_B", (ROOM_X / 2 - 0.012, (WIN_Y1 + ROOM_Y / 2) / 2, 0.045),
          (0.024, ROOM_Y / 2 - WIN_Y1, 0.09), rot=math.pi / 2)

# crown moulding (subtle, warm white)
for nm, loc, size, rot in [
    ("Crown_Back", (0, ROOM_Y / 2 - 0.035, ROOM_Z - 0.045), (ROOM_X, 0.07, 0.09), 0),
    ("Crown_Left", (-ROOM_X / 2 + 0.035, 0, ROOM_Z - 0.045), (0.07, ROOM_Y, 0.09), math.pi / 2),
    ("Crown_Right", (ROOM_X / 2 - 0.035, 0, ROOM_Z - 0.045), (0.07, ROOM_Y, 0.09), math.pi / 2),
]:
    make_box(nm, size, loc, COL_ARCH, M_TRIM, rotation=(0, 0, rot),
             bevel=0.008, segments=2, smooth=True)


# ---------------------------------------------------------------------------
# Window: frame, sill, glass, reveal, rod
# ---------------------------------------------------------------------------
win_cx = ROOM_X / 2 + 0.005
win_cy = (WIN_Y0 + WIN_Y1) / 2
win_h = WIN_Z1 - WIN_Z0
win_w = WIN_Y1 - WIN_Y0

# outer casing (inside face of the wall)
make_box("Window_Casing_Near", (0.055, 0.10, win_h + 0.16), (ROOM_X / 2 - 0.028, WIN_Y0 - 0.04, win_cy),
         COL_WINDOW, M_TRIM, bevel=0.008, segments=2)
make_box("Window_Casing_Far", (0.055, 0.10, win_h + 0.16), (ROOM_X / 2 - 0.028, WIN_Y1 + 0.04, win_cy),
         COL_WINDOW, M_TRIM, bevel=0.008, segments=2)
make_box("Window_Casing_Top", (0.055, win_w + 0.24, 0.10), (ROOM_X / 2 - 0.028, win_cy, WIN_Z1 + 0.045),
         COL_WINDOW, M_TRIM, bevel=0.008, segments=2)
make_box("Window_Sill", (0.24, win_w + 0.28, 0.055), (ROOM_X / 2 - 0.105, win_cy, WIN_Z0 - 0.016),
         COL_WINDOW, M_TRIM, bevel=0.012, segments=3)
make_box("Window_Sill_Apron", (0.028, win_w + 0.22, 0.10), (ROOM_X / 2 - 0.018, win_cy, WIN_Z0 - 0.095),
         COL_WINDOW, M_TRIM, bevel=0.006, segments=2)

# reveal / jamb boxes
make_box("Window_Jamb_Near", (WALL_T + 0.03, 0.035, win_h), (ROOM_X / 2 + WALL_T / 2, WIN_Y0 + 0.018, win_cy),
         COL_WINDOW, M_TRIM, bevel=0.004)
make_box("Window_Jamb_Far", (WALL_T + 0.03, 0.035, win_h), (ROOM_X / 2 + WALL_T / 2, WIN_Y1 - 0.018, win_cy),
         COL_WINDOW, M_TRIM, bevel=0.004)
make_box("Window_Head_Jamb", (WALL_T + 0.03, win_w, 0.035), (ROOM_X / 2 + WALL_T / 2, win_cy, WIN_Z1 - 0.018),
         COL_WINDOW, M_TRIM, bevel=0.004)

# window sash frame, centered in the wall depth
sash_x = ROOM_X / 2 + 0.065
frame_w = 0.045
# outer frame
make_box("Window_Sash_Near", (0.06, frame_w, win_h), (sash_x, WIN_Y0 + frame_w / 2, win_cy),
         COL_WINDOW, M_TRIM, bevel=0.004)
make_box("Window_Sash_Far", (0.06, frame_w, win_h), (sash_x, WIN_Y1 - frame_w / 2, win_cy),
         COL_WINDOW, M_TRIM, bevel=0.004)
make_box("Window_Sash_Bottom", (0.06, win_w, frame_w), (sash_x, win_cy, WIN_Z0 + frame_w / 2),
         COL_WINDOW, M_TRIM, bevel=0.004)
make_box("Window_Sash_Top", (0.06, win_w, frame_w), (sash_x, win_cy, WIN_Z1 - frame_w / 2),
         COL_WINDOW, M_TRIM, bevel=0.004)
# mullions: vertical center + horizontal transom
make_box("Window_Mullion_V", (0.05, 0.030, win_h - 2 * frame_w),
         (sash_x, win_cy, (WIN_Z0 + WIN_Z1) / 2), COL_WINDOW, M_TRIM,
         bevel=0.003, segments=2)
make_box("Window_Mullion_H", (0.05, win_w - 2 * frame_w, 0.030),
         (sash_x, win_cy, WIN_Z0 + 0.56), COL_WINDOW, M_TRIM,
         bevel=0.003, segments=2)

# glass
make_rect("Window_Glass", (sash_x, win_cy, (WIN_Z0 + WIN_Z1) / 2),
          win_w - 2 * frame_w - 0.02, win_h - 2 * frame_w - 0.02, "YZ",
          COL_WINDOW, M_GLASS)
window_glass_obj = bpy.data.objects.get("Window_Glass")
window_glass_obj.visible_shadow = False
window_glass_obj.visible_diffuse = False
window_glass_obj.visible_glossy = False

# rain overlay inside the glass
make_rect("Rain_Glass_Overlay", (ROOM_X / 2 - 0.002, win_cy, (WIN_Z0 + WIN_Z1) / 2),
          win_w - 2 * frame_w - 0.015, win_h - 2 * frame_w - 0.015, "YZ",
          COL_WINDOW, M_RAIN_GLASS_MOD)
rain_overlay = bpy.data.objects.get("Rain_Glass_Overlay")
rain_overlay.visible_shadow = False
rain_overlay.hide_render = True
rain_overlay.hide_viewport = True

# window hardware: a little brass latch
make_box("Window_Latch", (0.025, 0.055, 0.015), (ROOM_X / 2 - 0.03, win_cy, WIN_Z0 + 0.60),
         COL_WINDOW, M_BRASS, bevel=0.004, segments=3)
make_uv_sphere("Window_Latch_Knob", 0.018, (ROOM_X / 2 - 0.045, win_cy - 0.03, WIN_Z0 + 0.60),
               COL_WINDOW, M_BRASS, segments=24, rings=12)

# curtain rod
rod_y0, rod_y1 = WIN_Y0 - 0.38, WIN_Y1 + 0.38
make_curve("Curtain_Rod", [[(ROOM_X / 2 - 0.18, rod_y0, 2.55),
                            (ROOM_X / 2 - 0.18, rod_y1, 2.55)]],
           0.014, COL_WINDOW, M_BRASS_DARK, resolution=2, bevel_resolution=2)
for y in (rod_y0, rod_y1):
    make_uv_sphere("Curtain_Rod_Finial_%.2f" % y, 0.033,
                   (ROOM_X / 2 - 0.18, y, 2.55), COL_WINDOW, M_BRASS,
                   segments=32, rings=16)
make_box("Curtain_Rod_Bracket_L", (0.10, 0.025, 0.025),
         (ROOM_X / 2 - 0.12, rod_y0 + 0.3, 2.52), COL_WINDOW, M_BRASS_DARK,
         bevel=0.003)
make_box("Curtain_Rod_Bracket_R", (0.10, 0.025, 0.025),
         (ROOM_X / 2 - 0.12, rod_y1 - 0.3, 2.52), COL_WINDOW, M_BRASS_DARK,
         bevel=0.003)

# curtain rings
ring_y = [rod_y0 + 0.12 + i * 0.16 for i in range(int((rod_y1 - rod_y0 - 0.20) / 0.16) + 1)]
for i, y in enumerate(ring_y):
    make_torus("Curtain_Ring_%02d" % i, 0.028, 0.004,
               (ROOM_X / 2 - 0.18, y, 2.53), COL_WINDOW, M_BRASS_DARK,
               rotation=(0, math.pi / 2, 0), major_segments=24, minor_segments=6)


# ---------------------------------------------------------------------------
# Curtains (folded cloth)
# ---------------------------------------------------------------------------
def make_curtain_panel(name, y_center, width, x_plane, top, bottom, folds,
                       amplitude, collection, mat, phase=0.0):
    nu, nv = 46, 70
    verts = []
    for j in range(nv + 1):
        v = j / nv
        z = bottom + (top - bottom) * v
        # top gathered a little less deep, bottom folds fall open
        amp = amplitude * (0.58 + 0.42 * (1.0 - v))
        for i in range(nu + 1):
            u = i / nu
            y = y_center + width * (u - 0.5)
            fold = amp * (0.6 * math.sin(2 * math.pi * folds * u + phase)
                          + 0.3 * math.sin(4 * math.pi * folds * u + 0.7 + phase))
            x = x_plane - 0.030 + fold
            # a little sag and wave at the bottom
            zz = z + 0.012 * math.sin(3.0 * u * math.pi + 0.3) * (1.0 - v) ** 2
            verts.append((x, y, zz))
    faces = []
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            b = a + 1
            c = a + (nu + 1) + 1
            d = a + (nu + 1)
            faces.append((a, b, c, d))
    obj = mesh_object(name, verts, faces, collection, mat, smooth=True)
    add_solidify(obj, 0.008, offset=0.0)
    # tiny rolled hem, represented by an edge bevel
    return obj


make_curtain_panel("Curtain_Near", WIN_Y0 - 0.23, 0.62, ROOM_X / 2 - 0.07,
                   2.521, 0.018, 5.0, 0.052, COL_WINDOW, M_CURTAIN, phase=0.3)
make_curtain_panel("Curtain_Far", WIN_Y1 + 0.23, 0.62, ROOM_X / 2 - 0.07,
                   2.521, 0.018, 5.0, 0.052, COL_WINDOW, M_CURTAIN, phase=1.9)

# sheer panel, drawn across roughly half the glass at noon
make_curtain_panel("Curtain_Sheer", WIN_Y0 + 0.44, 0.95, ROOM_X / 2 - 0.055,
                   2.48, 0.03, 6.5, 0.030, COL_WINDOW, M_SHEER, phase=0.9)
bpy.data.objects["Curtain_Sheer"].hide_render = True
bpy.data.objects["Curtain_Sheer"].hide_viewport = True


# ---------------------------------------------------------------------------
# Rug and fringes
# ---------------------------------------------------------------------------
# A proper bedside runner on the window side where feet land when getting out.
RUG_C = (1.15, -0.20)
RUG_W, RUG_H = 1.15, 2.70
make_rounded_plane("Rug", RUG_C, RUG_W, RUG_H, 0.14, 0.018, COL_DECOR, M_RUG,
                   thickness=0.018, bevel=0.006)
# long pile fuzz: short fibres scattered over the exposed part of the rug
fibre_paths = []
for i in range(6200):
    t = random.uniform(0, 2 * math.pi)
    rr = random.uniform(0.52, 1.0)
    px = RUG_C[0] + 0.5 * RUG_W * rr * math.copysign(abs(math.cos(t)) ** 0.26, math.cos(t))
    py = RUG_C[1] + 0.5 * RUG_H * rr * math.copysign(abs(math.sin(t)) ** 0.26, math.sin(t))
    z0 = 0.033
    h = random.uniform(0.009, 0.021)
    dx = random.uniform(-0.008, 0.008)
    dy = random.uniform(-0.008, 0.008)
    fibre_paths.append([(px, py, z0), (px + dx * 0.7, py + dy * 0.7, z0 + h * 0.65),
                        (px + dx, py + dy, z0 + h)])
make_curve("Rug_Fibers", fibre_paths, 0.00085, COL_DECOR, M_RUG_FIBER,
           resolution=1, bevel_resolution=0)
# tassels on the two short ends
tassels = []
for side in (-1, 1):
    y_edge = RUG_C[1] + side * RUG_H / 2
    for i in range(105):
        x = -RUG_W / 2 + 0.10 + (RUG_W - 0.20) * i / 104 + random.uniform(-0.004, 0.004)
        x += RUG_C[0]
        out = side * random.uniform(0.055, 0.085)
        wig = random.uniform(-0.018, 0.018)
        tassels.append([(x, y_edge, 0.02),
                        (x + wig * 0.4, y_edge + out * 0.5, 0.014),
                        (x + wig, y_edge + out, 0.008)])
make_curve("Rug_Tassels", tassels, 0.0018, COL_DECOR, M_RUG_FIBER,
           resolution=1, bevel_resolution=0)


# ---------------------------------------------------------------------------
# Bed
# ---------------------------------------------------------------------------
# wooden base
for x in (BED_CX - BED_HW + 0.10, BED_CX + BED_HW - 0.10):
    for y in (BED_Y0 + 0.11, BED_Y1 - 0.11):
        make_box("Bed_Leg", (0.085, 0.085, 0.34),
                 (x, y, 0.17), COL_FURN, M_WALNUT_LEG, bevel=0.01, segments=3)
make_box("Bed_Side_Rail_L", (0.065, BED_Y1 - BED_Y0 - 0.10, 0.18),
         (BED_CX - BED_HW + 0.025, (BED_Y0 + BED_Y1) / 2, 0.38),
         COL_FURN, M_WALNUT_LEG, bevel=0.008, segments=2)
make_box("Bed_Side_Rail_R", (0.065, BED_Y1 - BED_Y0 - 0.10, 0.18),
         (BED_CX + BED_HW - 0.025, (BED_Y0 + BED_Y1) / 2, 0.38),
         COL_FURN, M_WALNUT_LEG, bevel=0.008, segments=2)
make_box("Bed_Foot_Rail", (2 * BED_HW - 0.02, 0.065, 0.20),
         (BED_CX, BED_Y0 + 0.035, 0.40), COL_FURN, M_WALNUT_LEG,
         bevel=0.01, segments=3)
make_box("Bed_Base", (2 * BED_HW - 0.10, BED_Y1 - BED_Y0 - 0.12, 0.20),
         (BED_CX, (BED_Y0 + BED_Y1) / 2, 0.39), COL_FURN, M_WALNUT_LEG,
         bevel=0.01, segments=2)

# headboard posts / rails / slats
for x in (BED_CX - BED_HW, BED_CX + BED_HW):
    make_box("Bed_Headboard_Post", (0.078, 0.078, 0.90),
             (x, BED_Y1 - 0.04, 0.82), COL_FURN, M_WALNUT_LEG,
             bevel=0.012, segments=3)
make_box("Bed_Headboard_TopRail", (2 * BED_HW + 0.04, 0.062, 0.075),
         (BED_CX, BED_Y1 - 0.04, 1.245), COL_FURN, M_WALNUT_LEG,
         bevel=0.018, segments=4)
make_box("Bed_Headboard_BottomRail", (2 * BED_HW - 0.02, 0.05, 0.045),
         (BED_CX, BED_Y1 - 0.04, 0.62), COL_FURN, M_WALNUT_LEG,
         bevel=0.008, segments=2)
# solid panelled wood headboard (not a skeletal row of thin slats)
make_box("Bed_Headboard_BackPanel", (2 * BED_HW - 0.04, 0.026, 0.57),
         (BED_CX, BED_Y1 - 0.005, 0.915), COL_FURN, M_WALNUT_LEG,
         bevel=0.006, segments=2)
panel_bottoms = 0.65
panel_h = 0.55
n_boards = 8
board_w = 0.188
gap = 0.012
total_w = n_boards * board_w + (n_boards - 1) * gap
start_x = BED_CX - total_w / 2 + board_w / 2
for i in range(n_boards):
    xx = start_x + i * (board_w + gap)
    make_box("Bed_Headboard_Batten_%02d" % i, (board_w, 0.018, panel_h),
             (xx, BED_Y1 - 0.035, panel_bottoms + panel_h / 2),
             COL_FURN, M_OAK, bevel=0.006, segments=3)

# mattress
make_box("Mattress", (2 * BED_HW - 0.12, BED_Y1 - BED_Y0 - 0.10, 0.28),
         (BED_CX, (BED_Y0 + BED_Y1) / 2, 0.585), COL_BED, M_SHEET_WHITE,
         bevel=0.075, segments=5, smooth=True)
# a sliver of a bed skirt / fitted sheet around the base
make_box("Fitted_Sheet_Apron", (2 * BED_HW - 0.12, 0.024, 0.18),
         (BED_CX, BED_Y0 + 0.045, 0.48), COL_BED, M_SHEET_WHITE,
         bevel=0.012, segments=3)


# duvet top ---------------------------------------------------------------
def make_duvet():
    nx, ny = 78, 80
    x0, x1 = BED_CX - BED_HW - 0.035, BED_CX + BED_HW + 0.035
    y0, y1 = BED_Y0 + 0.02, 1.99
    verts, uvs = [], []
    for j in range(ny + 1):
        v = j / ny
        y = y0 + (y1 - y0) * v
        for i in range(nx + 1):
            u = i / nx
            x = x0 + (x1 - x0) * u
            ex = min(u, 1 - u)
            ey = min(v, 1 - v)
            soft_edge = min(1.0, ex * 8.0) * min(1.0, ey * 7.0)
            broad = mnoise.noise(Vector((x * 3.2 + 4.1, y * 2.4, 0.7)))
            fine = mnoise.noise(Vector((x * 11.0, y * 8.0 + 5.2, 1.7)))
            folds = (0.0082 * math.sin(8.3 * x + 1.7 * math.sin(3.1 * y))
                     + 0.0052 * math.cos(5.2 * y + 2.0 * x)
                     + 0.0060 * broad + 0.0030 * fine)
            diag = math.exp(-(((y - 0.70) - 1.15 * (x - BED_CX)) ** 2) / 0.040)
            crease = (math.exp(-((x - (BED_CX + 0.38)) ** 2) / 0.014)
                      * math.exp(-((y - 1.18) ** 2) / 0.18))
            shoulder = math.exp(-((x - (BED_CX - 0.64)) ** 2) / 0.02) * (0.25 + 0.75 * v)
            z = (0.750 + 0.027 * soft_edge + 0.010 * math.sin(math.pi * v)
                 + folds - 0.012 * diag - 0.006 * crease - 0.005 * shoulder)
            verts.append((x, y, z))
            uvs.append((u, v))
    faces = []
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            b = a + 1
            c = a + (nx + 1) + 1
            d = a + (nx + 1)
            faces.append((a, b, c, d))
    obj = mesh_object("Duvet_Top", verts, faces, COL_BED, M_DUVET,
                      smooth=True, uvs=uvs)
    add_solidify(obj, 0.022, offset=-1.0)
    return obj


make_duvet()


def make_duvet_side(name, side, x_fixed=None, y_fixed=None, y0=None, y1=None,
                    x0=None, x1=None, top=0.748, bottom=0.45):
    n_u, n_v = 64, 32
    verts = []
    for j in range(n_v + 1):
        v = j / n_v
        for i in range(n_u + 1):
            u = i / n_u
            phase = 1.3 if side == "front" else (2.1 if side == "left" else 3.4)
            hem_noise = mnoise.noise(Vector((u * 5.2 + phase, v * 3.0, 1.4)))
            # a tailored, almost straight hem; the folds live above it
            hem = (0.004 * (v ** 2.0) * math.sin(2.4 * math.pi * u + phase)
                   + 0.002 * (v ** 2.0) * hem_noise)
            z = top - (top - bottom) * v + hem
            amp = 0.019 * (0.22 + 0.78 * v) * (1.0 - 0.55 * (v ** 3))
            if side in ("left", "right"):
                y = y0 + (y1 - y0) * u
                fold = amp * (0.72 * math.sin(3.8 * math.pi * u + z * 3.8 + phase)
                              + 0.28 * math.sin(6.4 * math.pi * u + 0.7))
                x = x_fixed + (fold if side == "left" else -fold)
                verts.append((x, y, z + 0.003 * math.sin(3.0 * math.pi * u) * v))
            else:
                x = x0 + (x1 - x0) * u
                fold = amp * (0.72 * math.sin(3.8 * math.pi * u + z * 3.8 + 1.1)
                              + 0.28 * math.cos(5.7 * math.pi * u))
                y = y_fixed + (fold if side == "front" else -fold)
                verts.append((x, y, z + 0.002 * math.sin(2.8 * math.pi * u) * v))
    faces = []
    for j in range(n_v):
        for i in range(n_u):
            a = j * (n_u + 1) + i
            b = a + 1
            c = a + (n_u + 1) + 1
            d = a + (n_u + 1)
            faces.append((a, b, c, d))
    obj = mesh_object(name, verts, faces, COL_BED, M_DUVET, smooth=True)
    add_solidify(obj, 0.010, offset=0.0)
    return obj


make_duvet_side("Duvet_Drop_Left", "left",
                x_fixed=BED_CX - BED_HW - 0.035,
                y0=BED_Y0 + 0.02, y1=1.99)
make_duvet_side("Duvet_Drop_Right", "right",
                x_fixed=BED_CX + BED_HW + 0.035,
                y0=BED_Y0 + 0.02, y1=1.99)
# The foot of the duvet is folded over the mattress rather than hanging as a
# long curtain; the dark wooden platform remains visible underneath.
foot_roll = []
for i in range(46):
    u = i / 45
    xx = BED_CX - BED_HW - 0.03 + (2 * BED_HW + 0.06) * u
    foot_roll.append((xx, BED_Y0 + 0.005 + 0.004 * math.sin(u * 10.0),
                      0.740 + 0.006 * math.sin(u * 7.0 + 0.5)))
make_curve("Duvet_Foot_Roll", [foot_roll], 0.018, COL_BED, M_DUVET,
           resolution=2, bevel_resolution=3)

# rolled top edge
roll_path = []
for i in range(42):
    u = i / 41
    xx = BED_CX - BED_HW - 0.02 + (2 * BED_HW + 0.04) * u
    roll_path.append((xx, 1.985 + 0.008 * math.sin(u * 9.0),
                      0.776 + 0.005 * math.sin(u * 8.0 + 1.0)))
make_curve("Duvet_Folded_Edge", [roll_path], 0.022, COL_BED, M_DUVET,
           resolution=2, bevel_resolution=3)


# pillows -----------------------------------------------------------------
make_superellipsoid("Pillow_Cream_L", (0.78, 0.22, 0.50),
                    (BED_CX - 0.35, 2.19, 0.95), COL_BED, M_PILLOW,
                    exponent=0.49, rotation=(-0.32, 0.02, 0.02),
                    wrinkle=0.010)
make_superellipsoid("Pillow_Taupe_R", (0.75, 0.22, 0.48),
                    (BED_CX + 0.355, 2.205, 0.955), COL_BED, M_PILLOW_TAUPE,
                    exponent=0.49, rotation=(-0.29, -0.015, -0.045),
                    wrinkle=0.010)
make_superellipsoid("Pillow_Camel", (0.56, 0.19, 0.33),
                    (BED_CX + 0.015, 2.045, 0.85), COL_BED, M_PILLOW_CAMEL,
                    exponent=0.51, rotation=(-0.22, 0.01, 0.04),
                    wrinkle=0.007)


def add_pillow_piping(pillow_name, w, h, mat, cord=0.0024):
    pillow = bpy.data.objects.get(pillow_name)
    if pillow is None:
        return
    pts2 = rounded_rect_points(w * 1.015, h * 1.015, 0.07, 64)
    path = [(x, 0.0, y) for x, y in pts2]
    piping = make_curve(pillow_name + "_Piping", [path], cord, COL_BED, mat,
                        resolution=1, bevel_resolution=1, cyclic=True)
    piping.location = pillow.location
    piping.rotation_euler = pillow.rotation_euler


add_pillow_piping("Pillow_Cream_L", 0.78, 0.50, M_PIPING, 0.0026)
add_pillow_piping("Pillow_Taupe_R", 0.75, 0.48, M_PIPING, 0.0024)
add_pillow_piping("Pillow_Camel", 0.56, 0.33, M_PIPING, 0.0022)

# wide folded top sheet, turned back over the duvet
sheet_verts = []
sheet_faces = []
nsu, nsv = 48, 9
for j in range(nsv + 1):
    v = j / nsv
    yy = 1.70 + 0.285 * v
    for i in range(nsu + 1):
        u = i / nsu
        x = BED_CX - BED_HW + 0.01 + (2 * BED_HW - 0.02) * u
        zz = (0.784 + 0.007 * math.sin(math.pi * v)
              + 0.005 * math.sin(8.0 * math.pi * u + 0.4)
              + 0.003 * math.sin((u + v) * 13.0))
        sheet_verts.append((x, yy + 0.008 * math.sin(u * 11.0), zz))
for j in range(nsv):
    for i in range(nsu):
        a = j * (nsu + 1) + i
        b = a + 1
        c = a + (nsu + 1) + 1
        d = a + (nsu + 1)
        sheet_faces.append((a, b, c, d))
sheet = mesh_object("Sheet_Turn_Down", sheet_verts, sheet_faces, COL_BED,
                    M_SHEET_WHITE, smooth=True)
add_solidify(sheet, 0.007, offset=0.0)

# softly rolled leading edge of the folded sheet
roll2 = []
for i in range(44):
    u = i / 43
    xx = BED_CX - BED_HW + 0.01 + (2 * BED_HW - 0.02) * u
    roll2.append((xx, 1.705 + 0.008 * math.sin(u * 11.0),
                  0.793 + 0.006 * math.sin(u * 9.0 + 0.4)))
make_curve("Sheet_Turn_Down_Roll", [roll2], 0.011, COL_BED, M_SHEET_WHITE,
           resolution=2, bevel_resolution=2)

# topstitching catches a little light
stitch = []
for i in range(54):
    u = i / 53
    xx = BED_CX - BED_HW + 0.02 + (2 * BED_HW - 0.04) * u
    stitch.append((xx, 1.755 + 0.008 * math.sin(u * 11.0),
                   0.793 + 0.005 * math.sin(u * 8.0 + 0.4)))
make_curve("Sheet_Topstitch", [stitch], 0.0011, COL_BED, M_LINEN_CREAM,
           resolution=1, bevel_resolution=0)


# caramel knit throw --------------------------------------------------------
def make_throw():
    nu, nv = 68, 48
    x0, x1 = BED_CX - BED_HW - 0.05, BED_CX + BED_HW - 0.03
    verts, uvs = [], []
    for j in range(nv + 1):
        t = j / nv
        # a folded throw lying across the foot of the bed; one end falls over
        # the left side (built separately below)
        y = 0.405 + 0.695 * t
        base_z = 0.830 - 0.022 * (1.0 - t) ** 3
        for i in range(nu + 1):
            u = i / nu
            x = x0 + (x1 - x0) * u
            yy = y + 0.11 * (u - 0.5)
            ex = min(u, 1 - u)
            edge = min(1.0, ex * 9.0)
            broad = (0.017 * math.sin(6.2 * y + 1.0 * x + 0.7)
                     + 0.010 * math.sin(3.4 * math.pi * u + 2.4 * y)
                     + 0.0050 * mnoise.noise(Vector((x * 5.0 + 8.0, y * 6.0, 2.1))))
            ridges = 0.0028 * math.sin(22.0 * math.pi * u + 5.0 * y + 0.4)
            z = base_z + (broad + ridges) * (0.5 + 0.5 * edge)
            z += 0.008 * (1.0 - edge) * math.sin(t * 4.0)
            verts.append((x, yy, z))
            uvs.append((u, t))
    faces = []
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            b = a + 1
            c = a + (nu + 1) + 1
            d = a + (nu + 1)
            faces.append((a, b, c, d))
    obj = mesh_object("Knit_Throw", verts, faces, COL_BED, M_THROW,
                      smooth=True, uvs=uvs)
    add_solidify(obj, 0.038, offset=-1.0)
    return obj


make_throw()
# a soft rounded crest where the throw folds back over itself
crest = []
for i in range(50):
    u = i / 49
    xx = BED_CX - BED_HW + 0.04 + (2 * BED_HW - 0.08) * u
    crest.append((xx, 0.405 + 0.11 * (u - 0.5) + 0.006 * math.sin(u * 12.0),
                  0.833 + 0.007 * math.sin(u * 11.0 + 0.4)))
make_curve("Throw_Crest_Fold", [crest], 0.021, COL_BED, M_THROW,
           resolution=2, bevel_resolution=3)

# The throw is deliberately folded back onto the bed rather than hanging over
# the side: a floor-to-bed cascade of brown cloth made the mattress read as a
# heavy box from the low three-quarter camera.

# a few fringe threads caught along the front fold
fringe = []
for i in range(34):
    u = i / 33
    x = BED_CX - BED_HW + 0.02 + (2 * BED_HW - 0.06) * u
    y = 0.402 + 0.11 * (u - 0.5) + 0.003 * math.sin(u * 13.0)
    z0 = 0.811 + 0.006 * math.sin(u * 15.0 + 0.3)
    fringe.append([(x, y, z0),
                   (x + random.uniform(-0.004, 0.004), y - 0.012, z0 - 0.028),
                   (x + random.uniform(-0.008, 0.008), y - 0.018, z0 - 0.050)])
make_curve("Throw_Fringe", fringe, 0.0018, COL_BED, M_THROW,
           resolution=2, bevel_resolution=0)

# The whole bedding stack is a touch lower than the frame, which makes the
# bed less monolithic in the 35 mm corner view.
for _ob in list(COL_BED.objects):
    _ob.location.z -= 0.045


# ---------------------------------------------------------------------------
# Nightstands, bedside lamp, clock, books, cup
# ---------------------------------------------------------------------------
def make_nightstand(name, cx, cy, w=0.46, d=0.40, h=0.62, mirrored=False):
    # legs
    for lx in (-1, 1):
        for ly in (-1, 1):
            px = cx + lx * (w / 2 - 0.055)
            py = cy + ly * (d / 2 - 0.055)
            make_cylinder(name + "_Leg", 0.022, 0.16, (px, py, 0.08),
                          COL_FURN, M_OAK_DARK, segments=16, r_top=0.027)
    # carcass
    make_box(name + "_Body", (w - 0.02, d - 0.02, h - 0.20),
             (cx, cy, 0.16 + (h - 0.20) / 2), COL_FURN, M_OAK,
             bevel=0.008, segments=3)
    make_box(name + "_Top", (w + 0.025, d + 0.025, 0.035),
             (cx, cy, h - 0.008), COL_FURN, M_OAK,
             bevel=0.008, segments=3)
    # two drawer fronts
    for i, zc in enumerate((h - 0.17, h - 0.355)):
        make_box(name + "_Drawer_%d" % i, (w - 0.065, 0.020, 0.145),
                 (cx, cy - d / 2 + 0.001, zc - 0.008), COL_FURN, M_OAK_DARK,
                 bevel=0.006, segments=2)
        # drawer pull, small brass knob
        make_uv_sphere(name + "_Knob_%d" % i, 0.018,
                       (cx, cy - d / 2 - 0.016, zc + 0.035), COL_FURN,
                       M_BRASS, segments=24, rings=12, scale=(1.0, 0.6, 1.0))
    # lower shadow gap
    make_box(name + "_Plinth", (w - 0.10, 0.020, 0.04),
             (cx, cy - d / 2 + 0.01, 0.14), COL_FURN, M_WALNUT_LEG,
             bevel=0.005, segments=2)
    return name


make_nightstand("Nightstand_Left", -1.12, 2.215)
make_nightstand("Nightstand_Right", 1.12, 2.215)


# bedside lamp
def make_bedside_lamp():
    # on the window-side nightstand, as requested
    cx, cy, z0 = 1.13, 2.27, 0.625
    # ceramic gourd base
    prof = [(0.0, 0.0), (0.072, 0.0), (0.088, 0.035), (0.115, 0.10),
            (0.105, 0.155), (0.075, 0.19), (0.052, 0.215), (0.048, 0.24),
            (0.030, 0.252), (0.030, 0.265), (0.0, 0.265)]
    make_lathe("Lamp_Bedside_Base", prof, (cx, cy, z0), COL_DECOR, M_CERAMIC,
               segments=72)
    make_cylinder("Lamp_Bedside_Stem", 0.009, 0.09, (cx, cy, z0 + 0.30),
                  COL_DECOR, M_BRASS, segments=20)
    # shade
    shade_prof = [(0.155, 0.0), (0.145, 0.012), (0.115, 0.19), (0.105, 0.20)]
    shade = make_lathe("Lamp_Bedside_Shade", shade_prof,
                       (cx, cy, z0 + 0.315), COL_DECOR, M_LAMP_SHADE_BEDSIDE,
                       segments=72, caps=False)
    add_solidify(shade, 0.003, offset=0.0)
    for zz, rr in ((0.0, 0.155), (0.20, 0.105)):
        make_torus("Lamp_Bedside_Trim_%s" % zz, rr, 0.003,
                   (cx, cy, z0 + 0.315 + zz), COL_DECOR, M_BRASS_DARK,
                   rotation=(0, 0, 0), major_segments=64, minor_segments=6)
    make_uv_sphere("Lamp_Bedside_Finial", 0.018,
                   (cx, cy, z0 + 0.53), COL_DECOR, M_BRASS,
                   segments=24, rings=12)
    # bulb inside
    make_uv_sphere("Lamp_Bedside_Bulb", 0.032,
                   (cx, cy, z0 + 0.395), COL_DECOR, M_BULB_BEDSIDE,
                   segments=24, rings=12)
    # little shade inner light object
    data = bpy.data.lights.new("Lamp_Bedside", "POINT")
    data.energy = 30.0
    data.color = (1.0, 0.55, 0.27)
    data.shadow_soft_size = 0.09
    ob = bpy.data.objects.new("Lamp_Bedside", data)
    COL_LIGHT.objects.link(ob)
    ob.location = (cx, cy, z0 + 0.40)
    for so in (bpy.data.objects.get("Lamp_Bedside_Shade"),
               bpy.data.objects.get("Lamp_Bedside_Bulb")):
        if so:
            so.visible_shadow = False
    return cx, cy, z0


make_bedside_lamp()

# books
def make_book(name, center, w, h, d, rot_z, cover_mat):
    cx, cy, cz = center
    make_box(name + "_Pages", (w * 0.94, h * 0.74, d * 0.94),
             (cx, cy, cz + h * 0.38), COL_DECOR, M_PAPER,
             rotation=(0, 0, rot_z), bevel=0.002, segments=1, smooth=False)
    make_box(name + "_CoverTop", (w, h * 0.12, d),
             (cx, cy, cz + h * 0.86), COL_DECOR, cover_mat,
             rotation=(0, 0, rot_z), bevel=0.002, segments=2)
    make_box(name + "_CoverBot", (w, h * 0.12, d),
             (cx, cy, cz + h * 0.05), COL_DECOR, cover_mat,
             rotation=(0, 0, rot_z), bevel=0.002, segments=2)
    # spine
    make_box(name + "_Spine", (w * 0.035, h * 0.85, d),
             (cx - w / 2 + w * 0.02, cy, cz + h * 0.46), COL_DECOR, cover_mat,
             rotation=(0, 0, rot_z), bevel=0.002, segments=2)
    return name


def make_flat_book(name, center, w, d, thick, rot_z, cover_mat):
    """A book lying flat; center is the bottom-centre on the desk."""
    cx, cy, cz = center
    make_box(name + "_Pages", (w * 0.94, d * 0.92, thick * 0.62),
             (cx, cy, cz + thick * 0.44), COL_DECOR, M_PAPER,
             rotation=(0, 0, rot_z), bevel=0.0015, segments=1, smooth=False)
    make_box(name + "_CoverTop", (w, d, thick * 0.12),
             (cx, cy, cz + thick * 0.86), COL_DECOR, cover_mat,
             rotation=(0, 0, rot_z), bevel=0.0015, segments=1, smooth=False)
    make_box(name + "_CoverBot", (w, d, thick * 0.12),
             (cx, cy, cz + thick * 0.06), COL_DECOR, cover_mat,
             rotation=(0, 0, rot_z), bevel=0.0015, segments=1, smooth=False)
    make_box(name + "_Spine", (w * 0.04, d * 0.98, thick * 0.98),
             (cx - w * 0.48, cy, cz + thick * 0.5), COL_DECOR, cover_mat,
             rotation=(0, 0, rot_z), bevel=0.0015, segments=1, smooth=False)
    return name


# a single cup of coffee on the left bedside table
cup_l = (-1.03, 2.075)
make_cylinder("Left_Coffee_Saucer", 0.062, 0.010, (cup_l[0], cup_l[1], 0.636),
              COL_DECOR, M_CERAMIC, segments=40)
make_lathe("Left_Coffee_Cup", [(0.0, 0.0), (0.032, 0.0), (0.041, 0.010),
                               (0.047, 0.056), (0.050, 0.062), (0.045, 0.064),
                               (0.040, 0.055), (0.035, 0.010), (0.0, 0.010)],
           (cup_l[0], cup_l[1], 0.642), COL_DECOR, M_CERAMIC, segments=40)
make_torus("Left_Coffee_Handle", 0.026, 0.0055,
           (cup_l[0] + 0.047, cup_l[1], 0.68), COL_DECOR, M_CERAMIC,
           rotation=(math.pi / 2, 0, 0), major_segments=28, minor_segments=8)
make_cylinder("Left_Coffee_Liquid", 0.038, 0.004,
              (cup_l[0], cup_l[1], 0.698), COL_DECOR, M_COFFEE, segments=32)
# alarm clock on the left nightstand
clock_c = (-1.28, 2.16)
make_cylinder("Alarm_Clock_Body", 0.062, 0.032, (clock_c[0], clock_c[1], 0.705),
              COL_DECOR, M_BRASS_DARK, rotation=(math.pi / 2, 0, 0),
              segments=48)
make_cylinder("Alarm_Clock_Face", 0.054, 0.005, (clock_c[0], clock_c[1] - 0.018, 0.705),
              COL_DECOR, M_CERAMIC, rotation=(math.pi / 2, 0, 0), segments=48)
# clock hands, simple dark strips
for ang, ln, w in ((-1.15, 0.035, 0.004), (-0.35, 0.047, 0.0035)):
    hx = clock_c[0] + math.sin(ang) * ln * 0.5
    hz = 0.705 + math.cos(ang) * ln * 0.5
    make_box("Alarm_Clock_Hand", (ln, 0.003, w), (hx, clock_c[1] - 0.024, hz),
             COL_DECOR, M_IRON, rotation=(0, ang, 0), bevel=0.001, segments=1)
for bs in (-1, 1):
    make_uv_sphere("Alarm_Clock_Bell", 0.023,
                   (clock_c[0] + bs * 0.045, clock_c[1], 0.778),
                   COL_DECOR, M_BRASS, segments=20, rings=10)
    make_cylinder("Alarm_Clock_Foot", 0.009, 0.022,
                  (clock_c[0] + bs * 0.045, clock_c[1] - 0.01, 0.629),
                  COL_DECOR, M_BRASS_DARK, rotation=(0.25, 0, 0), segments=12)
make_torus("Alarm_Clock_Hammer", 0.022, 0.0035,
           (clock_c[0], clock_c[1], 0.751), COL_DECOR, M_BRASS_DARK,
           rotation=(math.pi / 2, 0, 0), major_segments=24, minor_segments=6)


# ---------------------------------------------------------------------------
# Tall chest (dresser), top decor and wall shelf
# ---------------------------------------------------------------------------
def make_tall_chest():
    cx, cy = -1.78, 2.265
    w, d, h = 0.55, 0.40, 1.20
    # legs
    for lx in (-1, 1):
        for ly in (-1, 1):
            px = cx + lx * (w / 2 - 0.055)
            py = cy + ly * (d / 2 - 0.055)
            make_cylinder("Chest_Leg", 0.024, 0.12, (px, py, 0.06),
                          COL_FURN, M_OAK_DARK, segments=16, r_top=0.030)
    make_box("Chest_Body", (w - 0.02, d - 0.02, h - 0.16),
             (cx, cy, 0.12 + (h - 0.16) / 2), COL_FURN, M_OAK,
             bevel=0.01, segments=3)
    make_box("Chest_Top", (w + 0.03, d + 0.03, 0.04),
             (cx, cy, h - 0.005), COL_FURN, M_OAK,
             bevel=0.012, segments=3)
    for i in range(5):
        zc = 0.28 + i * 0.180
        make_box("Chest_Drawer_%d" % i, (w - 0.075, 0.022, 0.147),
                 (cx, cy - d / 2 + 0.001, zc), COL_FURN, M_OAK_DARK,
                 bevel=0.006, segments=2)
        for sx in (-1, 1):
            make_uv_sphere("Chest_Knob_%d_%d" % (i, sx), 0.016,
                           (cx + sx * 0.12, cy - d / 2 - 0.018, zc + 0.035),
                           COL_FURN, M_BRASS, segments=20, rings=10,
                           scale=(1, 0.55, 1))
    # top objects
    # vase
    vase_z = h + 0.022
    make_lathe("Chest_Vase", [(0.0, 0.0), (0.058, 0.0), (0.075, 0.09),
                              (0.060, 0.20), (0.040, 0.25), (0.042, 0.27),
                              (0.0, 0.27)],
               (cx - 0.09, cy + 0.01, vase_z), COL_DECOR, M_CERAMIC_TERRA,
               segments=56)
    # pampas stems & feathery tops
    stems, plumes = [], []
    for k in range(7):
        ang = random.uniform(-0.55, 0.55)
        offx = cx - 0.09 + random.uniform(-0.02, 0.02)
        offy = cy + 0.01 + random.uniform(-0.02, 0.02)
        topz = vase_z + random.uniform(0.45, 0.62)
        tipx = offx + math.sin(ang) * 0.16
        tipy = offy + math.cos(ang) * 0.11
        stems.append([(offx, offy, vase_z + 0.22), (offx + (tipx - offx) * 0.5, offy + (tipy - offy) * 0.5, (vase_z + 0.22 + topz) / 2), (tipx, tipy, topz)])
        # plume as small scatter of wavy tufts
        for q in range(4):
            t = q / 3
            plumes.append([(tipx, tipy, topz - 0.02),
                           (tipx + random.uniform(-0.035, 0.035), tipy + random.uniform(-0.025, 0.025), topz + 0.05 + t * 0.08),
                           (tipx + random.uniform(-0.05, 0.05), tipy + random.uniform(-0.04, 0.04), topz + 0.10 + t * 0.10)])
    make_curve("Chest_Pampas_Stems", stems, 0.0022, COL_DECOR, M_BARK,
               resolution=1, bevel_resolution=0)
    make_curve("Chest_Pampas_Plume", plumes, 0.0045, COL_DECOR, M_RUG_FIBER,
               resolution=1, bevel_resolution=0)
    # woven box and a little framed photo replace the old books
    make_box("Chest_Woven_Box", (0.24, 0.16, 0.12),
             (cx + 0.14, cy - 0.04, h + 0.06), COL_DECOR, M_RATTAN,
             bevel=0.012, segments=3)
    make_box("Chest_Photo_Frame", (0.13, 0.018, 0.17),
             (cx - 0.16, cy - 0.13, h + 0.085), COL_DECOR, M_WALNUT_LEG,
             bevel=0.004, segments=2)
    make_rect("Chest_Photo_Image", (cx - 0.16, cy - 0.141, h + 0.09),
              0.10, 0.13, "XZ", COL_DECOR, M_PAPER)
    return cx, cy, h


make_tall_chest()

# wall shelf on back wall
shelf_c = (1.12, ROOM_Y / 2 - 0.105, 1.74)
make_box("Wall_Shelf_Board", (0.72, 0.17, 0.035), shelf_c, COL_DECOR, M_OAK,
         bevel=0.006, segments=2)
for bx in (0.89, 1.35):
    make_box("Wall_Shelf_Bracket", (0.028, 0.15, 0.13),
             (bx, ROOM_Y / 2 - 0.085, 1.65), COL_DECOR, M_BRASS_DARK,
             bevel=0.004, segments=2)
# objects on shelf: ceramic vessel, little basket and a small frame
make_box("Shelf_Woven_Basket", (0.18, 0.11, 0.10),
         (0.84, 2.39, 1.805), COL_DECOR, M_RATTAN, bevel=0.012, segments=3)
make_lathe("Shelf_Bud_Vase", [(0.0, 0.0), (0.042, 0.0), (0.055, 0.08), (0.036, 0.16), (0.028, 0.18), (0.0, 0.18)],
           (1.08, 2.39, 1.758), COL_DECOR, M_CERAMIC, segments=48)
# little dried stems
shelf_stems = []
for k in range(4):
    ang = -0.7 + k * 0.45
    shelf_stems.append([(1.08, 2.39, 1.91),
                        (1.08 + math.sin(ang) * 0.08, 2.39 + math.cos(ang) * 0.03, 2.02),
                        (1.08 + math.sin(ang) * 0.13, 2.39 + math.cos(ang) * 0.05, 2.12)])
make_curve("Shelf_Dried_Stems", shelf_stems, 0.0018, COL_DECOR, M_BARK,
           resolution=1, bevel_resolution=0)
# small ceramic bowl
make_lathe("Shelf_Bowl", [(0.0, 0.0), (0.048, 0.0), (0.070, 0.025), (0.062, 0.045), (0.0, 0.045)],
           (1.33, 2.39, 1.758), COL_DECOR, M_CERAMIC, segments=48)


# ---------------------------------------------------------------------------
# Floor lamp (back right corner)
# ---------------------------------------------------------------------------
def make_floor_lamp():
    # slim reading lamp in the front-left corner, clear of the wardrobe and door
    cx, cy = -2.02, -2.31
    make_cylinder("Lamp_Floor_Base", 0.145, 0.025, (cx, cy, 0.025),
                  COL_DECOR, M_BRASS_DARK, segments=48)
    make_uv_sphere("Lamp_Floor_Base_Dome", 0.09, (cx, cy, 0.05),
                   COL_DECOR, M_BRASS_DARK, segments=32, rings=16,
                   scale=(1, 1, 0.35))
    make_cylinder("Lamp_Floor_Stem", 0.012, 1.36, (cx, cy, 0.72),
                  COL_DECOR, M_BRASS_DARK, segments=20)
    shade_prof = [(0.16, 0.0), (0.145, 0.014), (0.105, 0.20), (0.095, 0.215)]
    shade = make_lathe("Lamp_Floor_Shade", shade_prof,
                       (cx, cy, 1.35), COL_DECOR, M_LAMP_SHADE_FLOOR,
                       segments=64, caps=False)
    add_solidify(shade, 0.003, offset=0.0)
    for zz, rr in ((0.0, 0.16), (0.215, 0.095)):
        make_torus("Lamp_Floor_Trim_%s" % zz, rr, 0.0025,
                   (cx, cy, 1.35 + zz), COL_DECOR, M_BRASS_DARK,
                   major_segments=56, minor_segments=6)
    make_uv_sphere("Lamp_Floor_Bulb", 0.032, (cx, cy, 1.45),
                   COL_DECOR, M_BULB_FLOOR, segments=24, rings=12)
    data = bpy.data.lights.new("Lamp_Floor", "POINT")
    data.energy = 18.0
    data.color = (1.0, 0.53, 0.25)
    data.shadow_soft_size = 0.09
    ob = bpy.data.objects.new("Lamp_Floor", data)
    COL_LIGHT.objects.link(ob)
    ob.location = (cx, cy, 1.45)
    for so in (bpy.data.objects.get("Lamp_Floor_Shade"),
               bpy.data.objects.get("Lamp_Floor_Bulb")):
        if so:
            so.visible_shadow = False


make_floor_lamp()


# ---------------------------------------------------------------------------
# New built-ins: interior door, wardrobe, desk, TV wall, small decor
# ---------------------------------------------------------------------------
def make_simple_basket(name, cx, cy, z_base, w, d, h, rot=0.0):
    body = make_box(name + "_Body", (w, d, h),
                    (cx, cy, z_base + h / 2), COL_DECOR, M_RATTAN,
                    bevel=0.028, segments=4, rotation=(0, 0, rot))
    make_box(name + "_Rim", (w + 0.022, d + 0.022, 0.022),
             (cx, cy, z_base + h), COL_DECOR, M_RATTAN,
             bevel=0.009, segments=3, rotation=(0, 0, rot))
    # two simple bent-rattan handles
    handles = []
    for sx in (-1, 1):
        yy = cy + sx * (d / 2 + 0.003)
        handles.append([(cx - w * 0.22, yy, z_base + h - 0.12),
                        (cx - w * 0.25, yy + sx * 0.022, z_base + h - 0.02),
                        (cx - w * 0.10, yy + sx * 0.028, z_base + h + 0.018),
                        (cx + w * 0.10, yy + sx * 0.028, z_base + h + 0.018),
                        (cx + w * 0.25, yy + sx * 0.022, z_base + h - 0.02),
                        (cx + w * 0.22, yy, z_base + h - 0.12)])
    make_curve(name + "_Handles", handles, 0.0045, COL_DECOR, M_RATTAN,
               resolution=2, bevel_resolution=2)
    return body


def make_interior_door():
    wall_x = -ROOM_X / 2
    cy = -1.56
    w, h = 0.90, 2.10
    # simple wood casing, proud of the wall
    for sy in (-1, 1):
        make_box("Door_Casing_Side", (0.065, 0.085, 2.20),
                 (wall_x + 0.035, cy + sy * (w / 2 + 0.035), 1.10),
                 COL_ARCH, M_TRIM, bevel=0.006, segments=2)
    make_box("Door_Casing_Head", (0.065, w + 0.16, 0.085),
             (wall_x + 0.035, cy, 2.155), COL_ARCH, M_TRIM,
             bevel=0.006, segments=2)
    # closed slab, bottom just above the floor
    make_box("Door_Slab", (0.042, w, h),
             (wall_x + 0.045, cy, 0.028 + h / 2), COL_FURN, M_DOOR_WOOD,
             bevel=0.006, segments=2)
    # two tall, shallow shaker panels implied by proud moulding strips
    fx = wall_x + 0.068
    for sy in (-1, 1):
        py = cy + sy * 0.415
        make_box("Door_Groove_V", (0.006, 0.018, 1.70),
                 (fx + 0.008, py, 1.11), COL_FURN, M_OAK_DARK,
                 bevel=0.0015, segments=1)
    for sz in (0.20, 2.02):
        make_box("Door_Groove_H", (0.006, 0.76, 0.018),
                 (fx + 0.008, cy, sz), COL_FURN, M_OAK_DARK,
                 bevel=0.0015, segments=1)
    make_box("Door_Centre_Groove", (0.006, 0.018, 1.82),
             (fx + 0.008, cy, 1.11), COL_FURN, M_OAK_DARK,
             bevel=0.0015, segments=1)
    # brass lever handle with a stepped rose
    hx = wall_x + 0.074
    make_cylinder("Door_Handle_Rose", 0.034, 0.018,
                  (hx, cy + 0.345, 1.00), COL_DECOR, M_BRASS,
                  rotation=(0, math.pi / 2, 0), segments=32)
    make_cylinder("Door_Handle_Stem", 0.011, 0.075,
                  (hx + 0.046, cy + 0.345, 1.00), COL_DECOR, M_BRASS,
                  rotation=(0, math.pi / 2, 0), segments=20)
    make_box("Door_Handle_Lever", (0.060, 0.185, 0.024),
             (hx + 0.083, cy + 0.266, 1.00), COL_DECOR, M_BRASS,
             bevel=0.009, segments=3)
    make_box("Door_Keyhole", (0.006, 0.014, 0.030),
             (fx + 0.001, cy + 0.345, 0.90), COL_DECOR, M_IRON,
             bevel=0.002, segments=1)
    # thin brass threshold
    make_box("Door_Threshold", (0.085, w + 0.02, 0.012),
             (wall_x + 0.055, cy, 0.006), COL_ARCH, M_BRASS_DARK,
             bevel=0.003, segments=2)


make_interior_door()


def make_wardrobe():
    x_in = -ROOM_X / 2
    cx = x_in + 0.30
    cy, w, d, h = 0.15, 1.60, 0.60, 2.20
    # carcass
    make_box("Wardrobe_Body", (d - 0.02, w - 0.02, h - 0.08),
             (cx, cy, 0.06 + (h - 0.08) / 2), COL_FURN, M_WARDROBE_WOOD,
             bevel=0.008, segments=2)
    make_box("Wardrobe_Plinth", (d - 0.06, w - 0.08, 0.07),
             (cx + 0.02, cy, 0.035), COL_FURN, M_OAK_DARK,
             bevel=0.004, segments=2)
    make_box("Wardrobe_Cornice", (d + 0.025, w + 0.035, 0.055),
             (cx + 0.004, cy, h - 0.025), COL_FURN, M_WARDROBE_WOOD,
             bevel=0.008, segments=3)
    # dark recessed reveal behind the two doors, so their edges read clearly
    fx = x_in + d + 0.012
    make_box("Wardrobe_Front_Reveal", (0.012, w - 0.045, h - 0.20),
             (fx - 0.017, cy, 0.06 + (h - 0.16) / 2),
             COL_FURN, M_OAK_DARK, bevel=0.001, segments=1)
    # two tall flat doors, vertical grain, thin dark vertical pulls
    for i, dy in enumerate((-0.395, 0.395)):
        make_box("Wardrobe_Door_%d" % i, (0.030, w / 2 - 0.018, h - 0.16),
                 (fx, cy + dy, 0.06 + (h - 0.16) / 2),
                 COL_FURN, M_WARDROBE_WOOD, bevel=0.004, segments=2)
        hy = cy + (-0.075 if i == 0 else 0.075)
        make_box("Wardrobe_Handle_%d" % i, (0.014, 0.014, 0.34),
                 (fx + 0.022, hy, 1.14),
                 COL_DECOR, M_IRON, bevel=0.004, segments=2)
    # narrow shadow seam between doors, proud enough to read at distance
    make_box("Wardrobe_Seam", (0.010, 0.012, h - 0.20),
             (fx + 0.016, cy, 0.06 + (h - 0.16) / 2), COL_FURN, M_OAK_DARK,
             bevel=0.001, segments=1)
    # two baskets on top
    make_simple_basket("Wardrobe_Basket_A", cx, cy - 0.34, h + 0.025,
                       0.46, 0.40, 0.21)
    make_simple_basket("Wardrobe_Basket_B", cx, cy + 0.34, h + 0.025,
                       0.46, 0.40, 0.21)


make_wardrobe()


def make_desk_area():
    wall_x = ROOM_X / 2
    cx, cy = wall_x - 0.31, 1.28
    top_z, w, d = 0.745, 1.20, 0.60
    # top: grain runs along the desk's length (Y)
    make_box("Desk_Top", (d, w, 0.038), (cx, cy, top_z),
             COL_FURN, M_DESK_WOOD, bevel=0.008, segments=3)
    make_box("Desk_Apron", (d - 0.09, w - 0.09, 0.075),
             (cx, cy, top_z - 0.065), COL_FURN, M_OAK_DARK,
             bevel=0.004, segments=2)
    # slim tapered legs
    for sx in (-1, 1):
        for sy in (-1, 1):
            make_cylinder("Desk_Leg", 0.018, 0.70,
                          (cx + sx * (d / 2 - 0.055), cy + sy * (w / 2 - 0.06),
                           0.35), COL_FURN, M_WALNUT_LEG, segments=14,
                          r_top=0.014)
    # chair: oak frame, open woven cane back, half pulled out
    ch_x, ch_y = 1.36, 1.10
    for lx in (-1, 1):
        for ly in (-1, 1):
            make_cylinder("Desk_Chair_Leg", 0.016, 0.46,
                          (ch_x + lx * 0.185, ch_y + ly * 0.17, 0.23),
                          COL_FURN, M_WALNUT_LEG, segments=12,
                          r_top=0.012)
    make_box("Desk_Chair_Seat", (0.46, 0.44, 0.045),
             (ch_x, ch_y, 0.475), COL_FURN, M_OAK,
             bevel=0.025, segments=4)
    make_box("Desk_Chair_Cushion", (0.42, 0.40, 0.055),
             (ch_x, ch_y, 0.518), COL_BED, M_PILLOW,
             bevel=0.045, segments=5)
    # back frame at the room side of the chair
    bx = ch_x - 0.215
    for sy in (-1, 1):
        make_cylinder("Desk_Chair_BackPost", 0.017, 0.49,
                      (bx, ch_y + sy * 0.19, 0.72), COL_FURN, M_WALNUT_LEG,
                      segments=12, r_top=0.014)
    make_box("Desk_Chair_TopRail", (0.045, 0.42, 0.055),
             (bx, ch_y, 0.955), COL_FURN, M_OAK,
             bevel=0.012, segments=3)
    # upholstered cream back panel inside the oak frame
    make_box("Desk_Chair_CanePanel", (0.050, 0.36, 0.32),
             (bx + 0.028, ch_y, 0.755), COL_FURN, M_PILLOW,
             bevel=0.018, segments=4)
    # NOTE: the chair is intentionally left in world orientation; transforming
    # each part about a world pivot also transforms its object-space vertices
    # and lands the whole chair in the wrong place.  A half-pulled, slightly
    # turned chair is achieved by building it at this offset instead.
    # books - the only books in the scene, lying flat in a little stack
    make_flat_book("Desk_Book_1", (1.82, 1.00, 0.766),
                   0.24, 0.17, 0.040, 0.08, M_BOOK_CLOTH)
    make_flat_book("Desk_Book_2", (1.83, 1.01, 0.806),
                   0.21, 0.15, 0.028, -0.06, M_BOOK_GREEN)
    make_flat_book("Desk_Book_3", (1.82, 1.00, 0.834),
                   0.18, 0.14, 0.022, 0.11, M_BOOK_NAVY)
    # closed laptop
    make_box("Desk_Laptop_Base", (0.35, 0.245, 0.018),
             (2.02, 1.36, 0.773), COL_DECOR, M_TV_ALLOY,
             bevel=0.018, segments=3)
    make_box("Desk_Laptop_Lid", (0.35, 0.245, 0.012),
             (2.02, 1.36, 0.788), COL_DECOR, M_TV_BLACK,
             bevel=0.016, segments=3)
    make_uv_sphere("Desk_Laptop_Logo", 0.013,
                   (2.02, 1.36, 0.797), COL_DECOR, M_BRASS,
                   segments=20, rings=10, scale=(1.0, 1.0, 0.18))
    # pencil cup with pencils
    make_lathe("Desk_Pen_Holder",
               [(0.0, 0.0), (0.038, 0.0), (0.042, 0.012),
                (0.049, 0.085), (0.043, 0.095), (0.0, 0.085)],
               (1.79, 1.56, 0.764), COL_DECOR, M_CERAMIC_TERRA,
               segments=40)
    pencils = []
    for k, (ang, tilt) in enumerate(((-0.25, 0.10), (0.12, -0.06), (0.38, 0.04))):
        base = (1.79 + 0.010 * math.cos(ang), 1.56 + 0.010 * math.sin(ang), 0.84)
        pencils.append([base,
                        (base[0] + math.sin(tilt) * 0.15,
                         base[1] + math.cos(ang) * 0.06,
                         base[2] + 0.12)])
    make_curve("Desk_Pencils", pencils, 0.0024, COL_DECOR, M_WALNUT_LEG,
               resolution=1, bevel_resolution=1)
    # small transparent vase with dried stems
    make_lathe("Desk_Glass_Vase",
               [(0.0, 0.0), (0.040, 0.0), (0.042, 0.012),
                (0.035, 0.075), (0.030, 0.115), (0.036, 0.12),
                (0.0, 0.12)],
               (2.10, 0.89, 0.765), COL_DECOR, M_GLASS, segments=48)
    stems = []
    rnd = random.Random(76)
    for k in range(5):
        ang = -0.7 + k * 0.32
        bx = 2.10 + rnd.uniform(-0.014, 0.014)
        by = 0.89 + rnd.uniform(-0.014, 0.014)
        stems.append([(bx, by, 0.86),
                      (bx + math.sin(ang) * 0.055, by + math.cos(ang) * 0.035, 1.00),
                      (bx + math.sin(ang) * 0.10, by + math.cos(ang) * 0.06, 1.13)])
    make_curve("Desk_Dried_Stems", stems, 0.0018, COL_DECOR, M_BARK,
               resolution=1, bevel_resolution=0)
    # little desk lamp - named light is Lamp_Desk
    lx, ly = 2.08, 1.75
    make_cylinder("Lamp_Desk_Base", 0.058, 0.018, (lx, ly, 0.773),
                  COL_DECOR, M_BRASS, segments=32)
    make_cylinder("Lamp_Desk_Stem", 0.008, 0.29, (lx, ly, 0.915),
                  COL_DECOR, M_BRASS, segments=16)
    shade = make_lathe("Lamp_Desk_Shade",
                       [(0.085, 0.0), (0.080, 0.008), (0.052, 0.105), (0.048, 0.112)],
                       (lx, ly, 1.055), COL_DECOR, M_LAMP_SHADE_DESK,
                       segments=48, caps=False)
    add_solidify(shade, 0.0025, offset=0.0)
    make_uv_sphere("Lamp_Desk_Bulb", 0.020, (lx, ly, 1.09),
                   COL_DECOR, M_BULB_DESK, segments=20, rings=10)
    make_uv_sphere("Lamp_Desk_Finial", 0.012, (lx, ly, 1.17),
                   COL_DECOR, M_BRASS, segments=16, rings=8)
    data = bpy.data.lights.new("Lamp_Desk", "POINT")
    data.energy = 0.0
    data.color = (1.0, 0.63, 0.36)
    data.shadow_soft_size = 0.045
    ob = bpy.data.objects.new("Lamp_Desk", data)
    COL_LIGHT.objects.link(ob)
    ob.location = (lx, ly, 1.07)
    for so in (bpy.data.objects.get("Lamp_Desk_Shade"),
               bpy.data.objects.get("Lamp_Desk_Bulb")):
        if so:
            so.visible_shadow = False
    # small desk frame leaning against the wall
    make_box("Desk_Photo_Frame", (0.015, 0.16, 0.20),
             (2.275, 1.05, 0.855), COL_DECOR, M_WALNUT,
             bevel=0.004, segments=2)
    make_rect("Desk_Photo_Image", (2.267, 1.05, 0.860), 0.125, 0.16,
              "YZ", COL_DECOR, M_PAPER)


make_desk_area()


# --- TV wall ---------------------------------------------------------------
def make_tv_wall():
    wall_y = -ROOM_Y / 2
    cx = BED_CX
    screen_z = 1.30
    # slim wall-mounted TV body
    make_box("TV_Body", (1.22, 0.045, 0.70),
             (cx, wall_y + 0.030, screen_z), COL_DECOR, M_TV_BLACK,
             bevel=0.008, segments=2)
    make_box("TV_Bezel_Top", (1.24, 0.050, 0.022),
             (cx, wall_y + 0.028, screen_z + 0.36), COL_DECOR, M_TV_BLACK,
             bevel=0.005, segments=2)
    make_box("TV_Bezel_Bottom", (1.24, 0.050, 0.022),
             (cx, wall_y + 0.028, screen_z - 0.36), COL_DECOR, M_TV_BLACK,
             bevel=0.005, segments=2)
    make_rect("TV_Screen", (cx, wall_y + 0.058, screen_z), 1.16, 0.652,
              "XZ", COL_DECOR, M_TV_SCREEN)
    tv = bpy.data.objects["TV_Screen"]
    tv.data.materials.clear()
    tv.data.materials.append(M_TV_SCREEN)
    # The screen now shows the supplied game-results image; no 3D clock overlay.
    # low oak console, slightly off the wall for cable clearance
    cw, cd, ch = 1.50, 0.36, 0.35
    ccy = wall_y + 0.22
    make_box("TV_Console_Top", (cw, cd, 0.045),
             (cx, ccy, 0.335), COL_FURN, M_CONSOLE_WOOD, bevel=0.006, segments=3)
    for sx in (-1, 1):
        make_box("TV_Console_Side", (0.040, cd, 0.29),
                 (cx + sx * (cw / 2 - 0.02), ccy, 0.165), COL_FURN, M_CONSOLE_WOOD,
                 bevel=0.005, segments=2)
    make_box("TV_Console_Back", (cw - 0.04, 0.022, 0.29),
             (cx, wall_y + 0.055, 0.165), COL_FURN, M_OAK_DARK,
             bevel=0.004, segments=2)
    make_box("TV_Console_Shelf", (cw - 0.12, cd - 0.06, 0.025),
             (cx, ccy, 0.160), COL_FURN, M_OAK, bevel=0.004, segments=2)
    for sx in (-1, 1):
        make_cylinder("TV_Console_Leg", 0.016, 0.10,
                      (cx + sx * (cw / 2 - 0.06), ccy + 0.10, 0.05),
                      COL_FURN, M_IRON, segments=12)
    # two shallow drawer fronts make it read as a proper low TV cabinet
    make_box("TV_Console_Drawer_Back", (cw - 0.10, 0.020, 0.245),
             (cx, ccy + 0.178, 0.185), COL_FURN, M_OAK_DARK,
             bevel=0.002, segments=1)
    for i, sx in enumerate((-1, 1)):
        make_box("TV_Console_Drawer_%d" % i, (0.66, 0.030, 0.225),
                 (cx + sx * 0.365, ccy + 0.188, 0.185),
                 COL_FURN, M_CONSOLE_WOOD, bevel=0.005, segments=2)
        make_uv_sphere("TV_Console_Knob_%d" % i, 0.018,
                       (cx + sx * 0.365, ccy + 0.207, 0.190),
                       COL_DECOR, M_BRASS, segments=20, rings=10,
                       scale=(1.0, 0.55, 1.0))
    # console (Xbox-like) and controller
    make_box("Game_Console_Base", (0.34, 0.21, 0.018),
             (-0.34, ccy - 0.01, 0.365), COL_DECOR, M_TV_BLACK,
             bevel=0.012, segments=3)
    make_box("Game_Console_Body", (0.32, 0.20, 0.070),
             (-0.34, ccy - 0.01, 0.399), COL_DECOR, M_GAME_WHITE,
             bevel=0.022, segments=4)
    make_box("Game_Console_Vent", (0.22, 0.008, 0.055),
             (-0.34, ccy + 0.102, 0.399), COL_DECOR, M_GAME_DARK,
             bevel=0.002, segments=1)
    make_box("Game_Console_LED", (0.055, 0.004, 0.005),
             (-0.34, ccy + 0.107, 0.414), COL_DECOR, M_TV_UI,
             bevel=0.001, segments=1)
    make_uv_sphere("Game_Console_Button", 0.012,
                   (-0.20, ccy + 0.100, 0.407), COL_DECOR, M_BRASS,
                   segments=16, rings=8, scale=(1.0, 0.5, 1.0))
    # controller: body, two grips, joystick + buttons, casually turned
    gx, gy, gz = 0.18, ccy - 0.04, 0.390
    make_box("Game_Controller_Body", (0.14, 0.075, 0.036),
             (gx, gy, gz), COL_DECOR, M_GAME_DARK,
             bevel=0.018, segments=4, rotation=(0, 0, 0.35))
    for sx in (-1, 1):
        make_uv_sphere("Game_Controller_Grip", 1.0,
                       (gx + sx * 0.045, gy - 0.075, gz - 0.004),
                       COL_DECOR, M_GAME_DARK, segments=24, rings=12,
                       scale=(0.038, 0.095, 0.032),
                       rotation=(0.35, 0, sx * 0.12))
    make_uv_sphere("Game_Controller_Stick_L", 0.022,
                   (gx - 0.030, gy - 0.020, gz + 0.020), COL_DECOR,
                   M_GAME_WHITE, segments=16, rings=8, scale=(1, 1, 0.55))
    make_uv_sphere("Game_Controller_Stick_R", 0.022,
                   (gx + 0.030, gy - 0.020, gz + 0.020), COL_DECOR,
                   M_GAME_WHITE, segments=16, rings=8, scale=(1, 1, 0.55))
    for i, (bx, by) in enumerate(((-0.020, 0.018), (0.0, 0.024), (0.020, 0.018))):
        make_uv_sphere("Game_Controller_Button_%d" % i, 0.008,
                       (gx + bx, gy + by, gz + 0.022), COL_DECOR, M_CERAMIC,
                       segments=12, rings=6, scale=(1, 1, 0.5))
    # game cases standing vertically
    for i, (dx, mat, tilt) in enumerate(((-0.18, M_BOOK_NAVY, -0.08),
                                          (-0.13, M_BOOK_GREEN, 0.04),
                                          (-0.08, M_BOOK_CLOTH, -0.03))):
        make_box("Game_Case_%d" % i, (0.032, 0.135, 0.195),
                 (dx, ccy - 0.12, 0.445), COL_DECOR, mat,
                 bevel=0.004, segments=2, rotation=(0, 0, tilt))
        make_box("Game_Case_Label_%d" % i, (0.002, 0.10, 0.145),
                 (dx + 0.017, ccy - 0.12, 0.445), COL_DECOR, M_PAPER,
                 bevel=0.001, segments=1, rotation=(0, 0, tilt))
    # rattan basket beside the console
    make_simple_basket("TV_Basket", 1.03, ccy + 0.02, 0.06, 0.34, 0.28, 0.26)
    # cable from TV to console and then down, kept close to the wall
    cables = [
        [(0.0, wall_y + 0.055, 0.965), (0.0, wall_y + 0.035, 0.70),
         (0.0, wall_y + 0.030, 0.36), (0.20, wall_y + 0.035, 0.34),
         (0.28, wall_y + 0.045, 0.12)],
        [(-0.34, ccy - 0.10, 0.36), (-0.34, ccy - 0.18, 0.17),
         (-0.05, wall_y + 0.06, 0.03), (0.55, wall_y + 0.06, 0.025)],
    ]
    make_curve("TV_Cable_Run", cables, 0.004, COL_DECOR, M_IRON,
               resolution=2, bevel_resolution=1)
    # actual soft screen glow fill (not a visible fixture)
    data = bpy.data.lights.new("TV_Glow", "AREA")
    data.energy = 0.0
    data.shape = "RECTANGLE"
    data.size = 1.05
    data.size_y = 0.55
    data.color = (1.0, 0.52, 0.25)
    data.spread = math.radians(110)
    ob = bpy.data.objects.new("TV_Glow", data)
    COL_LIGHT.objects.link(ob)
    ob.location = (cx, wall_y + 0.13, screen_z)
    ob.rotation_euler = (Vector((cx, 1.0, 1.15)) - ob.location).to_track_quat("-Z", "Y").to_euler()
    ob.visible_camera = False


make_tv_wall()


# small candle on the left nightstand
def make_candle():
    cx, cy, z0 = -1.29, 2.315, 0.612
    make_cylinder("Candle_Jar", 0.052, 0.085, (cx, cy, z0 + 0.043),
                  COL_DECOR, M_CERAMIC, segments=40)
    make_cylinder("Candle_Wax", 0.043, 0.015, (cx, cy, z0 + 0.083),
                  COL_DECOR, M_CANDLE_WAX, segments=36)
    make_curve("Candle_Wick", [[(cx, cy, z0 + 0.090), (cx + 0.003, cy + 0.002, z0 + 0.104)]],
               0.0015, COL_DECOR, M_IRON, resolution=1, bevel_resolution=0)


make_candle()


# small ceramic tray and dried sprig on the right nightstand
def make_bedside_tray():
    cx, cy = 1.25, 2.03
    make_cylinder("Bedside_Tray", 0.075, 0.010, (cx, cy, 0.622),
                  COL_DECOR, M_OAK, segments=40)
    make_lathe("Bedside_Tiny_Vase", [(0.0, 0.0), (0.025, 0.0), (0.030, 0.03),
                                      (0.018, 0.075), (0.020, 0.085), (0.0, 0.085)],
               (cx - 0.015, cy + 0.005, 0.628), COL_DECOR, M_CERAMIC_TERRA,
               segments=32)
    make_curve("Bedside_Dried_Sprig",
               [[(cx - 0.015, cy + 0.005, 0.71), (cx - 0.04, cy + 0.01, 0.82),
                 (cx - 0.055, cy + 0.03, 0.90)]],
               0.0016, COL_DECOR, M_BARK, resolution=1, bevel_resolution=0)


make_bedside_tray()


# round wall clock above the interior door, away from the TV wall
def make_wall_clock():
    cx, cy, cz = -ROOM_X / 2 + 0.018, -1.56, 2.47
    make_cylinder("Wall_Clock_Body", 0.125, 0.026, (cx, cy, cz),
                  COL_DECOR, M_BRASS_DARK, rotation=(0, math.pi / 2, 0),
                  segments=48)
    make_cylinder("Wall_Clock_Face", 0.108, 0.006, (cx + 0.016, cy, cz),
                  COL_DECOR, M_CERAMIC, rotation=(0, math.pi / 2, 0),
                  segments=48)
    for i in range(12):
        ang = math.pi * 2 * i / 12.0
        make_box("Wall_Clock_Tick", (0.004, 0.012, 0.004),
                 (cx + 0.021, cy + math.sin(ang) * 0.085,
                  cz + math.cos(ang) * 0.085), COL_DECOR, M_IRON,
                 rotation=(ang, 0, 0), bevel=0.001, segments=1)
    make_box("Wall_Clock_Minute", (0.004, 0.006, 0.078),
             (cx + 0.022, cy, cz + 0.035), COL_DECOR, M_IRON,
             rotation=(0.20, 0, 0), bevel=0.001, segments=1)
    make_box("Wall_Clock_Hour", (0.004, 0.058, 0.006),
             (cx + 0.022, cy + 0.018, cz), COL_DECOR, M_IRON,
             bevel=0.001, segments=1)


make_wall_clock()


# No bed-foot basket and no seat cushion: she sits directly on the duvet.


# ---------------------------------------------------------------------------
# Artwork above the headboard
# ---------------------------------------------------------------------------
ART_W, ART_H = 0.45, 0.60
ART_CX, ART_CZ = BED_CX, 1.86
ART_Y = WALL_ART_Y
# backboard
make_box("Frame_Backboard", (ART_W - 0.03, 0.012, ART_H - 0.03),
         (ART_CX, ART_Y + 0.010, ART_CZ), COL_DECOR, M_WALNUT,
         bevel=0.002, segments=1)
# mat board (white)
mat_w, mat_h = ART_W - 0.075, ART_H - 0.075
make_rect("Frame_Mat", (ART_CX, ART_Y - 0.006, ART_CZ), mat_w, mat_h,
          "XZ", COL_DECOR, M_CERAMIC)
# image plane with exact aspect ratio 768:1296
img_w = mat_h * (768.0 / 1296.0)
img_h = mat_h
make_rect("Frame_Artwork", (ART_CX, ART_Y - 0.0095, ART_CZ), img_w, img_h,
          "XZ", COL_DECOR, M_ART, uvs=True)
# ensure every art vertex has UVs and the material is in its own slot
art_obj = bpy.data.objects["Frame_Artwork"]
art_obj.data.materials.clear()
art_obj.data.materials.append(M_ART)
uvl = art_obj.data.uv_layers.get("UVMap")
if uvl is None:
    uvl = art_obj.data.uv_layers.new(name="UVMap")
# Reassign a clean 0..1 unwrap
for poly in art_obj.data.polygons:
    for li in poly.loop_indices:
        vi = art_obj.data.loops[li].vertex_index
        if vi == 0:
            uvl.data[li].uv = (0.0, 0.0)
        elif vi == 1:
            uvl.data[li].uv = (1.0, 0.0)
        elif vi == 2:
            uvl.data[li].uv = (1.0, 1.0)
        else:
            uvl.data[li].uv = (0.0, 1.0)
# glass
make_rect("Frame_Glass", (ART_CX, ART_Y - 0.022, ART_CZ), mat_w, mat_h,
          "XZ", COL_DECOR, M_GLASS_ART)
g = bpy.data.objects.get("Frame_Glass")
if g:
    g.visible_shadow = False
# walnut frame bars
bw, bd, bz = 0.042, 0.034, ART_H
for nm, sz, loc in [
    ("Frame_Bar_Top", (ART_W, bd, bw), (ART_CX, ART_Y - 0.012, ART_CZ + ART_H / 2 - bw / 2)),
    ("Frame_Bar_Bottom", (ART_W, bd, bw), (ART_CX, ART_Y - 0.012, ART_CZ - ART_H / 2 + bw / 2)),
    ("Frame_Bar_Left", (bw, bd, ART_H - 2 * bw), (ART_CX - ART_W / 2 + bw / 2, ART_Y - 0.012, ART_CZ)),
    ("Frame_Bar_Right", (bw, bd, ART_H - 2 * bw), (ART_CX + ART_W / 2 - bw / 2, ART_Y - 0.012, ART_CZ)),
]:
    make_box(nm, sz, loc, COL_DECOR, M_WALNUT, bevel=0.007, segments=3)
# small brass hanging clips
for sx in (-1, 1):
    make_uv_sphere("Frame_Hanger", 0.012,
                   (ART_CX + sx * (ART_W / 2 - 0.06), ART_Y + 0.012, ART_CZ + ART_H / 2 - 0.03),
                   COL_DECOR, M_BRASS, segments=16, rings=8, scale=(1, 0.5, 1))

# The artwork is washed by a hidden, warm picture light; no visible fixture
# interrupts the top of the frame.


# ---------------------------------------------------------------------------
# Bedside / floor slippers
# ---------------------------------------------------------------------------
def make_slipper(name, cx, cy, rot):
    make_box(name + "_Sole", (0.115, 0.265, 0.022),
             (cx, cy, 0.045), COL_DECOR, M_SLIPPER,
             rotation=(0, 0, rot), bevel=0.014, segments=4, smooth=True)
    make_uv_sphere(name + "_Upper", 0.085,
                   (cx, cy + 0.015, 0.08), COL_DECOR, M_SLIPPER,
                   segments=32, rings=16, scale=(0.75, 1.35, 0.55),
                   rotation=(0.25, 0, rot))
    make_uv_sphere(name + "_Lining", 0.065,
                   (cx, cy - 0.035, 0.083), COL_DECOR, M_SLIPPER_LINING,
                   segments=28, rings=14, scale=(0.70, 0.75, 0.30),
                   rotation=(0.25, 0, rot))
    # little bow
    make_uv_sphere(name + "_Bow", 0.020,
                   (cx + 0.03, cy - 0.08, 0.105), COL_DECOR, M_SLIPPER_LINING,
                   segments=16, rings=8, scale=(1.1, 0.6, 0.45))


# Slippers were removed: the rug must stay completely clear of clutter.


# ---------------------------------------------------------------------------
# Plants: fiddle-leaf fig in the foreground corner + pothos on the sill
# ---------------------------------------------------------------------------
def make_leaf_mesh(name, length, width, loc, rot, collection, mat, curl=0.02,
                   veins=False):
    nu, nv = 11, 20
    verts, uvs = [], []
    for j in range(nv + 1):
        v = j / nv
        half = 0.5 * width * (math.sin(math.pi * v) ** 0.65) * (1.0 - 0.22 * v)
        for i in range(nu + 1):
            u = i / nu
            xx = (u - 0.5) * 2 * half
            yy = v * length
            # fold along midrib and curl at tip
            zz = (0.016 * (abs(u - 0.5) * 2) ** 1.8 * width / max(width, 1e-5)
                  + curl * v * v)
            # irregular margin wave
            if i == 0 or i == nu:
                zz += 0.006 * math.sin(v * 7.0 + 0.4) * (0.3 + 0.7 * v)
            # central rib raised a touch
            zz += 0.004 * math.exp(-((u - 0.5) ** 2) / 0.002)
            verts.append((xx, yy, zz))
            uvs.append((u, v))
    faces = []
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            b = a + 1
            c = a + (nu + 1) + 1
            d = a + (nu + 1)
            faces.append((a, b, c, d))
    obj = mesh_object(name, verts, faces, collection, mat, smooth=True,
                      uvs=uvs, location=loc, rotation=rot)
    add_solidify(obj, 0.0025, offset=0.0)
    if veins and length > 0.12:
        # Midrib and side veins in the leaf's local frame.
        rotm = Euler(rot, "XYZ").to_matrix()
        origin = Vector(loc)

        def wpt(u, v):
            half = 0.5 * width * (math.sin(math.pi * v) ** 0.65) * (1.0 - 0.22 * v)
            xx = (u - 0.5) * 2 * half
            yy = v * length
            zz = (0.016 * (abs(u - 0.5) * 2) ** 1.8
                  + curl * v * v
                  + 0.004 * math.exp(-((u - 0.5) ** 2) / 0.002))
            return origin + rotm @ Vector((xx, yy, zz + 0.0022))

        rib = [wpt(0.5, v / 10.0) for v in range(1, 10)]
        splines = [rib]
        for vv in (0.28, 0.52, 0.74):
            for side in (-1, 1):
                splines.append([wpt(0.5, vv),
                                wpt(0.5 + side * 0.22, vv + 0.035),
                                wpt(0.5 + side * 0.42, vv + 0.075)])
        make_curve(name + "_Veins", splines, 0.00065, collection,
                   M_LEAF_VEIN, resolution=1, bevel_resolution=0)
    return obj


def make_fiddle_leaf_plant():
    cx, cy = 1.92, -2.04
    pot_h = 0.34
    make_lathe("Monstera_Pot", [(0.0, 0.0), (0.19, 0.0), (0.22, 0.04),
                                (0.235, pot_h - 0.04), (0.225, pot_h),
                                (0.205, pot_h), (0.205, pot_h - 0.03),
                                (0.0, pot_h - 0.03)],
               (cx, cy, 0.018), COL_PLANTS, M_CERAMIC_TERRA, segments=64)
    make_cylinder("Plant_Soil", 0.198, 0.025, (cx, cy, 0.35),
                  COL_PLANTS, M_SOIL, segments=48)
    # a few trunks / stems
    stem_paths = []
    branches = []
    random.seed(444)
    base_z = 0.35
    for trunk in range(4):
        ox = cx + random.uniform(-0.07, 0.07)
        oy = cy + random.uniform(-0.06, 0.06)
        h = random.uniform(0.84, 1.08)
        seg = []
        for k in range(6):
            t = k / 5
            seg.append((ox + 0.06 * math.sin(t * 2.4 + trunk) * t,
                        oy + 0.04 * math.cos(t * 1.7 + trunk) * t,
                        base_z + t * h))
        stem_paths.append(seg)
        for j in range(6):
            t = 0.30 + j * 0.125
            p0 = (ox + 0.06 * math.sin(t * 2.4 + trunk) * t,
                  oy + 0.04 * math.cos(t * 1.7 + trunk) * t,
                  base_z + t * h)
            ang = random.uniform(0, 2 * math.pi)
            reach = random.uniform(0.14, 0.30)
            p1 = (p0[0] + math.cos(ang) * reach,
                  p0[1] + math.sin(ang) * reach,
                  p0[2] + random.uniform(0.02, 0.12))
            branches.append([p0, ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, p1[2] + 0.02), p1])
            # two leaves per branch point
            for li in range(2):
                rot_z = ang + math.pi + random.uniform(-0.6, 0.6) + li * 0.7
                rot_x = random.uniform(0.55, 1.25) * (1 if li else 0.8)
                rot_y = random.uniform(-0.3, 0.3)
                llen = random.uniform(0.15, 0.275)
                lwid = llen * random.uniform(0.56, 0.78)
                make_leaf_mesh("Fiddle_Leaf_%02d_%02d" % (trunk, j * 2 + li),
                               llen, lwid, p1, (rot_x, rot_y, rot_z),
                               COL_PLANTS, M_LEAF, curl=0.05, veins=True)
    make_curve("Fiddle_Trunks", stem_paths, 0.009, COL_PLANTS, M_BARK,
               resolution=2, bevel_resolution=2)
    make_curve("Fiddle_Branches", branches, 0.0045, COL_PLANTS, M_BARK,
               resolution=1, bevel_resolution=1)


make_fiddle_leaf_plant()


def make_sill_plant():
    cx, cy, cz = 2.135, 1.28, 0.875
    make_lathe("Sill_Pothos_Pot", [(0.0, 0.0), (0.058, 0.0), (0.070, 0.085),
                                   (0.062, 0.11), (0.0, 0.11)],
               (cx, cy, cz), COL_PLANTS, M_CERAMIC, segments=40)
    make_cylinder("Sill_Pothos_Soil", 0.055, 0.015, (cx, cy, cz + 0.078),
                  COL_PLANTS, M_SOIL, segments=32)
    paths, leaves = [], []
    rnd = random.Random(88)
    for k in range(12):
        ang = 2 * math.pi * k / 12 + rnd.uniform(-0.2, 0.2)
        reach = rnd.uniform(0.10, 0.24)
        p0 = (cx, cy, cz + 0.10)
        p1 = (cx + math.cos(ang) * reach * 0.55, cy + math.sin(ang) * reach * 0.55,
              cz + 0.17 + rnd.uniform(-0.02, 0.05))
        p2 = (cx + math.cos(ang) * reach, cy + math.sin(ang) * reach,
              cz + 0.10 + rnd.uniform(-0.04, 0.08))
        paths.append([p0, p1, p2])
        for q in range(2):
            pp = p2
            make_leaf_mesh("Pothos_Leaf_%02d_%d" % (k, q),
                           rnd.uniform(0.055, 0.085), rnd.uniform(0.035, 0.055),
                           pp, (rnd.uniform(-0.3, 0.4), rnd.uniform(-0.6, 0.6),
                                ang + rnd.uniform(-0.8, 0.8)),
                           COL_PLANTS, M_LEAF_POTHOS, curl=0.015)
    make_curve("Sill_Pothos_Vines", paths, 0.0018, COL_PLANTS, M_BARK,
               resolution=1, bevel_resolution=0)


make_sill_plant()


def make_sill_succulent():
    cx, cy, cz = 2.145, 1.70, 0.875
    make_lathe("Sill_Succulent_Pot", [(0.0, 0.0), (0.050, 0.0), (0.060, 0.035),
                                      (0.068, 0.082), (0.064, 0.095), (0.0, 0.095)],
               (cx, cy, cz), COL_PLANTS, M_CERAMIC, segments=48)
    make_cylinder("Sill_Succulent_Soil", 0.055, 0.012,
                  (cx, cy, cz + 0.078), COL_PLANTS, M_SOIL, segments=32)
    rnd = random.Random(301)
    for k in range(14):
        ang = 2 * math.pi * k / 14
        rr = rnd.uniform(0.012, 0.045)
        make_uv_sphere("Sill_Succulent_Leaf_%02d" % k, 1.0,
                       (cx + math.cos(ang) * rr, cy + math.sin(ang) * rr,
                        cz + 0.094 + rnd.uniform(0.0, 0.018)),
                       COL_PLANTS, M_LEAF_SUCCULENT,
                       segments=20, rings=10,
                       scale=(0.022, 0.055, 0.012),
                       rotation=(rnd.uniform(0.25, 0.7), 0.0, ang))
    # a small oval tray beside the pots
    make_cylinder("Sill_Decor_Tray", 0.090, 0.012,
                  (2.145, 1.48, 0.884), COL_DECOR, M_OAK,
                  segments=48)
    make_uv_sphere("Sill_Tray_Stone", 0.035,
                   (2.145, 1.48, 0.902), COL_DECOR, M_CERAMIC_TERRA,
                   segments=24, rings=12, scale=(1.0, 0.72, 0.28))


make_sill_succulent()


# ---------------------------------------------------------------------------
# Exterior window box, filled with foliage and small pale flowers
# ---------------------------------------------------------------------------
def make_window_box():
    before = set(bpy.data.objects)
    cx, cy = 2.58, 1.44
    # weathered terracotta trough just outside the sash
    make_box("Window_Box_Trough", (0.28, 1.66, 0.19),
             (cx, cy, 0.89), COL_OUT, M_OAK_DARK,
             bevel=0.014, segments=3)
    make_box("Window_Box_Rim", (0.32, 1.72, 0.035),
             (cx, cy, 0.99), COL_OUT, M_OAK_DARK,
             bevel=0.012, segments=3)
    make_box("Window_Box_Soil", (0.22, 1.56, 0.03),
             (cx + 0.01, cy, 0.998), COL_OUT, M_SOIL,
             bevel=0.005, segments=1, smooth=False)
    # ivy / trailing and upright greenery
    rnd = random.Random(812)
    stem_paths = []
    for k in range(18):
        yy = cy - 0.74 + 1.48 * (k / 17.0) + rnd.uniform(-0.03, 0.03)
        # upright stems of mixed height, with a slightly arching habit
        topz = rnd.uniform(1.03, 1.30)
        bend = rnd.uniform(-0.08, 0.08)
        stem_paths.append([(cx + 0.01, yy, 1.01),
                           (cx + 0.03 + bend * 0.3, yy + rnd.uniform(-0.04, 0.04), (1.02 + topz) / 2),
                           (cx + 0.05 + bend, yy + rnd.uniform(-0.06, 0.06), topz)])
        for q in range(2):
            leaf_len = rnd.uniform(0.060, 0.120)
            leaf_mat = M_LEAF_OUT if (k + q) % 3 == 0 else M_LEAF_POTHOS
            make_leaf_mesh("WindowBox_Leaf_%02d_%d" % (k, q),
                           leaf_len, leaf_len * rnd.uniform(0.62, 0.88),
                           (cx + 0.04 + bend + rnd.uniform(-0.025, 0.025),
                            yy + rnd.uniform(-0.04, 0.04),
                            topz - 0.012 - q * 0.035),
                           (rnd.uniform(0.45, 1.30), rnd.uniform(-0.65, 0.65),
                            rnd.uniform(0, 2 * math.pi)),
                           COL_OUT, leaf_mat, curl=0.015)
    # trailing ivy over the front lip
    trail_paths = []
    for k in range(8):
        yy = cy - 0.6 + 1.2 * (k / 7.0) + rnd.uniform(-0.03, 0.03)
        x0 = cx - 0.15
        trail_paths.append([(x0, yy, 1.02),
                            (x0 - 0.02, yy + rnd.uniform(-0.02, 0.02), 0.94),
                            (x0 - 0.01, yy + rnd.uniform(-0.03, 0.03), 0.85)])
        for q in range(2):
            make_leaf_mesh("WindowBox_Trail_%02d_%d" % (k, q),
                           rnd.uniform(0.055, 0.09), rnd.uniform(0.04, 0.07),
                           (x0 - 0.015, yy + rnd.uniform(-0.02, 0.02), 0.89 - q * 0.04),
                           (rnd.uniform(-0.4, 0.2), rnd.uniform(-0.5, 0.5),
                            rnd.uniform(0, 2 * math.pi)),
                           COL_OUT, M_LEAF_POTHOS, curl=0.01)
    make_curve("Window_Box_Stems", stem_paths, 0.0025, COL_OUT, M_BARK,
               resolution=1, bevel_resolution=0)
    make_curve("Window_Box_Trailing_Stems", trail_paths, 0.002, COL_OUT, M_BARK,
               resolution=1, bevel_resolution=0)
    # small pale flowers
    for k in range(20):
        yy = cy - 0.66 + 1.32 * (k / 19.0) + rnd.uniform(-0.02, 0.02)
        pz = rnd.uniform(1.06, 1.27)
        make_uv_sphere("WindowBox_Flower_%02d" % k, rnd.uniform(0.007, 0.013),
                       (cx + 0.085, yy + rnd.uniform(-0.04, 0.04), pz),
                       COL_OUT, M_CERAMIC, segments=12, rings=6,
                       scale=(0.7, 1.0, 0.7))
    # nothing outside the window should cast a hard shadow into the room
    for ob in set(bpy.data.objects) - before:
        ob.visible_shadow = False


make_window_box()


# ---------------------------------------------------------------------------
# Outdoor world: sky dome, city, trees, sun/moon, rain and haze
# ---------------------------------------------------------------------------
# sky dome
make_uv_sphere("Sky_Dome", 80.0, (0, 0, 0), COL_OUT, M_SKY_SUNNY,
               segments=128, rings=64)
sky_dome = bpy.data.objects["Sky_Dome"]
sky_dome.visible_shadow = False
# Let the procedural sky act as the real sky light: it illuminates the garden
# and spills through the window, while the walls still keep the room enclosed.
sky_dome.visible_diffuse = True
sky_dome.visible_glossy = True

# outdoor ground
make_box("Outdoor_Ground", (160.0, 160.0, 0.10), (0, 0, -0.06), COL_OUT,
         M_GROUND, bevel=0.0, smooth=False)
ground = bpy.data.objects["Outdoor_Ground"]
ground.visible_shadow = False

# distant city blocks: small, layered, low on the horizon
random.seed(2468)
n_buildings = 58
city_extent = []
for i in range(n_buildings):
    az = math.radians(random.uniform(8, 92))
    radius = random.uniform(44, 76)
    bx = radius * math.cos(az)
    by = radius * math.sin(az)
    width = random.uniform(1.7, 4.6)
    depth = random.uniform(1.4, 3.6)
    hgt = random.uniform(1.8, 5.2)
    if i % 11 == 0:
        hgt = random.uniform(6.0, 8.5)
    mat = M_CITY_WARM if random.random() < 0.35 else M_CITY
    ob = make_box("City_Block_%02d" % i, (width, depth, hgt),
                  (bx, by, hgt / 2), COL_OUT, mat,
                  rotation=(0, 0, az + math.pi / 2), bevel=0.05, segments=1,
                  smooth=False)
    ob.visible_shadow = False
    city_extent.append((az, radius, width, hgt))
    if random.random() < 0.55:
        make_box("City_Roof_%02d" % i, (width * 0.22, depth * 0.26, random.uniform(0.3, 1.0)),
                 (bx, by, hgt + random.uniform(0.16, 0.5)), COL_OUT, mat,
                 rotation=(0, 0, az + math.pi / 2), bevel=0.03, segments=1,
                 smooth=False)
        bpy.data.objects["City_Roof_%02d" % i].visible_shadow = False

# city window lights (one mesh, visible only at night / dusk)
light_verts, light_faces = [], []
random.seed(97531)
for i in range(130):
    az = math.radians(random.uniform(15, 78))
    radius = random.uniform(46, 76)
    width = random.uniform(2.0, 4.4)
    hgt = random.uniform(2.5, 7.0)
    # windows on the inward face
    face_dist = radius - 0.9
    wx = face_dist * math.cos(az)
    wy = face_dist * math.sin(az)
    tangent = Vector((-math.sin(az), math.cos(az), 0))
    n_windows = 2
    for k in range(n_windows):
        zc = random.uniform(1.0, max(1.2, hgt - 0.8))
        xoff = random.uniform(-width * 0.33, width * 0.33)
        center = Vector((wx, wy, zc)) + tangent * xoff
        ww, wh = random.uniform(0.22, 0.50), random.uniform(0.28, 0.62)
        # quad facing inward
        p0 = center - tangent * ww / 2 + Vector((0, 0, -wh / 2))
        p1 = center + tangent * ww / 2 + Vector((0, 0, -wh / 2))
        p2 = center + tangent * ww / 2 + Vector((0, 0, wh / 2))
        p3 = center - tangent * ww / 2 + Vector((0, 0, wh / 2))
        base = len(light_verts)
        light_verts.extend([tuple(p0), tuple(p1), tuple(p2), tuple(p3)])
        light_faces.append((base, base + 1, base + 2, base + 3))
city_lights = mesh_object("City_Lights", light_verts, light_faces, COL_OUT,
                          M_CITY_LIGHTS, smooth=False)
city_lights.visible_shadow = False
city_lights.hide_render = True
city_lights.hide_viewport = True

# leaf-card foliage clusters: much more organic than smooth spheres at distance
def make_foliage_cluster(name, center, rx, ry, rz, leaf_count, mat, seed,
                         core=True, size=(0.10, 0.20)):
    rnd = random.Random(seed)
    if core:
        core_obj = make_uv_sphere(name + "_Core", 1.0, center, COL_OUT,
                                  M_LEAF_OUT_DARK, segments=20, rings=10,
                                  scale=(rx * 0.72, ry * 0.72, rz * 0.72))
        core_obj.visible_shadow = False
    verts, faces = [], []
    for k in range(leaf_count):
        # bias the random directions slightly away from the centre
        th = rnd.uniform(0, 2 * math.pi)
        ph = math.acos(rnd.uniform(-0.92, 0.92))
        d = Vector((math.sin(ph) * math.cos(th), math.sin(ph) * math.sin(th),
                    math.cos(ph)))
        rad = rnd.uniform(0.84, 1.04)
        p = Vector(center) + Vector((d.x * rx, d.y * ry, d.z * rz)) * rad
        # tangent basis
        up = Vector((0, 0, 1))
        t1 = d.cross(up)
        if t1.length < 1e-4:
            t1 = Vector((1, 0, 0))
        t1.normalize()
        t2 = d.cross(t1).normalized()
        roll = rnd.uniform(0, 2 * math.pi)
        a = t1 * math.cos(roll) + t2 * math.sin(roll)
        b = -t1 * math.sin(roll) + t2 * math.cos(roll)
        ll = rnd.uniform(*size)
        ww = ll * rnd.uniform(0.38, 0.60)
        # 4-point diamond leaf, very slightly folded
        q0 = p - a * (ww * 0.5)
        q1 = p - b * (ll * 0.5)
        q2 = p + a * (ww * 0.5)
        q3 = p + b * (ll * 0.5)
        pc = p + d * (ll * 0.06)
        base = len(verts)
        verts.extend([tuple(q0), tuple(q1), tuple(q2), tuple(q3), tuple(pc)])
        faces.extend([(base, base + 1, base + 4), (base + 1, base + 2, base + 4),
                      (base + 2, base + 3, base + 4), (base + 3, base, base + 4)])
    obj = mesh_object(name, verts, faces, COL_OUT, mat, smooth=False)
    obj.visible_shadow = False
    return obj


# stylised outdoor trees with leaf-card canopies
def make_outdoor_tree(name, base_x, base_y, height, canopy_scale, seed):
    rnd = random.Random(seed)
    trunk_pts = []
    for k in range(6):
        t = k / 5
        trunk_pts.append((base_x + 0.18 * math.sin(t * 2.1 + seed) * t,
                          base_y + 0.12 * math.cos(t * 1.5 + seed) * t,
                          height * t))
    make_curve(name + "_Trunk", [trunk_pts], 0.10, COL_OUT, M_BARK,
               resolution=2, bevel_resolution=2)
    b = bpy.data.objects[name + "_Trunk"]
    if b:
        b.visible_shadow = False
    branches = []
    for k in range(6):
        t = rnd.uniform(0.4, 0.9)
        p0 = (base_x, base_y, height * t)
        ang = rnd.uniform(0, 2 * math.pi)
        p1 = (base_x + math.cos(ang) * canopy_scale * rnd.uniform(0.5, 1.0),
              base_y + math.sin(ang) * canopy_scale * rnd.uniform(0.5, 1.0),
              height * t + rnd.uniform(0.1, 0.8))
        branches.append([p0, p1])
        mat = M_LEAF_OUT_LIGHT if k % 3 == 0 else M_LEAF_OUT
        make_foliage_cluster(name + "_Canopy_%02d" % k,
                             (p1[0], p1[1], p1[2] + 0.2),
                             canopy_scale * rnd.uniform(0.7, 1.05),
                             canopy_scale * rnd.uniform(0.7, 1.05),
                             canopy_scale * rnd.uniform(0.55, 0.85),
                             int(95 * canopy_scale), mat, seed * 100 + k,
                             core=True, size=(0.11, 0.23))
    make_curve(name + "_Branches", branches, 0.045, COL_OUT, M_BARK,
               resolution=1, bevel_resolution=1)
    bb = bpy.data.objects[name + "_Branches"]
    if bb:
        bb.visible_shadow = False


# The window looks out over a quiet, low skyline and a leafy window box.  The
# tall trees live outside the visible cone, avoiding a green wall in the glass.
make_outdoor_tree("Tree_Outdoor_Left", 0.5, 26.0, 6.5, 2.1, 12)
make_outdoor_tree("Tree_Outdoor_Right", 44.0, 18.0, 8.0, 2.6, 77)

# airy low garden below the window line; no heavy cores, so it reads as leaves
# rather than a green wall
rnd = random.Random(141)
for i in range(12):
    px = rnd.uniform(4.8, 8.0)
    py = rnd.uniform(0.6, 12.5)
    pz = rnd.uniform(0.62, 1.05)
    rx = rnd.uniform(0.32, 0.62)
    mat = M_LEAF_OUT_LIGHT if i % 4 == 0 else M_LEAF_OUT
    make_foliage_cluster("Garden_Hedge_%02d" % i, (px, py, pz),
                         rx, rx * rnd.uniform(0.8, 1.3), rx * rnd.uniform(0.55, 0.85),
                         int(90 * rx), mat, 300 + i, core=False,
                         size=(0.075, 0.16))
# a sparse second row, lower and further back
for i in range(7):
    px = rnd.uniform(9.0, 15.0)
    py = rnd.uniform(4.0, 16.0)
    pz = rnd.uniform(1.0, 1.6)
    rx = rnd.uniform(0.55, 0.95)
    make_foliage_cluster("Garden_Bush_%02d" % i, (px, py, pz),
                         rx, rx * rnd.uniform(0.8, 1.2), rx * rnd.uniform(0.55, 0.85),
                         int(85 * rx), M_LEAF_OUT, 500 + i, core=False,
                         size=(0.09, 0.19))

# a soft far tree line below the city, catching the last light
rnd = random.Random(313)
for i in range(16):
    px = rnd.uniform(17.0, 34.0)
    py = rnd.uniform(3.0, 30.0)
    pz = rnd.uniform(1.0, 2.0)
    rx = rnd.uniform(0.7, 1.4)
    make_foliage_cluster("Distant_Tree_Line_%02d" % i, (px, py, pz),
                         rx, rx * rnd.uniform(0.9, 1.4), rx * rnd.uniform(0.6, 0.9),
                         int(80 * rx), M_LEAF_OUT_DARK, 700 + i, core=False,
                         size=(0.10, 0.22))

# A few soft mid-ground tree crowns between the window box and the city.  They
# are deliberately sparse and are softened by the lens, giving the view depth.
for i in range(7):
    az = math.radians(40.0 + i * 1.8)
    radius = 13.0 + i * 2.3
    px, py = radius * math.cos(az), radius * math.sin(az)
    pz = 2.3 + 0.4 * (i % 3)
    make_foliage_cluster("Midground_Tree_%02d" % i, (px, py, pz),
                         0.9 + 0.15 * (i % 3), 0.95, 0.65,
                         90, M_LEAF_OUT_LIGHT if i % 2 == 0 else M_LEAF_OUT,
                         900 + i, core=False, size=(0.11, 0.23))
# a few pale flower clusters for a bit of sparkle
rnd = random.Random(923)
for i in range(28):
    px = rnd.uniform(3.9, 4.4)
    py = rnd.uniform(0.8, 7.0)
    pz = rnd.uniform(1.05, 1.5)
    make_uv_sphere("Garden_Flower_%02d" % i, rnd.uniform(0.025, 0.05),
                   (px, py, pz), COL_OUT, M_CERAMIC,
                   segments=10, rings=5, scale=(1.0, 1.0, 0.6)).visible_shadow = False

# visible sun and moon discs
sun_pos = Vector((0, 0, 1.2)) + Vector((math.cos(math.radians(7.5)) * math.cos(math.radians(43)),
                                        math.cos(math.radians(7.5)) * math.sin(math.radians(43)),
                                        math.sin(math.radians(7.5)))) * 56.0
make_uv_sphere("Sun_Disc", 1.0, tuple(sun_pos), COL_OUT, M_SUN_DISC,
               segments=32, rings=16)
sun_disc = bpy.data.objects["Sun_Disc"]
sun_disc.visible_shadow = False
sun_disc.visible_diffuse = False
sun_disc.visible_glossy = False

moon_pos = Vector((0, 0, 1.2)) + Vector((math.cos(math.radians(46)) * math.cos(math.radians(50)),
                                         math.cos(math.radians(46)) * math.sin(math.radians(50)),
                                         math.sin(math.radians(46)))) * 50.0
make_uv_sphere("Moon", 0.85, tuple(moon_pos), COL_OUT, M_MOON,
               segments=32, rings=16)
moon = bpy.data.objects["Moon"]
moon.visible_shadow = False
moon.visible_diffuse = False
moon.visible_glossy = False
moon.hide_render = True
moon.hide_viewport = True

# rain haze plane (large, just outside the window)
make_rect("Rain_Haze", (3.35, 8.0, 5.0), 60.0, 26.0, "YZ", COL_OUT, M_HAZE)
haze = bpy.data.objects["Rain_Haze"]
haze.visible_shadow = False
haze.visible_diffuse = False
haze.visible_glossy = False
haze.hide_render = True
haze.hide_viewport = True

# rain curtains / sheets
rain_planes = []
for i in range(3):
    x = 4.2 + i * 1.55
    # wide enough to cover the diagonal view through the window
    y_center = 8.0 + i * 2.2
    make_rect("Rain_Curtain_%d" % (i + 1), (x, y_center, 7.0),
              50.0, 28.0, "YZ", COL_OUT, M_RAIN_CURTAIN_MOD)
    o = bpy.data.objects["Rain_Curtain_%d" % (i + 1)]
    o.visible_shadow = False
    o.visible_diffuse = False
    o.visible_glossy = False
    o.hide_render = True
    o.hide_viewport = True
    rain_planes.append(o)

# tiny distant stars (subtle; only at night)
star_verts, star_faces = [], []
rnd = random.Random(55)
for i in range(70):
    az = math.radians(rnd.uniform(20, 70))
    el = math.radians(rnd.uniform(7, 30))
    d = 70.0
    x = d * math.cos(el) * math.cos(az)
    y = d * math.cos(el) * math.sin(az)
    z = d * math.sin(el) + 1.2
    s = rnd.uniform(0.035, 0.08)
    base = len(star_verts)
    star_verts.extend([(x, y, z - s), (x + s, y, z), (x, y, z + s), (x - s, y, z)])
    star_faces.append((base, base + 1, base + 2, base + 3))
M_STARS = mat_emission("Stars_Mat", "#D8E8FF", strength=2.0,
                       node_name="Stars_Emission")
stars = mesh_object("Stars", star_verts, star_faces, COL_OUT, M_STARS,
                    smooth=False)
stars.visible_shadow = False
stars.visible_diffuse = False
stars.hide_render = True
stars.hide_viewport = True


# ---------------------------------------------------------------------------
# World shader
# ---------------------------------------------------------------------------
world = bpy.data.worlds.new("Sky")
scene.world = world
world.use_nodes = True
wnt = world.node_tree
wnt.nodes.clear()
wout = wnt.nodes.new("ShaderNodeOutputWorld")
wout.location = (500, 0)
wbg = wnt.nodes.new("ShaderNodeBackground")
wbg.name = "World_Background"
wbg.location = (260, 0)
wbg.inputs["Strength"].default_value = 0.7
wtc = wnt.nodes.new("ShaderNodeTexCoord")
wtc.location = (-700, 0)
wsep = wnt.nodes.new("ShaderNodeSeparateXYZ")
wsep.location = (-500, 0)
wnt.links.new(wtc.outputs["Generated"], wsep.inputs["Vector"])
wramp = wnt.nodes.new("ShaderNodeValToRGB")
wramp.name = "World_Gradient"
wramp.location = (-280, 0)
wramp.color_ramp.elements[0].position = 0.05
wramp.color_ramp.elements[0].color = hexrgba("#F5E7D3")
wramp.color_ramp.elements[1].position = 0.8
wramp.color_ramp.elements[1].color = hexrgba("#8CBAE4")
wnt.links.new(wsep.outputs["Z"], wramp.inputs["Fac"])
wnt.links.new(wramp.outputs["Color"], wbg.inputs["Color"])
wnt.links.new(wbg.outputs["Background"], wout.inputs["Surface"])

# ---------------------------------------------------------------------------
# Lights
# ---------------------------------------------------------------------------
def add_area_light(name, loc, target, energy, kelvin, size=(1.0, 1.0),
                   shape="RECTANGLE", color=None):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.shape = shape
    data.size = size[0]
    if shape == "RECTANGLE":
        data.size_y = size[1]
    data.color = color if color else (1.0, 0.6, 0.32)
    ob = bpy.data.objects.new(name, data)
    COL_LIGHT.objects.link(ob)
    ob.location = loc
    direction = Vector(target) - Vector(loc)
    ob.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return ob


# Sun key
sun_data = bpy.data.lights.new("Sun", "SUN")
sun_data.energy = 4.6
sun_data.angle = math.radians(1.3)
sun_data.color = (1.0, 0.72, 0.48)
sun_obj = bpy.data.objects.new("Sun", sun_data)
COL_LIGHT.objects.link(sun_obj)
sun_obj.location = (6, 6, 8)
sun_obj.rotation_euler = Vector((-1, -0.9, -0.4)).to_track_quat("-Z", "Y").to_euler()

# soft interior fill
fill = add_area_light("Fill_Soft", (0.0, -1.8, 2.55), (0.2, 1.2, 0.7),
                      12.0, 4000, size=(2.4, 1.5), shape="RECTANGLE")

# A large, soft daylight portal just outside the window.  This replaces the
# complex multiple-bounce skylight in a cheap but visually convincing way and
# is what actually makes the room read like daylight, not just lamplight.
fill_window = add_area_light("Fill_Window", (2.78, win_cy, 1.62),
                             (0.0, 1.15, 1.0), 55.0, 4600,
                             size=(1.62, 1.35), shape="RECTANGLE")
fill_window.visible_camera = False
fill_window.visible_glossy = False

# window bounce (very soft, helps the room read without flattening it)
bounce = add_area_light("Window_Bounce", (2.02, 1.45, 1.55), (0.0, 1.1, 1.0),
                        7.0, 5200, size=(1.5, 1.3), shape="RECTANGLE")
bounce.hide_render = True  # disabled by default; can be enabled by hand

# discrete warm picture light on the artwork
art_light = add_area_light("Art_Light", (ART_CX, 2.405, 2.20),
                           (ART_CX, 2.49, 1.91), 3.2, 2850,
                           size=(0.34, 0.035), shape="RECTANGLE")
art_light.data.spread = math.radians(80.0)

# lightning
lightning_data = bpy.data.lights.new("Lightning", "AREA")
lightning_data.energy = 0.0
lightning_data.shape = "RECTANGLE"
lightning_data.size = 5.0
lightning_data.size_y = 4.0
lightning_data.color = (0.70, 0.82, 1.0)
lightning = bpy.data.objects.new("Lightning", lightning_data)
COL_LIGHT.objects.link(lightning)
lightning.location = (8.0, 7.0, 8.0)
lightning.rotation_euler = (Vector((0, 0, 1.0)) - lightning.location).to_track_quat("-Z", "Y").to_euler()
lightning.hide_render = True
lightning.hide_viewport = True
scene["lightning_energy"] = 0.0


# ---------------------------------------------------------------------------
# Camera, composition and render settings
# ---------------------------------------------------------------------------
def add_camera_object(name, loc, target, lens=35.0, dof=False, fstop=4.0):
    data = bpy.data.cameras.new(name)
    data.lens = lens
    data.sensor_width = 36.0
    data.clip_start = 0.025
    data.clip_end = 400.0
    data.dof.use_dof = bool(dof)
    if dof:
        data.dof.aperture_fstop = fstop
        data.dof.aperture_blades = 7
    ob = bpy.data.objects.new(name, data)
    COL_CAM.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return ob


cam = add_camera_object("Camera", (-1.32, -2.18, 1.56),
                        (0.0, 1.10, 1.06), lens=35.0, dof=True, fstop=3.2)
scene.camera = cam
focus = bpy.data.objects.new("Focus_Target", None)
focus.empty_display_type = "SPHERE"
focus.empty_display_size = 0.05
focus.location = (0.0, 1.24, 1.02)
COL_CAM.objects.link(focus)
cam.data.dof.focus_object = focus

add_camera_object("Camera_Wide", (-1.80, -2.32, 1.64),
                  (0.0, 0.95, 1.05), lens=24.0)
add_camera_object("Camera_BedArt", (-0.05, -2.35, 1.55),
                  (0.0, 1.58, 1.32), lens=40.0)
add_camera_object("Camera_Desk", (1.55, 0.35, 1.60),
                  (1.95, 1.08, 0.78), lens=38.0)
add_camera_object("Camera_Desk_Wide", (0.18, 0.28, 2.12),
                  (1.98, 1.16, 0.68), lens=28.0)
add_camera_object("Camera_TV", (0.0, 0.42, 1.52),
                  (0.0, -2.42, 1.08), lens=28.0)
add_camera_object("Camera_Door", (1.45, -0.70, 1.65),
                  (-2.02, -0.38, 1.14), lens=24.0)
add_camera_object("Camera_Wardrobe", (0.72, 1.20, 1.60),
                  (-2.08, 0.16, 1.15), lens=29.0)
add_camera_object("Camera_Maid", (1.45, 0.65, 1.50),
                  (0.46, 1.95, 0.85), lens=50.0)
add_camera_object("Camera_Plants", (0.85, 0.95, 1.50),
                  (2.10, 1.34, 1.02), lens=48.0)

pano = add_camera_object("Camera_Pano", (0.0, -0.85, 1.55),
                         (1.20, -0.85, 1.55), lens=18.0)
pano.data.type = "PANO"
pano.data.panorama_type = "EQUIRECTANGULAR"
pano.data.dof.use_dof = False
try:
    # latitude is stored in radians; longitude is in degrees in Blender 5.x.
    pano.data.latitude_min = -math.pi / 2
    pano.data.latitude_max = math.pi / 2
    pano.data.longitude_min = -math.pi
    pano.data.longitude_max = math.pi
except Exception:
    pass

# render setup
scene.render.engine = "CYCLES"
scene.cycles.device = "GPU"
scene.cycles.samples = 256
scene.cycles.use_denoising = True
try:
    scene.cycles.denoiser = "OPTIX"
except Exception:
    try:
        scene.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
try:
    scene.cycles.denoising_use_gpu = True
except Exception:
    pass
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.02
scene.cycles.max_bounces = 8
scene.cycles.diffuse_bounces = 4
scene.cycles.glossy_bounces = 4
scene.cycles.transmission_bounces = 8
scene.cycles.transparent_max_bounces = 12
scene.cycles.volume_bounces = 0
scene.cycles.use_light_tree = True
scene.cycles.caustics_reflective = False
scene.cycles.caustics_refractive = False
scene.cycles.sample_clamp_indirect = 12.0
scene.cycles.sample_clamp_direct = 0.0
scene.render.use_persistent_data = True
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.render.image_settings.color_depth = "8"
scene.render.image_settings.compression = 25
scene.render.filepath = os.path.join(RENDER_DIR, "bedroom_dusk_sunny.png")
scene.render.film_transparent = False
scene.render.use_file_extension = True

# colour management
scene.view_settings.view_transform = "AgX"
try:
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass
scene.view_settings.exposure = 0.35
scene.view_settings.gamma = 1.0

# Subtle optical glow around the window / practicals (Blender 5 node group).
try:
    comp_ng = bpy.data.node_groups.get("Bedroom_Compositing")
    if comp_ng is None:
        comp_ng = bpy.data.node_groups.new("Bedroom_Compositing", "CompositorNodeTree")
    comp_ng.nodes.clear()
    if len(comp_ng.interface.items_tree) == 0:
        comp_ng.interface.new_socket(name="Image", in_out="OUTPUT",
                                     socket_type="NodeSocketColor")
    scene.compositing_node_group = comp_ng
    rl = comp_ng.nodes.new("CompositorNodeRLayers")
    rl.location = (-520, 0)
    glare = comp_ng.nodes.new("CompositorNodeGlare")
    glare.location = (-240, 0)
    try:
        glare.inputs["Type"].default_value = "Fog Glow"
    except Exception:
        pass
    try:
        glare.inputs["Quality"].default_value = "High"
    except Exception:
        pass
    glare.inputs["Threshold"].default_value = 1.15
    glare.inputs["Strength"].default_value = 0.16
    glare.inputs["Size"].default_value = 0.55
    glare.inputs["Saturation"].default_value = 1.0
    gout = comp_ng.nodes.new("NodeGroupOutput")
    gout.location = (80, 0)
    comp_ng.links.new(rl.outputs["Image"], glare.inputs["Image"])
    comp_ng.links.new(glare.outputs["Image"], gout.inputs[0])
except Exception as _e:
    print("COMPOSITOR_WARN", repr(_e))
    scene.compositing_node_group = None

# Cycles device preferences (headless factory startup needs this)
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "OPTIX"
    prefs.get_devices()
    for dev in prefs.devices:
        dev.use = dev.type == "OPTIX"
    scene.cycles.device = "GPU"
except Exception as e:
    print("GPU_WARN", repr(e))

# ---------------------------------------------------------------------------
# Controller text block and initial look
# ---------------------------------------------------------------------------
if os.path.exists(CONTROLLER_PATH):
    try:
        text = bpy.data.texts.load(CONTROLLER_PATH, internal=False)
        if text.name != "scene_controller.py":
            text.name = "scene_controller.py"
    except Exception:
        with open(CONTROLLER_PATH, "r", encoding="utf-8") as f:
            text = bpy.data.texts.new("scene_controller.py")
            text.write(f.read())
    ctrl = bpy.data.texts.get("scene_controller.py")
    if ctrl is not None:
        ns = {"__name__": "scene_controller_module"}
        exec(compile(ctrl.as_string(), "scene_controller.py", "exec"), ns)
        ns["set_time_of_day"]("dusk")
        ns["set_weather"]("sunny")
        ns["place_maid_on_bed"]()
        scene["controller_ready"] = True
        scene["maid_ready"] = True
else:
    print("CONTROLLER_MISSING", CONTROLLER_PATH)

# metadata
scene["project"] = "Warm Bedroom"
scene["units"] = "meters, 4.6 x 5.0 x 2.8"
scene["artwork_original"] = ARTWORK_PATH
scene["render_engine_notes"] = "Cycles GPU / 256 spp / OptiX denoise / AgX Medium High Contrast"

# ensure selected initial active object is something innocuous
bpy.context.view_layer.objects.active = None

# Save
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH, check_existing=False)
print("SAVED", BLEND_PATH)
print("OBJECTS", len(bpy.data.objects))

# diagnostics for controller-required names
required = ["Sun", "Lamp_Bedside", "Lamp_Floor", "Fill_Soft", "Lightning",
            "Sky_Dome", "Sun_Disc", "Moon", "Rain_Glass_Overlay",
            "Rain_Haze", "Rain_Curtain_1", "Rain_Curtain_2", "Rain_Curtain_3",
            "Curtain_Sheer", "City_Lights", "Frame_Artwork", "Camera"]
missing = [n for n in required if bpy.data.objects.get(n) is None]
print("MISSING_REQUIRED", missing)
print("MATERIALS", len(bpy.data.materials))
