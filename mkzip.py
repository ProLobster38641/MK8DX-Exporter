import sys, os, zipfile
src, out = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk(src):
        for f in files:
            if f.endswith('.pyc') or '__pycache__' in root: continue
            p = os.path.join(root, f)
            info = zipfile.ZipInfo.from_file(p, os.path.relpath(p, os.path.dirname(src)))
            with open(p, 'rb') as fh: z.writestr(info, fh.read(), zipfile.ZIP_DEFLATED)
