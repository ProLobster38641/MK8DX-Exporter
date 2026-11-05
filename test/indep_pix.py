import bpy, sys, addon_utils, numpy as np, struct
addon_utils.enable("bl_ext.user_default.io_scene_bfres", default_set=True)
a = sys.argv[sys.argv.index("--")+1:]
bpy.ops.wm.read_homefile(use_empty=True); bpy.ops.import_scene.bfres(filepath=a[0])
for name in a[1:]:
    i = bpy.data.images[name]; w, h = i.size
    px = np.empty(w*h*4, np.float32); i.pixels.foreach_get(px); px = px.reshape(h, w, 4)
    d = open(f"{a[0].rsplit('/',1)[0]}/{name}.rgba", "rb").read(); W, H = struct.unpack_from("<ii", d, 4)
    src = np.frombuffer(d[12:12+W*H*4], np.uint8).reshape(H, W, 4).astype(np.float64)
    best = []
    for flip in (False, True):
        b = (px[::-1] if flip else px) * 255
        mse = ((b[..., :3] - src[..., :3])**2).mean(); best.append((10*np.log10(255**2/max(mse,1e-9)), flip))
    print("PIX", name, "independent-decoder PSNR (best orientation):", max(best))
