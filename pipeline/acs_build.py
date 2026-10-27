"""Build the Romanian AC Shadows patch from D:\\acs-ro\\db\\acs.db.

For every current en-US LocalizationPackage (newest version per data ID, see loc_current.py) the Romanian strings
are written with locpkg (Ubisoft's dictionary + layout; AnvilToolkit's own writer crashes the game), the package goes
back into a copy of its .data folder, anvilcli repackall rebuilds the .data containers and anvilcli buildpatch makes
DataPC_boot_patch_03.forge on top of the current head of the boot chain.

Usage: python -I -X utf8 acs_build.py [--install]
"""
import json
import pathlib
import shutil
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import locpkg  # noqa: E402

ROOT = pathlib.Path(r"D:\acs-ro")
GAME = pathlib.Path(r"D:\SteamLibrary\steamapps\common\Assassin's Creed Shadows")
HEAD = GAME / "DataPC_boot_patch_02.forge"
BUILD = ROOT / "build"
DOTNET = str(ROOT / "tools" / "dotnet9" / "dotnet.exe")
CLI = str(ROOT / "anvilcli" / "bin" / "Release" / "net9.0-windows" / "anvilcli.dll")


def anvil(*args):
    r = subprocess.run([DOTNET, CLI, *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=3600)
    out = [l for l in r.stdout.splitlines() if l.startswith(("#", "FAIL"))]
    print("\n".join(out))
    if r.returncode != 0 or any(l.startswith("FAIL") for l in out):
        raise RuntimeError(f"anvilcli {args[0]} failed:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")


def main():
    con = sqlite3.connect(ROOT / "db" / "acs.db")
    ro = dict(con.execute("SELECT en, ro FROM units WHERE status = 'ok' AND ro IS NOT NULL"))
    cur = json.load(open(ROOT / "work" / "en_current.json", encoding="utf-8"))
    if BUILD.exists():
        shutil.rmtree(BUILD)
    (BUILD / "Extracted").mkdir(parents=True)
    done = total = kept = 0
    for pkg_id, p in cur.items():
        xml = pathlib.Path(p["xml"])
        src_pkg = xml.with_suffix(".LocalizationPackage")
        data_dir = xml.parent  # ...\Extracted\<index>_-_<ID>.data
        level_dir = data_dir.parent.parent
        orig_data = level_dir / data_dir.name
        pkg = locpkg.Package(src_pkg.read_bytes())
        strings = pkg.strings()
        new = {}
        for sid, en in strings.items():
            total += 1
            if en in ro and ro[en] != en:
                new[sid] = ro[en]
            else:
                kept += 1
        raw = pkg.encode(new)
        check = locpkg.Package(raw).strings()
        bad = [s for s, v in new.items() if check[s] != v]
        if bad:
            raise RuntimeError(f"{p['name']}: {len(bad)} strings do not read back")
        shutil.copy2(orig_data, BUILD / orig_data.name)
        dst = BUILD / "Extracted" / data_dir.name
        dst.mkdir()
        for f in data_dir.iterdir():
            if f.suffix.lower() not in (".xml",):
                shutil.copy2(f, dst / f.name)
        (dst / src_pkg.name).write_bytes(raw)
        done += 1
    print(f"{done} packages, {total} strings, {total - kept} in Romanian, {kept} kept in English")
    anvil("repackall", str(BUILD))
    datas = sorted(str(f) for f in (BUILD / "out").glob("*.data"))
    out = BUILD / "patch" / "out" / "DataPC_boot_patch_03.forge"
    anvil("buildpatch", str(HEAD), str(BUILD / "patch"), str(out), *datas, "--prefetch-from", str(HEAD))
    print(f"built {out} ({out.stat().st_size / 1e6:.1f} MB)")
    if "--install" in sys.argv:
        shutil.copy2(out, GAME / out.name)
        print(f"installed -> {GAME / out.name}")


if __name__ == "__main__":
    main()
