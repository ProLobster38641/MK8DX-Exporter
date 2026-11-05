import bpy, os, json, addon_utils, numpy as np, shutil
import tempfile; TMP = tempfile.gettempdir()
T = os.path.dirname(os.path.abspath(__file__)); O = TMP + "/anywhere"
shutil.rmtree(O, ignore_errors=True)
pkg = "bl_ext.user_default.mk8dx_szs_exporter"
addon_utils.enable(pkg, default_set=True)
p = bpy.context.preferences.addons[pkg].preferences
p.romfs_dir = ""; p.ryujinx_dir = ""          # nothing configured
bpy.ops.wm.read_homefile(use_empty=True)
sc = bpy.context.scene
img = bpy.data.images.new("road", 128, 128); px = np.ones((128,128,4), np.float32)*0.5; img.pixels.foreach_set(px.ravel())
m = bpy.data.materials.new("Road"); t = m.node_tree.nodes.new("ShaderNodeTexImage"); t.image = img
m.node_tree.links.new(t.outputs[0], m.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
bpy.ops.mesh.primitive_plane_add(size=10); o = bpy.context.object; o.data.materials.append(m); o.select_set(True)
def res(tag, r, path=None):
    print(f"RESULT {tag}: {r}" + (f" exists={os.path.exists(path)}" if path else ""))
def run(tag, path=None, **kw):
    try:
        r = bpy.ops.mk8dx.export_szs(**kw)
    except Exception as e:
        r = f"EXC {e}"
    res(tag, r, path)

res("load_materials nothing set", bpy.ops.mk8dx.load_materials())
run("B no template (expect CANCELLED)", filepath=O + "/a.szs")
run("B2 no template + placeholder", O + "/placeholder.szs", filepath=O + "/placeholder.szs", allow_synthetic=True)
sc.mk8dx.template_file = T + "/tmpl.szs"
res("load_materials picked file", bpy.ops.mk8dx.load_materials())
m.mk8dx.template = "mt_grass_template"
run("A any name/folder, picked .szs", O + "/sub dir/My Track v2.szs", filepath=O + "/sub dir/My Track v2.szs")
run("A2 no extension", O + "/noext.szs", filepath=O + "/noext")
sc.mk8dx.template_file = T + "/grass.bfmat"
res("load_materials bfmat", bpy.ops.mk8dx.load_materials())
run("C picked .bfmat", O + "/frombfmat.szs", filepath=O + "/frombfmat.szs")
sc.mk8dx.template_file = ""
p.romfs_dir = T + "/romfs"; sc.mk8dx.gu_folder = "Gu_FirstCircuit"
run("D ALSO ryujinx unset (expect cancellation)", O + "/d.szs", filepath=O + "/d.szs", course_dest="ALSO", course_kind="RYUJINX")
p.ryujinx_dir = O + "/Ryujinx"; sc.mk8dx.mod_name = "MyMod"
R = O + "/Ryujinx/mods/contents/0100152000022000/MyMod/romfs/course/Gu_FirstCircuit/course_model.szs"
# First export into a new mod needs an explicit source; a blank template now means the destination.
sc.mk8dx.template_file = T + "/tmpl.szs"
run("D2 ALSO ryujinx with explicit template", R, filepath=O + "/d2.szs", course_dest="ALSO", course_kind="RYUJINX")
print("D2 browser file too:", os.path.exists(O + "/d2.szs"))
run("D3 INSTEAD romfs root missing (expect CANCELLED, no dirs)", O + "/modroot", filepath=O + "/ignored.szs", course_dest="INSTEAD", course_kind="ROMFS", course_root=O + "/modroot")
print("D3 ignored file absent:", not os.path.exists(O + "/ignored.szs"))
run("D4 INSTEAD romfs w/o root (now falls back to prefs RomFS)", O + "/romfs_fallback_check", filepath=O + "/x.szs", course_dest="INSTEAD", course_kind="ROMFS")
