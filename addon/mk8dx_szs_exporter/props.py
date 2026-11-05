import json
import bpy
from bpy.props import StringProperty, EnumProperty, PointerProperty, BoolProperty

_enum_cache = []


def template_items(self, context):
    global _enum_cache
    items = [("NONE", "Automatic", "Automatic: plain opaque (or alpha) material from the template file")]
    try:
        data = json.loads(context.scene.mk8dx.materials_json or "[]")
    except Exception:
        data = []
    for m in data:
        samp = " ".join(f"{k}={v}" for k, v in m.get("Samplers", {}).items())
        items.append((m["Name"], m["Name"], f"{m.get('ShadingModel','')}  {samp}"))
    _enum_cache = items
    return items


TEX_FORMATS = [
    ("auto", "Auto (BC1, BC3 if alpha)", "sRGB BC1, or BC3 when the image has transparency"),
    ("BC1_SRGB", "BC1 sRGB", "Colour, no alpha"),
    ("BC3_SRGB", "BC3 sRGB", "Colour with alpha"),
    ("BC1_UNORM", "BC1 Unorm", "Non-colour data (normal/shadow), no alpha"),
    ("BC3_UNORM", "BC3 Unorm", "Non-colour data with alpha"),
    ("RGBA8_SRGB", "RGBA8 sRGB (uncompressed)", "Large, lossless"),
]


class MK8DX_MaterialSettings(bpy.types.PropertyGroup):
    template: EnumProperty(name="Clone from", description="Original MK8DX material whose shader setup is copied", items=template_items)
    tex_format: EnumProperty(name="Texture format", items=TEX_FORMATS, default="auto")
    texture_override: PointerProperty(name="Albedo image", type=bpy.types.Image,
                                      description="Optional: use this image instead of the one found in the node tree")
    bfmat_path: StringProperty(name="Linked .bfmat", subtype="FILE_PATH", default="",
                               description="Imported .bfmat whose exact shader setup is cloned on export (clear to use the normal template choice)")
    bfmat_albedo: PointerProperty(name="Imported albedo", type=bpy.types.Image,
                                  description="Albedo image from the import. While Base Color still uses it unchanged, export keeps the original texture")
    bfmat_info: StringProperty(default="")


class MK8DX_SceneSettings(bpy.types.PropertyGroup):
    materials_json: StringProperty(default="[]")
    export_opts: StringProperty(default="{}", description="Last-used export dialog options (JSON)")
    materials_source: StringProperty(default="")
    gu_folder: StringProperty(name="Course folder", default="Gu_FirstCircuit",
                              description="Course folder name, e.g. Gu_FirstCircuit (Mario Kart Stadium). Used for the optional RomFS template shortcut and the optional course-folder destination")
    mod_name: StringProperty(name="Mod name", default="MyCustomTrack")
    template_file: StringProperty(name="Template file", subtype="FILE_PATH", default="",
                                  description="Any MK8DX .szs/.bfres (e.g. an original course_model.szs) or a .bfmat from Switch Toolbox. "
                                              "Its materials are cloned for your materials. Leave empty to use the export destination's existing file (or its .orig backup)")


def register():
    bpy.utils.register_class(MK8DX_MaterialSettings)
    bpy.utils.register_class(MK8DX_SceneSettings)
    bpy.types.Material.mk8dx = PointerProperty(type=MK8DX_MaterialSettings)
    bpy.types.Scene.mk8dx = PointerProperty(type=MK8DX_SceneSettings)


def unregister():
    del bpy.types.Material.mk8dx
    del bpy.types.Scene.mk8dx
    bpy.utils.unregister_class(MK8DX_SceneSettings)
    bpy.utils.unregister_class(MK8DX_MaterialSettings)
