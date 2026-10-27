"""Second editor pass (user, 2026-10-27, repeated): everything must sound the way Romanians talk TODAY.

The first pass read "adapt to the era" as permission for bookish words ("înverșunată", "insuflându-i", "gambit").
This pass rewrites every text line (and the UI terms that contain bookish words) into plain, current Romanian.
Previous version kept in units.ro_v2; same masking/QA/length guard as acs_polish.py.

Usage: python -I -X utf8 acs_modern.py run [--size 30] | apply <batch_id>
"""
import json
import re
import subprocess
import sys

sys.path.insert(0, r"D:\acs-ro\pipeline")
import acs_translate as A  # noqa: E402
from acs_translate import Request, MessageCreateParamsNonStreaming, llm  # noqa: E402

BOOKISH = (r"înverșun\w*|insufl\w*|totodată|pe măsură ce|deoarece|întrucât|astfel încât|precum|dobând\w*|ulterior\w*|"
           r"efectu\w*|desfășur\w*|constitui\w*|reprezint\w*|în privința|aidoma|cuget\w*|sârguincio\w*|temeinic\w*|"
           r"neclintit\w*|nestrămutat\w*|vrednic\w*|întocmai|în cadrul|în vederea|în urma|atât .{1,40} cât și|"
           r"gambit\w*|nicicând|dintotdeauna|se află|consacrat\w*|prealabil\w*|cu desăvârșire|pricin\w*|fără zăbavă|"
           r"de îndată|însă|îndeajuns|anevoie|purcede\w*|nădejde|năzui\w*|tăinui\w*|osând\w*|oștean\w*|oștir\w*")
DETECT = [
    (re.compile(rf"\b({BOOKISH})\b", re.I), "cuvânt livresc/învechit → spune-o cum ar zice un român azi"),
    (re.compile(r"\b(voi|vei|va|vom|veți|vor)\s+(?!fi\b)[a-zăâîșț]{3,}"), "viitor livresc („va face”) → „o să facă” în replici"),
    (re.compile(r"\bpentru a\b"), "„pentru a” → „ca să”"),
    (re.compile(r"\b(acest|această|acești|aceste|acel|acea|acei|acele)\b"), "demonstrativ livresc în replică → ăsta/asta/ăla/aia"),
]

EDITOR = """Ești editorul român al traducerii jocului Assassin's Creed Shadows.
Regula userului, cea mai importantă: totul trebuie să sune EXACT cum vorbesc românii în ziua de azi.
Primești rânduri cu originalul englezesc ("en"), traducerea actuală ("ro") și uneori indicii ("hints").
- Înlocuiește orice cuvânt livresc, pretențios, de manual sau învechit cu cuvântul pe care îl folosește un român
  obișnuit azi: „înverșunată” → „încăpățânată”/„aprigă”, „insuflându-i” → „învățând-o”/„dându-i”, „dobândește” →
  „primește”/„capătă”, „totodată” → „și”, „deoarece/întrucât” → „pentru că”, „precum” → „ca”, „se află” → „e”,
  „gambit” → „șiretlic”, „în vederea” → „ca să”, „însă” → „dar”.
- Frazele lungi și încâlcite: simplifică-le, ordinea firească a cuvintelor în română, fără să pierzi informație.
- „Epoca” (Japonia, 1579) înseamnă DOAR: fără argou și fără anglicisme (ok, cool, job, super). NU înseamnă cuvinte
  vechi sau solemne. Fără arhaisme.
- Replici: vorbire firească („o să fac”, „asta”, „ăla”, „ca să”). Descrieri (personaje, iteme, codex): clare și
  simple, cum ar scrie un român azi într-un articol bun, nu ca într-un manual vechi.
- Dacă rândul sună deja firesc, întoarce-l neschimbat.
- Numele proprii, termenii japonezi și termenii de joc (iteme, abilități, locuri, titluri de jocuri) rămân exact.
- Marcajele ⟦1⟧, ⟦2⟧ … și rupturile de rând (\\n) rămân exact, o dată fiecare. Diacritice complete: ă â î ș ț.
- """ + A.FIXED + """
Răspunde DOAR cu JSON: {"t":[{"id":<id>,"f":"<rândul final>","m":""}]}, câte un rând pentru fiecare id."""


