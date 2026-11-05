using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Mk8SzsTool.Export
{
    /// <summary>Interchange written by the Blender add-on (export.json + geometry .bin + textures).</summary>
    public class Manifest
    {
        [JsonPropertyName("version")] public int Version { get; set; } = 1;
        [JsonPropertyName("model_name")] public string ModelName { get; set; } = "";
        /// <summary>Original course_model.szs (or any MK8DX .szs/.bfres). Used as base file and material/texture source.</summary>
        [JsonPropertyName("base")] public string? Base { get; set; }
        /// <summary>Optional extra template sources (.szs/.bfres/.bfmat) searched for materials.</summary>
        [JsonPropertyName("template_files")] public List<string> TemplateFiles { get; set; } = new();
        /// <summary>replace = drop original models, add ours. append = keep original models too.</summary>
        [JsonPropertyName("mode")] public string Mode { get; set; } = "replace";
        [JsonPropertyName("keep_animations")] public bool KeepAnimations { get; set; } = true;
        [JsonPropertyName("prune_textures")] public bool PruneTextures { get; set; } = true;
        [JsonPropertyName("neutral_other_samplers")] public bool NeutralOtherSamplers { get; set; } = true;
        [JsonPropertyName("force_repeat")] public bool ForceRepeat { get; set; } = true;
        [JsonPropertyName("allow_synthetic")] public bool AllowSynthetic { get; set; } = false;
        [JsonPropertyName("default_template")] public string? DefaultTemplate { get; set; }
        [JsonPropertyName("textures")] public List<TextureEntry> Textures { get; set; } = new();
        [JsonPropertyName("materials")] public List<MaterialEntry> Materials { get; set; } = new();
        [JsonPropertyName("meshes")] public List<MeshEntry> Meshes { get; set; } = new();

        public static Manifest Load(string path) =>
            JsonSerializer.Deserialize<Manifest>(File.ReadAllText(path)) ?? throw new InvalidDataException("bad manifest");
    }

    public class TextureEntry
    {
        [JsonPropertyName("name")] public string Name { get; set; } = "";
        [JsonPropertyName("file")] public string File { get; set; } = "";
        [JsonPropertyName("format")] public string Format { get; set; } = "auto";
        [JsonPropertyName("srgb")] public bool Srgb { get; set; } = true;
        [JsonPropertyName("mips")] public bool Mips { get; set; } = true;
    }

    public class MaterialEntry
    {
        [JsonPropertyName("name")] public string Name { get; set; } = "";
        /// <summary>Name of the material to clone from the base/template files (null = default_template).</summary>
        [JsonPropertyName("template")] public string? Template { get; set; }
        /// <summary>sampler -> texture name. Key "albedo" means "whatever the albedo sampler is (usually _a0)".</summary>
        [JsonPropertyName("textures")] public Dictionary<string, string> Textures { get; set; } = new();
        /// <summary>Blender material uses alpha (blend/clip). Forces an alpha-capable template in auto mode.</summary>
        [JsonPropertyName("alpha")] public bool Alpha { get; set; }
        /// <summary>Imported .bfmat to clone for this material (overrides template/auto).</summary>
        [JsonPropertyName("bfmat")] public string? Bfmat { get; set; }
        /// <summary>Files (.szs/.bfres/.bntx) holding the bfmat's original textures, copied in when still referenced.</summary>
        [JsonPropertyName("texture_sources")] public List<string> TextureSources { get; set; } = new();
    }

    public class ArrayRef
    {
        [JsonPropertyName("offset")] public long Offset { get; set; }
        [JsonPropertyName("components")] public int Components { get; set; }
    }

    public class MeshEntry
    {
        [JsonPropertyName("name")] public string Name { get; set; } = "";
        [JsonPropertyName("material")] public string Material { get; set; } = "";
        [JsonPropertyName("bin")] public string Bin { get; set; } = "geometry.bin";
        [JsonPropertyName("vertex_count")] public int VertexCount { get; set; }
        [JsonPropertyName("index_count")] public int IndexCount { get; set; }
        /// <summary>float32 arrays: "position","normal","tangent","uv0","uv1",...,"color0"</summary>
        [JsonPropertyName("arrays")] public Dictionary<string, ArrayRef> Arrays { get; set; } = new();
        [JsonPropertyName("indices_offset")] public long IndicesOffset { get; set; }
    }
}
