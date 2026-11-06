using BfresLibrary;
using BfresLibrary.Switch;
using Mk8SzsTool.Commands;
using Mk8SzsTool.Export;
using Mk8SzsTool.Formats;
using Mk8SzsTool.Materials;

void Check(bool ok, string text) { Console.WriteLine($"CHECK {text}: {(ok ? "PASS" : "FAIL")}"); if (!ok) throw new Exception(text); }
string dir = Path.Combine(Path.GetTempPath(), "mk8dx_lighting_tests"); Directory.CreateDirectory(dir);
string template = Path.Combine(dir, "template.szs"); TestTemplate.Make(template);
var source = BfresIO.Load(template);
var plain = source.Models[0].Materials[0];
plain.ShaderAssign.ShaderOptions.Add("gsys_normalmap_BC1", "0");
plain.ShaderAssign.ShaderOptions.Add("enable_emission", "0");
plain.ShaderAssign.ShaderOptions.Add("enable_diffuse", "1");
foreach (var sampler in new[] { "_b1", "_n0" }) {
 plain.Samplers.Add(sampler, new Sampler { Name = sampler, TexSampler = new BfresLibrary.GX2.TexSampler() });
 plain.TextureRefs.Add(new TextureRef { Name = "orig_bake" });
 plain.ShaderAssign.SamplerAssigns.Add(sampler, sampler);
}
// Bake1 is deliberately remapped: physical names must not override shader semantics.
plain.ShaderAssign.SamplerAssigns["_b1"] = "light_slot";
plain.Samplers.Rename("_b1", "light_slot");
plain.Samplers["light_slot"].Name = "light_slot";
var glow = MaterialTemplates.Clone(source, plain, "glow");
glow.ShaderAssign.ShaderOptions["enable_emission"] = "1";
var helper = MaterialTemplates.Clone(source, plain, "helper");
var ri = new RenderInfo { Name = "gsys_cube_map_only" }; ri.SetValue(new[] { "1" }); helper.RenderInfos.Add(ri.Name, ri);
source.Models[0].Materials.Clear();
source.Models[0].Materials.Add("glow", glow); source.Models[0].Materials.Add("helper", helper); source.Models[0].Materials.Add(plain.Name, plain);
Check(MaterialTemplates.AutoPick(source, false).mat == plain, "automatic selection avoids emissive and helper surfaces");
BfresIO.Save(source, template, true);
var man = new Manifest { Base = template, Materials = { new MaterialEntry { Name = "Road", Template = plain.Name } } };
var builder = new CourseBuilder(man, dir, Console.WriteLine);
var result = builder.Build();
string output = Path.Combine(dir, "result.szs"); BfresIO.Save(result, output, true); result = BfresIO.Load(output);
var mat = result.Models[0].Materials[0];
string Texture(string slot) => mat.TextureRefs[mat.Samplers.IndexOf(slot)].Name;
byte[] Pixel(string name) => BntxTextures.DecodeToRgba((SwitchTexture)result.Textures[name]).Pixels.Take(4).ToArray();
Check(Pixel(Texture("_b0")).SequenceEqual(new byte[] {255,255,255,255}), "shadow and AO remain unoccluded");
Check(Pixel(Texture("light_slot")).Take(3).All(v => v == 0), "baked light contributes zero, including remapped samplers");
Check(Pixel(Texture("_n0")).Take(2).All(v => v == 0), "signed-style flat normal has zero XY");
Check(MaterialTemplates.Map(mat.ShaderAssign.ShaderOptions).OrderBy(k=>k.Key).SequenceEqual(MaterialTemplates.Map(plain.ShaderAssign.ShaderOptions).OrderBy(k=>k.Key)), "compiled shader options unchanged");
// Re-exporting an old file must replace stale reserved neutral normal data.
man.Base = output; result = new CourseBuilder(man, dir, Console.WriteLine).Build();
Check(BntxTextures.DecodeToRgba((SwitchTexture)result.Textures["mk8exp_flat_normal_xy"]).Pixels[0] == 0, "re-export keeps corrected normal");
man.Base = template; man.NeutralOtherSamplers = false;
result = new CourseBuilder(man, dir, Console.WriteLine).Build();
Check(result.Models[0].Materials[0].TextureRefs.Any(t => t.Name == "orig_bake"), "keeping original maps is still supported");
// BC1-style flat normal uses unsigned mid-grey without BC quantization bias.
foreach (var m in source.Models[0].Materials.Values) m.ShaderAssign.ShaderOptions["gsys_normalmap_BC1"] = "1";
BfresIO.Save(source, template, true); man.NeutralOtherSamplers = true;
result = new CourseBuilder(man, dir, Console.WriteLine).Build();
Check(BntxTextures.DecodeToRgba((SwitchTexture)result.Textures["mk8exp_flat_normal"]).Pixels.Take(4).SequenceEqual(new byte[] {128,128,255,255}), "unsigned flat normal preserves exact channel values");
// A foreign material's normal packing can change during compatibility adaptation.
var foreign = MaterialTemplates.Clone(source, plain, "Foreign");
foreign.ShaderAssign.ShaderOptions["gsys_normalmap_BC1"] = "0";
string bfmat = Path.Combine(dir, "foreign.bfmat"); foreign.Export(bfmat, source);
man.Materials[0].Bfmat = bfmat;
result = new CourseBuilder(man, dir, Console.WriteLine).Build();
Check(result.Models[0].Materials[0].ShaderAssign.ShaderOptions["gsys_normalmap_BC1"].String == "1", "foreign options adapted to supported variation");
Check(result.Textures.ContainsKey("mk8exp_flat_normal"), "flat normal chosen after shader adaptation");
Check(BntxTextures.DecodeToRgba((SwitchTexture)result.Textures["mk8exp_flat_normal"]).Pixels[0] == 128, "adapted normal encoding is unsigned");
Console.WriteLine("RESULT: ALL PASS");
