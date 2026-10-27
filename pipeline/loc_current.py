"""Build the current English text set of AC Shadows from the exported LocalizationPackage XMLs.

Each package is identified by its data-file ID (folder "<index>_-_<HEXID>.data"); a later forge in the boot chain
(boot -> patch_01 -> patch_02) replaces the whole package, so the newest version of every ID wins.
Writes D:\\acs-ro\\work\\en_current.json: {pkg_id: {"name", "source", "xml", "strings": {string_id: text}}}.
"""
import json
import pathlib
import re
import xml.etree.ElementTree as ET

WORK = pathlib.Path(r"D:\acs-ro\work")
CHAIN = ["loc_boot", "loc_p01", "loc_p02"]

current = {}
for level in CHAIN:
    for xml in (WORK / level / "Extracted").rglob("*en-US*.xml"):
        pkg = re.search(r"_-_([0-9A-F]{16})\.data$", xml.parent.name).group(1)
        root = ET.parse(xml).getroot()
        current[pkg] = {"name": xml.stem.split("LocalizationPackage_", 1)[-1], "source": level, "xml": str(xml),
                        "strings": {s.get("ID"): s.text or "" for s in root.iter("String")}}

ids = {}
for pkg, p in current.items():
    for sid in p["strings"]:
        ids.setdefault(sid, []).append(pkg)
texts = [t for p in current.values() for t in p["strings"].values() if t.strip()]
print(f"{len(current)} en-US packages, {len(ids)} distinct string IDs, {len(texts)} strings, "
      f"{sum(len(t.split()) for t in texts)} words, {len(set(texts))} unique texts")
print(f"string IDs present in more than one package: {sum(len(v) > 1 for v in ids.values())}")
for pkg, p in sorted(current.items(), key=lambda kv: -len(kv[1]["strings"]))[:12]:
    print(f"  {len(p['strings']):6d}  {p['source']:8s} {pkg}  {p['name']}")
json.dump(current, open(WORK / "en_current.json", "w", encoding="utf-8"), ensure_ascii=False)
