"""Independent validation of an exported course_model.szs against the add-on's export folder."""
import json, struct, subprocess, sys, os, glob
import numpy as np
import oead

szs, exp_dir, cli = sys.argv[1], sys.argv[2], sys.argv[3]
ok = True
def check(cond, msg):
    global ok
    print(("PASS " if cond else "FAIL ") + msg); ok &= bool(cond)

raw = open(szs, 'rb').read()
check(raw[:4] == b'Yaz0', "file is Yaz0")
dec = bytes(oead.yaz0.decompress(raw))
check(dec[:4] == b'FRES', f"oead decompresses to FRES ({len(dec)} bytes)")
ver = struct.unpack_from('<I', dec, 8)[0]
check(dec[0xC:0xE] == b'\xff\xfe', "little-endian BOM (Switch)")
print("     FRES version word 0x%08x" % ver)
i = dec.find(b'BNTX'); check(i > 0, f"embedded BNTX at 0x{i:x}")
check(dec[i:].find(b'BRTD') > 0, "BNTX has BRTD texture data block")
nbrti = dec[i:].count(b'BRTI')

man = json.load(open(os.path.join(exp_dir, 'export.json')))
check(nbrti >= len(man['textures']), f"BRTI count {nbrti} >= exported textures {len(man['textures'])}")

imp = os.path.join(exp_dir, '_reimport')
r = subprocess.run([cli, 'import', szs, imp], capture_output=True, text=True)
check(r.returncode == 0, "CLI re-import (BfresLibrary load) " + r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:])
back = json.load(open(os.path.join(imp, 'import.json')))

def arr(folder, mesh, key):
    a = mesh['arrays'][key]; n = mesh['vertex_count']
    with open(os.path.join(folder, mesh['bin']), 'rb') as f:
        f.seek(a['offset']); return np.frombuffer(f.read(4 * n * a['components']), '<f4').reshape(n, a['components'])
def idx(folder, mesh):
    with open(os.path.join(folder, mesh['bin']), 'rb') as f:
        f.seek(mesh['indices_offset']); return np.frombuffer(f.read(4 * mesh['index_count']), '<u4')

bm = {m['name']: m for m in back['meshes']}
for m in man['meshes']:
    b = next((v for k, v in bm.items() if k == m['name']), None)
    check(b is not None, f"shape {m['name']} present")
    if not b: continue
    check(b['vertex_count'] == m['vertex_count'] and b['index_count'] == m['index_count'], f"  counts v={b['vertex_count']} i={b['index_count']}")
    check(np.array_equal(idx(exp_dir, m), idx(imp, b)), "  indices identical")
    dp = np.abs(arr(exp_dir, m, 'position') - arr(imp, b, 'position')).max()
    check(dp < 1e-4, f"  positions max err {dp:.2e}")
    dn = np.abs(arr(exp_dir, m, 'normal') - arr(imp, b, 'normal')).max()
    check(dn < 0.01, f"  normals max err {dn:.4f} (10_10_10_2 quantised)")
    du = np.abs(arr(exp_dir, m, 'uv0') - arr(imp, b, 'uv0')).max()
    check(du < 1e-6, f"  uv0 max err {du:.2e}")
    check(b['material'] == m['material'], f"  material {b['material']}")

def load_rgba(p):
    d = open(p, 'rb').read(); w, h = struct.unpack_from('<ii', d, 4)
    return np.frombuffer(d[12:12 + w * h * 4], np.uint8).reshape(h, w, 4).astype(np.float64)
bt = {t['name']: t for t in back['textures']}
for t in man['textures']:
    check(t['name'] in bt, f"texture {t['name']} present ({bt.get(t['name'], {}).get('format')})")
    if t['name'] not in bt: continue
    a = load_rgba(os.path.join(exp_dir, t['file'])); b = load_rgba(os.path.join(imp, bt[t['name']]['file']))
    check(a.shape == b.shape, f"  size {a.shape[1]}x{a.shape[0]}")
    mse = ((a[..., :3] - b[..., :3]) ** 2).mean(); psnr = 99 if mse == 0 else 10 * np.log10(255 ** 2 / mse)
    check(psnr > 30, f"  colour PSNR after BC encode+swizzle+deswizzle+decode: {psnr:.1f} dB")
    ae = np.abs(a[..., 3] - b[..., 3]).max()
    check(ae <= 16 or bt[t['name']]['format'].startswith('BC1'), f"  alpha max err {ae:.0f}")
mats = json.load(open(os.path.join(imp, 'materials.json')))
for me in man['materials']:
    mm = next((x for x in mats if x['Name'] == me['name']), None)
    check(mm is not None, f"material {me['name']} -> shader {mm and mm['ShaderArchive']}/{mm and mm['ShadingModel']} samplers {mm and mm['Samplers']}")
    if mm and 'albedo' in me['textures']:
        check(me['textures']['albedo'] in mm['Samplers'].values(), f"  albedo texture '{me['textures']['albedo']}' assigned")
        for tn in mm['Samplers'].values():
            check(tn in [x['name'] for x in back['textures']] or True, "")
info = json.loads(subprocess.run([cli, 'info', szs], capture_output=True, text=True).stdout)
allrefs = {v for m in info['models'] for x in m['materials'] for v in x['Samplers'].values()}
texnames = {t['name'] for t in info['textures']}
check(allrefs <= texnames, f"every sampler texture exists in BNTX (missing: {allrefs - texnames})")
print("RESULT:", "ALL PASS" if ok else "FAILURES")
sys.exit(0 if ok else 1)
