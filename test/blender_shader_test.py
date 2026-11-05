"""Optional integration test with private, legally dumped course fixtures (never bundled).
Set MK8DX_TEST_COURSE, MK8DX_TEST_FOREIGN_BFMAT and MK8DX_TEST_MATERIAL to run.
"""
import bpy, os, json, addon_utils, shutil, tempfile, subprocess
T = os.path.dirname(os.path.abspath(__file__))
CLI = os.path.join(T, "..", "cli", "publish", "linux-x64", "mk8szs")
course = os.environ["MK8DX_TEST_COURSE"]
foreign = os.environ["MK8DX_TEST_FOREIGN_BFMAT"]
same_name = os.environ["MK8DX_TEST_MATERIAL"]
O = os.path.join(tempfile.gettempdir(), "shader info test")
shutil.rmtree(O, ignore_errors=True); os.makedirs(O)
pkg = "bl_ext.user_default.mk8dx_szs_exporter"; addon_utils.enable(pkg, default_set=True)
ops = __import__(pkg + ".operators", fromlist=["x"])
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.mesh.primitive_plane_add(size=20)
m = bpy.data.materials.new("Road"); bpy.context.object.data.materials.append(m)
img = bpy.data.images.new("TestAlbedo", 8, 8)
img.pixels[:] = [0.5, 0.5, 0.5, 1.0] * 64
node = m.node_tree.nodes.new("ShaderNodeTexImage"); node.image = img
m.node_tree.links.new(node.outputs["Color"], m.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
sc = bpy.context.scene.mk8dx; sc.template_file = course
seen = []
original = ops.report_export_notes
def capture(op, warns, text):
    seen.append((list(warns), text)); return original(op, warns, text)
ops.report_export_notes = capture
def chk(tag, ok):
    print(f"CHECK {tag}: {'PASS' if ok else 'FAIL'}"); assert ok, tag
def run(name):
    return bpy.ops.mk8dx.export_szs(filepath=O + "/" + name, use_selection=False)
m.mk8dx.bfmat_path = foreign
chk("foreign material exports", run("foreign.szs") == {"FINISHED"})
warns, text = seen[-1]
chk("shader adaptation is INFO, never WARNING", "INFO: Adjusted 1 material" in text and "WARNING" not in text and not warns and "0 warning(s)" in text)
# A material extracted from the actual base is preserved without a swap message.
same = O + "/same.bfmat"
subprocess.run([CLI, "extract-bfmat", course, same_name, same], check=True)
m.mk8dx.bfmat_path = same
chk("same-course bfmat exports", run("same.szs") == {"FINISHED"})
warns, text = seen[-1]
chk("same-course material gets no swap message", "INFO: Adjusted" not in text and "adjusted to" not in text and "WARNING" not in text)
# The same holds for an explicit material name from the base .szs, not just a linked .bfmat.
m.mk8dx.bfmat_path = ""
bpy.ops.mk8dx.load_materials()
m.mk8dx.template = same_name
chk("same-course szs material exports without adjustment", run("named.szs") == {"FINISHED"} and "INFO: Adjusted" not in seen[-1][1])
# A re-exported course contains only its used materials, while the identical archive supports more.
dst = O + "/course_model.szs"
shutil.copyfile(O + "/foreign.szs", dst); shutil.copyfile(course, dst + ".orig")
sc.template_file = ""; m.mk8dx.bfmat_path = same
chk("blank destination uses identical-archive backup variants", run("course_model.szs") == {"FINISHED"} and "INFO: Adjusted" not in seen[-1][1])
chk("backup is unchanged", open(dst + ".orig", "rb").read() == open(course, "rb").read())
print("RESULT: ALL PASS")
