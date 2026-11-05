import bpy, os, sys, math, json
import numpy as np
T = os.path.dirname(os.path.abspath(__file__))
pkg = "bl_ext.user_default.mk8dx_szs_exporter"
import addon_utils
addon_utils.enable(pkg, default_set=True)
prefs = bpy.context.preferences.addons[pkg].preferences
prefs.romfs_dir = T + "/romfs"
prefs.ryujinx_dir = T + "/ryujinx"

bpy.ops.wm.read_homefile(use_empty=True)
sc = bpy.context.scene; sc.mk8dx.template_file = T + "/tmpl.szs"
sc.mk8dx.gu_folder = "Gu_FirstCircuit"; sc.mk8dx.mod_name = "TestTrack"

# --- textures: road (opaque checker 128x128) and fence (with alpha 64x32)
def make_img(name, w, h, alpha):
    img = bpy.data.images.new(name, w, h, alpha=alpha)
    y, x = np.mgrid[0:h, 0:w]
    chk = ((x // 16 + y // 16) % 2).astype(np.float32)
    px = np.zeros((h, w, 4), np.float32)
    px[..., 0] = 0.2 + 0.6 * chk; px[..., 1] = 0.2 + 0.3 * (y / h); px[..., 2] = 0.3; px[..., 3] = 1.0
    if alpha: px[..., 3] = np.where(x % 8 < 4, 1.0, 0.0)
    img.pixels.foreach_set(px.ravel())
    img.pack()
    return img

road_img = make_img("road_asphalt.png", 128, 128, False)
fence_img = make_img("fence", 64, 32, True)

def make_mat(name, img, mapping=False):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; bsdf = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if mapping:
        mp = nt.nodes.new("ShaderNodeMapping"); tc = nt.nodes.new("ShaderNodeTexCoord")
        nt.links.new(tc.outputs["UV"], mp.inputs["Vector"]); nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    return m

road_mat = make_mat("Road", road_img)
fence_mat = make_mat("Fence", fence_img, mapping=True)
r = bpy.ops.mk8dx.load_materials()
print("load_materials:", r, len(json.loads(sc.mk8dx.materials_json)))
road_mat.mk8dx.template = "mt_road_template"

# --- road: bezier curve + plane segment with Array(fit curve) + Curve
bpy.ops.curve.primitive_bezier_circle_add(radius=30, location=(0, 0, 0))
curve = bpy.context.object; curve.name = "RoadPath"
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
seg = bpy.context.object; seg.name = "Road"
seg.scale = (2, 8, 1); bpy.ops.object.transform_apply(scale=True)
seg.data.materials.append(road_mat)
# UV tiling done on real UVs (x4 along length)
uv = seg.data.uv_layers.active.data
for d in uv: d.uv = (d.uv[0], d.uv[1] * 4)
arr = seg.modifiers.new("Array", "ARRAY"); arr.fit_type = "FIT_CURVE"; arr.curve = curve
arr.relative_offset_displace = (1, 0, 0)
cm = seg.modifiers.new("Curve", "CURVE"); cm.object = curve
# --- fence: a cube with the alpha material
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 3))
fence = bpy.context.object; fence.name = "Fence"; fence.data.materials.append(fence_mat)

for o in bpy.data.objects: o.select_set(o.type == "MESH")
bpy.context.view_layer.objects.active = seg
r = bpy.ops.mk8dx.export_szs(course_dest="INSTEAD", course_kind="RYUJINX", use_selection=True, scale=10.0, keep_temp=True)
print("export:", r)
out = T + "/ryujinx/mods/contents/0100152000022000/TestTrack/romfs/course/Gu_FirstCircuit/course_model.szs"
print("exists:", os.path.exists(out), os.path.getsize(out) if os.path.exists(out) else 0)
# Stats for comparison
dg = bpy.context.evaluated_depsgraph_get()
for o in (seg, fence):
    me = o.evaluated_get(dg).to_mesh(); me.calc_loop_triangles(); print("blender tris", o.name, len(me.loop_triangles)); o.evaluated_get(dg).to_mesh_clear()
bpy.ops.wm.save_as_mainfile(filepath=T + "/test_scene.blend")
