"""Robust path handling and file placement (Windows-safe)."""
import os
import re
import shutil
import time


def norm(p):
    """Expand ~ and %VARS%, resolve Blender // paths, make absolute + normalised."""
    if not p:
        return ""
    p = p.strip().strip('"')
    try:
        import bpy
        p = bpy.path.abspath(p)
    except Exception:
        pass
    p = os.path.expandvars(os.path.expanduser(p))
    return os.path.normpath(os.path.abspath(p))


def course_from_path(path):
    """'...\\romfs\\course\\Gu_Expert\\course_model.szs' -> 'Gu_Expert' (handles / and \\), else ''."""
    parts = [x for x in re.split(r"[\\/]+", path or "") if x]
    for i in range(len(parts) - 1, 0, -1):
        if parts[i - 1].lower() == "course" and parts[i].lower().startswith("gu_"):
            return parts[i]
    m = next((x for x in reversed(parts[:-1]) if x.lower().startswith("gu_")), "")
    return m


def place(src, dst, retries=6, delay=0.5, backup_original=False, create_dirs=True):
    """Copy src to dst atomically: temp file in the destination folder, then os.replace.
    Retries when the target is locked (OneDrive/Ryujinx/antivirus). Verifies size afterwards.
    Returns (ok, message)."""
    dst = os.path.normpath(os.path.abspath(dst))
    want = os.path.getsize(src)
    if not create_dirs:
        if not os.path.isdir(os.path.dirname(dst)):
            return False, f"folder does not exist: {os.path.dirname(dst)} (not created)"
    else:
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
        except OSError as e:
            return False, f"cannot create folder {os.path.dirname(dst)}: {e}"
    if backup_original and os.path.isfile(dst):
        bak = dst + ".orig"
        if not os.path.exists(bak):
            try:
                shutil.copy2(dst, bak)
            except OSError as e:
                return False, f"cannot back up original to {bak}: {e}"
    tmp = dst + ".mk8tmp"
    last = None
    for attempt in range(retries):
        try:
            shutil.copyfile(src, tmp)
            os.replace(tmp, dst)
            last = None
            break
        except OSError as e:
            last = e
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass
            time.sleep(delay)
    if last is not None:
        return False, (f"could not write {dst}: {last}. Is the file open/locked (Ryujinx running a game, "
                       f"OneDrive syncing, Switch Toolbox)? Close it and export again.")
    if not os.path.isfile(dst):
        return False, f"{dst} does not exist after writing"
    got = os.path.getsize(dst)
    if got != want:
        return False, f"{dst} has {got} bytes, expected {want}"
    return True, dst
