import json
import os
import bpy

from . import operators


class MK8DX_PT_material(bpy.types.Panel):
    bl_label = "MK8DX Export"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"

    @classmethod
    def poll(cls, context):
        return context.material is not None

    def draw(self, context):
        l = self.layout
        m = context.material
        sc = context.scene.mk8dx
        n = len(json.loads(sc.materials_json or "[]"))
        row = l.row()
        row.operator("mk8dx.load_materials", icon="FILE_REFRESH")
        row.label(text=f"{n} originals loaded" if n else "none loaded")
        if m.mk8dx.bfmat_path:
            b = l.box()
            ok = os.path.isfile(bpy.path.abspath(m.mk8dx.bfmat_path))
            b.label(text="Linked .bfmat (export clones it):", icon="CHECKMARK" if ok else "ERROR")
            b.prop(m.mk8dx, "bfmat_path", text="")
            from .gather import find_albedo_image as _fa
            cur, _ = _fa(m)
            keep = cur is not None and cur == m.mk8dx.bfmat_albedo and not cur.is_dirty
            b.label(text="Albedo: original texture kept" if keep else "Albedo: replaced by your Base Color image", icon="IMAGE_DATA")
            try:
                for t in json.loads(m.mk8dx.bfmat_info or "{}").get("textures", []):
                    b.label(text=f"{t['sampler']}: {t['texture']}" + ("" if t.get("found") else "  (not found)"))
            except Exception:
                pass
        else:
            l.prop(m.mk8dx, "template")
        l.prop(m.mk8dx, "tex_format")
        l.prop(m.mk8dx, "texture_override")
        from .gather import find_albedo_image
        img, warns = find_albedo_image(m)
        l.label(text=f"Albedo (_a0): {img.name}" if img else "No image texture found", icon="IMAGE_DATA" if img else "ERROR")
        for w in warns:
            l.label(text="Mapping node tiling is not exported - scale UVs instead", icon="ERROR")


class MK8DX_PT_scene(bpy.types.Panel):
    bl_label = "MK8DX Export"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MK8DX"

    def draw(self, context):
        l = self.layout
        sc = context.scene.mk8dx
        l.label(text="Template file (.szs / .bfmat):")
        l.prop(sc, "template_file", text="")
        tpl = operators.resolve_template(context)
        if tpl:
            l.label(text="Using: " + tpl.replace("\\", "/").split("/")[-1], icon="CHECKMARK")
        else:
            l.label(text="No template set", icon="INFO")
        col = l.column(align=True)
        col.label(text="Course (optional shortcut / copy):")
        col.prop(sc, "gu_folder")
        col.prop(sc, "mod_name")
        l.operator("mk8dx.load_materials", icon="FILE_REFRESH")
        r = l.row(align=True)
        r.operator("mk8dx.import_bfmat", icon="IMPORT", text="Import .bfmat")
        r.operator("mk8dx.import_szs_materials", icon="IMPORT", text="Materials from .szs")
        from . import placeholder
        placeholder.draw_panel(l)
        l.operator("mk8dx.export_szs", icon="EXPORT")
        l.operator("mk8dx.export_kcl", icon="EXPORT")


classes = (MK8DX_PT_material, MK8DX_PT_scene)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
