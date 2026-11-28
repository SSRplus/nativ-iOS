#!/usr/bin/env python3
"""From an unpacked download to a game ready to recompile: what the CI workflow does after find_inputs.py.

  prepare_game.py <folder> [--title PCSB00875] [--experimental] [--github-output $GITHUB_OUTPUT]

  1. firmware   every PSP2UPDAT.PUP / PSVUPDAT.PUP / *.PUP found, until one decrypts (vitarecomp firmware)
  2. scan       vitarecomp scan <folder> --import-licences: every game, update and licence in it, the licences kept
  3. add        each game, then its updates (vitarecomp add --no-build: decrypted and kept, nothing built yet)
  4. import     vitarecomp import <title>; a version the game's pack doesn't play is imported --experimental when
                that is allowed (FORCE=1)
  5. analyze, recompile: the game's C (vitarecomp analyze / recompile)

Then writes `title=<TITLEID>` (and `name=<game name>`) to --github-output, for the build that follows. The build itself
(vitarecomp build, then export-ios) is the workflow's: it is the long step and has its own log group.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
VR = [sys.executable, os.path.join(ROOT, "pipeline", "vitarecomp.py")]
# one library for every stage: firmware, decrypted games, the recompiled code. (Without this the first command to run, before dump/
# exists, uses the user library folder and the next ones dump/: the firmware is then not where the game's import looks.)
DUMP = os.environ.setdefault("ATIV_DUMP", os.path.join(ROOT, "dump"))
os.makedirs(DUMP, exist_ok=True)


def say(*a):
    print(*a, flush=True)


def vr(*args, check=True):
    say("::group::vitarecomp " + " ".join(os.path.basename(a) for a in args))
    r = subprocess.run(VR + list(args), cwd=ROOT)
    say("::endgroup::")
    if check and r.returncode:
        sys.exit(f"vitarecomp {' '.join(args[:1])} failed ({r.returncode})")
    return r.returncode


def main(argv):
    if not argv or argv[0].startswith("-"):
        sys.stdout.write(__doc__)
        return 2
    folder = os.path.abspath(argv[0])
    opt = lambda k: argv[argv.index(k) + 1] if k in argv else None
    experimental = "--experimental" in argv
    want = opt("--title")

    # what is in the download (find_inputs.py's own search, which also unpacks archives inside it)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import find_inputs
    found = find_inputs.find(folder)

    # 1. firmware: the first file that decrypts
    fw_ok = bool(sorted(p for p in os.listdir(os.path.join(DUMP, "firmware")) if not p.startswith("."))) if os.path.isdir(os.path.join(DUMP, "firmware")) else False
    for pup in found["firmware"]:
        if fw_ok:
            break
        say(f"firmware file: {os.path.relpath(pup, folder)}")
        fw_ok = vr("firmware", pup, check=False) == 0
    if not fw_ok:
        sys.exit("no firmware: put PSP2UPDAT.PUP (or PSVUPDAT.PUP) in the zip, or give a firmware link")

    # 2. what the scan sees; the licences it finds are kept for the adds below
    rows_file = os.path.join(DUMP, "scan.tsv")
    os.makedirs(os.path.dirname(rows_file), exist_ok=True)
    vr("scan", folder, "--import-licences", "--out", rows_file)
    cols = "kind form title_id version status licence name path licence_file content_id note".split()
    rows = []
    with open(rows_file, encoding="utf-8") as f:
        for line in f:
            v = line.rstrip("\n").split("\t")
            if len(v) >= 8:
                rows.append(dict(zip(cols, v + [""] * (len(cols) - len(v)))))
    for r in rows:
        say(f"  {r['kind']:8} {r['form']:6} {r['title_id']:10} v{r['version']:6} {r['status']:12} licence={r['licence']:5} {r['name']}")
    games = [r for r in rows if r["kind"] == "game"]
    if want:
        games = [r for r in games if r["title_id"] == want]
    if not games:
        sys.exit("no game in the download that the scan can read" + (f" for {want}" if want else ""))
    title = games[0]["title_id"]
    if any(g["title_id"] != title for g in games):
        say(f"more than one game found; building {title} ({games[0]['name']}); pass title to pick another")
    updates = [r for r in rows if r["kind"] == "update" and r["title_id"] == title]

    # 3. add: the game, then its update. A game's licence travels with it (work.bin, or the one the scan kept)
    for r in games[:1] + updates:
        if r["form"] == "pkg" and r["licence"] == "rif" and not r.get("licence_file"):
            say(f"warning: {os.path.basename(r['path'])} has no licence in the download (work.bin): decrypting it will probably stop")
        args = ["add", r["path"], "--no-build"]
        if r.get("licence_file") and r["licence_file"] not in ("-", ""):
            args += ["--license", r["licence_file"]]
        vr(*args, check=(r["kind"] == "game"))

    # 4. import: one version of the game is built, the one its pack plays. Another one (a region, an update the pack doesn't
    #    know) stops here unless FORCE=1 (vitarecomp's: "unknown" version: the game runs, the pack's per-version fixes don't apply)
    forced = False
    rc = vr("import", title, check=False)
    if rc:
        if not experimental:
            sys.exit(f"{title}: a version its pack doesn't play; run again with experimental on to try it anyway")
        say(f"{title}: not a version the pack plays: importing it anyway (FORCE=1: no per-version fixes for it)")
        os.environ["FORCE"] = "1"
        forced = True
        vr("import", title)

    # 5. the game's C
    vr("analyze", title)
    vr("recompile", title)

    name = games[0]["name"]
    say(f"ready: {title} {name}")
    out = opt("--github-output")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"title={title}\nname={name}\n" + ("force=1\n" if forced else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
