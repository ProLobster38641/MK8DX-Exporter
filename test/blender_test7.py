import bpy, os, addon_utils, shutil
import tempfile; TMP = tempfile.gettempdir()
T = os.path.dirname(os.path.abspath(__file__)); B = TMP + "/romfs dest"; shutil.rmtree(B, ignore_errors=True)
G = B + "/Game Dump/romfs/course/Gu_Expert"; os.makedirs(G)
shutil.copy(T + "/tmpl.szs", G + "/course_model.szs"); open(G + "/course_kcl.szs", "wb").write(b"ORIGKCL")
orig = os.path.getsize(G + "/course_model.szs")
pkg = "bl_ext.user_default.mk8dx_szs_exporter"; addon_utils.enable(pkg, default_set=True)
p = bpy.context.preferences.addons[pkg].preferences; p.ryujinx_dir = ""; p.romfs_dir = ""
bpy.ops.wm.read_homefile(use_empty=True); sc = bpy.context.scene
sc.mk8dx.template_file = T + "/tmpl.szs"; sc.mk8dx.gu_folder = "Gu_Expert"
bpy.ops.mesh.primitive_plane_add(size=10); o = bpy.context.object
o.mk8dx_col.role = "BOTH"; o.mk8dx_col.attr = 0
def chk(t, ok, x=""): print(f"CHECK {t}: {'PASS' if ok else 'FAIL'} {x}")
def run(op, **kw):
    try: return op(**kw)
    except RuntimeError as e: return str(e)[:160]
def tree(): return sorted(os.path.join(d, x) for d, ds, fs in os.walk(B) for x in ds + fs)
# romfs folder itself
r = run(bpy.ops.mk8dx.export_szs, filepath="", course_dest="INSTEAD", course_kind="ROMFS", course_root=B + "/Game Dump/romfs")
chk("romfs folder: replaced in place", r == {"FINISHED"} and os.path.getsize(G + "/course_model.szs") != orig and os.path.getsize(G + "/course_model.szs.orig") == orig)
# parent of romfs
r = run(bpy.ops.mk8dx.export_kcl, filepath="", course_dest="INSTEAD", course_kind="ROMFS", course_root=B + "/Game Dump")
chk("parent folder detected (kcl)", r == {"FINISHED"} and open(G + "/course_kcl.szs.orig", "rb").read() == b"ORIGKCL" and os.path.getsize(G + "/course_kcl.szs") > 100)
chk("no romfs/course created elsewhere", not os.path.exists(B + "/Game Dump/course") and not os.path.exists(B + "/Game Dump/romfs/romfs"))
# prefs RomFS fallback
p.romfs_dir = B + "/Game Dump"
r = run(bpy.ops.mk8dx.export_szs, filepath="", course_dest="INSTEAD", course_kind="ROMFS")
chk("prefs RomFS used", r == {"FINISHED"})
# missing course folder -> error, nothing created
before = tree(); sc.mk8dx.gu_folder = "Gu_Missing"; sc.mk8dx.template_file = T + "/tmpl.szs"
r = run(bpy.ops.mk8dx.export_szs, filepath=B + "/out.szs", course_dest="ALSO", course_kind="ROMFS", course_root=B + "/Game Dump/romfs")
chk("missing Gu folder -> error naming path", r != {"FINISHED"} and "Gu_Missing" in str(r), str(r))
r = run(bpy.ops.mk8dx.export_kcl, filepath="", course_dest="INSTEAD", course_kind="ROMFS", course_root=B + "/Nowhere")
chk("missing romfs -> error", r != {"FINISHED"} and "Nowhere" in str(r), str(r))
chk("no dirs/files created", tree() == before)
# template folder: write only into existing folder
sc.mk8dx.template_file = G + "/course_model.szs"
r = run(bpy.ops.mk8dx.export_kcl, filepath="", course_dest="INSTEAD", course_kind="TEMPLATE")
chk("template folder replace", r == {"FINISHED"})
# Ryujinx still creates mod folders
p.ryujinx_dir = B + "/Ryujinx"; sc.mk8dx.mod_name = "Mod"
r = run(bpy.ops.mk8dx.export_kcl, filepath="", course_dest="INSTEAD", course_kind="RYUJINX")
chk("ryujinx creates mod folders", r == {"FINISHED"} and os.path.isfile(B + "/Ryujinx/mods/contents/0100152000022000/Mod/romfs/course/Gu_Expert/course_kcl.szs"))
