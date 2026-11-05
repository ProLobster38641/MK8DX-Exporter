import bpy, os, json, subprocess, addon_utils, shutil, tempfile
TMP = tempfile.gettempdir(); T = os.path.dirname(os.path.abspath(__file__))
O = os.path.join(TMP, "opts test"); shutil.rmtree(O, ignore_errors=True); os.makedirs(O)
CLI = os.path.join(T, "..", "cli", "publish", "linux-x64", "mk8szs")
pkg = "bl_ext.user_default.mk8dx_szs_exporter"; addon_utils.enable(pkg, default_set=True)
ops = __import__(pkg + ".operators", fromlist=["x"]); col = __import__(pkg + ".collision", fromlist=["x"])
p = bpy.context.preferences.addons[pkg].preferences
def chk(t, ok, x=""): print(f"CHECK {t}: {'PASS' if ok else 'FAIL'} {x}")
def info(f): return subprocess.run([CLI, "info", f], capture_output=True, text=True).stdout
def kcl(f): return json.loads(subprocess.run([CLI, "kcl-info", f], capture_output=True, text=True).stdout)
chk("ryujinx blank by default", p.ryujinx_dir == "")
bpy.ops.wm.read_homefile(use_empty=True); sc = bpy.context.scene; sc.mk8dx.template_file = T + "/tmpl.szs"
bpy.ops.mesh.primitive_plane_add(size=20); road = bpy.context.object; road.name = "PlainRoad"
bpy.ops.mesh.primitive_plane_add(size=4, location=(30, 0, 0)); other = bpy.context.object; other.name = "OtherMesh"
chk("unassigned mesh = Visual + collision, Road 0x0000", col.role_of(road) == "BOTH" and road.mk8dx_col.attr == 0 and road.mk8dx_col.role == "BOTH")
# 1. Selected only ON with one selected -> only that one
bpy.ops.object.select_all(action="DESELECT"); road.select_set(True)
r = bpy.ops.mk8dx.export_szs(filepath=O + "/sel.szs", use_selection=True); t = info(O + "/sel.szs")
chk("selected only ON: only selected", r == {"FINISHED"} and "PlainRoad" in t and "OtherMesh" not in t)
# 2. Selected only OFF, nothing selected -> all visible; model + kcl
bpy.ops.object.select_all(action="DESELECT")
r = bpy.ops.mk8dx.export_szs(filepath=O + "/all.szs", use_selection=False, with_kcl=True); t = info(O + "/all.szs")
chk("selected only OFF: all visible (nothing selected)", r == {"FINISHED"} and "PlainRoad" in t and "OtherMesh" in t)
k = kcl(O + "/course_kcl.szs")
chk("unassigned meshes in KCL as COL_0", k["triangles"] == 4 and k["attributes"] == {"COL_0": 4}, str(k["attributes"]))
# 3. Selected only ON but nothing selected -> fallback, no 'Nothing to export'
r = bpy.ops.mk8dx.export_szs(filepath=O + "/fb.szs", use_selection=True)
chk("selected only ON + nothing selected -> falls back, no error", r == {"FINISHED"} and "OtherMesh" in info(O + "/fb.szs"))
# 4. persistence: last execute stored; a fresh invoke-style load restores it
class Fake:  # same attributes the dialog has, fresh defaults
    bl_idname = "MK8DX_OT_export_szs"
    def __init__(s): s.use_selection, s.scale, s.export_uv1, s.with_kcl, s.course_dest, s.course_kind, s.course_root, s.mode, s.neutral_other, s.force_repeat, s.prune, s.keep_anims = True, 1.0, True, False, "NONE", "TEMPLATE", "", "replace", True, True, True, True
bpy.ops.mk8dx.export_szs(filepath=O + "/p.szs", use_selection=False, scale=2.5, export_uv1=False, with_kcl=True)
f = Fake(); f.bl_idname = bpy.types.MK8DX_OT_export.bl_idname if hasattr(bpy.types, "MK8DX_OT_export") else "mk8dx.export_szs"
stored = json.loads(sc.mk8dx.export_opts)
key = next(iter(stored)); f.bl_idname = key
ops.load_opts(f, bpy.context, ops.MODEL_OPTS)
chk("reopened dialog keeps settings (scene)", (f.use_selection, f.scale, f.export_uv1, f.with_kcl) == (False, 2.5, False, True), str(stored))
chk("also stored in add-on prefs (other .blend files)", key in json.loads(p.export_opts))
# new file: scene empty -> prefs used
bpy.ops.wm.read_homefile(use_empty=True); f2 = Fake(); f2.bl_idname = key; ops.load_opts(f2, bpy.context, ops.MODEL_OPTS)
chk("new .blend restores from prefs", (f2.use_selection, f2.scale) == (False, 2.5))
# KCL dialog
sc = bpy.context.scene; bpy.ops.mesh.primitive_plane_add(size=4)
bpy.ops.mk8dx.export_kcl(filepath=O + "/k.szs", use_selection=True, scale=3.0)
d = json.loads(sc.mk8dx.export_opts); kk = [x for x in d if "kcl" in x.lower()]
chk("KCL options stored", kk and d[kk[0]]["use_selection"] is True and d[kk[0]]["scale"] == 3.0, str(d))
# real invoke path persists across reopen (simulate: call invoke via operator with EXEC? use the class directly)
