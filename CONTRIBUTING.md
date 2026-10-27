# Cum corectezi traducerea

## 1. Găsește textul

Toată traducerea e în `translations/`, câte un fișier pentru fiecare pachet de localizare din joc:

- `MAIN_General.*.json`: meniuri, iteme, abilități, obiective, codex, scrisori
- `MAIN_Subtitles.*.json`: dialoguri și subtitrări
- `EVT_*`, `FUNC_*`, `SP_*`, `EXP_*`: evenimente, funcții adăugate prin update-uri, conținut special

Cel mai simplu: apasă `T` pe pagina repository-ului (sau folosește căutarea GitHub) și caută textul **în engleză**
sau o bucată din traducerea greșită.

## 2. Editează doar câmpul `"ro"`

Fiecare text arată așa:

```json
{
 "id": "12411925795714194803",
 "en": "Hiromichi sent you, didn't he?",
 "ro": "Te-a trimis Hiromichi, nu?"
}
```

- Schimbi **doar** textul din `"ro"`. **Nu** schimba `"id"`, `"en"`, `"package"` sau `"data_id"`.
- Păstrează exact marcajele din engleză: `{0}`, `{NumberTag}`, `[NumberTag]`, `[BOLD_BEGIN]`/`[BOLD_END]`,
  `[[laughs]`, `[beat]`, `<style ...>`, `[CT_...]`, și rupturile de rând. Verificarea automată respinge textul
  dacă lipsesc sau apar în plus.
- Scrie **cu diacritice** (ă, â, î, ș, ț): fontul jocului le are.
- Un text englezesc care apare de mai multe ori în joc are aceeași traducere peste tot; ajunge să-l corectezi o dată.

Din browser: deschizi fișierul pe GitHub, apeși creionul (Edit), modifici, apoi **Commit changes → Create a new branch
→ Propose changes**. GitHub face singur fork-ul și Pull Request-ul.

## 3. Regulile de stil, pe scurt

Detaliile sunt în [glossary/REGULI_DE_STIL.md](glossary/REGULI_DE_STIL.md).

- **Româna vorbită azi**: cuvinte uzuale, fraze simple, nimic livresc sau de manual („încăpățânată”, nu
  „înverșunată”; „ca să”, nu „pentru a”; „o să fac”, nu „voi face” în replici).
- Epoca (Japonia, 1579) înseamnă doar: fără argou și fără anglicisme. Nu înseamnă cuvinte vechi sau solemne.
- Expresiile se traduc **după sens**, cum ar zice un român, nu cuvânt cu cuvânt.
- Numele japoneze rămân (Naoe, Yasuke, Oda Nobunaga, Iga), la fel katana, tantō, kanabō, shinobi, rōnin.
  „Lord X” → „Seniorul X”, „Lady X” → „Doamna X”.
- Titlurile de jocuri și expansiuni rămân în engleză (Shadows, Claws of Awaji). Anii: d.Hr. / î.Hr.
- Obiectivele sunt la imperativ: „Găsește-l pe X”, „Întâlnește-te cu X”, „Întoarce-te la X”.
- Iteme și abilități se scriu **exact** ca în [glossary/termeni.csv](glossary/termeni.csv). Dacă vrei să schimbi un
  termen, deschide întâi un Issue: el poate apărea în multe locuri.
