"""Import .bfmat files (or all materials of a course .szs) as Blender materials linked to their original shader setup."""
import json
import os
import shutil
import struct
import tempfile

import bpy
import numpy as np
from bpy.props import BoolProperty, CollectionProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from . import cli, files


def data_dir():
    """Folder that keeps imported .bfmat copies and PNGs: next to the .blend, else a cache folder."""
    if bpy.data.filepath:
        base = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
        return os.path.join(os.path.dirname(bpy.data.filepath), base + "_mk8dx"), True
    return os.path.join(tempfile.gettempdir(), "mk8dx_import_cache"), False


def load_rgba(path, name, non_color):
    with open(path, "rb") as f:
        hdr = f.read(12)
        w, h = struct.unpack("<ii", hdr[4:12])
        px = np.frombuffer(f.read(w * h * 4), np.uint8).reshape(h, w, 4)[::-1]
    img = bpy.data.images.get(name)
    if img is None or tuple(img.size) != (w, h):
        if img is not None:
            img.name = name + "_old"
        img = bpy.data.images.new(name, w, h, alpha=True)
    img.colorspace_settings.name = "Non-Color" if non_color else "sRGB"   # before pixels: changing it regenerates the buffer
    img.pixels.foreach_set((px.astype(np.float32) / 255.0).ravel())
    return img


def save_png(img, folder):
    os.makedirs(folder, exist_ok=True)
    p = os.path.join(folder, img.name + ".png")
    img.filepath_raw = p
    img.file_format = "PNG"
    img.save()
    return p


