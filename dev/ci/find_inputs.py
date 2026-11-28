#!/usr/bin/env python3
"""Search an unpacked download for what a build needs, at any depth.

  find_inputs.py <folder> [--json out.json] [--no-nested]

Looks for (names are matched without regard to case):
  *.pkg                       a game's (or its update's) PKG
  work.bin                    its licence (a NoNpDrm release keeps it beside the PKG)
  PSP2UPDAT.PUP, PSVUPDAT.PUP Sony's firmware update file (any *.PUP is taken as one)
  a game folder               sce_sys/param.sfo and eboot.bin together (a copy of ux0:app/<title>)

An archive inside the folder (.zip, and .7z / .rar when 7z or bsdtar is installed) is unpacked next to itself first,
once, so a zip of zips is found too. Prints one `kind<TAB>path` line per find, then a summary; exit status 1 when there
is neither a PKG nor a game folder to build from. Nothing here decrypts or reads the files' contents.
"""
import json
import os
import shutil
import subprocess
import sys
import zipfile

ARCHIVES = (".zip", ".7z", ".rar")
MAX_ROUNDS = 3   # archives within archives within archives


def unpack(path):
    """unpack one archive next to itself (<name>.unpacked); True when it worked"""
    dest = path + ".unpacked"
    if os.path.isdir(dest):
        return False
    try:
        if path.lower().endswith(".zip") and zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                z.extractall(dest)
            return True
    except (OSError, zipfile.BadZipFile, NotImplementedError) as e:
        print(f"  {path}: not unpacked ({e})", file=sys.stderr)
        return False
    for tool in (["7zz", "x", "-y"], ["7z", "x", "-y"], ["bsdtar", "-xf"]):
        if not shutil.which(tool[0]):
            continue
        os.makedirs(dest, exist_ok=True)
        cmd = tool + ([f"-o{dest}", path] if tool[0] != "bsdtar" else [path, "-C", dest])
        if subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            return True
        shutil.rmtree(dest, ignore_errors=True)
    return False


def walk(root):
    for d, dirs, files in os.walk(root, followlinks=True):
        dirs[:] = [x for x in dirs if x != "__MACOSX"]   # (a Mac's zip adds ._ copies of every file there)
        yield d, dirs, [f for f in files if not f.startswith("._")]


def find(root, nested=True):
    if nested:
        for _ in range(MAX_ROUNDS):
            found = [os.path.join(d, f) for d, _, fs in walk(root) for f in fs
                     if f.lower().endswith(ARCHIVES) and not os.path.isdir(os.path.join(d, f) + ".unpacked")]
            if not any(unpack(a) for a in found):
                break
    out = {"pkg": [], "work_bin": [], "firmware": [], "game_folder": []}
    for d, dirs, files in walk(root):
        low = {f.lower(): f for f in files}
        for f in files:
            lf = f.lower()
            p = os.path.join(d, f)
            if lf.endswith(".pkg"):
                out["pkg"].append(p)
            elif lf == "work.bin":
                out["work_bin"].append(p)
            elif lf.endswith(".pup"):
                out["firmware"].append(p)
        if "eboot.bin" in low and os.path.isfile(os.path.join(d, "sce_sys", "param.sfo")):
            out["game_folder"].append(d)
    # 
    for k in out:
        out[k].sort()
    # PSVUPDAT.PUP first: the full update. A PSP2UPDAT.PUP beside it can be the small recovery one, with no libgxm in it
    out["firmware"].sort(key=lambda p: (os.path.basename(p).lower() != "psvupdat.pup", p))
    return out


def main(argv):
    if not argv or argv[0].startswith("-"):
        sys.stdout.write(__doc__)
        return 2
    root = os.path.abspath(argv[0])
    js = argv[argv.index("--json") + 1] if "--json" in argv else None
    r = find(root, "--no-nested" not in argv)
    for kind, label in (("pkg", "PKG"), ("work_bin", "work.bin"), ("firmware", "firmware (.PUP)"), ("game_folder", "game folder")):
        for p in r[kind]:
            print(f"{label}\t{os.path.relpath(p, root)}")
    if js:
        with open(js, "w", encoding="utf-8") as f:
            json.dump(r, f, indent=1)
    print(f"found: {len(r['pkg'])} PKG, {len(r['work_bin'])} work.bin, {len(r['firmware'])} firmware file(s), {len(r['game_folder'])} game folder(s)")
    if not (r["pkg"] or r["game_folder"]):
        print("error: no .pkg and no game folder (sce_sys/param.sfo + eboot.bin) in the download", file=sys.stderr)
        return 1
    if r["pkg"] and not r["work_bin"]:
        print("warning: PKG without a work.bin: it decrypts only if its licence is kept elsewhere", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
