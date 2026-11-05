"""Release template selection, shared UI property, persistence and report-level regression tests."""
import bpy, os, json, addon_utils, shutil, tempfile, hashlib, inspect
from types import SimpleNamespace
T = os.path.dirname(os.path.abspath(__file__))
O = os.path.join(tempfile.gettempdir(), "release template test")
shutil.rmtree(O, ignore_errors=True); os.makedirs(O)
pkg = "bl_ext.user_default.mk8dx_szs_exporter"; addon_utils.enable(pkg, default_set=True)
ops = __import__(pkg + ".operators", fromlist=["x"])
sc = bpy.context.scene.mk8dx; prefs = bpy.context.preferences.addons[pkg].preferences
bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_plane_add(size=20)
def chk(tag, ok):
    print(f"CHECK {tag}: {'PASS' if ok else 'FAIL'}")
    assert ok, tag
def digest(f): return hashlib.sha256(open(f, "rb").read()).hexdigest()
def export(path, **kw):
    return bpy.ops.mk8dx.export_szs(filepath=path, use_selection=False, **kw)
def log(f): return open(os.path.splitext(f)[0] + "_export_log.txt").read()
source = T + "/tmpl.szs"; dst = O + "/course_model.szs"
shutil.copyfile(source, dst); before = digest(dst)
# Neither stale RomFS preferences nor an original backup should override the CURRENT output.
sc.template_file = ""; prefs.romfs_dir = O + "/unrelated RomFS"
shutil.copyfile(source, dst + ".orig"); backup = digest(dst + ".orig")
chk("blank template uses existing destination", export(dst) == {"FINISHED"} and "Template used (destination file): " + dst in log(dst))
chk("destination is read before replacing; original preserved", digest(dst) != before and digest(dst + ".orig") == backup)
chk("re-export prefers current destination over .orig", export(dst) == {"FINISHED"} and "Template used (destination file): " + dst in log(dst) and digest(dst + ".orig") == backup)
os.remove(dst)
chk("missing output falls back to .orig", export(dst) == {"FINISHED"} and "Template used (destination backup): " + dst + ".orig" in log(dst))
# A browser-only overwrite must now create its backup too.
fresh = O + "/fresh.szs"; shutil.copyfile(source, fresh)
chk("browser overwrite creates .orig once", export(fresh) == {"FINISHED"} and digest(fresh + ".orig") == before)
sc.template_file = source
explicit = O + "/explicit.szs"
chk("explicit template still works", export(explicit) == {"FINISHED"} and "Template used (explicit template): " + source in log(explicit))
# The draw function binds to the actual scene property used by the N-panel, not an independent copy.
chk("dialog shares N-panel template property", 'box.prop(sc, "template_file"' in inspect.getsource(ops.MK8DX_OT_export.draw))
stored = json.loads(sc.export_opts); key = next(k for k in stored if "export_szs" in k)
chk("template path saved in scene and preferences", stored[key]["template_file"] == source and json.loads(prefs.export_opts)[key]["template_file"] == source)
f = SimpleNamespace(bl_idname=key)
sc.template_file = ""; ops.load_opts(f, bpy.context, ops.MODEL_OPTS)
chk("clearing the field is not undone by stale settings", sc.template_file == "")
# Simulate a new .blend; unset RNA value allows last-used preferences to seed it.
sc.property_unset("template_file"); sc.export_opts = "{}"
ops.load_opts(f, bpy.context, ops.MODEL_OPTS)
chk("new scene restores template from preferences", sc.template_file == source)
sc.template_file = ""
# Template-folder destination uses the browser directory when no source is explicitly set.
prefs.romfs_dir = ""
chk("blank template works in template-folder destination", export(dst, course_dest="INSTEAD", course_kind="TEMPLATE") == {"FINISHED"})
# Existing RomFS file and .orig-only file are both allowed, but not a missing folder.
root = O + "/romfs"; course = root + "/course/Gu_FirstCircuit"; os.makedirs(course)
ct = course + "/course_model.szs"; shutil.copyfile(source, ct + ".orig")
chk("RomFS .orig fallback does not require live output", export(O + "/ignored.szs", course_dest="INSTEAD", course_kind="ROMFS", course_root=root) == {"FINISHED"} and "destination backup" in log(ct))
# ALSO must use the course target as template, not a possibly unrelated browser copy.
chk("ALSO takes template from course destination", export(O + "/copy.szs", course_dest="ALSO", course_kind="ROMFS", course_root=root) == {"FINISHED"} and "destination file): " + ct in log(O + "/copy.szs"))
reports = []
r = SimpleNamespace(report=lambda level, text: reports.append((level, text)))
ops.report_export_notes(r, [], "INFO: Material Road: adjusted to variation X\nINFO: Adjusted 1 material to fit the course shaders (see log)\nINFO: Adjusted 2 materials to fit the course shaders (see log)")
chk("shader swap produces one INFO and no WARNING", len(reports) == 1 and reports[0][0] == {"INFO"})
ops.report_export_notes(r, ["real gather warning"], "WARNING: Missing texture")
chk("real warnings retain WARNING level", len([x for x in reports if x[0] == {"WARNING"}]) == 2)
missing = O + "/does-not-exist.szs"
try: result = export(missing)
except RuntimeError as e: result = str(e)
chk("missing template gives clear error without output", result != {"FINISHED"} and "neither" in str(result) and not os.path.exists(missing))
sc.template_file = O + "/bad-explicit.szs"
try: result = export(dst)
except RuntimeError as e: result = str(e)
chk("invalid explicit template cannot silently use another file", result != {"FINISHED"} and "Template file not found" in str(result))
print("RESULT: ALL PASS")
