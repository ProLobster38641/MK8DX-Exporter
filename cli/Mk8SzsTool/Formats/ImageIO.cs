using System;
using System.IO;
using StbImageSharp;

namespace Mk8SzsTool.Formats
{
    public class RgbaImage
    {
        public int Width, Height; public byte[] Pixels = Array.Empty<byte>(); // RGBA8, top row first

        public bool HasAlpha()
        {
            for (int i = 3; i < Pixels.Length; i += 4) if (Pixels[i] < 250) return true;
            return false;
        }
    }

    public static class ImageIO
    {
        /// <summary>Loads PNG/JPG/TGA/BMP (StbImageSharp) or the add-on's raw ".rgba" dump ("RGBA" + u32 w + u32 h + pixels, top-down).</summary>
        public static RgbaImage Load(string path)
        {
            var bytes = File.ReadAllBytes(path);
            if (bytes.Length > 12 && bytes[0] == 'R' && bytes[1] == 'G' && bytes[2] == 'B' && bytes[3] == 'A')
            {
                int w = BitConverter.ToInt32(bytes, 4), h = BitConverter.ToInt32(bytes, 8);
                var px = new byte[w * h * 4]; Buffer.BlockCopy(bytes, 12, px, 0, px.Length);
                return new RgbaImage { Width = w, Height = h, Pixels = px };
            }
            var img = ImageResult.FromMemory(bytes, ColorComponents.RedGreenBlueAlpha);
            return new RgbaImage { Width = img.Width, Height = img.Height, Pixels = img.Data };
        }

        public static void SaveRaw(string path, RgbaImage img)
        {
            using var w = new BinaryWriter(File.Create(path));
            w.Write(new[] { (byte)'R', (byte)'G', (byte)'B', (byte)'A' }); w.Write(img.Width); w.Write(img.Height); w.Write(img.Pixels);
        }

        static readonly float[] SrgbToLin = BuildLut();
        static float[] BuildLut()
        {
            var t = new float[256];
            for (int i = 0; i < 256; i++) { double c = i / 255.0; t[i] = (float)(c <= 0.04045 ? c / 12.92 : Math.Pow((c + 0.055) / 1.055, 2.4)); }
            return t;
        }
        static byte LinToSrgb(double l)
        {
            double c = l <= 0.0031308 ? l * 12.92 : 1.055 * Math.Pow(l, 1 / 2.4) - 0.055;
            return (byte)Math.Clamp(Math.Round(c * 255), 0, 255);
        }

        /// <summary>2x box downsample (gamma-correct for sRGB colour channels).</summary>
        public static RgbaImage Downsample(RgbaImage s, bool srgb)
        {
            int w = Math.Max(1, s.Width / 2), h = Math.Max(1, s.Height / 2);
            var d = new byte[w * h * 4];
            for (int y = 0; y < h; y++)
                for (int x = 0; x < w; x++)
                    for (int c = 0; c < 4; c++)
                    {
                        double acc = 0; int n = 0;
                        for (int dy = 0; dy < 2; dy++)
                            for (int dx = 0; dx < 2; dx++)
                            {
                                int sx = Math.Min(x * 2 + dx, s.Width - 1), sy = Math.Min(y * 2 + dy, s.Height - 1);
                                byte v = s.Pixels[(sy * s.Width + sx) * 4 + c];
                                acc += (srgb && c < 3) ? SrgbToLin[v] : v; n++;
                            }
                        acc /= n;
                        d[(y * w + x) * 4 + c] = (srgb && c < 3) ? LinToSrgb(acc) : (byte)Math.Round(acc);
                    }
            return new RgbaImage { Width = w, Height = h, Pixels = d };
        }
    }
}
