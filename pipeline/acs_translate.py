"""AC Shadows → Romanian translation through the Claude Message Batches API (Haiku 5.5).

Units are the unique English texts of the current en-US packages (D:\\acs-ro\\work\\en_current.json).
  pass 1 ("term"): short UI strings — item, place, ability, title names — become the glossary
  pass 2 ("text"): everything else, with the glossary entries that occur in each batch injected into the prompt
Markup the game needs ({NumberTag}, [BOLD_BEGIN], [CT_*], [TX_*], <br />, [beat], [[laughs]] …) is masked as ⟦n⟧ and
must come back unchanged; visible bracketed choices like [Refuse] are translated.

Usage: python -I -X utf8 acs_translate.py prepare
       python -I -X utf8 acs_translate.py run term|text [--size 40] [--only-missing]
       python -I -X utf8 acs_translate.py apply <batch_id>
       python -I -X utf8 acs_translate.py stats
"""
import json
import pathlib
import re
import sqlite3
import subprocess
import sys
import time

sys.path.insert(0, r"D:\cp77-ro\tools\pylib")
sys.path.insert(0, r"D:\cp77-ro\pipeline")
import anthropic  # noqa: E402
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming  # noqa: E402
from anthropic.types.messages.batch_create_params import Request  # noqa: E402

import llm  # noqa: E402

ROOT = pathlib.Path(r"D:\acs-ro")
DB = ROOT / "db" / "acs.db"
PLANS = ROOT / "batch"
MODEL = "claude-haiku-5-5"
STYLE = (ROOT / "STYLE.md").read_text(encoding="utf-8")

# markup the game interprets: kept byte-for-byte (masked); other [bracketed text] is visible and gets translated
PROTECT = re.compile(r"\{[^{}]*\}|\[\[[^\[\]]*\]\]?|<[^<>]+>|"
                     r"\[(?:NumberTag\d*|BOLD_(?:BEGIN|END)|(?:CT|TX|Icon|Color|Btn|Img)_[^\[\]]*|"
                     r"[a-z][a-z0-9 \-]*)\]")
SENTENCE = re.compile(r"[.!?…:;]\s|[.!?…]$")


def mask(text):
    toks = []

    def sub(m):
        toks.append(m.group(0))
        return f"⟦{len(toks)}⟧"
    return PROTECT.sub(sub, text), toks


def unmask(text, toks):
    for i, t in enumerate(toks, 1):
        text = text.replace(f"⟦{i}⟧", t)
    return text


def db():
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB, timeout=60)
    con.execute("""CREATE TABLE IF NOT EXISTS units (id INTEGER PRIMARY KEY, en TEXT UNIQUE, kind TEXT, pkg TEXT,
                   ord INTEGER, ro TEXT, status TEXT, notes TEXT, model TEXT, updated REAL)""")
    con.execute("CREATE TABLE IF NOT EXISTS batches (batch_id TEXT PRIMARY KEY, pass TEXT, created REAL, applied REAL)")
    return con


def prepare():
    cur = json.load(open(ROOT / "work" / "en_current.json", encoding="utf-8"))
    con = db()
    seen, n = set(), 0
    # MAIN packages first, then the update/collab packages; inside a package, string-ID order keeps scenes together
    for pkg in sorted(cur, key=lambda k: (not cur[k]["name"].startswith("MAIN"), cur[k]["name"])):
        p = cur[pkg]
        sub = "Subtitles" in p["name"]
        for sid in sorted(p["strings"], key=int):
            en = p["strings"][sid]
            if not en.strip() or en in seen:
                continue
            seen.add(en)
            masked, toks = mask(en)
            plain = re.sub(r"⟦\d+⟧", "", masked).strip()
            if not re.search(r"[A-Za-z]", plain):
                kind = "copy"  # only markup / numbers: nothing to translate
            elif not sub and len(plain.split()) <= 5 and not SENTENCE.search(plain) and "\n" not in plain:
                kind = "term"
            else:
                kind = "text"
            con.execute("INSERT OR IGNORE INTO units (en, kind, pkg, ord) VALUES (?,?,?,?)", (en, kind, p["name"], n))
            n += 1
    con.execute("UPDATE units SET ro = en, status = 'ok' WHERE kind = 'copy' AND ro IS NULL")
    con.commit()
    for kind, c in con.execute("SELECT kind, count(*) FROM units GROUP BY kind"):
        print(f"{kind}: {c}")


FIXED = """Termeni ficși (decizii de glosar, folosește-i exact):
  Pommel → măciulie (capătul mânerului; NICIODATĂ „pom”) · Handle → mâner · Guard (la armă) → gardă ·
  Saya → teacă (articulat: teaca; niciodată „tecaua”) · Blade → lamă · Kanabo Club / Club (armă) → kanabō
  („Eikyo Kanabo Club” → „Kanabō Eikyo”) · Teppo → teppō · Tanto → tantō · Bo (armă) → bō · Kanabo → kanabō ·
  Leap of Faith → Saltul credinței · Eagle Vision → Vederea vulturului · Hidden Blade → Lama ascunsă ·
  Animus → Animus · Kakurega → kakurega.
  Titlurile de jocuri și expansiuni rămân în engleză: Shadows, Odyssey, Origins, Valhalla, Mirage, Black Flag
  (Resynced), Claws of Awaji (→ „expansiunea Claws of Awaji”) · CE → d.Hr. · BCE → î.Hr. (niciodată e.n./î.e.n.) ·
  „Track down X” → „Găsește-l pe X” (nu „Urmărește”, nu „Dă de urma”) · „Quit to X” → „Înapoi la X”,
  „Quit to Desktop” → „Ieși din joc” · „Gambit” → „Șiretlic”."""

