# Lithuanian Shorts — vidinis įrankis

Du dalykai, kurių prašėte:

1. **Filmų programų pasiūlymų rengimas** iš archyvo (lithuanianshorts.com), laikantis
   filmų skaičiaus ir bendros trukmės ribų.
2. **Filmų rodymų ataskaitų rengimas** — kur, kada, kiek kartų rodyta ir kokios pajamos.

Abu rezultatai eksportuojami į **Word (.docx)** ir **PDF**, **lietuvių arba anglų kalba**.

---

## Kur saugomi duomenys

Archyvas, rodymai ir vartotojai saugomi **Supabase** (Postgres)
duomenų bazėje, todėl visa komanda mato tuos pačius duomenis, o įrankis veikia
ir internete. Prieiga — su el. paštu ir slaptažodžiu; paskyras kuria
administratorius skiltyje **Vartotojai**.

## Paleidimas kompiuteryje

```bash
pip install -r requirements.txt
```

Nusikopijuokite `.env.example` į `.env` ir įrašykite `SUPABASE_URL`,
`SUPABASE_SERVICE_KEY` bei `FLASK_SECRET_KEY`.

```bash
python run.py serve
```

Tada naršyklėje atidarykite <http://127.0.0.1:5000>.

## Duomenų bazės paruošimas

Supabase SQL redaktoriuje paleiskite iš eilės:

| Failas | Ką sukuria |
|---|---|
| `sql/01_schema.sql` | filmai, raktažodžiai, rodymai, dokumentai |
| `sql/02_auth.sql` | vartotojai ir prisijungimo funkcijos |
| `sql/03_rls.sql` | RLS — viešieji raktai nemato nieko |
| `sql/04_seed_admin.sql` | pirmasis administratorius (pakeiskite el. paštą ir slaptažodį) |
| `sql/05_keepalive.sql` | lentelė, į kurią rašo kasdienis „nemiegok" signalas |

Seni failai iš `data/` perkeliami vieną kartą:

```bash
python migrate_to_supabase.py
```

## Archyvo atnaujinimas

```bash
python run.py scrape
```

Paleidžiama kompiuteryje — rezultatas įrašomas į tą pačią duomenų bazę, tad
internetinis įrankis jį pamato iš karto. Viso archyvo perkrovimas trunka
minutes, todėl serveryje vienu kartu to daryti negalima.

Kad nauji svetainės filmai atsirastų patys, Vercel kas pirmadienį 4:00 kviečia
`/api/sync-films`. Tai tas pats atnaujinimas, tik pritaikytas serveriui: jau
turimi raktažodžių vertimai panaudojami pakartotinai, o per vieną kartą paimama
iki 40 naujausių pasikeitusių filmų (ir ne ilgiau kaip 120 sek.) — kas nespėta,
pasiimama kito paleidimo metu. Išmatuota su tikra svetaine: paleidimas be naujų
filmų trunka ~8 sek., su 12 naujų — ~10 sek.

Nelaukti savaitės nebūtina: skiltyje **Archyvas** yra mygtukas **„Atnaujinti iš
svetainės"** — jis daro tą patį čia ir dabar, parodo, kiek filmų perimta, ir
jei kažkas nespėta, kiek liko (tada spaudžiama dar kartą). Ten pat matyti ir
kada archyvas atnaujintas paskutinį kartą. Iš komandinės eilutės tą patį daro
`python run.py scrape`, o `--force` perkrauna visus filmus nuo nulio.

## Kad Supabase neužmigtų

Nemokamas Supabase projektas sustabdomas, jei savaitę negauna „pakankamai
duomenų bazės veiklos" — dokumentacijoje tai apibūdinta kaip *keli kreipimaisi
per dieną*. Anksčiau signalas buvo siunčiamas du kartus per savaitę ir tik
skaitė vieną eilutę; to nepakako ir 2026-09-21 projektas buvo sustabdytas.

Dabar:

- Vercel kviečia `/api/keepalive` **kasdien** (9:00; Hobby plane cron'as
  paleidžiamas tos valandos bėgyje);
- signalas ne tik skaito, bet ir **rašo** į `keepalive` lentelę, o joje lieka
  paskutinio sėkmingo kreipimosi laikas ir bendras skaičius;
