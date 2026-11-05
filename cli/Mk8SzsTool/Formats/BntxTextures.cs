using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using BfresLibrary;
using BfresLibrary.Switch;
using Syroot.NintenTools.NSW.Bntx;
using Syroot.NintenTools.NSW.Bntx.GFX;

namespace Mk8SzsTool.Formats
{
    /// <summary>Create / read BNTX textures embedded in a Switch BFRES ("textures.bntx" external file).</summary>
    public static class BntxTextures
    {
        public static BntxFile NewBntx(string name = "textures") => new BntxFile
        {
            Target = new[] { 'N', 'X', ' ', ' ' }, Name = name, Alignment = 0xC, TargetAddressSize = 0x40,
            VersionMajor = 0, VersionMajor2 = 4, VersionMinor = 0, VersionMinor2 = 0,
            Textures = new List<Texture>(), TextureDict = new Syroot.NintenTools.NSW.Bntx.ResDict(),
            RelocationTable = new RelocationTable(), Flag = 0,
        };

        /// <summary>Returns the BNTX attached to the res file, creating "textures.bntx" when missing.</summary>
        public static BntxFile GetOrCreate(ResFile res)
        {
            foreach (var ext in res.ExternalFiles)
                if (ext.Key.EndsWith(".bntx") && ext.Value.LoadedFileData is BntxFile b) return b;
            var bntx = NewBntx(string.IsNullOrEmpty(res.Name) ? "textures" : res.Name);
            res.ExternalFiles.Add("textures.bntx", new ExternalFile { Data = new byte[0], LoadedFileData = bntx });
            return bntx;
        }

        public static SurfaceFormat ParseFormat(string fmt, RgbaImage img, bool srgbDefault)
        {
            switch ((fmt ?? "auto").ToUpperInvariant())
            {
                case "BC1_SRGB": return SurfaceFormat.BC1_SRGB;
                case "BC1_UNORM": return SurfaceFormat.BC1_UNORM;
                case "BC3_SRGB": return SurfaceFormat.BC3_SRGB;
                case "BC3_UNORM": return SurfaceFormat.BC3_UNORM;
                case "RGBA8_SRGB": return SurfaceFormat.R8_G8_B8_A8_SRGB;
                case "RGBA8_UNORM": return SurfaceFormat.R8_G8_B8_A8_UNORM;
                case "AUTO_UNORM": return img.HasAlpha() ? SurfaceFormat.BC3_UNORM : SurfaceFormat.BC1_UNORM;
                default: // auto
                    bool a = img.HasAlpha();
                    return srgbDefault ? (a ? SurfaceFormat.BC3_SRGB : SurfaceFormat.BC1_SRGB)
                                       : (a ? SurfaceFormat.BC3_UNORM : SurfaceFormat.BC1_UNORM);
            }
        }

        static bool IsSrgb(SurfaceFormat f) => f == SurfaceFormat.BC1_SRGB || f == SurfaceFormat.BC3_SRGB || f == SurfaceFormat.R8_G8_B8_A8_SRGB;
        static bool IsBc3(SurfaceFormat f) => f == SurfaceFormat.BC3_SRGB || f == SurfaceFormat.BC3_UNORM;
        static bool IsRgba8(SurfaceFormat f) => f == SurfaceFormat.R8_G8_B8_A8_SRGB || f == SurfaceFormat.R8_G8_B8_A8_UNORM;

        public static uint AutoMipCount(int w, int h)
        {
            uint n = 1; int m = Math.Min(w, h);
            while ((m >> (int)n) >= 4) n++;
            return n;
        }

