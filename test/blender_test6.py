import bpy, os, json, subprocess, addon_utils, numpy as np, shutil, bmesh
import tempfile; TMP = tempfile.gettempdir()
T = os.path.dirname(os.path.abspath(__file__)); O = TMP + "/kcl test"; shutil.rmtree(O, ignore_errors=True); os.makedirs(O)
CLI = os.path.join(T, "..", "cli", "publish", "linux-x64", "mk8szs")
pkg = "bl_ext.user_default.mk8dx_szs_exporter"; addon_utils.enable(pkg, default_set=True)
p = bpy.context.preferences.addons[pkg].preferences
def chk(tag, ok, extra=""): print(f"CHECK {tag}: {'PASS' if ok else 'FAIL'} {extra}")
chk("prefs ryujinx default blank", p.ryujinx_dir == "" and p.romfs_dir == "", repr(p.ryujinx_dir))
p.ryujinx_dir = ""; p.romfs_dir = ""
from bl_ui.space_toolsystem_common import ToolSelectPanelHelper
cls = ToolSelectPanelHelper._tool_class_from_space_type("VIEW_3D")
ids = [getattr(t, "idname", None) for mode in ("OBJECT", "EDIT_MESH") for t in ToolSelectPanelHelper._tools_flatten(cls.tools_from_context(bpy.context, mode)) if t]
chk("toolbar tools registered", "mk8dx.collision_tool_object" in ids and "mk8dx.collision_tool_edit" in ids)
bpy.ops.wm.read_homefile(use_empty=True); sc = bpy.context.scene
sc.mk8dx.template_file = T + "/tmpl.szs"
m = bpy.data.materials.new("Road")
# visual road (10x10 grid), collision-only road copy with per-face types, a wall, visual+collision ramp, and a 'Collision' collection object
bpy.ops.mesh.primitive_grid_add(x_subdivisions=4, y_subdivisions=4, size=20); vis = bpy.context.object; vis.name = "VisualRoad"; vis.data.materials.append(m)
bpy.ops.mesh.primitive_grid_add(x_subdivisions=4, y_subdivisions=4, size=20); col = bpy.context.object; col.name = "ColRoad"   # 4x4 = 16 quads
bpy.ops.mesh.primitive_plane_add(size=4, location=(0, 10, 2), rotation=(1.5708, 0, 0)); wall = bpy.context.object; wall.name = "Wall"
bpy.ops.mesh.primitive_plane_add(size=4, location=(15, 0, 1)); ramp = bpy.context.object; ramp.name = "Ramp"; ramp.data.materials.append(m)
cc = bpy.data.collections.new("Collision"); sc.collection.children.link(cc)
bpy.ops.mesh.primitive_plane_add(size=50, location=(0, 0, -20)); fall = bpy.context.object; fall.name = "FallPlane"
for c in list(fall.users_collection): c.objects.unlink(fall)
cc.objects.link(fall)
fall.mk8dx_col.attr = 0x3C
ts = sc.mk8dx_coltool
def select(*objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
# object mode: whole ColRoad = Road asphalt, collision only
select(col); ts.preset = "ROAD"; ts.role = "COLLISION"; chk("apply obj", bpy.ops.mk8dx.col_apply() == {"FINISHED"})
# edit mode: 2 faces boost, 1 face custom 8086
bpy.ops.object.mode_set(mode="EDIT"); bm = bmesh.from_edit_mesh(col.data); bm.faces.ensure_lookup_table()
for f in bm.faces: f.select = f.index in (0, 1)
bmesh.update_edit_mesh(col.data); ts.preset = "BOOST"; bpy.ops.mk8dx.col_apply()
bm = bmesh.from_edit_mesh(col.data); bm.faces.ensure_lookup_table()
for f in bm.faces: f.select = f.index == 4
bmesh.update_edit_mesh(col.data); ts.preset = "CUSTOM"; ts.use_custom = True; ts.custom_hex = "8086"; bpy.ops.mk8dx.col_apply()
bpy.ops.object.mode_set(mode="OBJECT"); ts.use_custom = False
fa = [d.value for d in col.data.attributes["mk8dx_col"].data]
chk("per-face values stored", fa[0] == 0xA and fa[1] == 0xA and fa[4] == 0x8086 and fa.count(-1) == 13, str(fa))
select(wall); ts.preset = "WALL"; ts.role = "COLLISION"; bpy.ops.mk8dx.col_apply()
select(ramp); ts.preset = "RAMP"; ts.role = "BOTH"; bpy.ops.mk8dx.col_apply()
rf = __import__(pkg + ".collision", fromlist=["x"]).role_of
chk("roles (unassigned VisualRoad = BOTH)", (rf(col), rf(wall), rf(ramp), rf(vis), rf(fall)) == ("COLLISION", "COLLISION", "BOTH", "BOTH", "COLLISION"))
chk("display colour attr", "MK8DX_Collision" in col.data.color_attributes and tuple(col.color)[:3] != (1, 1, 1))
# KCL export (file browser path with spaces)
r = bpy.ops.mk8dx.export_kcl(filepath=O + "/my col/course_kcl.szs")
K = O + "/my col/course_kcl.szs"
chk("kcl export", r == {"FINISHED"} and os.path.isfile(K))
info = json.loads(subprocess.run([CLI, "kcl-info", K, "--hit-test"], capture_output=True, text=True).stdout)
print(json.dumps(info))
want = {"COL_0": 58, "COL_A": 4, "COL_8086": 2, "COL_11": 2, "COL_1000": 2, "COL_3C": 2}
chk("triangle count", info["triangles"] == 70, str(info["triangles"]))
chk("attributes match", info["attributes"] == want, str(info["attributes"]))
chk("switch format", info["yaz0"] and info["version"] == "Version2" and info["byte_order"] == "LittleEndian")
h = info["octree_hit_test"].split("/"); chk("octree hit test", h[0] == h[1], info["octree_hit_test"])
# geometry roundtrip: wall triangle positions (Blender z=2..? -> MK8 y)
subprocess.run([CLI, "kcl-dump", K, O + "/p.bin", O + "/a.bin"], check=True)
P = np.fromfile(O + "/p.bin", np.float32).reshape(-1, 3, 3); A = np.fromfile(O + "/a.bin", np.uint16)
w = P[A == 0x11].reshape(-1, 3)
chk("wall geometry (Y-up, Blender y=10 -> MK8 z=-10, height 0..4)", np.allclose(w[:, 2], -10, atol=1e-3) and np.isclose(w[:, 1].min(), 0, atol=1e-3) and np.isclose(w[:, 1].max(), 4, atol=1e-3), str(w[:3]))
fl = P[A == 0x3C].reshape(-1, 3); chk("fall plane at y=-20", np.allclose(fl[:, 1], -20, atol=1e-3))
# normals of road point up (+Y)
road = P[A == 0]; n = np.cross(road[:, 1] - road[:, 0], road[:, 2] - road[:, 0]); chk("road normals up", (n[:, 1] > 0).all())
# model export excludes collision-only objects
bpy.ops.object.select_all(action="SELECT")
r = bpy.ops.mk8dx.export_szs(filepath=O + "/course_model.szs", keep_temp=True, with_kcl=True)
chk("model + kcl export", r == {"FINISHED"} and os.path.isfile(O + "/course_kcl.szs"))
mi = json.loads(subprocess.run([CLI, "info", O + "/course_model.szs"], capture_output=True, text=True).stdout)
txt = json.dumps(mi)
chk("model has VisualRoad + Ramp only", "VisualRoad" in txt and "Ramp" in txt and "ColRoad" not in txt and "Wall" not in txt and "FallPlane" not in txt)
chk("collision colour attr not in model", "color0" not in txt and "_c0" not in txt)
# collision-only selection -> model export errors clearly, nothing written
select(col, wall)
try: r = bpy.ops.mk8dx.export_szs(filepath=O + "/none.szs")
except RuntimeError as e: r = str(e)[:120]
t2 = subprocess.run([CLI, "info", O + "/none.szs"], capture_output=True, text=True).stdout if os.path.exists(O + "/none.szs") else ""
chk("collision-only selection falls back to visible objects", r == {"FINISHED"} and "VisualRoad" in t2 and "ColRoad" not in t2, str(r))
# KCL replace in template course folder with backup
G = O + "/dump dir/romfs/course/Gu_Expert"; os.makedirs(G); shutil.copy(T + "/tmpl.szs", G + "/course_model.szs")
open(G + "/course_kcl.szs", "wb").write(b"ORIGINAL")
sc.mk8dx.template_file = G + "/course_model.szs"
r = bpy.ops.mk8dx.export_kcl(filepath="", course_dest="INSTEAD", course_kind="TEMPLATE")
chk("kcl replace + .orig backup", r == {"FINISHED"} and open(G + "/course_kcl.szs.orig", "rb").read() == b"ORIGINAL" and os.path.getsize(G + "/course_kcl.szs") > 100)
# blank ryujinx with Ryujinx destination -> clear error, no crash
try: r = bpy.ops.mk8dx.export_kcl(filepath=O + "/x.szs", course_dest="ALSO", course_kind="RYUJINX")
except RuntimeError as e: r = "ERR"
chk("blank ryujinx dest -> error only when chosen", r != {"FINISHED"} and not os.path.exists(O + "/x.szs"))
