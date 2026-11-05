# MK8DX SZS Exporter for Blender (1.0.0)

Export a Blender track straight to **Mario Kart 8 Deluxe (Switch)** course files:

- **`course_model.szs`**: the visual model (Yaz0 BFRES). Materials are cloned automatically from a real MK8DX material, and textures are written as BNTX (BC1/BC3, mipmaps, sRGB).
- **`course_kcl.szs`**: the collision (Yaz0 KCL v2, little endian), with a per-object or per-face collision type.

There's no Collada, OBJ or Switch Toolbox round trip. Tested with Blender 5.0. The bundled `mk8szs` backend is self-contained, so you don't need to install .NET (Windows x64 build in the release zip).

> You need your own legally dumped copy of the game for the template `course_model.szs`. This project ships no game files.

## Install / update
1. Download `mk8dx_szs_exporter_windows_1.0.zip` (or the unversioned Windows release zip) (don't unzip it).
2. In Blender, go to **Edit > Preferences > Get Extensions**, open the **v** menu (top right), choose **Install from Disk...** and pick the zip.
3. To update, install the new zip over the old one, then restart Blender.

Every path in the preferences is optional and starts blank:
- **RomFS folder**: your extracted `romfs` (contains `course`). Shortcut for the template.
- **Ryujinx data folder**: contains `mods`. On Windows this is usually `%APPDATA%\Ryujinx`. Only needed for the "Ryujinx mods" destination.

## Model export
1. Build your track. Modifiers are applied on export. Use real mesh UVs (Mapping-node tiling isn't exported).
2. Go to **File > Export > MK8DX course_model (.szs)**. The dialog's **Template file (.szs/.bfmat)** field and **N-panel > MK8DX > Template file** edit the same setting. For the first export to a new file, pick an original MK8DX course `.szs` (recommended), or a `.bfmat` with a course `.szs` supplied as the extra template/base.
3. **Leave Template file blank** to use the existing file at the export destination, read before replacing it. If that file is missing, its adjacent `.orig` is used; if neither exists, export stops and asks you to select a template. For **Also save** / **Save only**, the course-folder target supplies the template, not the browser copy. Explicitly selecting a template keeps using its `.orig` backup when present.
4. Optional **Course folder** setting: **Also save** or **Save only**. Destinations:
   - **Template's course folder (replace)**: overwrites the file next to your template. With the template blank and no RomFS shortcut set, uses the browser's existing course folder. The original is kept once as `*.orig`.
   - **Ryujinx mod folder** (separate from RomFS; creates the mod folders): `<Ryujinx>\mods\contents\0100152000022000\<Mod name>\romfs\course\<Gu_folder>\`
   - **Existing RomFS (replace)**: replaces the file in your existing `<romfs>\course\<Gu_folder>\` (point it at the romfs folder or its parent). It never creates folders and stops with an error naming the path if the course folder or file is missing
5. Optional: tick **Also export collision** to write `course_kcl.szs` alongside the model.

Every Blender material becomes an MK8DX material with the same name, with its Base Color image embedded. Without an image, the colour is baked into a small solid texture. The shader setup is cloned automatically from a plain opaque material in the template (or an alpha one for transparent materials). You can override this per material in **Material Properties > MK8DX Export**, or with a `.bfmat`.

The dialog remembers its options and Template file per .blend and in add-on preferences (across files/sessions when Blender saves preferences). Clearing the template field means automatic destination selection; it does not pin that destination as a new explicit template.

Shader variations from the base course are kept unchanged. Imported materials with different shader settings are adapted to the closest known course variation when needed; this is an **INFO** note, not an error/warning. Detailed changes and the chosen template are in `*_export_log.txt`. Matching variations from a `.orig` backup or extra `.szs` are also recognised when their embedded shader archive is byte-identical. Adaptation may simplify the material's appearance; using materials from the base course is best.

Files are written safely: a temp file is replaced into place, with retries if the file is locked, then checked after writing. Existing model outputs are backed up once as `*.orig`; existing backups are never replaced. The info bar lists every path saved. If anything fails you get an error, not a success message.

## Importing materials (.bfmat / .szs)
- **File > Import > MK8DX material (.bfmat)** (multi-select), or the **Import .bfmat** button in N-panel > MK8DX. Each file becomes a Blender material with the same name. Importing again updates the existing material instead of making a duplicate.
- **File > Import > MK8DX materials from course .szs** imports every material of a course (or only the names you list), with their textures.
- **Textures:** a .bfmat only stores texture names, so they are looked up by name (case-insensitive, extension ignored), in this order: the dialog's **Texture folder** (optionally **Include subfolders**), its **Texture file** (.szs/.bfres/.bntx, or a folder path typed in), then the Template file.
  - **Folders** may hold Switch Toolbox `.bftex` exports, `.png`, `.tga`, `.bmp`, `.jpg` and `.dds` (BC1/BC3/BC4/BC5 or uncompressed). Copy suffixes like `name (1)` or `name_0` are tolerated.
  - **Same name twice** (e.g. `Road_Alb.png` and `Road_Alb.bftex`, or copies in subfolders): that texture is skipped. A warning in the status bar names it and the conflicting files; everything else still imports.
  - **Not found:** a warning lists the missing names and every place searched.
  - **Albedo (`_a0`):** decoded to PNG and connected to Base Color.
  - **Normal map (`_n0`):** connected through a Normal Map node.
  - **Other maps:** listed in Material Properties > MK8DX Export.
- **Where files go:** PNGs and .bfmat copies are saved in a `<blend name>_mk8dx` folder next to the .blend (save the .blend first), and the images are packed by default.
- **Missing textures:** the material is still created, with a note in the panel.
- **On export:** an imported material clones its linked .bfmat exactly. If Base Color still uses the imported image, unchanged, the original texture is copied in as-is. If you change the image, it replaces the albedo as usual.

## Start grid placeholder
- **Add:** Shift+A > MK8DX > **Add Start Grid Placeholder**, or the N-panel button. It adds 12 wireframe kart markers in a staggered 2-column grid plus a road-width outline, under one empty in their own collection.
- **Size:** markers use the Scale from your last model export. Defaults (game units, adjustable in the redo panel; community estimates, not official values): kart about 140 x 100 x 70, columns ±250 from the centre, 230 between racers, road about 2400 wide.
- **Never exported:** neither exporter includes them.
- **Remove:** press **Remove**, or simply delete the empty (X); the whole grid, its collection and its mesh data go with it.

## Collision (KCL)
### Assigning collision types
- **Toolbar:** the **MK8DX Collision** tool in the 3D Viewport's left toolbar (Object mode and Edit mode). The tool header and the **N-panel > MK8DX Collision** show the type picker:
  - **Quick presets**: Road, Grass/Dirt/Sand/Snow off-road, Ice, Boost, Anti-gravity, Glider panel, Glider activator, Trick ramp, Walls, Invisible wall, Fall out (void/water/lava), Lakitu, Item road/wall.
  - **Custom collision (set type + flags)**: type + variant (sound/effects) + flags (trickable, high gravity).
  - **Custom hex**: e.g. `8086`.
- **Object mode > Apply:** the type applies to the whole selected object(s).
- **Edit mode > Apply:** the type applies to the selected faces only. It's stored in the int face attribute `mk8dx_col`; `-1` means "use the object's type".
- **Default:** every mesh you never assigned counts as **Visual + collision** with type Road 1 / Asphalt (`0x0000`), so a plain road mesh goes into both files. Set *Visual only* for scenery without collision, or *Collision only* for meshes that must stay out of `course_model.szs`.
- **Object becomes** (tool option when applying a type): *Collision only* or *Visual + collision*.
- **Collection shortcut:** unassigned objects in a collection whose name starts with `Collision` count as collision only (default type Road, `0x0000`).
- **Collision preview:** a flat, untextured view of collision colours per type (including face overrides); visual-only meshes are neutral/dim. Materials and textures are never displayed in this view. Click again to restore the viewport's previous shading exactly, including Material Preview / Rendered, lighting, colours, shadows and X-ray settings. This is viewport-only: it does not replace materials or change mesh/vertex-colour data; linked meshes can show different object collision types. The older display attribute `MK8DX_Collision` is still never exported to the model.

### Exporting
Use **File > Export > MK8DX collision (course_kcl.szs)**. It has the same destination options as the model and the default name `course_kcl.szs`. Use the **same Scale** as the model export.

### Flag format
`flag = type (0x00-0x1F) + variant * 0x20 + special flags` (`0x1000` trickable, `0x2000` trickable extra, `0x4000` high gravity, `0x8000` high gravity 2). Switch Toolbox shows groups as `COL_<hex>`, e.g. `COL_1060` = Road 1 / Wood + Trickable.

Main types: `00-03` Road, `04` Sand, `05` Weak off-road, `06-07` Off-road, `08` Heavy off-road, `09` Slippery, `0A` Dash, `0B` Anti-gravity panel, `0C` Glider panel, `0D` Pull, `0F` Item road, `10` Lakitu rescue, `11-13` Wall, `15` Item wall, `16` Bouncy wall, `17` Invisible wall, `1C` Fall out (variants: void/water/lava), `1F` Zone (variant 0 = glider activator).

Sources: [mk8.tockdom.com KCL flag](https://mk8.tockdom.com/wiki/KCL_flag) and [Track Studio collision docs](https://mapstudioproject.github.io/TrackStudioDocs/col/Collison.html).

Tips: separate roads and walls, and make walls a wall type. A glider needs a small Zone/glider-activator plane above the ramp, plus a glider path. Fall-out planes go under the track.

## Not covered
Paths, objects (`course_muunt.byaml`), lighting and minimap still go through Track Studio. Skinned or animated meshes aren't supported. Only albedo comes from Blender; other maps come from the template or are neutral.

## Command line
```
mk8szs export export.json out.szs           model (what the add-on runs)
mk8szs kcl-export pos.bin attr.bin out.szs  collision: float32 xyz*3 per triangle + uint16 flag per triangle [--raw for .kcl]
mk8szs kcl-info course_kcl.szs [--hit-test] KCL summary + octree self-check
mk8szs kcl-dump course_kcl.szs pos.bin attr.bin
mk8szs export-bftex course.szs <texture> out.bftex   single-texture file (Switch Toolbox compatible)
mk8szs mat-import outdir [--bfmat f]... [--szs f [--only a,b]] [--tex file|folder|folder/**]...   materials -> .bfmat copies + decoded textures + JSON
mk8szs info | materials | extract-bfmat | import | yaz0-d | yaz0-c
```

## Building from source
- **Requirements:** .NET 8 SDK; clone [BfresLibrary](https://github.com/KillzXGaming/BfresLibrary) and [KclLibrary](https://github.com/KillzXGaming/KclLibrary) into `ext/`. (On Linux/macOS change KclLibrary's `<TargetFrameworks>netstandard2.1;net46</TargetFrameworks>` to `<TargetFramework>netstandard2.1</TargetFramework>`.)
- **Build:**
  ```
  dotnet publish cli/Mk8SzsTool -c Release -r win-x64 --self-contained -p:PublishSingleFile=true -p:EnableCompressionInSingleFile=true -o cli/publish/win-x64
  ```
- **Package:** copy `addon/mk8dx_szs_exporter`, put `mk8szs.exe` in its `bin/` folder, then run `python mkzip.py <folder> out.zip`.
- **Tests:** headless Blender tests are in `test/` (`run_blender_test.sh blender_test6.py`, etc.). Set BLENDER to your Blender executable. The fixtures are synthetic, not game assets. Tests generate temporary exports and `test_scene.blend`; generated scenes/outputs are not part of the source release. The optional `blender_shader_test.py` uses your private dumped course files through environment variables (see its header).

## Changelog
- **1.0.0 — public release**: Template file is available in the model export dialog and shared with the N-panel; it persists with the export options. A blank template reads the destination's current file, then its `.orig` backup. Shader adaptation is informational (one short status note plus details in the log), and matching source-course variations are preserved. Collision preview uses flat type colours only (non-collision meshes neutral), with exact shading restoration. Safe replacement/backups, model and collision export, material import and the start grid are included.
- **Beta 0.3.x**: .bfmat/.szs material import, texture folders with duplicate protection, start grid placeholder, persistent export options, default Visual + collision / Road 1 (`0x0000`), and the in-game shader-variation compatibility fix.
- **Earlier previews**: initial BFRES/BNTX model export, collision export/type tools, course-folder destinations and verified writes.

Upgrading from previews: install the new zip and restart Blender. Some early previews used a higher 1.x number; if Blender will not replace one, uninstall that preview in Preferences, restart, then install 1.0.0. Keep your .blend and `.orig` course backups.

## License
The add-on is GPL-3.0-or-later (`LICENSE`). The bundled tool uses MIT-licensed BfresLibrary, KclLibrary and Syroot libraries, plus StbImageSharp (Unlicense/MIT). See `THIRD_PARTY_NOTICES.txt`. Mario Kart 8 Deluxe is a trademark of Nintendo; this is an unofficial fan tool.