def build_material(entry, folder, pack, warns):
    name = entry["name"]
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    if not getattr(mat, "node_tree", None):
        mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (400, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (100, 0)
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    albedo_img = None
    y = 300
    missing = [t for t in entry["textures"] if t.get("texture") and not t.get("found") and not t.get("duplicate")]
    if missing:
        warns.append(f"Material '{name}': textures not found: {', '.join(t['texture'] for t in missing)} ({missing[0].get('note', '')}). "
                     "The material is created anyway; export uses neutral/template textures for them.")
    for t in entry["textures"]:
        if not t.get("file"):
            if t.get("albedo") and t.get("found"):
                warns.append(f"{name}: albedo '{t['texture']}' {t.get('note') or ''}")
            continue
        is_normal = t["sampler"].startswith("_n")
        img = load_rgba(t["file"], t["texture"], non_color=is_normal)
        try:
            save_png(img, os.path.join(folder, "textures"))
            if pack:
                img.pack()
        except Exception as e:
            warns.append(f"{name}: could not save {t['texture']}.png ({e}); image packed instead")
            img.pack()
        tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img; tex.location = (-400, y); tex.label = f"{t['sampler']} {t['texture']}"
        y -= 300
        if t.get("albedo"):
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
            if entry.get("has_alpha"):
                nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
                for attr, val in (("surface_render_method", "DITHERED"), ("blend_method", "CLIP")):
                    if hasattr(mat, attr):
                        try:
                            setattr(mat, attr, val)
                        except Exception:
                            pass
            albedo_img = img
        elif is_normal and t["sampler"] == "_n0":
            nm = nt.nodes.new("ShaderNodeNormalMap"); nm.location = (-150, -250)
            nt.links.new(tex.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    s = mat.mk8dx
    s.bfmat_path = entry["bfmat"]
    s.bfmat_albedo = albedo_img
    s.bfmat_info = json.dumps({"textures": [{k: t.get(k) for k in ("sampler", "texture", "format", "found", "duplicate", "note")} for t in entry["textures"]],
                               "texture_sources": entry.get("texture_sources", []), "shading_model": entry.get("shading_model"),
                               "model": entry.get("model")})
    return mat


def source_specs(op):
    """Dialog sources (folder and/or file) in priority order. A folder path typed into the file field works too."""
    out = []
    for p, rec in ((getattr(op, "tex_folder", ""), getattr(op, "tex_subfolders", False)), (getattr(op, "tex_source", ""), getattr(op, "tex_subfolders", False))):
        if not p:
            continue
        n = files.norm(p)
        if os.path.isdir(n):
            out.append(n + ("/**" if rec else ""))
        elif os.path.isfile(n):
            out.append(n)
        else:
            op.report({"WARNING"}, f"Texture source not found: {n}")
    return out


def run_import(op, context, bfmats=(), szs="", only="", tex_source=""):
    from .operators import resolve_template
    folder, persistent = data_dir()
    work = tempfile.mkdtemp(prefix="mk8dx_matimp_")
    args = ["mat-import", folder]
    for b in bfmats:
        args += ["--bfmat", b]
    if szs:
        args += ["--szs", szs]
        if only.strip():
            args += ["--only", only]
    srcs = source_specs(op)
    tpl = resolve_template(context)
    if tpl and not tpl.lower().endswith(".bfmat") and os.path.isfile(tpl):
        srcs.append(tpl)
    for s in srcs:
        if s != szs:
            args += ["--tex", s]
    try:
        code, so, se = cli.run(context, args)
        if code != 0:
            op.report({"ERROR"}, "Material import failed: " + ((se or so).strip().splitlines() or ["?"])[-1][:300])
            return {"CANCELLED"}
        data = json.loads(so)
        warns = [w.replace("WARNING: ", "") for w in data.get("warnings", [])]
        mats = [build_material(e, folder, op.pack, warns) for e in data["materials"]]
        # raw decoded files are no longer needed (PNGs are kept)
        for f in os.listdir(os.path.join(folder, "textures")) if os.path.isdir(os.path.join(folder, "textures")) else []:
            if f.endswith(".rgba"):
                os.remove(os.path.join(folder, "textures", f))
        if not persistent:
            warns.append("The .blend is not saved yet: imported .bfmat copies are in a temporary cache folder. Save the .blend and re-import to keep them next to it.")
        for w in warns:
            op.report({"WARNING"}, w)
        op.report({"INFO"}, f"Imported {len(mats)} material(s): {', '.join(m.name for m in mats[:8])}{' ...' if len(mats) > 8 else ''}  (files in {folder})")
        return {"FINISHED"}
    finally:
        shutil.rmtree(work, ignore_errors=True)


class MK8DX_OT_import_bfmat(bpy.types.Operator, ImportHelper):
    """Import .bfmat file(s) as Blender materials. Export reuses each .bfmat's exact shader setup"""
    bl_idname = "mk8dx.import_bfmat"
    bl_label = "Import MK8DX material (.bfmat)"
    bl_options = {"UNDO"}
    filename_ext = ".bfmat"
    filter_glob: StringProperty(default="*.bfmat", options={"HIDDEN"})
    files: CollectionProperty(type=bpy.types.OperatorFileListElement, options={"HIDDEN", "SKIP_SAVE"})
    directory: StringProperty(subtype="DIR_PATH", options={"HIDDEN"})
    tex_folder: StringProperty(name="Texture folder", subtype="DIR_PATH", default="",
                               description="Optional: folder with .bftex / .png / .tga / .dds files named like the textures (searched first)")
    tex_subfolders: BoolProperty(name="Include subfolders", default=False)
    tex_source: StringProperty(name="Texture file (.szs/.bntx)", subtype="FILE_PATH", default="",
                               description="Optional: a .szs/.bfres/.bntx (a folder path typed here works too). The Template .szs is searched last")

    def draw(self, context):
        l = self.layout
        b = l.box(); b.label(text="Textures (optional, searched in this order):")
        b.prop(self, "tex_folder"); b.prop(self, "tex_subfolders"); b.prop(self, "tex_source")
        b.label(text="then the Template file", icon="INFO")
        for k in ("only", "pack"):
            if hasattr(self, k):
                l.prop(self, k)
    pack: BoolProperty(name="Pack images into .blend", default=True)

    def execute(self, context):
        paths = [os.path.join(self.directory, f.name) for f in self.files if f.name] or [self.filepath]
        paths = [files.norm(p) for p in paths if p.lower().endswith(".bfmat") and os.path.isfile(files.norm(p))]
        if not paths:
            self.report({"ERROR"}, "No .bfmat file selected")
            return {"CANCELLED"}
        return run_import(self, context, bfmats=paths)


class MK8DX_OT_import_szs_materials(bpy.types.Operator, ImportHelper):
    """Import materials (with textures) from an MK8DX course_model.szs as Blender materials"""
    bl_idname = "mk8dx.import_szs_materials"
    bl_label = "Import materials from MK8DX .szs"
    bl_options = {"UNDO"}
    filename_ext = ".szs"
    filter_glob: StringProperty(default="*.szs;*.bfres", options={"HIDDEN"})
    only: StringProperty(name="Only these (comma separated)", default="", description="Leave empty to import every material")
    tex_folder: StringProperty(name="Texture folder", subtype="DIR_PATH", default="",
                               description="Optional: folder with .bftex / .png / .tga / .dds files named like the textures (searched first)")
    tex_subfolders: BoolProperty(name="Include subfolders", default=False)
    tex_source: StringProperty(name="Texture file (.szs/.bntx)", subtype="FILE_PATH", default="",
                               description="Optional: a .szs/.bfres/.bntx (a folder path typed here works too). The Template .szs is searched last")

    def draw(self, context):
        l = self.layout
        b = l.box(); b.label(text="Textures (optional, searched in this order):")
        b.prop(self, "tex_folder"); b.prop(self, "tex_subfolders"); b.prop(self, "tex_source")
        b.label(text="then the Template file", icon="INFO")
        for k in ("only", "pack"):
            if hasattr(self, k):
                l.prop(self, k)
    pack: BoolProperty(name="Pack images into .blend", default=True)

    def execute(self, context):
        p = files.norm(self.filepath)
        if not os.path.isfile(p):
            self.report({"ERROR"}, f"File not found: {p}")
            return {"CANCELLED"}
        return run_import(self, context, szs=p, only=self.only)


def menu_func(self, context):
    self.layout.operator(MK8DX_OT_import_bfmat.bl_idname, text="MK8DX material (.bfmat)")
    self.layout.operator(MK8DX_OT_import_szs_materials.bl_idname, text="MK8DX materials from course .szs")


classes = (MK8DX_OT_import_bfmat, MK8DX_OT_import_szs_materials)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.TOPBAR_MT_file_import.append(menu_func)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
