"""Editor pass for the AC Shadows Romanian text: makes every line sound the way a Romanian would actually say it.

Haiku 5.5 gets the English, the current Romanian and per-line hints (calques, literary future, "Domnul" for Lord…)
and returns the line rewritten only where needed. Same masking/QA as acs_translate.py; the previous version is kept
in units.ro_v1. Batch API.

Usage: python -I -X utf8 acs_polish.py run [--size 30]
"""
import json
import re
import sqlite3
import subprocess
import sys
import time

sys.path.insert(0, r"D:\acs-ro\pipeline")
import acs_translate as A  # noqa: E402
from acs_translate import Request, MessageCreateParamsNonStreaming, llm  # noqa: E402

DETECT = [
    (r"\b(voi|vei|va|vom|veți|vor)\s+(?!fi\b)[a-zăâîșț]{3,}", "viitor livresc în replică (voi/vei/va + verb) → „o să”"),
    (r"\bDomnul(ui)? [A-Z]", "„Lord X” se traduce „Seniorul X”, nu „Domnul X”"),
    (r"\bDoamna [A-Z]", None),
    (r"\bpentru a\b", "„pentru a” → „ca să”"),
    (r"\bcu adevărat\b", "„cu adevărat” e adesea calc (really/truly)"),
    (r"\bde asemenea\b", "„de asemenea” e calc (also/too) → „și”, „la fel”"),
    (r"\bEi bine\b", "„Ei bine” sună tradus → „Păi”, „Ei”, „Mă rog”"),
    (r"\bnu-i așa\?", "„nu-i așa?” → „nu?”"),
    (r"\bexistă\b", "„există” e livresc în vorbire → „e”, „sunt”, „ai”"),
    (r"\b(este|sunt) despre\b", "„e despre” e calc (it's about)"),
    (r"\bla sfârșitul zilei\b", "calc „at the end of the day” → „până la urmă”"),
    (r"\bface sens\b", "calc „makes sense” → „are sens”"),
    (r"\b(acest|această|acești|aceste|acel|acea|acei|acele)\b", "demonstrativ livresc în replică → ăsta/asta/ăla/aia"),
    (r"\b(the|and|you|with|that|this|what)\b", "a rămas un cuvânt englezesc"),
    (r"^Moară\b|\bMoară pentru\b", "imperativ greșit („Die for X” → „Muriți pentru X” / „Mori pentru X”)"),
]
DETECT = [(re.compile(rx), msg) for rx, msg in DETECT if msg]

EDITOR = """Ești editorul român al traducerii jocului Assassin's Creed Shadows (Japonia feudală, 1579).
Primești rânduri cu originalul englezesc ("en") și traducerea actuală ("ro"), uneori cu indicii ("hints").
Sarcina ta: fă fiecare rând să sune exact cum s-ar exprima un român, firesc, păstrând sensul, tonul și registrul.
- Rescrie DOAR ce nu sună românește: calcuri din engleză, topică englezească, formulări de manual, viitor livresc
  („voi face” → „o să fac”) în replici, demonstrative livrești („acest/această”) în vorbire, repetiții stângace,
  expresii traduse cuvânt cu cuvânt (înlocuiește-le cu expresia românească echivalentă).
- Dacă rândul e deja bun, întoarce-l neschimbat. Nu „îmbunătăți” ce e firesc.
- Epoca: ușor adaptat (fără argou modern, fără anglicisme), dar FĂRĂ arhaisme. „Lord X” → „Seniorul X”,
  „Lady X” → „Doamna X”. Numele și termenii japonezi rămân.
- Descrieri de iteme și abilități: clare, scurte, în stil de joc (prezent, fără „va oferi” → „oferă”).
- Păstrează termenii de joc deja folosiți (nume de iteme, abilități, locuri) exact cum sunt în traducere.
- Marcajele ⟦1⟧, ⟦2⟧ … și rupturile de rând (\\n) rămân exact, o dată fiecare.
- Diacritice complete: ă â î ș ț.
- """ + A.FIXED + """
Răspunde DOAR cu JSON: {"t":[{"id":<id>,"f":"<rândul final>","m":""}]}, câte un rând pentru fiecare id."""


def hints(ro, pkg):
    out = []
    for rx, msg in DETECT:
        if rx.search(ro):
            if "demonstrativ" in msg and "Subtitles" not in pkg:
                continue  # descriptions may keep a more written register
            out.append(msg)
    return out


