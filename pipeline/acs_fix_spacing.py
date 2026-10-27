"""Deterministic layout fix: where the English has a space right after (or before) a markup token, the Romanian
gets it too ("[[wheezes]] We" → "[[wheezes]] Putem", not "[[wheezes]]Putem")."""
import re
import sqlite3
import sys

sys.path.insert(0, r"D:\acs-ro\pipeline")
import acs_translate as A  # noqa: E402

con = sqlite3.connect(r"D:\acs-ro\db\acs.db")
fixed = 0
for uid, en, ro in con.execute("SELECT id, en, ro FROM units WHERE status = 'ok' AND kind = 'text'").fetchall():
    new = ro
    for tok in set(A.PROTECT.findall(en)):
        t = re.escape(tok)
        if re.search(t + r" ", en) and not re.search(t + r"(\s|$)", new):
            new = re.sub(t + r"(?=\S)", lambda m: m.group(0) + " ", new)
        if re.search(r" " + t, en) and not re.search(r"(^|\s)" + t, new):
            new = re.sub(r"(?<=\S)" + t, lambda m: " " + m.group(0), new)
    if new != ro and A.check(en, new) is None:
        con.execute("UPDATE units SET ro = ? WHERE id = ?", (new, uid))
        fixed += 1
con.commit()
print(f"spacing fixed in {fixed} lines")
