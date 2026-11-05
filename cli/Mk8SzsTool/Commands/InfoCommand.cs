using System.Collections.Generic;
using System.Linq;
using BfresLibrary;
using BfresLibrary.Helpers;
using BfresLibrary.Switch;
using Mk8SzsTool.Materials;

namespace Mk8SzsTool.Commands
{
    /// <summary>Structured summary of a BFRES, used for validation and by the add-on's material picker.</summary>
    public static class InfoCommand
    {
        public static object Describe(ResFile res)
        {
            return new
            {
                name = res.Name, platform_switch = res.IsPlatformSwitch, version = $"{res.VersionMajor}.{res.VersionMajor2}.{res.VersionMinor}.{res.VersionMinor2}",
                models = res.Models.Values.Select(m => new
                {
                    name = m.Name, bones = m.Skeleton.Bones.Count,
                    shapes = m.Shapes.Values.Select(s =>
                    {
                        var vb = m.VertexBuffers[s.VertexBufferIndex];
                        var h = new VertexBufferHelper(vb, res.ByteOrder);
                        var uv = h.Contains("_u0") ? h["_u0"].Data : null;
                        return new
                        {
                            name = s.Name, material = m.Materials[s.MaterialIndex].Name, vertex_count = vb.VertexCount,
                            attributes = vb.Attributes.Values.Select(a => $"{a.Name}:{a.Format}").ToList(),
                            index_count = s.Meshes[0].IndexCount, index_format = s.Meshes[0].IndexFormat.ToString(),
                            max_index = s.Meshes[0].GetIndices().DefaultIfEmpty().Max(),
                            radius = s.RadiusArray.FirstOrDefault(),
                            uv0_range = uv == null ? null : new[] { uv.Min(v => v.X), uv.Max(v => v.X), uv.Min(v => v.Y), uv.Max(v => v.Y) },
                        };
                    }).ToList(),
                    materials = m.Materials.Values.Select(x => MaterialTemplates.Describe(m, x)).ToList(),
                }).ToList(),
                textures = res.Textures.Keys.Select(k => new { Key = k, Value = res.Textures[k] }).Select(kv => kv.Value is SwitchTexture st ? new
                {
                    name = kv.Key, width = st.Texture.Width, height = st.Texture.Height, format = st.Texture.Format.ToString(),
                    mips = st.Texture.MipCount, mip_data_count = st.Texture.TextureData[0].Count, mip_offsets = st.Texture.MipOffsets, block_height_log2 = st.Texture.BlockHeightLog2, image_size = st.Texture.ImageSize,
                } : null).Where(x => x != null).ToList(),
                external_files = res.ExternalFiles.Keys.ToList(),
                anims = new { skeletal = res.SkeletalAnims.Count, tex_srt = res.TexSrtAnims.Count, shader_param = res.ShaderParamAnims.Count, tex_pattern = res.TexPatternAnims.Count },
            };
        }
    }
}