def run(size):
    con = A.db()
    cols = [r[1] for r in con.execute("PRAGMA table_info(units)")]
    if "ro_v1" not in cols:
        con.execute("ALTER TABLE units ADD COLUMN ro_v1 TEXT")
        con.execute("ALTER TABLE units ADD COLUMN polished INTEGER DEFAULT 0")
        con.commit()
    rows = con.execute("""SELECT id, en, ro, pkg FROM units WHERE kind = 'text' AND status = 'ok'
                          AND coalesce(polished, 0) = 0 ORDER BY ord""").fetchall()
    reqs, plan = [], {}
    for b in range(0, len(rows), size):
        batch = rows[b:b + size]
        lines, meta = [], []
        for i, (uid, en, ro, pkg) in enumerate(batch):
            men, toks = A.mask(en)
            mro = ro
            for k, t in enumerate(toks, 1):
                mro = mro.replace(t, f"⟦{k}⟧", 1)
            line = {"id": i, "en": men, "ro": mro}
            h = hints(ro, pkg)
            if h:
                line["hints"] = h
            lines.append(line)
            meta.append([uid, toks, ro])
        cid = f"p{b // size}"
        reqs.append(Request(custom_id=cid, params=MessageCreateParamsNonStreaming(
            model=A.MODEL, max_tokens=16000,
            system=[{"type": "text", "text": EDITOR, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": json.dumps({"lines": lines}, ensure_ascii=False)}],
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": llm.LINES_SCHEMA}})))
        plan[cid] = meta
    batch = A.client().messages.batches.create(requests=reqs)
    A.PLANS.mkdir(exist_ok=True)
    (A.PLANS / f"{batch.id}.json").write_text(json.dumps({"pass": "polish", "plan": plan}, ensure_ascii=False),
                                              encoding="utf-8")
    print(f"submitted {batch.id}: {len(reqs)} requests, {len(rows)} lines", flush=True)
    A.wait(batch.id)
    apply(batch.id)


def apply(batch_id):
    plan = json.loads((A.PLANS / f"{batch_id}.json").read_text(encoding="utf-8"))["plan"]
    out = A.PLANS / f"{batch_id}.results.jsonl"
    url = A.client().messages.batches.retrieve(batch_id).results_url
    subprocess.run(["curl", "-sS", "--retry", "5", "--retry-all-errors", "-o", str(out),
                    "-H", f"x-api-key: {llm.anthropic_key()}", "-H", "anthropic-version: 2023-06-01", url], check=True)
    con = A.db()
    changed = kept = rejected = lost = 0
    tok = {"in": 0, "cw": 0, "cr": 0, "out": 0}
    for line in open(out, encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        meta = plan.get(r["custom_id"], [])
        if r["result"]["type"] != "succeeded":
            lost += len(meta)
            continue
        msg = r["result"]["message"]
        u = msg["usage"]
        tok["in"] += u.get("input_tokens") or 0
        tok["cw"] += u.get("cache_creation_input_tokens") or 0
        tok["cr"] += u.get("cache_read_input_tokens") or 0
        tok["out"] += u.get("output_tokens") or 0
        try:
            got = {x.get("id"): x.get("f", "") for x in json.loads(
                next(c["text"] for c in msg["content"] if c["type"] == "text")).get("t", [])}
        except (ValueError, StopIteration):
            lost += len(meta)
            continue
        for i, (uid, toks, old) in enumerate(meta):
            if i not in got:
                lost += 1
                continue
            en = con.execute("SELECT en FROM units WHERE id = ?", (uid,)).fetchone()[0]
            new = A.unmask(got[i], toks).replace("ş", "ș").replace("ţ", "ț").replace("Ş", "Ș").replace("Ţ", "Ț")
            lead, trail = en[:len(en) - len(en.lstrip())], en[len(en.rstrip()):]
            new = lead + new.strip() + trail
            # an editor rewrite must pass QA and stay close in length; otherwise the translation stays
            if A.check(en, new) or not (0.6 < len(new) / max(len(old), 1) < 1.6):
                rejected += 1
                con.execute("UPDATE units SET polished = 1 WHERE id = ?", (uid,))
                continue
            if new != old:
                con.execute("UPDATE units SET ro_v1 = ro, ro = ?, polished = 1 WHERE id = ?", (new, uid))
                changed += 1
            else:
                con.execute("UPDATE units SET polished = 1 WHERE id = ?", (uid,))
                kept += 1
    con.commit()
    p = llm.PRICES[A.MODEL]
    usd = (tok["in"] * p[0] + tok["cw"] * p[1] + tok["cr"] * p[2] + tok["out"] * p[3]) / 1e6 / 2
    print(f"applied {batch_id}: {changed} rewritten, {kept} kept, {rejected} rejected by QA, {lost} lost; "
          f"cost ${usd:.2f}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "run":
        run(int(a[a.index("--size") + 1]) if "--size" in a else 30)
    elif a[0] == "apply":
        apply(a[1])
