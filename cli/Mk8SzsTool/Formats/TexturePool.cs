using System.Text.RegularExpressions;
using Syroot.NintenTools.NSW.Bntx;
using Syroot.NintenTools.NSW.Bntx.GFX;

namespace Mk8SzsTool.Formats
{
    /// <summary>Found texture: either a native Switch texture (from .szs/.bntx/.bftex, embeddable as-is) or a plain image (png/tga/dds...).</summary>
    public class FoundTexture
    {
        public string Name = "", Origin = "";
        public Texture? Native;
        public RgbaImage? Image;
        public string Format => Native != null ? Native.Format.ToString() : "image";
    }

    /// <summary>Texture lookup over several sources in priority order. A source is a .szs/.bfres/.bntx file or a folder
    /// (.bftex/.png/.tga/.bmp/.jpg/.dds; "dir/**" = include subfolders). Names match case-insensitively, ignoring extension.</summary>
    public class TexturePool
    {
        static readonly string[] Exts = { ".bftex", ".png", ".tga", ".bmp", ".jpg", ".jpeg", ".dds" };
        readonly List<(string label, Dictionary<string, Texture>? files, Dictionary<string, List<string>>? dir)> sources = new();
        public readonly List<string> Warnings = new();
        public readonly HashSet<string> Duplicates = new(StringComparer.OrdinalIgnoreCase);

        public IEnumerable<string> Labels => sources.Select(s => s.label);

        public void Add(string spec)
        {
            bool rec = spec.EndsWith("/**") || spec.EndsWith("\\**");
            string path = rec ? spec[..^3] : spec;
            try
            {
                if (Directory.Exists(path))
                {
                    var idx = new Dictionary<string, List<string>>(StringComparer.OrdinalIgnoreCase);
                    foreach (var f in Directory.EnumerateFiles(path, "*", rec ? SearchOption.AllDirectories : SearchOption.TopDirectoryOnly))
                    {
                        if (!Exts.Contains(Path.GetExtension(f).ToLowerInvariant())) continue;
                        string stem = Path.GetFileNameWithoutExtension(f);
                        if (stem.EndsWith(".bftex", StringComparison.OrdinalIgnoreCase)) stem = stem[..^6];   // "x.bftex.png"
                        (idx.TryGetValue(stem, out var l) ? l : idx[stem] = new List<string>()).Add(f);
                    }
                    sources.Add((Path.GetFullPath(path) + (rec ? " (with subfolders)" : ""), null, idx));
                }
                else if (File.Exists(path))
                {
                    var d = new Dictionary<string, Texture>(StringComparer.OrdinalIgnoreCase);
                    foreach (var t in TextureSource.Load(path)) d.TryAdd(t.Name, t);
                    sources.Add((Path.GetFullPath(path), d, null));
                }
                else Warnings.Add($"Texture source not found: {path}");
            }
            catch (Exception e) { Warnings.Add($"Could not read texture source {path}: {e.Message}"); }
        }

        /// <summary>Toolbox/OS copies sometimes get suffixes: "name (1)", "name_0", "name.0", "name#0".</summary>
        static string StripSuffix(string s) => Regex.Replace(s, @"(\s*\(\d+\)|[_.#]\d+)$", "");

        readonly Dictionary<string, FoundTexture?> cache = new(StringComparer.OrdinalIgnoreCase);

        public FoundTexture? Find(string name)
        {
            if (string.IsNullOrEmpty(name)) return null;
            if (cache.TryGetValue(name, out var c)) return c;
            FoundTexture? r = null;
            foreach (var (label, files, dir) in sources)
            {
                if (files != null && files.TryGetValue(name, out var t)) { r = new FoundTexture { Name = name, Native = t, Origin = label }; break; }
                if (dir == null) continue;
                var hits = dir.TryGetValue(name, out var l) ? l : dir.Where(kv => StripSuffix(kv.Key).Equals(name, StringComparison.OrdinalIgnoreCase)).SelectMany(kv => kv.Value).ToList();
                if (hits.Count > 1)
                {
                    Duplicates.Add(name);
                    Warnings.Add($"Duplicate texture '{name}' skipped (rename or remove one): {string.Join(" | ", hits.Select(Path.GetFullPath))}");
                    r = null; cache[name] = null; return null;   // never guess between duplicates
                }
                if (hits.Count == 1)
                {
                    try { r = LoadFile(hits[0], name); break; }
                    catch (Exception e) { Warnings.Add($"Could not read {hits[0]}: {e.Message}"); }
                }
            }
            cache[name] = r;
            return r;
        }

