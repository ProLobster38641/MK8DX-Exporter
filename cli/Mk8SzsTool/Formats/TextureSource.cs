using BfresLibrary;
using BfresLibrary.Switch;
using Syroot.NintenTools.NSW.Bntx;

namespace Mk8SzsTool.Formats
{
    /// <summary>Textures from a .szs/.bfres (embedded BNTX) or a standalone .bntx (optionally Yaz0).</summary>
    public static class TextureSource
    {
        public static List<Texture> Load(string path)
        {
            var d = BfresIO.ReadMaybeYaz0(path);
            if (d.Length >= 4 && d[0] == 'B' && d[1] == 'N' && d[2] == 'T' && d[3] == 'X')
                return new BntxFile(new MemoryStream(d)).Textures.ToList();
            var res = BfresIO.Load(path);
            return res.Textures.Values.OfType<SwitchTexture>().Select(t => t.Texture).ToList();
        }

    }
}
