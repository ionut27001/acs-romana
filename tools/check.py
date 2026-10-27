"""Checks translation files: valid JSON, nothing missing, and the same game markup as the English line.

Usage: python tools/check.py [file ...]   (no arguments = every file under translations/)
Exit code 1 if anything is wrong; each problem is printed with its file and string id.
"""
import json
import pathlib
import re
import sys

# markup the game needs untouched: {0} {NumberTag}, [[laughs], <style ...>, [BOLD_BEGIN], [CT_Attack], [beat], line breaks
PROTECT = re.compile(r"\{[^{}]*\}|\[\[[^\[\]]*\]\]?|<[^<>]+>|"
                     r"\[(?:NumberTag\d*|BOLD_(?:BEGIN|END)|(?:CT|TX|Icon|Color|Btn|Img)_[^\[\]]*|"
                     r"[a-z][a-z0-9 \-]*)\]")
ROOT = pathlib.Path(__file__).resolve().parent.parent


def tokens(text):
    return sorted(PROTECT.findall(text or ""))


def check(path):
    problems = []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        return [f"{path}: invalid JSON ({e})"]
    if not isinstance(doc, dict) or "data_id" not in doc or not isinstance(doc.get("entries"), list):
        return [f"{path}: expected {{\"package\": ..., \"data_id\": ..., \"entries\": [...]}}"]
    for e in doc["entries"]:
        sid = e.get("id")
        if not isinstance(e.get("en"), str) or not isinstance(e.get("ro"), str):
            problems.append(f"{path} id {sid}: \"en\" and \"ro\" must be text")
            continue
        if e["en"].strip() and not e["ro"].strip():
            problems.append(f"{path} id {sid}: empty translation")
        if tokens(e["en"]) != tokens(e["ro"]):
            problems.append(f"{path} id {sid}: markup differs from English: {tokens(e['en'])} vs {tokens(e['ro'])}")
        if e["en"].count("\n") != e["ro"].count("\n"):
            problems.append(f"{path} id {sid}: different number of line breaks than English")
    return problems


def main():
    files = [pathlib.Path(a) for a in sys.argv[1:] if a.endswith(".json")] or \
        sorted((ROOT / "translations").glob("*.json"))
    problems = [p for f in files if f.exists() for p in check(f)]
    for p in problems:
        print(p)
    print(f"{len(files)} files checked, {len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