        static FoundTexture LoadFile(string f, string name)
        {
            string ext = Path.GetExtension(f).ToLowerInvariant();
            var ft = new FoundTexture { Name = name, Origin = Path.GetFullPath(f) };
            if (ext == ".bftex")
            {
                var t = new Texture();
                using (var s = new MemoryStream(BfresIO.ReadMaybeYaz0(f))) t.Import(s, true);
                t.Name = name;
                ft.Native = t;
            }
            else if (ext == ".dds") ft.Image = Dds.Load(f);
            else ft.Image = ImageIO.Load(f);
            return ft;
        }

        /// <summary>Decoded RGBA (for previews), or null if the native format can't be decoded.</summary>
        public static RgbaImage? Decode(FoundTexture ft) =>
            ft.Image ?? (ft.Native != null ? BntxTextures.DecodeToRgba(new BfresLibrary.Switch.SwitchTexture(BntxTextures.NewBntx(), ft.Native)) : null);
    }

    /// <summary>Minimal DDS reader: uncompressed RGBA/BGRA, DXT1/DXT3?(no)/DXT5, ATI1/BC4, ATI2/BC5, DX10 BC1-5 (mip 0 only).</summary>
    public static class Dds
    {
        public static RgbaImage Load(string path)
        {
            var d = File.ReadAllBytes(path);
            if (d.Length < 128 || d[0] != 'D' || d[1] != 'D' || d[2] != 'S') throw new InvalidDataException("not a DDS");
            int h = BitConverter.ToInt32(d, 12), w = BitConverter.ToInt32(d, 16);
            uint pfFlags = BitConverter.ToUInt32(d, 80); string four = System.Text.Encoding.ASCII.GetString(d, 84, 4);
            int bits = BitConverter.ToInt32(d, 88); int off = 128;
            if (four == "DX10")
            {
                uint dxgi = BitConverter.ToUInt32(d, 128); off = 148;
                four = dxgi switch { 71 or 72 => "DXT1", 77 or 78 => "DXT5", 80 => "ATI1", 81 => "BC4S", 83 => "ATI2", 84 => "BC5S", 28 or 29 => "RGBA", 87 or 91 => "BGRA", _ => "?" + dxgi };
            }
            byte[] px;
            var data = d.Skip(off).ToArray();
            switch (four)
            {
                case "DXT1": px = BcCodec.Decode(data, w, h, false); break;
                case "DXT5": px = BcCodec.Decode(data, w, h, true); break;
                case "ATI1": case "BC4U": px = BcCodec.DecodeBc45(data, w, h, false, false); break;
                case "BC4S": px = BcCodec.DecodeBc45(data, w, h, false, true); break;
                case "ATI2": case "BC5U": px = BcCodec.DecodeBc45(data, w, h, true, false); break;
                case "BC5S": px = BcCodec.DecodeBc45(data, w, h, true, true); break;
                case "RGBA": px = data.Take(w * h * 4).ToArray(); break;
                default:
                    if ((pfFlags & 0x40) != 0 && bits == 32)   // uncompressed; assume BGRA masks
                    { px = data.Take(w * h * 4).ToArray(); for (int i = 0; i < px.Length; i += 4) (px[i], px[i + 2]) = (px[i + 2], px[i]); }
                    else if (four == "BGRA") { px = data.Take(w * h * 4).ToArray(); for (int i = 0; i < px.Length; i += 4) (px[i], px[i + 2]) = (px[i + 2], px[i]); }
                    else throw new InvalidDataException($"unsupported DDS format {four}");
                    break;
            }
            return new RgbaImage { Width = w, Height = h, Pixels = px };
        }
    }
}
