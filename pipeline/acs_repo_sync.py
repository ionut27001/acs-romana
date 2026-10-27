"""Sync the public GitHub repo (D:\\acs-ro\\github\\acs-romana) with the translation DB.

export: translations/<package>[.NNN].json = {"package", "data_id", "entries": [{"id", "en", "ro"}]}, at most 2,000
        entries per file so GitHub's web editor can open them; plus glossary/termeni.csv and the style guide.
import: every "ro" that differs from the DB (contributors' Pull Requests) goes back into units.ro, keyed by the
        English text like the build. Lines left English in the game have "ro" == "en".

Usage: python -I -X utf8 acs_repo_sync.py export | import
"""
import csv
import json
import pathlib
import shutil
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import locpkg  # noqa: E402

ROOT = pathlib.Path(r"D:\acs-ro")
REPO = ROOT / "github" / "acs-romana"
CHUNK = 2000


def db():
    return sqlite3.connect(ROOT / "db" / "acs.db")


def export():
    con = db()
    ro = dict(con.execute("SELECT en, ro FROM units WHERE status = 'ok' AND ro IS NOT NULL"))
    cur = json.load(open(ROOT / "work" / "en_current.json", encoding="utf-8"))
    out = REPO / "translations"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    files = strings = 0
    for data_id, p in cur.items():
        src = pathlib.Path(p["xml"]).with_suffix(".LocalizationPackage")
        entries = [{"id": sid, "en": en, "ro": ro.get(en, en)}
                   for sid, en in locpkg.Package(src.read_bytes()).strings().items() if en.strip()]
        if not entries:
            continue
        name = p["name"].replace("en-US_", "")
        parts = [entries[i:i + CHUNK] for i in range(0, len(entries), CHUNK)]
        for n, part in enumerate(parts, 1):
            fn = f"{name}.{n:03}.json" if len(parts) > 1 else f"{name}.json"
            (out / fn).write_text(json.dumps({"package": p["name"], "data_id": data_id, "entries": part},
                                             ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
            files += 1
        strings += len(entries)
    gl = REPO / "glossary"
    gl.mkdir(exist_ok=True)
    with open(gl / "termeni.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["en", "ro"])
        for en, r in con.execute("SELECT en, ro FROM units WHERE kind = 'term' AND status = 'ok' AND ro IS NOT NULL "
                                 "AND ro != en AND length(en) <= 60 ORDER BY lower(en)"):
            w.writerow([en.strip(), r.strip()])
    shutil.copy2(ROOT / "STYLE.md", gl / "REGULI_DE_STIL.md")
    print(f"exported {strings} strings in {files} files")


def import_():
    con = db()
    cur = dict(con.execute("SELECT en, ro FROM units WHERE status = 'ok'"))
    changed = 0
    for f in sorted((REPO / "translations").glob("*.json")):
        for e in json.loads(f.read_text(encoding="utf-8"))["entries"]:
            en, r = e["en"], e["ro"]
            if en in cur and r != (cur[en] or en):
                con.execute("UPDATE units SET ro = ?, notes = 'github' WHERE en = ?", (r, en))
                cur[en] = r
                changed += 1
    con.commit()
    print(f"imported {changed} changed lines from the repo")


if __name__ == "__main__":
    {"export": export, "import": import_}[sys.argv[1]]()