def hints(ro, pkg, kind):
    out = []
    for rx, msg in DETECT:
        if rx.search(ro):
            if "demonstrativ" in msg and ("Subtitles" not in pkg or kind != "text"):
                continue
            out.append(msg)
    return out


def ensure_cols(con, backup="ro_v2", flag="modern"):
    cols = [r[1] for r in con.execute("PRAGMA table_info(units)")]
    if backup not in cols:
        con.execute(f"ALTER TABLE units ADD COLUMN {backup} TEXT")
        con.execute(f"ALTER TABLE units ADD COLUMN {flag} INTEGER DEFAULT 0")
        con.commit()


def run(size):
    con = A.db()
    ensure_cols(con)
    rows = con.execute("""SELECT id, en, ro, pkg, kind FROM units WHERE kind IN ('text', 'term') AND status = 'ok'
                          AND ro IS NOT NULL AND ro != en AND coalesce(modern, 0) = 0 ORDER BY ord""").fetchall()
    # every text line; UI terms only when they contain a bookish word (their wording is the glossary)
    rows = [r for r in rows if r[4] == "text" or DETECT[0][0].search(r[2])]
    reqs, plan = [], {}
    for b in range(0, len(rows), size):
        batch = rows[b:b + size]
        lines, meta = [], []
        for i, (uid, en, ro, pkg, kind) in enumerate(batch):
            men, toks = A.mask(en)
            mro = ro
            for k, t in enumerate(toks, 1):
                mro = mro.replace(t, f"⟦{k}⟧", 1)
            line = {"id": i, "en": men, "ro": mro}
            if kind == "term":
                line["tip"] = "termen scurt de interfață (titlu, misiune, item)"
            h = hints(ro, pkg, kind)
            if h:
                line["hints"] = h
            lines.append(line)
            meta.append([uid, toks, ro])
        cid = f"m{b // size}"
        reqs.append(Request(custom_id=cid, params=MessageCreateParamsNonStreaming(
            model=A.MODEL, max_tokens=16000,
            system=[{"type": "text", "text": EDITOR, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": json.dumps({"lines": lines}, ensure_ascii=False)}],
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": llm.LINES_SCHEMA}})))
        plan[cid] = meta
    batch = A.client().messages.batches.create(requests=reqs)
    A.PLANS.mkdir(exist_ok=True)
    (A.PLANS / f"{batch.id}.json").write_text(json.dumps({"pass": "modern", "plan": plan}, ensure_ascii=False),
                                              encoding="utf-8")
    print(f"submitted {batch.id}: {len(reqs)} requests, {len(rows)} lines", flush=True)
    A.wait(batch.id)
    apply(batch.id)


def apply(batch_id, backup="ro_v2", flag="modern"):
    plan = json.loads((A.PLANS / f"{batch_id}.json").read_text(encoding="utf-8"))["plan"]
    out = A.PLANS / f"{batch_id}.results.jsonl"
    url = A.client().messages.batches.retrieve(batch_id).results_url
    subprocess.run(["curl", "-sS", "--retry", "5", "--retry-all-errors", "-o", str(out),
                    "-H", f"x-api-key: {llm.anthropic_key()}", "-H", "anthropic-version: 2023-06-01", url], check=True)
    con = A.db()
    ensure_cols(con, backup, flag)
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
            # short UI labels may legitimately change length a lot ("Meet X" → "Întâlnește-te cu X")
            if A.check(en, new) or not (0.6 < len(new) / max(len(old), 1) < 1.6 or abs(len(new) - len(old)) <= 12):
                rejected += 1
                con.execute(f"UPDATE units SET {flag} = 1 WHERE id = ?", (uid,))
                continue
            if new != old:
                con.execute(f"UPDATE units SET {backup} = ro, ro = ?, {flag} = 1 WHERE id = ?", (new, uid))
                changed += 1
            else:
                con.execute(f"UPDATE units SET {flag} = 1 WHERE id = ?", (uid,))
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
