# Assassin's Creed Shadows — Traducere în limba română

Traducere neoficială, făcută de fani, a textului din **Assassin's Creed Shadows** (jocul de bază, versiunea 1.1.13):
meniuri, misiuni și obiective, iteme și abilități, codex, scrisori și subtitrări. Vocea rămâne cea originală.

**Descarcă mod-ul:** Nexus Mods: https://www.nexusmods.com/assassinscreedshadows/mods/279

Acest repository e locul unde **oricine poate corecta traducerea**: o replică ciudată, un termen tradus greșit,
o formulare care nu sună românește. Corecturile acceptate intră în următoarea versiune a mod-ului.

## Instalare

1. Descarcă arhiva de pe Nexus și copiază `DataPC_boot_patch_03.forge` în folderul jocului, lângă
   `ACShadows.exe` (de ex. `...\steamapps\common\Assassin's Creed Shadows\`).
2. Pornește jocul. Limba textului din joc rămâne **English**: mod-ul înlocuiește textul englezesc cu cel românesc.

Dezinstalare: ștergi `DataPC_boot_patch_03.forge`. Mod-ul nu e compatibil cu alte moduri care folosesc tot
`DataPC_boot_patch_03.forge`. După un update al jocului, s-ar putea să fie nevoie de o versiune nouă a mod-ului.

## Claws of Awaji și alte jocuri

Expansiunea **Claws of Awaji** nu e inclusă: are fișierele ei separate, iar eu nu o am. Dacă vrei s-o traduc, mi-o
poți face cadou pe [Steam](https://steamcommunity.com/profiles/76561199120542317). La fel, dacă vrei alt joc tradus în
română, scrie-mi pe Nexus în comentarii. Nu e obligatoriu: traducerile rămân gratuite.

## Cum ajuți

- **Ai găsit o greșeală, dar nu vrei să editezi fișiere?** Deschide un
  [Issue „Greșeală de traducere”](../../issues/new/choose): scrii unde apare, ce e greșit și ce ai propune.
  O captură de ecran ajută mult.
- **Vrei să corectezi direct?** Vezi [CONTRIBUTING.md](CONTRIBUTING.md): găsești textul în `translations/`, editezi
  câmpul `"ro"` și trimiți un Pull Request. Se poate face și din browser, fără să instalezi nimic.

## Ce e în repository

| Folder | Ce conține |
|---|---|
| `translations/` | Tot textul, câte un fișier JSON pentru fiecare pachet de localizare din joc: originalul (`en`) și traducerea (`ro`). Pachetele mari sunt împărțite în bucăți `.001.json`, `.002.json`... |
| `glossary/termeni.csv` | Termenii scurți din interfață (iteme, abilități, obiective, locuri) și cum sunt traduși |
| `glossary/REGULI_DE_STIL.md` | Regulile de stil ale traducerii |
| `tools/check.py` | Verificarea automată rulată pe fiecare Pull Request |
| `pipeline/` | Scripturile cu care a fost făcută traducerea și construit mod-ul (pentru cine e curios) |

## Cum a fost făcută

Textul a fost extras din joc cu un driver propriu peste [AnvilToolkit](https://www.nexusmods.com/assassinscreedodyssey/mods/266)
(pachetele `LocalizationPackage` sunt rescrise de `pipeline/locpkg.py`, care păstrează formatul Ubisoft), apoi
tradus cu un model de limbaj AI (Claude), ghidat de glosar și de regulile de stil, trecut prin două runde de editare
„să sune cum vorbește un român azi” și verificat în joc. Tocmai de aceea ajută orice corectură venită de la oameni
care joacă.

Licențe și drepturi: vezi [NOTICE.md](NOTICE.md).