TERM_RULES = """Ești traducătorul român al jocului Assassin's Creed Shadows (Japonia feudală, 1579). Traduci termeni scurți din
interfață: nume de iteme, arme, armuri, abilități, locuri, misiuni, titluri, categorii de meniu, butoane.
Acești termeni devin glosarul fix al traducerii, deci alege varianta pe care un român ar folosi-o firesc și consecvent.
- Numele proprii japoneze rămân (Naoe, Yasuke, Oda Nobunaga, Iga, Kyoto, Azuchi, Kakurega, Mon, Shinbakufu); la fel
  termenii japonezi consacrați (katana, tantō, naginata, kanabō, kusarigama, shinobi, samurai, rōnin, daimyō, kami).
- Iteme: ordinea românească ("Punisher Samurai Helmet" → "Coiful samuraiului pedepsitor"), majusculă doar la primul
  cuvânt și la numele proprii, fără articol nehotărât.
- Butoane și meniuri: forma scurtă de imperativ sau substantiv obișnuită în jocurile traduse în română
  ("Equip" → "Echipează", "Settings" → "Setări", "Load" → "Încarcă").
- Fără arhaisme, fără argou modern, fără anglicisme inutile.
- Textul cu ⟦1⟧, ⟦2⟧ … conține marcaje care trebuie păstrate exact, în aceeași ordine logică.
- """ + FIXED + """
Răspunde DOAR cu JSON: {"t":[{"id":<id>,"f":"<traducere>","m":""}]}, câte un rând pentru fiecare id."""

TEXT_RULES = """Ești traducătorul român al jocului Assassin's Creed Shadows. Traduci replici, descrieri și texte de interfață.
Respectă ghidul de stil de mai jos și GLOSARUL dat pentru fiecare lot: termenii din glosar se scriu exact așa, în
forma gramaticală potrivită (articulat, plural, genitiv), dar cu același cuvânt.
- Replicile: româna vorbită firesc, cum ar spune-o un român, nu cuvânt cu cuvânt. Fără calcuri și fără arhaisme.
- Când nu e clar cui i se adresează replica (Naoe e femeie, Yasuke e bărbat), preferă o formulare neutră ca gen.
- Marcajele ⟦1⟧, ⟦2⟧ … sunt cod de joc: păstrează-le pe toate exact, o dată fiecare, în locul potrivit din frază.
  Păstrează și rupturile de rând (\\n).
- Textul între paranteze drepte fără ⟦⟧ (de ex. „[Refuse]”) e vizibil pentru jucător: îl traduci, păstrând parantezele.
- Diacritice complete: ă â î ș ț (cu virgulă dedesubt).
- """ + FIXED + """
Răspunde DOAR cu JSON: {"t":[{"id":<id>,"f":"<traducere>","m":""}]}, câte un rând pentru fiecare id.

GHID DE STIL:
""" + STYLE


def glossary(con):
    return {en: ro for en, ro in con.execute(
        "SELECT en, ro FROM units WHERE kind = 'term' AND status = 'ok' AND ro IS NOT NULL")}


def glossary_for(texts, gl, index):
    """Glossary entries (≥ 2 words or capitalized) whose English occurs in the batch, longest first, max 80."""
    hits = {}
    blob = "\n".join(texts)
    for en, ro in index:
        if en in blob and re.search(rf"(?<![A-Za-z]){re.escape(en)}(?![A-Za-z])", blob):
            hits[en] = ro
            if len(hits) >= 80:
                break
    return hits


def client():
    return anthropic.Anthropic(api_key=llm.anthropic_key(), max_retries=5)


