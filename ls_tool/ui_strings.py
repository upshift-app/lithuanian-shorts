"""Interface strings for the internal web tool.

Kept separate from the document strings in ls_tool.i18n on purpose: the team may
browse the tool in English while still exporting a Lithuanian PDF, or the other
way round. The navbar switch changes only what is in here.

Key prefixes: ``nav_``/``th_`` shared chrome, ``p_`` programme page,
``r_`` reports page, ``a_`` archive page.
"""
from __future__ import annotations

from typing import Optional

STRINGS = {
    "lt": {
        # ------------------------------------------------------------- chrome
        "nav_programmes": "Programos",
        "nav_reports": "Ataskaitos",
        "nav_archive": "Archyvas",
        "films_count": "filmai",
        "updated": "atnaujinta",
        "switch_lang": "EN",
        "switch_title": "Switch to English",
        "footer": "Vidinis įrankis · duomenys iš lithuanianshorts.com",
        "dir_prefix": "rež.",
        "download_pdf": "Atsisiųsti PDF",
        "download_word": "Atsisiųsti Word",

        # ------------------------------------------------------ table headers
        "th_no": "Nr.",
        "th_id": "ID",
        "th_film": "Filmas",
        "th_year": "Metai",
        "th_genre": "Žanras",
        "th_duration": "Trukmė",
        "th_keywords": "Raktažodžiai",
        "th_total": "Iš viso",
        "th_date": "Data",
        "th_event": "Renginys",
        "th_venue": "Vieta",
        "th_films": "Filmai",
        "th_events": "Renginiai",
        "th_screenings": "Seansai",
        "th_revenue": "Pajamos",

        # --------------------------------------------------- programme page
        "p_title": "Filmų programos pasiūlymas",
        "p_lede": "Pasirinkite temą ir apribojimus. Įrankis iš {n} archyvo filmų "
                  "sudarys programos variantus, neviršydamas filmų skaičiaus ir "
                  "bendros trukmės.",
        "p_name": "Programos pavadinimas",
        "p_name_ph": "pvz. Šeima ir vaikystė",
        "p_occasion": "Renginys / kontekstas",
        "p_occasion_ph": "pvz. festivalis, teambuilding",
        "p_intro": "Programos aprašymas",
        "p_intro_ph": "Kelios pastraipos apie programą — spausdinamos dokumento pradžioje",
        "p_rating": "Amžiaus cenzas",
        "p_rating_ph": "pvz. N-16",
        "p_rating_none": "Nenurodyta",
        "p_rating_custom": "Kita...",
        "p_doclang": "Dokumento kalba",
        "p_doclang_hint": "Word ir PDF kalba: pavadinimai, anotacijos ir antraštės.",
        "p_theme": "Tema",
        "p_keywords": "Raktažodžiai",
        "p_keywords_hint": "Naudojami filmų, įtrauktų į katalogą nuo 2020 m., "
                           "raktažodžiai.",
        "p_query": "Laisvo teksto paieška",
        "p_query_ph": "ieško pavadinime ir anotacijoje",
        "p_extra_kw": "Papildomi raktažodžiai",
        "p_extra_kw_ph": "atskirti kableliais",
        "p_genre": "Žanras",
        "p_genre_hint": "Nepasirinkus įtraukiami visi žanrai.",
        "p_genre_all": "Visi žanrai",
        "p_variants_all": "Visi",
        "p_variants_found": "Pagal šiuos kriterijus rasta skirtingų variantų: {n}.",
        "p_limits": "Apribojimai",
        "p_films_from": "Filmų nuo",
        "p_films_to": "Filmų iki",
        "p_max_minutes": "Maks. trukmė (min)",
        "p_year_from": "Metai nuo",
        "p_year_to": "Metai iki",
        "p_variants": "Variantų skaičius",
        "p_pin": "Būtinai įtraukti (filmų ID)",
        "p_pin_ph": "pvz. 22005, 21877",
        "p_exclude": "Neįtraukti (filmų ID)",
        "p_submit": "Sudaryti programą",
        "p_id_hint_pre": "ID rasite",
        "p_id_hint_post": "skiltyje.",
        "p_fail": "Nepavyko sudaryti programos.",
        "p_fail_body": "Pagal šiuos kriterijus rasta {n} tinkamų filmų. Pabandykite "
                       "atlaisvinti filtrus arba padidinti trukmės ribą.",
        # --- field help, shown behind the "i" next to each label
        "h_name": "Programos pavadinimas. Jis atsiduria dokumento viršuje ir "
                  "failo pavadinime. Paliktas tuščias - dokumentas vadinsis "
                  "\u201eFilmų programos pasiūlymas\u201c.",
        "h_occasion": "Renginys, kuriam programa skirta. Naujame PDF nerodomas - "
                      "tai tik jūsų žyma pasiūlymams atskirti.",
        "h_rating": "Amžiaus cenzas, spausdinamas po trukme. Pasirinkite iš "
                    "sąrašo arba \u201eKita...\u201c ir įrašykite savo.",
        "h_doclang": "Kokia kalba rengiamas dokumentas: lietuviški pavadinimai "
                     "ir anotacijos ar angliški. Sąsajos kalba nesikeičia.",
        "h_intro": "Įžanginė pastraipa apie visą programą. Galite įrašyti čia "
                   "arba vėliau, prie pasirinkto varianto, kur yra ir AI "
                   "juodraščio mygtukas.",
        "h_intro_option": "Ši pastraipa atsiduria dokumento pradžioje. "
                          "\u201eParašyti aprašymą (AI)\u201c parengia "
                          "juodraštį pagal šio varianto filmus - perskaitykite "
                          "ir pataisykite prieš siųsdami.",
        "h_keywords": "Programos tema. Pažymėti raktažodžiai filmų neatmeta, o "
                      "kelia juos aukščiau atrankoje. Skaičius skliaustuose - "
                      "kiek archyvo filmų tuo pažymėti.",
        "h_query": "Paieška filmo tekste: pavadinime, anotacijoje, žanre, "
                   "režisieriaus pavardėje, šalyje, raktažodžiuose. Tai griežtas "
                   "filtras ir turi sutapti VISI įrašyti žodžiai, todėl keli "
                   "žodžiai greitai nepalieka nė vieno filmo.",
        "h_extra_kw": "Raktažodžiai, kurių nėra sąraše. Rašomi kableliais, "
                      "veikia taip pat kaip pažymėtieji.",
        "h_genre": "Palikite \u201eVisi žanrai\u201c ir programa gali juos "
                   "maišyti. Pažymėjus kelis - filmai bus tik iš jų.",
        "h_films_from": "Mažiausias filmų skaičius programoje. Jei tiek "
                        "nesusidaro, dokumente atsiranda pastaba.",
        "h_films_to": "Didžiausias filmų skaičius programoje.",
        "h_max_minutes": "Bendros trukmės riba minutėmis. Ilgesni filmai iškrenta "
                         "iš karto, o programa renkama taip, kad kuo geriau "
                         "užpildytų šį laiką.",
        "h_year_from": "Ankstyviausi filmo metai. Tuščia - nuo seniausio archyve.",
        "h_year_to": "Vėliausi filmo metai. Tuščia - iki naujausio archyve.",
        "h_variants": "Kiek skirtingų programos variantų parodyti. "
                      "\u201eVisi\u201c - tiek, kiek pavyks sudaryti (iki 8).",
        "h_strict_kw": "Į atranką patenka tik filmai, turintys bent vieną iš "
                       "pažymėtų raktažodžių. Be varnelės raktažodžiai tik kelia "
                       "filmus aukščiau.",
        "h_pin": "Filmų ID, kurie privalo būti programoje. Jiems kiti filtrai "
                 "netaikomi. ID rasite archyvo puslapyje.",
        "h_exclude": "Filmų ID, kurių į programą neįtraukti. Kableliais.",
        "p_proposals": "Pasiūlymai",
        "p_download_hint": "Atsisiųskite tą variantą, kurį pasirinkote - į dokumentą pateks tik jis.",
        "p_describe": "Parašyti aprašymą (AI)",
        "p_describing": "Rašoma...",
        "p_variant": "{n} variantas",
        "p_films": "filmai",
        "p_match": "atitikimas",
        "p_coverage": "Raktažodžių atitikimas:",
        "p_alternates": "Taip pat tematiškai tiktų",
        "p_alternates_note": "Atitinka temą, bet netilpo į trukmės limitą.",

        # ------------------------------------------------------ reports page
        "r_title": "Filmų rodymų ataskaita",
        "r_lede": "Kur ir kada filmas rodytas, kiek kartų ir kokias pajamas surinko. "
                  "Duomenys imami iš rodymų žurnalo.",
        "r_sheet_error": "Lentelės klaida:",
        "r_empty": "Dar neįrašytas nė vienas rodymas",
        "r_empty_body": "Ataskaita sudaroma iš rodymų žurnalo. Įrašykite pirmąjį "
                        "rodymą - kur, kada, kiek seansų ir koks įkainis - ir "
                        "ataskaitą galėsite parengti iš karto.",
        "r_fee_note": "Įkainį įrašote ranka kiekvienam rodymui, o pajamos "
                      "apskaičiuojamos padauginus jį iš seansų skaičiaus.",
        "r_name": "Ataskaitos pavadinimas",
        "r_recipient": "Kam skirta",
        "r_recipient_ph": "pvz. rež. vardas pavardė",
        "r_director": "Režisierius/ė",
        "r_all": "visi",
        "r_date_from": "Data nuo",
        "r_date_to": "Data iki",
        "r_films": "Filmai",
        "r_films_hint": "Nepasirinkus įtraukiami visi lentelėje esantys filmai.",
        "r_dir_combo": "kartu",
        "r_pick_all": "Žymėti visus",
        "r_pick_none": "Nužymėti",
        "r_films_hidden": "Rodomi tik pasirinkto režisieriaus filmai ({n} iš {total}).",
        "r_no_films": "Lentelėje nėra nė vieno atpažinto filmo.",
        "r_submit": "Parengti ataskaitą",
        "r_none": "Pagal šiuos filtrus rodymų nerasta.",
        "r_results": "Rezultatai",
        "r_screenings_events": "{s} seansai · {e} renginiai",

        # ---------------------------------------------- screening log (įvedimas)
        "nav_screenings": "Rodymai",
        "s_title": "Rodymų žurnalas",
        "s_lede": "Įrašykite kiekvieną filmo rodymą: kur, kada, kiek seansų ir koks "
                  "įkainis. Iš šių įrašų sudaromos ataskaitos kūrėjams.",
        "s_add": "Naujas rodymas",
        "s_film": "Filmas",
        "s_film_ph": "pasirinkite filmą",
        "s_film_hint": "Nerandate? Pridėkite jį archyve ranka.",
        "s_event": "Renginys / festivalis",
        "s_event_ph": "pvz. Kaunas IFF",
        "s_venue": "Vieta",
        "s_venue_ph": "pvz. Romuva",
        "s_city": "Miestas",
        "s_country": "Šalis",
        "s_date": "Data",
        "s_count": "Seansų sk.",
        "s_fee": "Įkainis (EUR)",
        "s_fee_hint": "Vieno seanso įkainis. Pajamos = įkainis × seansų sk.",
        "s_programme": "Programa",
        "s_notes": "Pastabos",
        "s_save": "Pridėti rodymą",
        "s_added": "Rodymas įrašytas.",
        "s_deleted": "Rodymas ištrintas.",
        "s_delete": "Ištrinti",
        "s_delete_confirm": "Ištrinti šį rodymą iš lentelės?",
        "s_err_film": "Pasirinkite filmą arba įrašykite pavadinimą.",
        "s_err_count": "Seansų skaičius turi būti didesnis už nulį.",
        "s_err_fee": "Įkainis negali būti neigiamas.",
        "s_err_date": "Data turi būti formato MMMM-MM-DD.",
        "s_log": "Įrašyti rodymai",
        "s_log_empty": "Rodymų dar nėra. Pirmąjį įrašykite viršuje esančia forma.",
        "s_rows": "{n} įrašai · {s} seansai · {v}",
        "s_to_reports": "Sudaryti ataskaitą",

        # ------------------------------------------------------ archive page
        "a_title": "Filmų archyvas",
        "a_lede": "Vietinė svetainės archyvo kopija. Filmo ID reikalingas, kai norite "
                  "filmą būtinai įtraukti į programą arba iš jos pašalinti.",
        "a_search": "Paieška",
        "a_search_ph": "pavadinimas, režisierius, anotacija, raktažodis",
        "a_search_btn": "Ieškoti",
        "a_found": "Rasta {n} filmų.",
        "a_showing": "Rasta {n} filmų, rodomi pirmieji {shown}.",
        "a_add": "Pridėti filmą",
        "a_manual": "pridėtas ranka",
        "a_edit": "Redaguoti",
        "a_delete": "Ištrinti",
        "a_delete_confirm": "Ištrinti šį filmą? Veiksmo atšaukti negalėsite.",
        "a_only_manual": "Redaguoti galima tik ranka pridėtus filmus. "
                         "Iš svetainės paimti filmai atnaujinami per „scrape“.",

        # -------------------------------------------- add / edit a film by hand
        "nf_add_title": "Naujas filmas",
        "nf_edit_title": "Redaguoti filmą",
        "nf_lede": "Filmams, kurių nėra svetainėje. Įrašai saugomi atskirai, todėl "
                   "archyvo atnaujinimas jų neištrina.",
        "nf_s_basic": "Pagrindinė informacija",
        "nf_s_en": "Angliška versija",
        "nf_s_crew": "Komanda",
        "nf_s_text": "Anotacija",
        "nf_f_title": "Pavadinimas",
        "nf_f_title_en": "Pavadinimas (EN)",
        "nf_f_year": "Metai",
        "nf_f_genre": "Žanras",
        "nf_f_genre_en": "Žanras (EN)",
        "nf_f_duration": "Trukmė (min)",
        "nf_f_country": "Gamybos šalis",
        "nf_f_country_en": "Gamybos šalis (EN)",
        "nf_f_language": "Dialogai",
        "nf_f_language_en": "Dialogai (EN)",
        "nf_f_director": "Režisierius/ė",
        "nf_f_producer": "Prodiuseris/ė",
        "nf_f_company": "Prodiuserinė kompanija",
        "nf_f_distributor": "Platintojas",
        "nf_f_synopsis": "Anotacija",
        "nf_f_synopsis_en": "Anotacija (EN)",
        "nf_f_keywords": "Raktažodžiai",
        "nf_f_keywords_en": "Raktažodžiai (EN)",
        "nf_f_url": "Nuoroda",
        "nf_f_url_en": "Nuoroda (EN)",
        "nf_kw_hint": "Atskirti kableliais.",
        "nf_dur_hint": "Būtina, kad filmą būtų galima įtraukti į programą.",
        "nf_save": "Išsaugoti",
        "nf_cancel": "Atšaukti",
        "nf_err_title": "Įrašykite pavadinimą.",
        "nf_err_duration": "Trukmė turi būti didesnė už nulį.",
        "nf_added": "Filmas pridėtas.",
        "nf_updated": "Pakeitimai išsaugoti.",
        "nf_deleted": "Filmas ištrintas.",

        # ------------------------------------------- keyword review (AI pasiūlymai)
        "nav_keywords": "Raktažodžiai",
        "kw_title": "Raktažodžių peržiūra",
        "kw_lede": "Dalis archyvo filmų neturi raktažodžių, todėl jų nerandame pagal "
                   "temą. Čia pateikiami AI pasiūlymai iš esamo {vocab} raktažodžių "
                   "sąrašo. Patvirtinami tik tie, kuriuos pažymite jūs.",
        "kw_progress": "Be raktažodžių: {untagged} · pasiūlyta: {suggested} · "
                       "patvirtinta: {approved}",
        "kw_empty": "Pasiūlymų dar nėra",
        "kw_empty_body": "Paleiskite komandą, kuri parengs pasiūlymus peržiūrai:",
        "kw_ai_note": "AI perskaito tik anotaciją, todėl akivaizdžias temas pagauna, "
                      "o potekstę ar toną gali praleisti. Tai pirmas juodraštis, ne "
                      "galutinis sprendimas.",
        "kw_synopsis": "Anotacija",
        "kw_suggested": "Pasiūlyti raktažodžiai",
        "kw_add_more": "Pridėti kitų",
        "kw_add_hint": "Iš to paties sąrašo, atskirti kableliais.",
        "kw_none_returned": "Pasiūlymų šiam filmui negauta.",
        "kw_save": "Patvirtinti pažymėtus",
        "kw_saved": "Raktažodžiai patvirtinti: {n} filmai.",
        "kw_filter_pending": "Nepatvirtinti",
        "kw_filter_approved": "Patvirtinti",
        "kw_filter_all": "Visi",
        "kw_page": "{page} iš {pages}",
        "kw_prev": "Ankstesni",
        "kw_next": "Kiti",
        "kw_badge_ai": "AI",
        "kw_badge_ai_title": "Raktažodžiai pasiūlyti AI ir patvirtinti rankiniu būdu",
        "kw_nothing": "Šiame puslapyje nieko nėra.",
        "kw_filter_missing": "Be pasiūlymų",
        "kw_search": "Ieškoti filmo",
        "kw_search_ph": "pavadinimas, režisierius, anotacija",
        "kw_search_btn": "Ieškoti",
        "kw_matched": "Rasta: {n}.",
        "kw_suggest_one": "Parengti pasiūlymą",
        "kw_suggest_page": "Parengti pasiūlymus šiam puslapiui ({n})",
        "kw_no_suggestion_yet": "Pasiūlymų šiam filmui dar nėra.",
        "kw_pick_films": "Pažymėkite filmus, kuriems norite pasiūlymų.",
        "kw_suggest_selected": "Generuoti pažymėtiems",
        "kw_suggest_all": "Generuoti visiems be pasiūlymų ({n})",
        "kw_suggest_time": "Vienam filmui užtrunka kelias sekundes; {n} filmų - "
                           "apie {min} min. Neuždarykite lango, kol baigsis.",
        "kw_select_all": "Žymėti visus",
        "kw_select_none": "Nužymėti",
        "kw_tick_all": "Pažymėti visus siūlomus raktažodžius",
        "kw_per_page": "Rodyti po",
        "kw_missing_note": "Šie filmai dar neturi pasiūlymų. Pasirinkite, kuriems "
                           "juos parengti.",
    },

    "en": {
        "nav_programmes": "Programmes",
        "nav_reports": "Reports",
        "nav_archive": "Archive",
        "films_count": "films",
        "updated": "updated",
        "switch_lang": "LT",
        "switch_title": "Perjungti į lietuvių kalbą",
        "footer": "Internal tool · data from lithuanianshorts.com",
        "dir_prefix": "dir.",
        "download_pdf": "Download PDF",
        "download_word": "Download Word",

        "th_no": "No.",
        "th_id": "ID",
        "th_film": "Film",
        "th_year": "Year",
        "th_genre": "Genre",
        "th_duration": "Running time",
        "th_keywords": "Keywords",
        "th_total": "Total",
        "th_date": "Date",
        "th_event": "Event",
        "th_venue": "Venue",
        "th_films": "Films",
        "th_events": "Events",
        "th_screenings": "Screenings",
        "th_revenue": "Revenue",

        "p_title": "Film programme proposal",
        "p_lede": "Choose a theme and the limits. The tool builds programme options "
                  "from the {n} films in the archive, staying within the film count "
                  "and the total running time.",
        "p_name": "Programme title",
        "p_name_ph": "e.g. Family and childhood",
        "p_occasion": "Event / context",
        "p_occasion_ph": "e.g. festival, team building",
        "p_intro": "Programme description",
        "p_intro_ph": "A few sentences about the programme - printed at the top of the document",
        "p_rating": "Age rating",
        "p_rating_ph": "e.g. N-16",
        "p_rating_none": "Not specified",
        "p_rating_custom": "Other...",
        "p_doclang": "Document language",
        "p_doclang_hint": "Word and PDF language: titles, synopses and headings.",
        "p_theme": "Theme",
        "p_keywords": "Keywords",
        "p_keywords_hint": "Keywords of the films added to the catalogue since 2020.",
        "p_query": "Free text search",
        "p_query_ph": "searches titles and synopses",
        "p_extra_kw": "Additional keywords",
        "p_extra_kw_ph": "comma separated",
        "p_genre": "Genre",
        "p_genre_hint": "Leave empty to include every genre.",
        "p_genre_all": "All genres",
        "p_variants_all": "All",
        "p_variants_found": "{n} distinct option(s) possible with these filters.",
        "p_limits": "Limits",
        "p_films_from": "Films from",
        "p_films_to": "Films up to",
        "p_max_minutes": "Max running time (min)",
        "p_year_from": "Year from",
        "p_year_to": "Year to",
        "p_variants": "Number of options",
        "p_pin": "Always include (film IDs)",
        "p_pin_ph": "e.g. 22005, 21877",
        "p_exclude": "Exclude (film IDs)",
        "p_submit": "Build programme",
        "p_id_hint_pre": "You will find the IDs in the",
        "p_id_hint_post": "section.",
        "p_fail": "Could not build a programme.",
        "p_fail_body": "These criteria matched {n} eligible films. Try relaxing the "
                       "filters or raising the running-time limit.",
        # --- field help, shown behind the "i" next to each label
        "h_name": "The name of the programme. It heads the document and names "
                  "the file. Left empty, the document is called \u201cFilm "
                  "Programme Proposal\u201d.",
        "h_occasion": "The event this programme is for. It does not appear in "
                      "the new PDF - it is your own label for telling proposals "
                      "apart.",
        "h_rating": "The age rating printed under the running time. Pick one "
                    "from the list, or \u201cOther...\u201d to type your own.",
        "h_doclang": "Which language the document is written in: Lithuanian "
                     "titles and synopses, or English ones. The language of this "
                     "interface does not change.",
        "h_intro": "The opening paragraph about the programme as a whole. Write "
                   "it here, or later on the option you pick, where the AI draft "
                   "button also lives.",
        "h_intro_option": "This paragraph opens the document. \u201cDraft "
                          "description (AI)\u201d writes a first version from "
                          "the films in this option - read and edit it before "
                          "the document goes anywhere.",
        "h_keywords": "The theme of the programme. Ticked keywords do not "
                      "exclude films, they pull matching ones up the ranking. "
                      "The number is how many archive films carry that keyword.",
        "h_query": "Searches a film's text: title, synopsis, genre, director, "
                   "country, keywords. This is a hard filter and ALL the words "
                   "you type must appear, so two or three words can easily leave "
                   "nothing to choose from.",
        "h_extra_kw": "Keywords that are not in the list. Comma separated, and "
                      "they work exactly like the ticked ones.",
        "h_genre": "Leave \u201cAll genres\u201d and the programme may mix "
                   "them. Tick some and films come only from those.",
        "h_films_from": "The fewest films the programme may contain. If that many "
                        "cannot be found, the document says so in a note.",
        "h_films_to": "The most films the programme may contain.",
        "h_max_minutes": "The running-time limit in minutes. Longer films drop "
                         "out immediately, and the programme is built to use as "
                         "much of this slot as it can.",
        "h_year_from": "Earliest year of production. Empty means the oldest film "
                       "in the archive.",
        "h_year_to": "Latest year of production. Empty means the newest film in "
                     "the archive.",
        "h_variants": "How many different programmes to propose. \u201cAll\u201d "
                      "gives every one that can be built, up to 8.",
        "h_strict_kw": "Only films carrying at least one of the ticked keywords "
                       "are considered. Without this, keywords merely pull films "
                       "up the ranking.",
        "h_pin": "Film IDs that must be in the programme. The other filters do "
                 "not apply to them. IDs are on the archive page.",
        "h_exclude": "Film IDs to keep out of the programme. Comma separated.",
        "p_proposals": "Proposals",
        "p_download_hint": "Download the option you picked - the document contains only that programme.",
        "p_describe": "Draft description (AI)",
        "p_describing": "Writing...",
        "p_variant": "Option {n}",
        "p_films": "films",
        "p_match": "match",
        "p_coverage": "Keyword coverage:",
        "p_alternates": "Also a thematic fit",
        "p_alternates_note": "Matches the theme but did not fit the running-time limit.",

        "r_title": "Film screening report",
        "r_lede": "Where and when a film screened, how many times, and what it earned. "
                  "Data comes from the screening log.",
        "r_sheet_error": "Spreadsheet error:",
        "r_empty": "No screenings logged yet",
        "r_empty_body": "Reports are built from the screening log. Add the first "
                        "screening - where, when, how many shows and at what fee - "
                        "and the report is ready straight away.",
        "r_fee_note": "You type the fee in by hand for each screening; the revenue "
                      "is that fee multiplied by the number of shows.",
        "r_name": "Report title",
        "r_recipient": "Prepared for",
        "r_recipient_ph": "e.g. dir. name surname",
        "r_director": "Director",
        "r_all": "all",
        "r_date_from": "Date from",
        "r_date_to": "Date to",
        "r_films": "Films",
        "r_films_hint": "Leave empty to include every film in the sheet.",
        "r_dir_combo": "together",
        "r_pick_all": "Select all",
        "r_pick_none": "Clear",
        "r_films_hidden": "Showing only the selected director's films ({n} of {total}).",
        "r_no_films": "No recognised films in the sheet yet.",
        "r_submit": "Build report",
        "r_none": "No screenings match these filters.",
        "r_results": "Results",
        "r_screenings_events": "{s} screenings · {e} events",

        "nav_screenings": "Screenings",
        "s_title": "Screening log",
        "s_lede": "Record every screening: where, when, how many shows and at what "
                  "fee. The reports for the directors are built from these entries.",
        "s_add": "New screening",
        "s_film": "Film",
        "s_film_ph": "pick a film",
        "s_film_hint": "Not listed? Add it by hand in the archive.",
        "s_event": "Event / festival",
        "s_event_ph": "e.g. Kaunas IFF",
        "s_venue": "Venue",
        "s_venue_ph": "e.g. Romuva",
        "s_city": "City",
        "s_country": "Country",
        "s_date": "Date",
        "s_count": "Screenings",
        "s_fee": "Fee (EUR)",
        "s_fee_hint": "Fee for a single screening. Revenue = fee × screenings.",
        "s_programme": "Programme",
        "s_notes": "Notes",
        "s_save": "Add screening",
        "s_added": "Screening saved.",
        "s_deleted": "Screening deleted.",
        "s_delete": "Delete",
        "s_delete_confirm": "Delete this screening from the sheet?",
        "s_err_film": "Pick a film or type a title.",
        "s_err_count": "The number of screenings must be greater than zero.",
        "s_err_fee": "The fee cannot be negative.",
        "s_err_date": "The date must be in YYYY-MM-DD form.",
        "s_log": "Logged screenings",
        "s_log_empty": "No screenings yet. Add the first one with the form above.",
        "s_rows": "{n} entries · {s} screenings · {v}",
        "s_to_reports": "Build a report",

        "a_title": "Film archive",
        "a_lede": "A local copy of the site archive. You need a film ID to pin a film "
                  "into a programme or to exclude it.",
        "a_search": "Search",
        "a_search_ph": "title, director, synopsis, keyword",
        "a_search_btn": "Search",
        "a_found": "{n} films found.",
        "a_showing": "{n} films found, showing the first {shown}.",
        "a_add": "Add film",
        "a_manual": "added by hand",
        "a_edit": "Edit",
        "a_delete": "Delete",
        "a_delete_confirm": "Delete this film? This cannot be undone.",
        "a_only_manual": "Only hand-added films can be edited. Films taken from the "
                         "website are refreshed by the scrape.",

        "nf_add_title": "New film",
        "nf_edit_title": "Edit film",
        "nf_lede": "For films that are not on the website. Entries are stored "
                   "separately, so refreshing the archive never deletes them.",
        "nf_s_basic": "Basic information",
        "nf_s_en": "English version",
        "nf_s_crew": "Team",
        "nf_s_text": "Synopsis",
        "nf_f_title": "Title",
        "nf_f_title_en": "Title (EN)",
        "nf_f_year": "Year",
        "nf_f_genre": "Genre",
        "nf_f_genre_en": "Genre (EN)",
        "nf_f_duration": "Running time (min)",
        "nf_f_country": "Production country",
        "nf_f_country_en": "Production country (EN)",
        "nf_f_language": "Dialogues",
        "nf_f_language_en": "Dialogues (EN)",
        "nf_f_director": "Director",
        "nf_f_producer": "Producer",
        "nf_f_company": "Production company",
        "nf_f_distributor": "Distributor",
        "nf_f_synopsis": "Synopsis",
        "nf_f_synopsis_en": "Synopsis (EN)",
        "nf_f_keywords": "Keywords",
        "nf_f_keywords_en": "Keywords (EN)",
        "nf_f_url": "Link",
        "nf_f_url_en": "Link (EN)",
        "nf_kw_hint": "Comma separated.",
        "nf_dur_hint": "Required before the film can be used in a programme.",
        "nf_save": "Save",
        "nf_cancel": "Cancel",
        "nf_err_title": "Please enter a title.",
        "nf_err_duration": "Running time must be greater than zero.",
        "nf_added": "Film added.",
        "nf_updated": "Changes saved.",
        "nf_deleted": "Film deleted.",

        "nav_keywords": "Keywords",
        "kw_title": "Keyword review",
        "kw_lede": "Part of the archive has no keywords, so those films never turn up "
                   "in a thematic search. These are AI suggestions drawn from the "
                   "existing {vocab}-term vocabulary. Only what you tick is saved.",
        "kw_progress": "Without keywords: {untagged} · suggested: {suggested} · "
                       "approved: {approved}",
        "kw_empty": "No suggestions yet",
        "kw_empty_body": "Run this command to prepare suggestions for review:",
        "kw_ai_note": "The model reads only the synopsis, so it catches the obvious "
                      "themes and can miss tone and subtext. Treat it as a first "
                      "draft, not a verdict.",
        "kw_synopsis": "Synopsis",
        "kw_suggested": "Suggested keywords",
        "kw_add_more": "Add others",
        "kw_add_hint": "From the same vocabulary, comma separated.",
        "kw_none_returned": "No suggestions were returned for this film.",
        "kw_save": "Approve ticked",
        "kw_saved": "Keywords approved for {n} film(s).",
        "kw_filter_pending": "Not approved",
        "kw_filter_approved": "Approved",
        "kw_filter_all": "All",
        "kw_page": "{page} of {pages}",
        "kw_prev": "Previous",
        "kw_next": "Next",
        "kw_badge_ai": "AI",
        "kw_badge_ai_title": "Keywords suggested by AI and approved by hand",
        "kw_nothing": "Nothing on this page.",
        "kw_filter_missing": "No suggestions",
        "kw_search": "Find a film",
        "kw_search_ph": "title, director, synopsis",
        "kw_search_btn": "Search",
        "kw_matched": "{n} match(es).",
        "kw_suggest_one": "Generate suggestion",
        "kw_suggest_page": "Generate for this page ({n})",
        "kw_no_suggestion_yet": "No suggestions for this film yet.",
        "kw_pick_films": "Tick the films you want suggestions for.",
        "kw_suggest_selected": "Generate for selected",
        "kw_suggest_all": "Generate for all without suggestions ({n})",
        "kw_suggest_time": "A film takes a few seconds; {n} films take about "
                           "{min} min. Keep this tab open until it finishes.",
        "kw_select_all": "Select all",
        "kw_select_none": "Clear",
        "kw_tick_all": "Tick every suggested keyword",
        "kw_per_page": "Show",
        "kw_missing_note": "These films have no suggestions yet. Pick the ones you "
                           "want them generated for.",
    },
}

