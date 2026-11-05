using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using BfresLibrary;
using BfresLibrary.GX2;

namespace Mk8SzsTool.Materials
{
    public class MaterialInfo
    {
        public string Model { get; set; } = "";
        public string Name { get; set; } = "";
        public string ShaderArchive { get; set; } = "";
        public string ShadingModel { get; set; } = "";
        public Dictionary<string, string> Samplers { get; set; } = new();     // sampler name -> texture name
        public Dictionary<string, string> SamplerAssigns { get; set; } = new();
        public Dictionary<string, string> AttribAssigns { get; set; } = new();
        public Dictionary<string, string> ShaderOptions { get; set; } = new();
        public Dictionary<string, string> RenderInfo { get; set; } = new();
        public int ShaderParamCount { get; set; }
        public bool HasAlpha { get; set; }
    }

    /// <summary>
    /// Material template layer: read (list/describe/extract .bfmat) and write (clone, retarget textures).
    /// The future importer uses the read side; the exporter uses both.
    /// </summary>
    public static class MaterialTemplates
    {
        public static Dictionary<string, string> Map(ResDict<ResString>? d)
        {
            var r = new Dictionary<string, string>();
            if (d == null) return r;
            foreach (var kv in d) r[kv.Key] = kv.Value?.String ?? "";
            return r;
        }

        public static MaterialInfo Describe(Model? model, Material m)
        {
            var info = new MaterialInfo
            {
                Model = model?.Name ?? "", Name = m.Name,
                ShaderArchive = m.ShaderAssign?.ShaderArchiveName ?? "", ShadingModel = m.ShaderAssign?.ShadingModelName ?? "",
                SamplerAssigns = Map(m.ShaderAssign?.SamplerAssigns), AttribAssigns = Map(m.ShaderAssign?.AttribAssigns),
                ShaderOptions = Map(m.ShaderAssign?.ShaderOptions), ShaderParamCount = m.ShaderParams?.Count ?? 0,
            };
            for (int i = 0; i < m.Samplers.Count; i++)
                info.Samplers[m.Samplers.GetKey(i)] = i < m.TextureRefs.Count ? m.TextureRefs[i].Name : "";
            foreach (var ri in m.RenderInfos)
            {
                object? d = ri.Value.Data;
                string s = d switch { string[] a => string.Join(",", a), int[] a => string.Join(",", a), float[] a => string.Join(",", a), _ => d?.ToString() ?? "" };
                info.RenderInfo[ri.Key] = s;
            }
            info.HasAlpha = info.RenderInfo.Values.Any(v => v.Contains("translucent") || v.Contains("mask"));
            return info;
        }

        public static List<MaterialInfo> List(ResFile res)
        {
            var list = new List<MaterialInfo>();
            foreach (var model in res.Models.Values)
                foreach (var m in model.Materials.Values) list.Add(Describe(model, m));
            return list;
        }

        public static Material? Find(ResFile res, string name)
        {
            foreach (var model in res.Models.Values)
                if (model.Materials.ContainsKey(name)) return model.Materials[name];
            return null;
        }

        public static void ExportBfmat(ResFile res, Material m, string path) => m.Export(path, res);

        public static Material ImportBfmat(string path, ResFile res)
        {
            var m = new Material();
            m.Import(path, res);
            return m;
        }

        /// <summary>Deep clone through a .bfmat round trip (same code path as Switch Toolbox's .bfmat files).</summary>
        public static Material Clone(ResFile res, Material src, string newName)
        {
            string tmp = Path.Combine(Path.GetTempPath(), $"mk8exp_{Guid.NewGuid():N}.bfmat");
            try
            {
                src.Export(tmp, res);
                var m = ImportBfmat(tmp, res);
                m.Name = newName;
                return m;
            }
            finally { try { File.Delete(tmp); } catch { } }
        }

        /// <summary>Point sampler(s) at new texture names. Returns the samplers that were not found.</summary>
        public static List<string> SetTextures(Material m, Dictionary<string, string> samplerToTexture, bool forceRepeat)
        {
            var missing = new List<string>();
            foreach (var kv in samplerToTexture)
            {
                int idx = m.Samplers.IndexOf(kv.Key);
                if (idx < 0) { missing.Add(kv.Key); continue; }
                while (m.TextureRefs.Count <= idx) m.TextureRefs.Add(new TextureRef { Name = kv.Value });
                m.TextureRefs[idx] = new TextureRef { Name = kv.Value };
                if (forceRepeat)
                {
                    m.Samplers[idx].TexSampler.ClampX = GX2TexClamp.Wrap;
                    m.Samplers[idx].TexSampler.ClampY = GX2TexClamp.Wrap;
                }
            }
            return missing;
        }

