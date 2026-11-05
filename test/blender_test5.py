import bpy, os, addon_utils, numpy as np, shutil, stat
import tempfile; TMP = tempfile.gettempdir()
T = os.path.dirname(os.path.abspath(__file__)); O = TMP + "/win style/Game Dump"
shutil.rmtree(TMP + "/win style", ignore_errors=True)
G = O + "/romfs/course/Gu_Expert"; os.makedirs(G); shutil.copy(T + "/tmpl.szs", G + "/course_model.szs")
orig_size = os.path.getsize(G + "/course_model.szs")
pkg = "bl_ext.user_default.mk8dx_szs_exporter"; addon_utils.enable(pkg, default_set=True)
p = bpy.context.preferences.addons[pkg].preferences
os.environ["FAKEAPPDATA"] = TMP + "/win style/AppData Roaming"
p.romfs_dir = ""; p.ryujinx_dir = "$FAKEAPPDATA/Ryujinx"   # env-var path like %APPDATA%
bpy.ops.wm.read_homefile(use_empty=True); sc = bpy.context.scene
img = bpy.data.images.new("road", 64, 64); img.pixels.foreach_set((np.ones((64,64,4), np.float32)*0.5).ravel())
m = bpy.data.materials.new("Road"); t = m.node_tree.nodes.new("ShaderNodeTexImage"); t.image = img
m.node_tree.links.new(t.outputs[0], m.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
bpy.ops.mesh.primitive_plane_add(size=10); o = bpy.context.object; o.data.materials.append(m)
sc.mk8dx.template_file = G + "/course_model.szs"; sc.mk8dx.gu_folder = "Gu_FirstCircuit"; sc.mk8dx.mod_name = "My Mod"
def chk(tag, ok): print(f"CHECK {tag}: {'PASS' if ok else 'FAIL'}")
r = bpy.ops.mk8dx.export_szs(filepath=O + "/out copy.szs", course_dest="ALSO", course_kind="TEMPLATE")
s = os.path.getsize(G + "/course_model.szs")
chk("replace in template folder", r == {"FINISHED"} and s != orig_size and s == os.path.getsize(O + "/out copy.szs"))
chk("original backed up", os.path.getsize(G + "/course_model.szs.orig") == orig_size)
r = bpy.ops.mk8dx.export_szs(filepath=O + "/x.szs", course_dest="INSTEAD", course_kind="TEMPLATE")
chk("re-export uses .orig, backup untouched", r == {"FINISHED"} and os.path.getsize(G + "/course_model.szs.orig") == orig_size)
R = TMP + "/win style/AppData Roaming/Ryujinx/mods/contents/0100152000022000/My Mod/romfs/course/Gu_Expert/course_model.szs"
r = bpy.ops.mk8dx.export_szs(filepath=O + "/y.szs", course_dest="INSTEAD", course_kind="RYUJINX")
chk("ryujinx $VAR expanded, course taken from template path (Gu_Expert not Gu_FirstCircuit)", r == {"FINISHED"} and os.path.isfile(R))
os.chmod(os.path.dirname(R), stat.S_IREAD | stat.S_IEXEC)
try:
    r = bpy.ops.mk8dx.export_szs(filepath=O + "/z.szs", course_dest="ALSO", course_kind="RYUJINX")
except RuntimeError as e:
    r = "ERR " + str(e)[:200]
print("locked result:", r)
chk("locked target -> error, not success", r != {"FINISHED"})
os.chmod(os.path.dirname(R), 0o755)
sc.mk8dx.mod_name = ""
try: r = bpy.ops.mk8dx.export_szs(filepath=O + "/w.szs", course_dest="ALSO", course_kind="RYUJINX")
except RuntimeError as e: r = "ERR"
chk("incomplete ALSO -> error", r != {"FINISHED"} and not os.path.exists(O + "/w.szs"))