- tą patį adresą kasdien kviečia ir GitHub Actions
  (`.github/workflows/keepalive.yml`) — nepriklausomas antras signalas, kuris,
  jei nepavyksta, **atsiunčia laišką**. Vercel cron'o klaida nematoma niekur,
  išskyrus logus, todėl ir nepastebėjome.

Reikia dviejų GitHub repozitorijos „secrets": `KEEPALIVE_URL`
(`https://<adresas>/api/keepalive`) ir `CRON_SECRET` (toks pat kaip Vercel).

Jei projektas vis dėlto sustabdomas, jį reikia atstatyti ranka Supabase
skydelyje („unpause"); duomenys 90 dienų niekur nedingsta.

## Paleidimas internete (Vercel)

1. Vercel → **Add New → Project** → `upshift-app/lithuanian-shorts`.
2. Root Directory palikite `./`, Framework — **Other** (`vercel.json` viską nurodo).
3. Environment Variables: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `FLASK_SECRET_KEY`.
4. Deploy.

`SUPABASE_SERVICE_KEY` apeina RLS, todėl jis laikomas **tik** serverio pusėje —
niekada naršyklėje ir niekada `NEXT_PUBLIC_`-tipo kintamajame.

---

## Iš kur imami duomenys

Svetainė sukurta su WordPress, todėl duomenys imami tiesiai iš jos — jokių
rankinių eksportų nereikia:

| Duomuo | Šaltinis |
|---|---|
| Filmų sąrašas, raktažodžiai, kategorijos | WordPress REST API (`filmas`, `post_tag`, `kategorija`) |
| Metai, žanras, trukmė, šalis, komanda, anotacija | Filmo puslapio HTML |
| Angliški pavadinimai, anotacijos, žanrai | Angliška to paties filmo versija (`/en/film-database/...`) |
| Rodymai ir įkainiai | `data/screenings.xlsx` (jūsų pildoma lentelė) |

Šiuo metu archyve **435 filmai**. Visi turi trukmę, metus, žanrą ir anglišką
versiją; **179 filmai turi raktažodžius** (tai katalogo filmai nuo 2020 m.,
kaip ir minėjote).

`python run.py scrape` galima leisti bet kada — perkraunami tik tie filmai,
kurie svetainėje pasikeitė, todėl atnaujinimas greitas.

---

## 1. Filmų programos

Skiltis **Programos**. Pasirenkate:

- **temą** — raktažodžius (iš tų pačių 150 svetainės raktažodžių), laisvo teksto
  paiešką, žanrą;
- **apribojimus** — filmų skaičių (numatyta 5–6), bendros trukmės intervalą
  (numatyta 75–90 min), metų intervalą;
- **konkrečius filmus**, kuriuos būtina įtraukti arba atmesti (pagal ID).

Įrankis pateikia **1–5 skirtingus programos variantus**. Viršutinė trukmės riba
griežta — bendra trukmė jos niekada neviršija; apatinė yra tikslas: programa
renkama taip, kad pakliūtų į intervalą, o jei nepavyksta, dokumente atsiranda
pastaba. Nereikia apatinės ribos — įrašykite 0.

Kaip ir prašėte, po variantų pateikiamas sąrašas **„Taip pat tematiškai tiktų“** —
filmai, kurie atitinka temą, bet netilpo į trukmės limitą.

Kiekvienas variantas vertinamas pagal keturis rodiklius:

| Rodiklis | Ką vertina |
|---|---|
| Atitikimas | kiek filmo raktažodžiai sutampa su užklausa |
| Padengimas | ar programa paliečia visus prašytus raktažodžius |
| Trukmė | ar bendra trukmė pakliūva į nurodytą intervalą |
| Dermė | ar nesikartoja režisieriai, ar išlaikyta žanrų, metų ir trukmių įvairovė |

Dokumente pateikiama: programos lentelė, kiekvieno filmo anotacija ir metaduomenys,
raktažodžiai ir nuoroda į filmo puslapį.

### Komandinė eilutė

```bash
python run.py programme -k "šeima,vaikystė" --year-from 2018 --lang lt
```

```bash
python run.py programme -k "gamta,bendruomenė" --max-minutes 75 --lang en --format pdf
```

---

## 2. Rodymų ataskaitos

Skiltis **Ataskaitos**. Rodymai vedami pačiame įrankyje (skiltis **Rodymai**) ir
saugomi duomenų bazėje — vienas seansas viena eilutė:

| Stulpelis | Reikšmė |
|---|---|
| `film_id` | filmo ID (rasite skiltyje **Archyvas**) |
| `film_title` | filmo pavadinimas (jei ID nežinomas) |
| `event` | renginys / festivalis |
| `venue`, `city`, `country` | vieta |
| `date` | data (`YYYY-MM-DD`) |
| `screenings` | kiek kartų rodyta |
| `fee_eur` | **įkainis eurais** — įrašomas ranka |
| `programme` | programos pavadinimas |
| `notes` | pastabos |

Įkainių formulės nėra — kaip ir sakėte, kiekvienas atvejis vertinamas atskirai,
todėl `fee_eur` yra tiesiog laukelis, į kurį įrašote sumą. Pajamos skaičiuojamos
kaip `fee_eur × screenings`.

Ataskaitą galima filtruoti pagal filmą, režisierių ir datų intervalą — tinka
rengti ataskaitą vienam kūrėjui apie jo filmą. PDF ir Word atsisiunčiate patys
ir siunčiate, kam reikia.

Skiltyje **Ataskaitos** yra ir **pavyzdys** (PDF / Word) — tikri archyvo filmai
su išgalvotais rodymais, datomis ir sumomis. Skirtas parodyti dokumento formą,
kol tikrų rodymų dar neįvesta; dokumento viršuje aiškiai parašyta, kad duomenys
netikri.

```bash
python run.py report --director "Vardas Pavardė" --date-from 2025-01-01 --lang en
```

---

## Komandos

| Komanda | Ką daro |
|---|---|
| `python run.py serve` | paleidžia vidinį web įrankį |
| `python run.py scrape` | atnaujina filmų archyvą iš svetainės |
| `python run.py scrape --force` | perkrauna visus filmus iš naujo |
| `python run.py keywords` | parodo visus raktažodžius, žanrus, kategorijas |
| `python run.py programme ...` | sudaro programą iš komandinės eilutės |
| `python run.py report ...` | parengia ataskaitą iš komandinės eilutės |

Iš komandinės eilutės sugeneruoti dokumentai išsaugomi kataloge `output/`;
web įrankyje jie atsisiunčiami tiesiai iš naršyklės.

---

## Šriftai

Programos pasiūlymas renkamas serifiniu šriftu. Pirmenybė — **Times New Roman**
(kompiuteryje jis yra), paskui **Liberation Serif**, o jei nė vieno nėra —
**DejaVu Serif**. Vercel serveryje sisteminių šriftų nėra, todėl ten naudojamas
DejaVu Serif. Norint, kad ir internete dokumentas atrodytų kaip Times, į
`ls_tool/assets/fonts/` reikia įdėti keturis `LiberationSerif-*.ttf` failus
(jis Times atitinka raidė į raidę) — daugiau nieko keisti nereikia.

---

## Failų struktūra

```
ls_tool/
  scraper.py      duomenų surinkimas iš svetainės (LT + EN)
  catalog.py      filmų modelis, filtravimas
  programme.py    programų sudarymo logika ir vertinimas
  screenings.py   rodymų lentelė ir ataskaitų skaičiavimas
  i18n.py         lietuviški / angliški dokumentų tekstai
  export_docx.py  Word eksportas
  export_pdf.py   PDF eksportas
  fonts.py        šriftas su lietuviškomis raidėmis PDF'uose
  webapp.py       web įrankis (Flask)
  store.py        visa prieiga prie Supabase
  auth.py         prisijungimas ir teisės
  cli.py          komandinė eilutė
  assets/fonts/   DejaVu šriftai (kad PDF veiktų ir Linux serveryje)
api/index.py      Vercel įėjimo taškas
sql/              Supabase schema, prisijungimo funkcijos, RLS
migrate_to_supabase.py   vienkartinis senų failų importas
output/           sugeneruoti Word ir PDF dokumentai (tik komandinė eilutė)
```

## Reikalavimai

Python 3.9+. Bibliotekos — `requirements.txt`.
PDF'ams naudojamas Calibri arba Arial (lietuviškos raidės), automatiškai
parenkamas iš sistemos.