# Account pages. Kept in their own block and merged in, so the two big tables
# above stay as they were.
AUTH_STRINGS = {
    "lt": {
        "nav_users": "Vartotojai",
        "nav_password": "Slaptažodis",
        "nav_logout": "Atsijungti",
        "login_title": "Prisijungimas",
        "login_lede": "Vidinis Lithuanian Shorts įrankis.",
        "login_email": "El. paštas",
        "login_password": "Slaptažodis",
        "login_submit": "Prisijungti",
        "login_failed": "Neteisingas el. paštas arba slaptažodis.",
        "login_admin_note": "Paskyras sukuria administratorius.",
        "pw_title": "Pakeisti slaptažodį",
        "pw_old": "Dabartinis slaptažodis",
        "pw_new": "Naujas slaptažodis",
        "pw_confirm": "Pakartokite naują slaptažodį",
        "pw_submit": "Pakeisti",
        "pw_saved": "Slaptažodis pakeistas.",
        "pw_rule": "Bent 8 simboliai.",
        "pw_must_change": "Prieš tęsdami, nustatykite savo slaptažodį.",
        "u_title": "Vartotojai",
        "u_add": "Pridėti darbuotoją",
        "u_name": "Vardas (nebūtina)",
        "u_admin": "Administratorius",
        "u_create": "Sukurti",
        "u_created": "Paskyra sukurta.",
        "u_updated": "Pakeitimai išsaugoti.",
        "u_deleted": "Paskyra ištrinta.",
        "u_password_set": "Slaptažodis nustatytas.",
        "u_role": "Rolė",
        "u_role_admin": "Administratorius",
        "u_role_staff": "Darbuotojas",
        "u_status": "Būsena",
        "u_active": "Aktyvi",
        "u_disabled": "Išjungta",
        "u_last_login": "Paskutinis prisijungimas",
        "u_never": "niekada",
        "u_enable": "Įjungti",
        "u_disable": "Išjungti",
        "u_make_admin": "Suteikti admin",
        "u_revoke_admin": "Atimti admin",
        "u_set_password": "Nustatyti slaptažodį",
        "u_delete": "Ištrinti",
        "u_confirm_delete": "Ištrinti šią paskyrą?",
        "u_plain_note": "Slaptažodis rodomas atviru tekstu, kad galėtumėte jį perduoti.",
    },
    "en": {
        "nav_users": "Users",
        "nav_password": "Password",
        "nav_logout": "Sign out",
        "login_title": "Sign in",
        "login_lede": "Lithuanian Shorts internal tool.",
        "login_email": "Email",
        "login_password": "Password",
        "login_submit": "Sign in",
        "login_failed": "Wrong email or password.",
        "login_admin_note": "Accounts are created by an admin.",
        "pw_title": "Change password",
        "pw_old": "Current password",
        "pw_new": "New password",
        "pw_confirm": "Repeat the new password",
        "pw_submit": "Change",
        "pw_saved": "Password changed.",
        "pw_rule": "At least 8 characters.",
        "pw_must_change": "Set your own password before you continue.",
        "u_title": "Users",
        "u_add": "Add an employee",
        "u_name": "Name (optional)",
        "u_admin": "Admin",
        "u_create": "Create",
        "u_created": "Account created.",
        "u_updated": "Saved.",
        "u_deleted": "Account deleted.",
        "u_password_set": "Password set.",
        "u_role": "Role",
        "u_role_admin": "Admin",
        "u_role_staff": "Employee",
        "u_status": "Status",
        "u_active": "Active",
        "u_disabled": "Disabled",
        "u_last_login": "Last login",
        "u_never": "never",
        "u_enable": "Enable",
        "u_disable": "Disable",
        "u_make_admin": "Make admin",
        "u_revoke_admin": "Revoke admin",
        "u_set_password": "Set password",
        "u_delete": "Delete",
        "u_confirm_delete": "Delete this account?",
        "u_plain_note": "The password is shown in plain text so you can hand it over.",
    },
}
for _lang, _items in AUTH_STRINGS.items():
    STRINGS.setdefault(_lang, {}).update(_items)

DEFAULT_LANG = "lt"


def ui(lang: Optional[str], key: str, **kwargs) -> str:
    """Look up an interface string. Falls back to Lithuanian, then to the key."""
    table = STRINGS.get((lang or DEFAULT_LANG), STRINGS[DEFAULT_LANG])
    text = table.get(key, STRINGS[DEFAULT_LANG].get(key, key))
    return text.format(**kwargs) if kwargs else text
