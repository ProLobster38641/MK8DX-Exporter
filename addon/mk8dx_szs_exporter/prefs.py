import os
import bpy
from bpy.props import StringProperty


class MK8DX_Prefs(bpy.types.AddonPreferences):
    bl_idname = __package__

    romfs_dir: StringProperty(
        name="MK8DX RomFS folder (optional)",
        description="Optional. Your extracted romfs folder (contains 'course'). Shortcut: if no template file is picked, romfs/course/<Course folder>/course_model.szs is used as template",
        subtype="DIR_PATH", default="")
    ryujinx_dir: StringProperty(
        name="Ryujinx data folder (optional)",
        description="Optional. Ryujinx/Ryubing data folder (contains 'mods'), on Windows usually %APPDATA%\\Ryujinx. Only needed for the 'Ryujinx mods' destination",
        subtype="DIR_PATH", default="")
    export_opts: StringProperty(default="{}", options={"HIDDEN"})
    cli_override: StringProperty(
        name="mk8szs tool (optional)",
        description="Only set this if you want to use a different mk8szs.exe than the bundled one",
        subtype="FILE_PATH", default="")

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "romfs_dir")
        col.prop(self, "ryujinx_dir")
        col.prop(self, "cli_override")
        col.label(text="All optional. Example Ryujinx folder on Windows: %APPDATA%\\Ryujinx", icon="INFO")


def register():
    bpy.utils.register_class(MK8DX_Prefs)


def unregister():
    bpy.utils.unregister_class(MK8DX_Prefs)
