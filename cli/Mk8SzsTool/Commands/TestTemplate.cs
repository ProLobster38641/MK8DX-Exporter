using System.IO;
using BfresLibrary;
using Mk8SzsTool.Export;
using Mk8SzsTool.Formats;
using Mk8SzsTool.Materials;
using System.Collections.Generic;

namespace Mk8SzsTool.Commands
{
    /// <summary>Builds a stand-in "original course" (fake materials named like MK8 ones, one shape, two textures) for offline tests.</summary>
    public static class TestTemplate
    {
        public static void Make(string outPath)
        {
            string dir = Path.Combine(Path.GetTempPath(), "mk8exp_tmpl"); Directory.CreateDirectory(dir);
            // one quad
            using (var w = new BinaryWriter(File.Create(Path.Combine(dir, "g.bin"))))
            {
                foreach (var f in new float[] { -1, 0, -1, 1, 0, -1, -1, 0, 1, 1, 0, 1 }) w.Write(f);
                foreach (var f in new float[] { 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0 }) w.Write(f);
                foreach (var f in new float[] { 0, 0, 1, 0, 0, 1, 1, 1 }) w.Write(f);
                foreach (var i in new uint[] { 0, 2, 1, 1, 2, 3 }) w.Write(i);
            }
            var px = new byte[16 * 16 * 4]; for (int i = 0; i < px.Length; i++) px[i] = (byte)(i % 4 == 3 ? 255 : 90);
            ImageIO.SaveRaw(Path.Combine(dir, "t.rgba"), new RgbaImage { Width = 16, Height = 16, Pixels = px });
            var man = new Manifest
            {
                ModelName = "Gu_TestCourse", AllowSynthetic = true, NeutralOtherSamplers = false,
                Textures = { new TextureEntry { Name = "orig_road_alb", File = "t.rgba" }, new TextureEntry { Name = "orig_bake", File = "t.rgba", Srgb = false } },
                Materials = {
                    new MaterialEntry { Name = "mt_road_template", Textures = { ["_a0"] = "orig_road_alb", ["_b0"] = "orig_bake" } },
                    new MaterialEntry { Name = "mt_grass_template", Textures = { ["_a0"] = "orig_road_alb", ["_b0"] = "orig_bake" } },
                    new MaterialEntry { Name = "ef_water01", Textures = { ["_a0"] = "orig_road_alb", ["_b0"] = "orig_bake" } },
                    new MaterialEntry { Name = "mt_fence_mask", Textures = { ["_a0"] = "orig_road_alb", ["_b0"] = "orig_bake" } },
                },
                Meshes = {
                    new MeshEntry { Name = "orig_shape", Material = "mt_road_template", Bin = "g.bin", VertexCount = 4, IndexCount = 6, IndicesOffset = 112,
                        Arrays = { ["position"] = new ArrayRef { Offset = 0, Components = 3 }, ["normal"] = new ArrayRef { Offset = 48, Components = 3 }, ["uv0"] = new ArrayRef { Offset = 96, Components = 2 } } },
                },
            };
            // indices offset: 48+48+32 = 128
            man.Meshes[0].IndicesOffset = 128;
            var res = new CourseBuilder(man, dir, _ => { }).Build();
            var fm = res.Models[0].Materials["mt_fence_mask"];
            var ri = new RenderInfo { Name = "gsys_render_state_mode" }; ri.SetValue(new[] { "mask" });
            fm.RenderInfos.RemoveKey("gsys_render_state_mode"); fm.RenderInfos.Add(ri.Name, ri);
            // stand-in for the shader archive real course files embed
            res.ExternalFiles.Add("Turbo_UBER.bfsha", new ExternalFile { Data = System.Text.Encoding.ASCII.GetBytes("FAKE_BFSHA_FOR_TESTS") });
            BfresIO.Save(res, outPath, true);
        }
    }
}
