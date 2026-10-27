"""User feedback 2026-10-27: game/DLC titles stay English, eras d.Hr./î.Hr., menu commands, objectives."""
import re
import sqlite3

con = sqlite3.connect(r"D:\acs-ro\db\acs.db")
SET = {
    334: "Shadows", 1484: "SHADOWS", 1499: "ODYSSEY", 38472: "BLACK FLAG RESYNCED", 38635: "BLACK FLAG",
    40472: "Black Flag", 38223: "Claws of Awaji", 1525: "Expansiunea Claws of Awaji",
    1390: "[NumberTag] d.Hr.", 1549: "861 d.Hr.", 1595: "[NumberTag] î.Hr.", 1603: "431 î.Hr.",
    3599: "Șiretlicul contrabandistului",
    232: "Înapoi la Amintiri", 779: "Ieși din joc", 781: "Înapoi la ecranul principal", 2122: "Înapoi la Animus",
    3206: "Găsește-l pe Samemaru", 2351: "Găsește-o pe Katsuhime", 3326: "Află unde e Roata",
    3684: "Găsește-l pe Duarte de Melo", 6903: "Găsește-l pe otrăvitor", 10195: "Găsește-l pe negustorul de sclavi",
    42059: "Găsește-l pe maestrul de bō", 12914: "Întoarce-te la Doamna Oichi",
}
n = 0
for uid, ro in SET.items():
    n += con.execute("UPDATE units SET ro = ? WHERE id = ?", (ro, uid)).rowcount
SUBS = [
    (r"Ghearele din Awaji au fost (\[BOLD_BEGIN\])lansate", r"Expansiunea Claws of Awaji a fost \1lansată"),
    (r"Ghearele din Awaji", "Claws of Awaji"),
    (r"î\.e\.n\.", "î.Hr."), (r"(?<![î.])\be\.n\.", "d.Hr."),
    (r"^Întoarcere la ", "Întoarce-te la "),
]
for uid, ro in con.execute("SELECT id, ro FROM units WHERE status = 'ok'").fetchall():
    new = ro
    for a, b in SUBS:
        new = re.sub(a, b, new)
    if new != ro:
        con.execute("UPDATE units SET ro = ? WHERE id = ?", (new, uid))
        n += 1
con.commit()
print("fixed", n)
