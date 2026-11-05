using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Mk8SzsTool.Commands;
using Mk8SzsTool.Export;
using Mk8SzsTool.Formats;
using Mk8SzsTool.Import;
using Mk8SzsTool.Materials;

namespace Mk8SzsTool
{
    public static class Program
    {
        const string Usage = @"mk8szs - MK8 Deluxe course_model.szs tool (Blender exporter backend)

Commands:
  export <export.json> <out.szs|out.bfres> [--no-yaz0]   Build a course model from the add-on's export folder
  materials <file.szs|.bfres> [--json]                   List materials (template picker)
  extract-bfmat <file.szs> <material> <out.bfmat>        Save one material as .bfmat (Switch Toolbox compatible)
  info <file.szs|.bfres>                                 JSON summary (models, shapes, materials, textures)
  import <file.szs> <out_dir>                            Unpack to export.json-compatible folder (import groundwork)
  decode-texture <file.szs> <texture> <out.rgba>         Decode one texture back to RGBA
  yaz0-d <in> <out> | yaz0-c <in> <out>                  Yaz0 decompress / compress
  make-test-template <out.szs>                           Synthetic Switch BFRES with fake materials (offline tests only)
  version";

        /// <summary>Keeps library debug prints off stdout so JSON output stays parseable.</summary>
        static T Quiet<T>(Func<T> f)
        {
            var o = Console.Out; Console.SetOut(Console.Error);
            try { return f(); } finally { Console.SetOut(o); }
        }

