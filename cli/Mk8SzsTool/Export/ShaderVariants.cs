using System.Collections.Generic;
using System.Linq;
using BfresLibrary;

namespace Mk8SzsTool.Export
{
    /// <summary>
    /// MK8DX courses embed a trimmed Turbo_UBER.bfsha that only contains the shader programs (option
    /// combinations) used by that course's own materials. A material whose static options match no
    /// program is silently not drawn in game (other tools still show it with their own shaders).
    /// Materials from a .bfmat or another course are therefore snapped to the closest option set that
    /// the base course actually uses.
    /// </summary>
    public static class ShaderVariants
    {
        public class Variant
        {
            public string Material = "", Model = "";
            public Dictionary<string, string> Options = new();
            public HashSet<string> Samplers = new(), Attribs = new();
        }

        static Dictionary<string, string> Opts(ShaderAssign sa)
        {
            var d = new Dictionary<string, string>();
            for (int i = 0; i < sa.ShaderOptions.Count; i++) d[sa.ShaderOptions.GetKey(i)] = sa.ShaderOptions[i].String;
            return d;
        }

        public static List<Variant> Collect(ResFile res) =>
            res.Models.Values.SelectMany(m => m.Materials.Values).Where(m => m.ShaderAssign != null).Select(m => new Variant
            {
                Material = m.Name, Model = m.ShaderAssign.ShadingModelName, Options = Opts(m.ShaderAssign),
                Samplers = new HashSet<string>(m.ShaderAssign.SamplerAssigns.Keys),
                Attribs = new HashSet<string>(m.ShaderAssign.AttribAssigns.Keys),
            }).ToList();

        /// <summary>Only combine known variations from sources embedding byte-identical shader archives.</summary>
        public static bool SameArchive(ResFile a, ResFile b)
        {
            const string key = "Turbo_UBER.bfsha";
            return a.ExternalFiles.ContainsKey(key) && b.ExternalFiles.ContainsKey(key)
                && a.ExternalFiles[key].Data.SequenceEqual(b.ExternalFiles[key].Data);
        }

        static int Diff(Dictionary<string, string> a, Dictionary<string, string> b) =>
            a.Keys.Union(b.Keys).Count(k => !a.TryGetValue(k, out var x) || !b.TryGetValue(k, out var y) || x != y);

        /// <summary>Returns the base material used and the list of changed options (empty when already valid).</summary>
        public static (string from, List<string> changed) Snap(Material mat, List<Variant> variants)
        {
            var sa = mat.ShaderAssign;
            var cur = Opts(sa);
            var same = variants.Where(v => v.Model == sa.ShadingModelName).ToList();
            if (same.Count == 0 || same.Any(v => Diff(v.Options, cur) == 0)) return ("", new List<string>());
            var samplers = new HashSet<string>(sa.SamplerAssigns.Keys);
            var attribs = new HashSet<string>(sa.AttribAssigns.Keys);
            var fits = same.Where(v => v.Samplers.IsSubsetOf(samplers) && v.Attribs.IsSubsetOf(attribs)).ToList();
            var best = (fits.Count > 0 ? fits : same).OrderBy(v => Diff(v.Options, cur)).First();
            var changed = new List<string>();
            foreach (var k in best.Options.Keys.Union(cur.Keys).ToList())
            {
                best.Options.TryGetValue(k, out var nv); cur.TryGetValue(k, out var ov);
                if (nv != ov) changed.Add($"{k} {ov ?? "-"}->{nv ?? "-"}");
            }
            sa.ShaderOptions = new ResDict<ResString>();
            foreach (var kv in best.Options) sa.ShaderOptions.Add(kv.Key, kv.Value);
            return (best.Material, changed);
        }
    }
}
