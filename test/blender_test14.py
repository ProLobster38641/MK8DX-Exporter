"""Missing-texture imports retain available images, names and material identity."""
import bpy, os, json, tempfile, shutil, subprocess, addon_utils, struct
from types import SimpleNamespace
T = os.path.dirname(os.path.abspath(__file__))
CLI = os.path.join(T, "..", "cli", "publish", "linux-x64", "mk8szs")
O = tempfile.mkdtemp(prefix="mk8dx_missing_test_")
pkg = "bl_ext.user_default.mk8dx_szs_exporter"
addon_utils.enable(pkg, default_set=True)
imp = __import__(pkg + ".importer", fromlist=["x"])
gather = __import__(pkg + ".gather", fromlist=["x"])
def chk(text, ok):
    print(f"CHECK {text}: {'PASS' if ok else 'FAIL'}"); assert ok, text
def command(*args):
    return subprocess.run([CLI, *args], check=True, capture_output=True, text=True).stdout
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.wm.save_as_mainfile(filepath=O + "/scene.blend")
bpy.context.scene.mk8dx.template_file = ""
command("extract-bfmat", T + "/tmpl.szs", "mt_road_template", O + "/Road.bfmat")
reports = []
op = SimpleNamespace(pack=True, tex_folder="", tex_source="", tex_subfolders=False,
                     report=lambda levels, text: reports.append((levels, text)))
chk("bfmat with no textures succeeds", imp.run_import(op, bpy.context, bfmats=[O + "/Road.bfmat"]) == {"FINISHED"})
m = bpy.data.materials["Road (missing textures)"]
chk("warning lists missing names", any("orig_road_alb" in text and "orig_bake" in text for _, text in reports))
chk("missing slots are empty", all(n.image is None for n in m.node_tree.nodes if n.type == "TEX_IMAGE"))
bpy.ops.mesh.primitive_plane_add(); obj = bpy.context.object; obj.data.materials.append(m)
identity = m.as_pointer()
# Supply only the albedo: missing auxiliary textures must still be reported.
os.makedirs(O + "/partial")
i = bpy.data.images.new("partial", 8, 8); i.pixels[:] = [0.2, 0.4, 0.6, 1] * 64
i.filepath_raw = O + "/partial/orig_road_alb.png"; i.file_format = "PNG"; i.save()
op.tex_folder = O + "/partial"; reports.clear()
chk("partial source succeeds", imp.run_import(op, bpy.context, bfmats=[O + "/Road.bfmat"]) == {"FINISHED"})
chk("available albedo kept", m.mk8dx.bfmat_albedo is not None and gather.find_albedo_image(m)[0] == m.mk8dx.bfmat_albedo)
chk("only missing auxiliary listed", json.loads(m["mk8dx_missing_textures"]) == ["orig_bake"])
# Full source restores the same datablock and assignments; missing it again marks it once.
op.tex_source = T + "/tmpl.szs"
chk("recovery import succeeds", imp.run_import(op, bpy.context, bfmats=[O + "/Road.bfmat"]) == {"FINISHED"})
chk("recovery removes suffix without duplicates", m.name == "Road" and m.as_pointer() == identity and obj.data.materials[0] == m)
op.tex_folder = ""; op.tex_source = ""
imp.run_import(op, bpy.context, bfmats=[O + "/Road.bfmat"])
imp.run_import(op, bpy.context, bfmats=[O + "/Road.bfmat"])
chk("repeated missing import marks once", m.name == "Road (missing textures)" and len([x for x in bpy.data.materials if x.get("mk8dx_import_name") == "Road"]) == 1)
# A damaged decoded image cannot abort other slots/materials.
entry = {"name": "Damaged", "bfmat": O + "/Road.bfmat", "textures": [
 {"sampler": "_a0", "texture": "lost_albedo", "albedo": True, "found": True, "file": O + "/gone.rgba"},
 {"sampler": "_n0", "texture": "normal", "found": True, "file": O + "/normal.rgba"}]}
with open(O + "/normal.rgba", "wb") as f: f.write(b"RGBA" + struct.pack("<ii", 8, 8) + bytes([128,128,255,255]) * 64)
warnings = []; damaged = imp.build_material(entry, O, True, warnings)
chk("missing decoded file imports other slots", damaged.name.endswith(" (missing textures)") and any(n.image and n.image.name == "normal" for n in damaged.node_tree.nodes if n.type == "TEX_IMAGE"))
chk("normal cannot become missing albedo on export", gather.find_albedo_image(damaged)[0] is None)
# A .szs with one absent map must import every material, not cancel the batch.
manifest = {"base": T + "/tmpl.szs", "neutral_other_samplers": False,
            "materials": [{"name": "CoursePartial", "template": "mt_road_template", "textures": {"_b0": "missing_course_bake"}},
                          {"name": "CourseComplete", "template": "mt_road_template"}]}
with open(O + "/export.json", "w") as f: json.dump(manifest, f)
command("export", O + "/export.json", O + "/missing.szs")
reports.clear()
chk("szs missing map imports full batch", imp.run_import(op, bpy.context, szs=O + "/missing.szs") == {"FINISHED"})
partial = bpy.data.materials["CoursePartial (missing textures)"]
chk("szs available albedo retained", partial.mk8dx.bfmat_albedo is not None)
chk("szs complete material unmarked", "CourseComplete" in bpy.data.materials)
chk("szs warning names absent texture", any("missing_course_bake" in text for _, text in reports))
print("RESULT: ALL PASS")