        static int Main(string[] args)
        {
            var opts = new JsonSerializerOptions { WriteIndented = true };
            try
            {
                if (args.Length == 0) { Console.WriteLine(Usage); return 1; }
                switch (args[0])
                {
                    case "version": Console.WriteLine("mk8szs 1.0.0"); return 0;
                    case "export":
                        {
                            var man = Manifest.Load(args[1]);
                            var b = new CourseBuilder(man, Path.GetDirectoryName(Path.GetFullPath(args[1]))!, Console.WriteLine);
                            var res = b.Build();
                            bool yaz = !args.Contains("--no-yaz0") && !args[2].EndsWith(".bfres", StringComparison.OrdinalIgnoreCase);
                            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(args[2]))!);
                            BfresIO.Save(res, args[2], yaz);
                            // self-check: reload what we wrote
                            var back = BfresIO.Load(args[2]);
                            int shapes = back.Models.Values.Sum(m => m.Shapes.Count);
                            Console.WriteLine($"OK: wrote {args[2]} ({new FileInfo(args[2]).Length} bytes, {(yaz ? "Yaz0" : "raw")}); reload: {back.Models.Count} model(s), {shapes} shape(s), {back.Textures.Count} texture(s), {b.Warnings.Count} warning(s)");
                            return 0;
                        }
                    case "materials":
                        {
                            var list = args[1].EndsWith(".bfmat", StringComparison.OrdinalIgnoreCase)
                                ? new List<MaterialInfo> { MaterialTemplates.Describe(null, Quiet(() => MaterialTemplates.ImportBfmat(args[1], new BfresLibrary.ResFile(true)))) }
                                : MaterialTemplates.List(Quiet(() => BfresIO.Load(args[1])));
                            if (args.Contains("--json")) Console.WriteLine(JsonSerializer.Serialize(list, opts));
                            else foreach (var m in list)
                                    Console.WriteLine($"{m.Name}\t[{m.Model}] {m.ShadingModel}\t" + string.Join(" ", m.Samplers.Select(s => $"{s.Key}={s.Value}")));
                            return 0;
                        }
                    case "extract-bfmat":
                        {
                            var res = BfresIO.Load(args[1]);
                            var m = MaterialTemplates.Find(res, args[2]) ?? throw new Exception($"material '{args[2]}' not found");
                            MaterialTemplates.ExportBfmat(res, m, args[3]); Console.WriteLine("OK"); return 0;
                        }
                    case "info":
                        Console.WriteLine(JsonSerializer.Serialize(InfoCommand.Describe(Quiet(() => BfresIO.Load(args[1]))), opts)); return 0;
                    case "import":
                        CourseImporter.Run(args[1], args[2], Console.WriteLine); return 0;
                    case "decode-texture":
                        {
                            var res = BfresIO.Load(args[1]);
                            var img = BntxTextures.DecodeToRgba((BfresLibrary.Switch.SwitchTexture)res.Textures[args[2]]) ?? throw new Exception("unsupported format");
                            ImageIO.SaveRaw(args[3], img); Console.WriteLine($"OK {img.Width}x{img.Height}"); return 0;
                        }
                    case "kcl-export":
                        {
                            var pb = File.ReadAllBytes(args[1]); var ab = File.ReadAllBytes(args[2]);
                            var pos = new float[pb.Length / 4]; Buffer.BlockCopy(pb, 0, pos, 0, pb.Length);
                            var at = new ushort[ab.Length / 2]; Buffer.BlockCopy(ab, 0, at, 0, ab.Length);
                            if (pos.Length != at.Length * 9) { Console.Error.WriteLine("ERROR: position/attribute count mismatch"); return 2; }
                            var w = new List<string>();
                            var bytes = Quiet(() => Mk8SzsTool.Collision.KclIO.Build(pos, at, !args.Contains("--raw"), out int _n, w));
                            File.WriteAllBytes(args[3], bytes);
                            foreach (var x in w) Console.WriteLine(x);
                            Console.WriteLine(JsonSerializer.Serialize(Mk8SzsTool.Collision.KclIO.Describe(args[3], false), opts));
                            return 0;
                        }
                    case "mat-import":
                        {
                            // mat-import <outdir> [--bfmat f]... [--szs f [--only a,b]] [--tex f]...
                            var bf = new List<string>(); var tex = new List<string>(); string? szs = null; HashSet<string>? only = null;
                            for (int i = 2; i < args.Length - 1; i++)
                            {
                                if (args[i] == "--bfmat") bf.Add(args[++i]);
                                else if (args[i] == "--tex") tex.Add(args[++i]);
                                else if (args[i] == "--szs") szs = args[++i];
                                else if (args[i] == "--only") only = new HashSet<string>(args[++i].Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries));
                            }
                            var w = new List<string>();
                            var r = Quiet(() => Mk8SzsTool.Import.MaterialImport.Run(bf, szs, only, tex, args[1], w));
                            foreach (var x in w) Console.Error.WriteLine(x);
                            Console.WriteLine(JsonSerializer.Serialize(new { materials = r, warnings = w }, opts));
                            return 0;
                        }
                    case "export-bftex":
                        {   // export-bftex <.szs/.bntx> <texture> <out.bftex>  (single-texture file, Switch Toolbox compatible)
                            var t = TextureSource.Load(args[1]).FirstOrDefault(x => x.Name == args[2]) ?? throw new Exception($"texture '{args[2]}' not found");
                            var bn = BntxTextures.NewBntx(); bn.Textures.Add(t); bn.TextureDict.Add(t.Name);
                            t.Export(args[3], bn); Console.WriteLine("OK"); return 0;
                        }
                    case "kcl-info":
                        Console.WriteLine(JsonSerializer.Serialize(Quiet(() => Mk8SzsTool.Collision.KclIO.Describe(args[1], args.Contains("--hit-test"))), opts)); return 0;
                    case "kcl-dump": Quiet(() => { Mk8SzsTool.Collision.KclIO.Dump(args[1], args[2], args[3]); return 0; }); return 0;
                    case "yaz0-d": File.WriteAllBytes(args[2], Yaz0.Decompress(File.ReadAllBytes(args[1]))); return 0;
                    case "yaz0-c": File.WriteAllBytes(args[2], Yaz0.Compress(File.ReadAllBytes(args[1]))); return 0;
                    case "make-test-template": TestTemplate.Make(args[1]); Console.WriteLine("OK"); return 0;
                    default: Console.WriteLine(Usage); return 1;
                }
            }
            catch (Exception e)
            {
                Console.Error.WriteLine("ERROR: " + e.Message);
                Console.Error.WriteLine(e.ToString());
                return 2;
            }
        }
    }
}
