"""Stats for exported AC Shadows LocalizationPackage XMLs (UTF-16, <String ID="...">text</String>)."""
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter

for path in sys.argv[1:]:
    root = ET.parse(path).getroot()
    rows = [(s.get("ID"), s.text or "") for s in root.iter("String")]
    words = sum(len(t.split()) for _, t in rows)
    nonempty = [t for _, t in rows if t.strip()]
    tags = Counter(m for _, t in rows for m in re.findall(r"<[^>]{1,40}>|\{[^}]{1,40}\}|\[[^\]]{1,40}\]", t))
    print(f"{path.split(chr(92))[-1]}: {len(rows)} strings, {len(nonempty)} non-empty, {words} words, "
          f"{len(set(nonempty))} unique texts, attrs={root.attrib}")
    print("   top markup:", tags.most_common(12))
    for _, t in rows[100:104]:
        print("   e.g.", t[:140].replace("\n", "\\n"))
