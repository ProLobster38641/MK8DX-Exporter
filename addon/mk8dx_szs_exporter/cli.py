"""Locate and run the bundled mk8szs command line tool."""
import json
import os
import subprocess
import sys

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))


def addon_prefs(context):
    pkg = __package__
    addon = context.preferences.addons.get(pkg)
    return addon.preferences if addon else None


def cli_path(context):
    p = addon_prefs(context)
    if p and p.cli_override and os.path.isfile(bpy_abspath(p.cli_override)):
        return bpy_abspath(p.cli_override)
    exe = "mk8szs.exe" if sys.platform.startswith("win") else "mk8szs"
    cand = os.path.join(ADDON_DIR, "bin", exe)
    if os.path.isfile(cand):
        if not sys.platform.startswith("win"):
            try:
                os.chmod(cand, 0o755)
            except OSError:
                pass
        return cand
    raise FileNotFoundError(f"mk8szs tool not found at {cand}. Reinstall the add-on zip or set the CLI path in the add-on preferences.")


def bpy_abspath(p):
    import bpy
    return os.path.normpath(bpy.path.abspath(p)) if p else p


def run(context, args, timeout=1800):
    exe = cli_path(context)
    kw = {}
    if sys.platform.startswith("win"):
        kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    proc = subprocess.run([exe] + list(args), capture_output=True, text=True, timeout=timeout, **kw)
    return proc.returncode, proc.stdout, proc.stderr


def list_materials(context, szs_path):
    code, out, err = run(context, ["materials", szs_path, "--json"], timeout=600)
    if code != 0:
        raise RuntimeError((err or out).strip().splitlines()[0] if (err or out).strip() else "mk8szs failed")
    return json.loads(out)