        /// <summary>Picks the sampler used for albedo: "_a0" by convention, else the shader's _a0 assignment, else the first.</summary>
        public static string AlbedoSampler(Material m)
        {
            if (m.Samplers.ContainsKey("_a0")) return "_a0";
            var sa = Map(m.ShaderAssign?.SamplerAssigns);
            if (sa.TryGetValue("_a0", out var v) && m.Samplers.ContainsKey(v)) return v;
            return m.Samplers.Count > 0 ? m.Samplers.GetKey(0) : "_a0";
        }

        static IEnumerable<MaterialAnim> AllMatAnims(ResFile res) =>
            res.ShaderParamAnims.Values.Concat(res.TexSrtAnims.Values).Concat(res.ColorAnims.Values)
               .Concat(res.TexPatternAnims.Values).Concat(res.MatVisibilityAnims.Values);

        public static HashSet<string> AnimatedMaterialNames(ResFile res) =>
            new(AllMatAnims(res).SelectMany(a => a.MaterialAnimDataList ?? new List<MaterialAnimData>()).Select(d => d.Name));

        public static HashSet<string> AnimTextureNames(ResFile res) =>
            new(AllMatAnims(res).Where(a => a.TextureNames != null).SelectMany(a => a.TextureNames.Values).Select(t => t.Name));

        static string RenderMode(Material m)
        {
            foreach (var ri in m.RenderInfos)
                if (ri.Key == "gsys_render_state_mode" && ri.Value.Data is string[] a && a.Length > 0) return a[0];
            return "";
        }

        /// <summary>
        /// Automatic template choice: a plain, non-animated material with an albedo (_a0) sampler, whose render
        /// mode matches the texture (opaque, or mask/translucent when the texture has alpha). Materials from the
        /// file the course is built on are preferred because their shader variations exist in its embedded
        /// Turbo_UBER.bfsha.
        /// </summary>
        public static (Model? model, Material? mat, string why) AutoPick(ResFile res, bool alpha, HashSet<string>? animated = null)
        {
            animated ??= AnimatedMaterialNames(res);
            string[] fx = { "ef_", "water", "sea", "river", "lava", "glow", "emi", "light", "sky", "vr_", "cloud", "glass", "crystal", "fall" };
            (Model?, Material?, string) best = (null, null, ""); int bestScore = int.MinValue;
            foreach (var model in res.Models.Values)
                foreach (var m in model.Materials.Values)
                {
                    int sc = 0; var why = new List<string>();
                    if (m.Samplers.ContainsKey("_a0")) { sc += 20; why.Add("has _a0"); } else sc -= 50;
                    string mode = RenderMode(m);
                    bool alphaMode = mode == "mask" || mode == "translucent";
                    if (alpha ? alphaMode : mode == "opaque") { sc += 10; why.Add("mode " + mode); }
                    if (alpha && mode == "mask") sc += 3;
                    if (animated.Contains(m.Name)) { sc -= 15; why.Add("animated"); }
                    string ln = m.Name.ToLowerInvariant();
                    if (fx.Any(f => ln.Contains(f))) { sc -= 8; why.Add("effect-like name"); }
                    sc -= Math.Max(0, m.Samplers.Count - 4) * 2;
                    if (sc > bestScore) { bestScore = sc; best = (model, m, string.Join(", ", why)); }
                }
            return best;
        }

        /// <summary>
        /// A minimal stand-in material, used ONLY for offline tests or as an explicit fallback.
        /// It is not an MK8DX shader setup and will not render correctly in-game.
        /// </summary>
        public static Material Synthetic(string name)
        {
            var m = new Material { Name = name };
            m.ShaderAssign = new ShaderAssign
            {
                ShaderArchiveName = "synthetic_test", ShadingModelName = "synthetic_test",
                AttribAssigns = new ResDict<ResString>(), SamplerAssigns = new ResDict<ResString>(), ShaderOptions = new ResDict<ResString>(),
            };
            foreach (var a in new[] { "_p0", "_n0", "_u0", "_u1" }) m.ShaderAssign.AttribAssigns.Add(a, a);
            foreach (var s in new[] { "_a0", "_b0" })
            {
                m.ShaderAssign.SamplerAssigns.Add(s, s);
                m.Samplers.Add(s, new Sampler { Name = s, TexSampler = new TexSampler() });
                m.TextureRefs.Add(new TextureRef { Name = "missing" });
            }
            var ri = new RenderInfo { Name = "gsys_render_state_mode" }; ri.SetValue(new[] { "opaque" });
            m.RenderInfos.Add(ri.Name, ri);
            return m;
        }
    }
}