        public static Texture Create(string name, RgbaImage img, SurfaceFormat fmt, bool mips, BntxFile parent)
        {
            uint mipCount = mips ? AutoMipCount(img.Width, img.Height) : 1;
            var tex = new Texture
            {
                Name = name, Path = "", Width = (uint)img.Width, Height = (uint)img.Height, Depth = 1, ArrayLength = 1,
                MipCount = mipCount, Format = fmt, TileMode = TileMode.Default, Dim = Dim.Dim2D, SurfaceDim = SurfaceDim.Dim2D,
                AccessFlags = AccessFlags.Texture, Swizzle = 0, SampleCount = 1, Pitch = 32,
                ChannelRed = ChannelType.Red, ChannelGreen = ChannelType.Green, ChannelBlue = ChannelType.Blue,
                ChannelAlpha = ChannelType.Alpha, Regs = new uint[0], textureLayout = 0, textureLayout2 = 0x010007,
                UserData = new List<Syroot.NintenTools.NSW.Bntx.UserData>(), UserDataDict = new Syroot.NintenTools.NSW.Bntx.ResDict(),
                TextureData = new List<List<byte[]>> { Enumerable.Range(0, (int)mipCount).Select(_ => new byte[0]).ToList() },
            };
            var surf = new MemoryStream();
            var cur = img;
            bool srgb = IsSrgb(fmt);
            for (int m = 0; m < mipCount; m++)
            {
                if (m > 0) cur = ImageIO.Downsample(cur, srgb);
                surf.Write(IsRgba8(fmt) ? cur.Pixels : BcCodec.Encode(cur.Pixels, cur.Width, cur.Height, IsBc3(fmt)));
            }
            var sw = new SwitchTexture(parent, tex);
            sw.SwizzleImage(surf.ToArray(), 0);
            // Like Switch Toolbox: [0] holds all mips combined; the list length is the mip count the BNTX writer uses.
            // Fill the other slots with the per-mip slices so any reader that walks them gets real data.
            for (int m = 1; m < mipCount; m++)
            {
                long start = tex.MipOffsets[m], end = m + 1 < mipCount ? tex.MipOffsets[m + 1] : tex.TextureData[0][0].Length;
                tex.TextureData[0][m] = tex.TextureData[0][0].Skip((int)start).Take((int)(end - start)).ToArray();
            }
            return tex;
        }

        public static void AddOrReplace(ResFile res, Texture tex)
        {
            var bntx = GetOrCreate(res);
            int idx = bntx.TextureDict.IndexOf(tex.Name);
            if (idx >= 0) bntx.Textures[idx] = tex;
            else { bntx.Textures.Add(tex); bntx.TextureDict.Add(tex.Name); }
            if (res.Textures.ContainsKey(tex.Name)) res.Textures.RemoveKey(tex.Name);
            res.Textures.Add(tex.Name, new SwitchTexture(bntx, tex));
        }

        public static void Remove(ResFile res, string name)
        {
            var bntx = GetOrCreate(res);
            int idx = bntx.TextureDict.IndexOf(name);
            if (idx >= 0) { bntx.Textures.RemoveAt(idx); bntx.TextureDict.Remove(name); }
            if (res.Textures.ContainsKey(name)) res.Textures.RemoveKey(name);
        }

        /// <summary>Decodes mip 0 back to RGBA8 (BC1/BC3/RGBA8). Used for validation and the future importer.</summary>
        public static RgbaImage? DecodeToRgba(SwitchTexture st)
        {
            var t = st.Texture;
            if (t.Format is SurfaceFormat.BC4_UNORM or SurfaceFormat.BC4_SNORM or SurfaceFormat.BC5_UNORM or SurfaceFormat.BC5_SNORM)
            {
                var r45 = st.GetDeswizzledData(0, 0);
                bool bc5 = t.Format is SurfaceFormat.BC5_UNORM or SurfaceFormat.BC5_SNORM;
                return new RgbaImage { Width = (int)t.Width, Height = (int)t.Height,
                    Pixels = BcCodec.DecodeBc45(r45, (int)t.Width, (int)t.Height, bc5, t.Format is SurfaceFormat.BC4_SNORM or SurfaceFormat.BC5_SNORM) };
            }
            if (!(IsRgba8(t.Format) || t.Format == SurfaceFormat.BC1_SRGB || t.Format == SurfaceFormat.BC1_UNORM || IsBc3(t.Format)))
                return null;
            var raw = st.GetDeswizzledData(0, 0);
            var px = IsRgba8(t.Format) ? raw.Take((int)(t.Width * t.Height * 4)).ToArray()
                                       : BcCodec.Decode(raw, (int)t.Width, (int)t.Height, IsBc3(t.Format));
            return new RgbaImage { Width = (int)t.Width, Height = (int)t.Height, Pixels = px };
        }
    }
}
