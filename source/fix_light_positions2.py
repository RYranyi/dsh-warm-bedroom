# -*- coding: utf-8 -*-
"""Align light objects to their fixtures, correctly handling parenting.

A first pass set `.location`, which does nothing for parented lights.  These
lights are children of a parent empty/object, so the world position must be
written through `matrix_world`.  This pass also reports the parent chain so the
fix is verifiable.
"""
import bpy, os, sys
from mathutils import Vector, Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

BLEND = paths.blend()
bpy.ops.wm.open_mainfile(filepath=BLEND)


def bb_center(o):
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return Vector([(min(v[i] for v in bb) + max(v[i] for v in bb)) * 0.5 for i in range(3)])


def chain(o):
    names = []
    p = o.parent
    while p is not None:
        names.append(p.name)
        p = p.parent
    return names or ["<root>"]


print("=== PARENTS ===")
for n in ("Lamp_Desk", "Lamp_Bedside", "Lamp_Floor", "TV_Glow", "Art_Light",
          "Lamp_Desk_Bulb", "Lamp_Bedside_Bulb", "Lamp_Floor_Bulb", "TV_Screen", "Frame_Artwork"):
    o = bpy.data.objects.get(n)
    if o:
        print("  %-20s parent_chain=%s local=%s world=%s" % (
            n, chain(o), tuple(round(v, 4) for v in o.location),
            tuple(round(v, 4) for v in o.matrix_world.translation)))

report = []

# --- desk lamp light -> desk bulb centre, keep rotation -----------------------
lo = bpy.data.objects.get("Lamp_Desk")
fixture = bpy.data.objects.get("Lamp_Desk_Bulb")
if lo and fixture:
    before = tuple(round(v, 4) for v in lo.matrix_world.translation)
    target = bb_center(fixture)
    m = lo.matrix_world.copy()
    m.translation = target
    lo.matrix_world = m
    report.append(("Lamp_Desk", before, tuple(round(v, 4) for v in lo.matrix_world.translation)))
    bpy.context.view_layer.update()

# --- TV glow: 5 cm in front of the screen plane, facing into the room ---------
lo = bpy.data.objects.get("TV_Glow")
fixture = bpy.data.objects.get("TV_Screen")
if lo and fixture:
    before = tuple(round(v, 4) for v in lo.matrix_world.translation)
    c = bb_center(fixture)
    m = lo.matrix_world.copy()
    m.translation = Vector((c.x, c.y + 0.05, c.z))
    lo.matrix_world = m
    report.append(("TV_Glow", before, tuple(round(v, 4) for v in lo.matrix_world.translation)))
    bpy.context.view_layer.update()

# --- art light: centred above the frame, just off the wall, aimed at the art --
lo = bpy.data.objects.get("Art_Light")
fixture = bpy.data.objects.get("Frame_Artwork")
if lo and fixture:
    before = tuple(round(v, 4) for v in lo.matrix_world.translation)
    bb = [fixture.matrix_world @ Vector(c) for c in fixture.bound_box]
    top_z = max(v.z for v in bb)
    wall_y = max(v.y for v in bb)
    lo.matrix_world = Matrix.Translation(Vector((0.0, wall_y - 0.10, top_z + 0.09)))
    d = bb_center(fixture) - lo.matrix_world.translation
    lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    report.append(("Art_Light", before, tuple(round(v, 4) for v in lo.matrix_world.translation)))
    bpy.context.view_layer.update()

print("=== CHANGED ===")
for n, a, b in report:
    print("  %-12s %s -> %s" % (n, a, b))

print("=== FINAL DISTANCE (world light -> fixture centre) ===")
for lname, fname in (("Lamp_Bedside", "Lamp_Bedside_Bulb"), ("Lamp_Desk", "Lamp_Desk_Bulb"),
                     ("Lamp_Floor", "Lamp_Floor_Bulb"), ("TV_Glow", "TV_Screen"),
                     ("Art_Light", "Frame_Artwork")):
    a = bpy.data.objects.get(lname)
    b = bpy.data.objects.get(fname)
    if a and b:
        print("  %-14s -> %-20s %.4f m" % (lname, fname, (a.matrix_world.translation - bb_center(b)).length))

bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print("SAVED", BLEND)
