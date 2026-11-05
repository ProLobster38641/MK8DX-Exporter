import bpy, os, json, subprocess, addon_utils, numpy as np, shutil, tempfile
TMP = tempfile.gettempdir(); T = os.path.dirname(os.path.abspath(__file__))
O = os.path.join(TMP, "texfolder test"); shutil.rmtree(O, ignore_errors=True); os.makedirs(O)
CLI = os.path.join(T, "..", "cli", "publish", "linux-x64", "mk8szs")
pkg = "bl_ext.user_default.mk8dx_szs_exporter"; addon_utils.enable(pkg, default_set=True)
g = __import__(pkg + ".gather", fromlist=["x"])
def chk(t, ok, x=""): print(f"CHECK {t}: {'PASS' if ok else 'FAIL'} {x}")
def cli(*a): return subprocess.run([CLI, *a], capture_output=True, text=True).stdout
def run(op, **kw):
    try: return op(**kw)
    except RuntimeError as e: return "ERR " + str(e)[:200]
def rgba(path):
    b = open(path, "rb").read(); w, h = np.frombuffer(b[4:12], np.int32); return np.frombuffer(b[12:], np.uint8).reshape(h, w, 4)
# source course with material Brick -> textures brick (32x32) + mk8exp_white
bpy.ops.wm.read_homefile(use_empty=True); bpy.context.scene.mk8dx.template_file = T + "/tmpl.szs"
img = bpy.data.images.new("brick", 32, 32); y, x = np.mgrid[0:32, 0:32]
px = np.zeros((32, 32, 4), np.float32); px[..., 0] = x / 31; px[..., 1] = y / 31; px[..., 2] = .3; px[..., 3] = 1; img.pixels.foreach_set(px.ravel())
m = bpy.data.materials.new("Brick"); n = m.node_tree.nodes.new("ShaderNodeTexImage"); n.image = img
m.node_tree.links.new(n.outputs[0], m.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
bpy.ops.mesh.primitive_plane_add(size=4); bpy.context.object.data.materials.append(m)
SRC = O + "/src/course_model.szs"; bpy.ops.mk8dx.export_szs(filepath=SRC)
cli("extract-bfmat", SRC, "Brick", O + "/Brick.bfmat")
def folder(name, files):
    d = os.path.join(O, name); os.makedirs(d, exist_ok=True)
    for rel, kind in files.items():
        p = os.path.join(d, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
        if kind == "bftex": cli("export-bftex", SRC, os.path.splitext(os.path.basename(rel))[0].lower(), p)
        else:
            im = bpy.data.images.new("tmp_" + rel, 16, 16); im.pixels.foreach_set(np.tile(np.array(kind, np.float32), 256)); im.filepath_raw = p; im.file_format = "PNG"; im.save(); bpy.data.images.remove(im)
    return d
def fresh(name):
    bpy.ops.wm.read_homefile(use_empty=True); sc = bpy.context.scene; sc.mk8dx.template_file = T + "/tmpl.szs"
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(O, name + ".blend"))
def imp(**kw): return run(bpy.ops.mk8dx.import_bfmat, filepath=O + "/Brick.bfmat", files=[{"name": "Brick.bfmat"}], directory=O, **kw)
def tinfo(mat): return {t["texture"]: t for t in json.loads(mat.mk8dx.bfmat_info)["textures"]}
def export(tag):
    mat = bpy.data.materials["Brick"]
    bpy.ops.mesh.primitive_plane_add(size=4); bpy.context.object.data.materials.append(mat)
    out = os.path.join(O, tag, "course_model.szs"); r = run(bpy.ops.mk8dx.export_szs, filepath=out); return r, out
# A: .bftex folder
fresh("a"); d = folder("bftex", {"brick.bftex": "bftex"})
r = imp(tex_folder=d); mat = bpy.data.materials.get("Brick"); im, _ = g.find_albedo_image(mat)
chk("A bftex folder import", r == {"FINISHED"} and im is not None and tuple(im.size) == (32, 32), str(r))
r, out = export("A"); cli("decode-texture", SRC, "brick", O + "/a0.rgba"); cli("decode-texture", out, "brick", O + "/a1.rgba")
chk("A export embeds bftex unchanged", r == {"FINISHED"} and os.path.isfile(O + "/a1.rgba") and open(O + "/a0.rgba", "rb").read() == open(O + "/a1.rgba", "rb").read())
chk("A log says kept original", "kept original" in open(os.path.join(O, "A", "course_model_export_log.txt")).read())
# B: PNG folder, different case, folder typed into the FILE field
fresh("b"); d = folder("png", {"BRICK.png": (1, 0, 0, 1)})
r = imp(tex_source=d); mat = bpy.data.materials["Brick"]; im, _ = g.find_albedo_image(mat)
p2 = np.empty(16 * 16 * 4, np.float32); im.pixels.foreach_get(p2) if im else None
chk("B png folder (case-insensitive, folder in file field)", r == {"FINISHED"} and im and tuple(im.size) == (16, 16) and p2[0] > .9 and p2[1] < .1)
r, out = export("B"); cli("decode-texture", out, "brick", O + "/b1.rgba")
chk("B export re-encodes png", r == {"FINISHED"} and rgba(O + "/b1.rgba")[..., 0].min() > 240 and rgba(O + "/b1.rgba")[..., 1].max() < 15)
# C: mixed, subfolders: brick.bftex top + sub/mk8exp_white.png
fresh("c"); d = folder("mixed", {"brick.bftex": "bftex", "sub/mk8exp_white.png": (1, 1, 1, 1)})
r = imp(tex_folder=d, tex_subfolders=True); ti = tinfo(bpy.data.materials["Brick"])
chk("C mixed + subfolders both found", r == {"FINISHED"} and ti["brick"]["found"] and ti["mk8exp_white"]["found"], str({k: v["note"] for k, v in ti.items()}))
r = imp(tex_folder=d, tex_subfolders=False); ti = tinfo(bpy.data.materials["Brick"])
chk("C without subfolders: sub not searched", ti["brick"]["found"] and not ti["mk8exp_white"]["found"] and "looked in" in (ti["mk8exp_white"]["note"] or ""))
# D: duplicate names -> skipped with warning, material still created
fresh("d"); d = folder("dup", {"brick.bftex": "bftex", "Brick.png": (0, 1, 0, 1)})
r = imp(tex_folder=d); mat = bpy.data.materials.get("Brick"); ti = tinfo(mat); im, _ = g.find_albedo_image(mat)
chk("D duplicate skipped, material created", r == {"FINISHED"} and mat and not ti["brick"]["found"] and ti["brick"].get("duplicate") and im is None, str(ti["brick"]))
# E: missing (empty folder, no template)
fresh("e"); bpy.context.scene.mk8dx.template_file = ""; d = folder("empty", {})
r = imp(tex_folder=d); mat = bpy.data.materials.get("Brick"); ti = tinfo(mat)
chk("E missing -> material, note lists where", r == {"FINISHED"} and mat and not ti["brick"]["found"] and d in ti["brick"]["note"], ti["brick"]["note"])
# F: priority: dialog folder (red png) beats Template/other file (SRC has brick too)
fresh("f"); d = folder("prio", {"brick.png": (0, 0, 1, 1)})
r = imp(tex_folder=d, tex_source=SRC); ti = tinfo(bpy.data.materials["Brick"])
chk("F dialog folder has priority", "prio" in (ti["brick"]["note"] or ""), ti["brick"]["note"])
