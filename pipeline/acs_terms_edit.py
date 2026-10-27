"""Editor pass for the short UI terms (user, 2026-10-27: "look for more, make it sound like a Romanian talks").

Audit found: item names in English word order ("Lama Floare de oțel", "Mânerul katanei Eleganței"), objectives as nouns
("Întâlnire cu X"), three verbs for one English verb (Urmărește/Urmează/Localizează), stat labels with several
wordings. This pass rewrites every translated term with fixed UI conventions. Backup in units.ro_v3.

Usage: python -I -X utf8 acs_terms_edit.py run [--size 60] | apply <batch_id>
"""
import json
import sys

sys.path.insert(0, r"D:\acs-ro\pipeline")
import acs_translate as A  # noqa: E402
import acs_modern as M  # noqa: E402
from acs_translate import Request, MessageCreateParamsNonStreaming, llm  # noqa: E402

EDITOR = """Ești editorul român al interfeței jocului Assassin's Creed Shadows. Primești termeni scurți (nume de iteme,
obiective de misiune, butoane, statistici, abilități, locuri) cu originalul ("en") și traducerea actuală ("ro").
Fă fiecare termen să sune cum l-ar scrie un român azi într-un joc bine tradus. Dacă e deja bun, lasă-l neschimbat.

OBIECTIVE ȘI BUTOANE (imperativ, persoana a II-a singular):
- Find / Locate / Track down X → „Găsește X” / „Găsește-l pe X” / „Găsește-o pe X” (NU „Localizează”, NU „Dă de urma”)
- Follow X (mergi după un aliat) → „Urmează-l pe X”; Follow (pe ascuns) / Tail → „Urmărește-l pe X”;
  Chase X → „Fugi după X”; Follow Road/River → „Urmează drumul/râul”
- Meet (with) X → „Întâlnește-te cu X”; Talk/Speak to X → „Vorbește cu X”; Return to X → „Întoarce-te la X”
- Kill / Assassinate X → „Ucide-l pe X” / „Asasinează-l pe X”; Escape → „Fugi” / „Scapă”
- Quit to X → „Înapoi la X”; Quit to Desktop → „Ieși din joc”
- Butoane din meniu: forma scurtă obișnuită („Echipează”, „Setări”, „Încarcă”, „Confirmă”, „Înapoi”).

STATISTICI (aceleași cuvinte peste tot): Damage → Daune · Health → Viață · Posture → Postură · Armor → Armură ·
Adrenaline → Adrenalină · Critical Chance → Șansă critică · Critical Damage → Daune critice · Melee → corp la corp ·
Ranged → la distanță · Stealth → furișare · Assassination Damage → Daune la asasinare · Heavy Attack → Atac puternic ·
Light Attack → Atac ușor · Gain → câștigată/câștigat (după gen) · Weapon DPS → DPS armă.

ITEME:
- Ordinea românească, majusculă DOAR la primul cuvânt și la numele proprii japoneze (fără Title Case englezesc):
  „Chemarea Vidului” → „Chemarea vidului”, „Lanțul Ecourilor Groaznice” → „Lanțul ecourilor înfiorătoare”.
- Piese de armă/echipament („<Nume armă> Blade/Handle/Guard/Chain/Pommel”): piesa + numele armei la genitiv,
  firesc: „Steel Blossom Blade” → „Lama Florii de oțel”, „Katana of Elegance Handle” → „Mânerul Katanei eleganței”,
  „Whip of the Deserter Blade” → „Lama Biciului dezertorului”.
- Numele de arme care sunt japoneze și în engleză rămân (Yami no Kage). Tipuri: Outfit → Ținută, Helmet/Headgear →
  Coif, Trinket → Talisman, Amulet → Amuletă, Legendary → legendar/legendară.
- Kusarigama, katana, tantō, naginata, kanabō, teppō, bō: fără „-ul” forțat („kusarigama”, nu „kusarigama-ul”).

ALTELE:
- Nume de locuri, personaje, clanuri: rămân cum sunt; schimbă doar ordinea/forma dacă sună englezește.
- Titlurile de jocuri și expansiuni rămân în engleză. Lungimea: cât mai aproape de original (spațiu limitat în UI).
- Marcajele ⟦1⟧, ⟦2⟧ … rămân exact. Diacritice complete: ă â î ș ț.
- """ + A.FIXED + """
Răspunde DOAR cu JSON: {"t":[{"id":<id>,"f":"<termenul final>","m":""}]}, câte un rând pentru fiecare id."""


def run(size):
    con = A.db()
    M.ensure_cols(con, "ro_v3", "termed")
    rows = con.execute("""SELECT id, en, ro FROM units WHERE kind = 'term' AND status = 'ok' AND ro IS NOT NULL
                          AND ro != en AND coalesce(termed, 0) = 0 ORDER BY ord""").fetchall()
    reqs, plan = [], {}
    for b in range(0, len(rows), size):
        lines, meta = [], []
        for i, (uid, en, ro) in enumerate(rows[b:b + size]):
            men, toks = A.mask(en)
            mro = ro
            for k, t in enumerate(toks, 1):
                mro = mro.replace(t, f"⟦{k}⟧", 1)
            lines.append({"id": i, "en": men, "ro": mro})
            meta.append([uid, toks, ro])
        cid = f"t{b // size}"
        reqs.append(Request(custom_id=cid, params=MessageCreateParamsNonStreaming(
            model=A.MODEL, max_tokens=16000,
            system=[{"type": "text", "text": EDITOR, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": json.dumps({"lines": lines}, ensure_ascii=False)}],
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": llm.LINES_SCHEMA}})))
        plan[cid] = meta
    batch = A.client().messages.batches.create(requests=reqs)
    A.PLANS.mkdir(exist_ok=True)
    (A.PLANS / f"{batch.id}.json").write_text(json.dumps({"pass": "terms", "plan": plan}, ensure_ascii=False),
                                              encoding="utf-8")
    print(f"submitted {batch.id}: {len(reqs)} requests, {len(rows)} terms", flush=True)
    A.wait(batch.id)
    M.apply(batch.id, "ro_v3", "termed")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "run":
        run(int(a[a.index("--size") + 1]) if "--size" in a else 60)
    elif a[0] == "apply":
        M.apply(a[1], "ro_v3", "termed")