def run(kind, size, only_missing):
    con = db()
    where = "kind = ? AND (ro IS NULL OR status = 'fail')" if only_missing else "kind = ? AND ro IS NULL"
    rows = con.execute(f"SELECT id, en, pkg FROM units WHERE {where} ORDER BY ord", (kind,)).fetchall()
    if not rows:
        print("nothing to translate")
        return
    gl = glossary(con)
    index = sorted(((en, ro) for en, ro in gl.items() if len(en) > 3 and (" " in en or en[:1].isupper())),
                   key=lambda kv: -len(kv[0]))
    reqs, plan = [], {}
    for b in range(0, len(rows), size):
        batch = rows[b:b + size]
        lines, meta = [], []
        for i, (uid, en, pkg) in enumerate(batch):
            m, toks = mask(en)
            lines.append({"id": i, "en": m, "ctx": pkg})
            meta.append([uid, toks])
        user = {"lines": lines}
        if kind == "text":
            g = glossary_for([en for _, en, _ in batch], gl, index)
            user = {"glossary": g, "lines": lines}
        cid = f"{kind}{b // size}"
        reqs.append(Request(custom_id=cid, params=MessageCreateParamsNonStreaming(
            model=MODEL, max_tokens=16000,
            system=[{"type": "text", "text": TERM_RULES if kind == "term" else TEXT_RULES,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": json.dumps(user, ensure_ascii=False)}],
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": llm.LINES_SCHEMA}})))
        plan[cid] = meta
    batch = client().messages.batches.create(requests=reqs)
    PLANS.mkdir(exist_ok=True)
    (PLANS / f"{batch.id}.json").write_text(json.dumps({"pass": kind, "plan": plan}, ensure_ascii=False),
                                            encoding="utf-8")
    con.execute("INSERT INTO batches VALUES (?,?,?,NULL)", (batch.id, kind, time.time()))
    con.commit()
    print(f"submitted {batch.id}: {len(reqs)} requests, {len(rows)} units", flush=True)
    wait(batch.id)
    apply(batch.id)


def wait(batch_id):
    c = client()
    while True:
        b = c.messages.batches.retrieve(batch_id)
        rc = b.request_counts
        done = rc.succeeded + rc.errored + rc.canceled + rc.expired
        print(f"{time.strftime('%H:%M')} {b.processing_status}: {done}/{done + rc.processing} "
              f"({rc.errored} errored)", flush=True)
        if b.processing_status == "ended":
            return
        time.sleep(60)


def check(en, ro):
    """QA: same markup, no leftover mask, not empty, not untranslated English."""
    if not ro.strip():
        return "empty"
    if "⟦" in ro or "⟧" in ro:
        return "unmasked marker left"
    if sorted(PROTECT.findall(en)) != sorted(PROTECT.findall(ro)):
        return "markup differs"
    if en.count("\n") != ro.count("\n"):
        return "line breaks differ"
    words = re.findall(r"[A-Za-z]{4,}", PROTECT.sub("", en))
    if len(words) >= 4 and ro == en:
        return "unchanged"
    return None


def apply(batch_id):
    data = json.loads((PLANS / f"{batch_id}.json").read_text(encoding="utf-8"))
    plan = data["plan"]
    out = PLANS / f"{batch_id}.results.jsonl"
    url = client().messages.batches.retrieve(batch_id).results_url
    subprocess.run(["curl", "-sS", "--retry", "5", "--retry-all-errors", "-o", str(out),
                    "-H", f"x-api-key: {llm.anthropic_key()}", "-H", "anthropic-version: 2023-06-01", url], check=True)
    con = db()
    tok = {"in": 0, "cw": 0, "cr": 0, "out": 0}
    ok = bad = lost = 0
    now = time.time()
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
        text = next((c["text"] for c in msg["content"] if c["type"] == "text"), "")
        try:
            got = {x.get("id"): x.get("f", "") for x in json.loads(text).get("t", [])}
        except ValueError:
            lost += len(meta)
            continue
        for i, (uid, toks) in enumerate(meta):
            if i not in got:
                lost += 1
                continue
            en = con.execute("SELECT en FROM units WHERE id = ?", (uid,)).fetchone()[0]
            ro = unmask(got[i], toks).replace("ş", "ș").replace("ţ", "ț").replace("Ş", "Ș").replace("Ţ", "Ț")
            # the game's leading/trailing whitespace and newlines are layout: copy them from the original exactly
            lead, trail = en[:len(en) - len(en.lstrip())], en[len(en.rstrip()):]
            ro = lead + ro.strip() + trail
            problem = check(en, ro)
            con.execute("UPDATE units SET ro = ?, status = ?, notes = ?, model = ?, updated = ? WHERE id = ?",
                        (ro, "fail" if problem else "ok", problem, MODEL, now, uid))
            bad += bool(problem)
            ok += not problem
    con.execute("UPDATE batches SET applied = ? WHERE batch_id = ?", (now, batch_id))
    con.commit()
    p = llm.PRICES[MODEL]
    usd = (tok["in"] * p[0] + tok["cw"] * p[1] + tok["cr"] * p[2] + tok["out"] * p[3]) / 1e6 / 2
    print(f"applied {batch_id}: {ok} ok, {bad} failed QA, {lost} lost; tokens {tok}; cost ${usd:.2f} (batch -50%)")


def stats():
    con = db()
    for row in con.execute("SELECT kind, status, count(*) FROM units GROUP BY kind, status ORDER BY kind, status"):
        print(row)
    for row in con.execute("SELECT notes, count(*) FROM units WHERE status = 'fail' GROUP BY notes"):
        print("  fail:", row)


if __name__ == "__main__":
    a = sys.argv[1:]
    opt = {a[i][2:]: a[i + 1] for i in range(len(a) - 1) if a[i].startswith("--") and not a[i + 1].startswith("--")}
    if a[0] == "prepare":
        prepare()
    elif a[0] == "run":
        run(a[1], int(opt.get("size", 40)), "--only-missing" in a)
    elif a[0] == "apply":
        apply(a[1])
    elif a[0] == "stats":
        stats()
