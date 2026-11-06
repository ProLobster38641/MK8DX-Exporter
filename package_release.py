"""Package the Windows add-on and source without fixtures or generated build files."""
import pathlib
import shutil
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
NAME = "mk8dx_szs_exporter"

def archive(folder, destination):
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo.from_file(path, path.relative_to(folder.parent).as_posix())
                z.writestr(info, path.read_bytes(), zipfile.ZIP_DEFLATED)

def main():
    dist = ROOT / "dist"; dist.mkdir(exist_ok=True)
    executable = ROOT / "cli/publish/win-x64/mk8szs.exe"
    if not executable.is_file():
        raise SystemExit("Build the Windows backend first (see README).")
    with tempfile.TemporaryDirectory(prefix="mk8dx_release_") as tmp:
        tmp = pathlib.Path(tmp)
        addon = tmp / "windows" / NAME
        shutil.copytree(ROOT / "addon" / NAME, addon, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "bin"))
        (addon / "bin").mkdir()
        shutil.copy2(executable, addon / "bin/mk8szs.exe")
        for name in ("LICENSE", "THIRD_PARTY_NOTICES.txt"):
            shutil.copy2(ROOT / name, addon / name)
        archive(addon, dist / f"{NAME}_windows_1.1.zip")
        source = tmp / "source" / NAME; source.mkdir(parents=True)
        for name in ("README.md", "ARCHITECTURE.md", "LICENSE", "THIRD_PARTY_NOTICES.txt", ".gitignore", "mkzip.py", "package_release.py"):
            shutil.copy2(ROOT / name, source / name)
        shutil.copytree(ROOT / "addon", source / "addon", ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "bin"))
        shutil.copytree(ROOT / "cli/Mk8SzsTool", source / "cli/Mk8SzsTool", ignore=shutil.ignore_patterns("bin", "obj", "*.pdb"))
        (source / "test/LightingTests").mkdir(parents=True)
        for pattern in ("*.py", "*.sh"):
            for path in (ROOT / "test").glob(pattern):
                shutil.copy2(path, source / "test" / path.name)
        for pattern in ("*.cs", "*.csproj"):
            for path in (ROOT / "test/LightingTests").glob(pattern):
                shutil.copy2(path, source / "test/LightingTests" / path.name)
        archive(source, dist / f"{NAME}_source_1.1.zip")
    for path in sorted(dist.glob("*1.1.zip")):
        print(path)

if __name__ == "__main__":
    main()
