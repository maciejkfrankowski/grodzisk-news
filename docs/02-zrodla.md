# 02 – Katalog źródeł (stan: 2026-11-14)

Wdrożone w `sources.yaml`: **gmina**, **powiat**, **gpa**, **biblioteka**, **ck-wydarzenia**, **ck**, **psp**. Reszta to kandydaci na kolejne etapy.

## A. Instytucje publiczne

| # | Źródło | URL | Adapter | Stan |
|---|---|---|---|---|
| 1 | Urząd Miejski / Gmina | https://grodzisk.pl/feed | rss | wdrożone; sprawdzić świeżość feedu (ostatni znany wpis: 15.09.2026) |
| 2 | Centrum Kultury | https://www.centrumkultury.eu/wydarzenia/ , /category/ogloszenia/ , /category/komunikaty/ | tribe_events (kalendarz) + rss (ogłoszenia) | wdrożone |
| 2a | CK – podstrony | /kino-centrum-kultury/ , /kino-wolnosc/ , /mediateka/ , /dworek-chelmonskiego/ , /willa-niespodzianka/ , /willa-radogoszcz/ , /poczekalnia-pkp/ , /sas/ , /swietlice/ , /wystawy/ | rss per podstrona | feedy niepotwierdzone |
| 3 | Biblioteka Publiczna | https://biblioteka.grodzisk.pl/aktualnosci/ | rss (`/feed/`) | wdrożone |
| 4 | Powiat Grodziski | https://www.powiat-grodziski.pl/aktualnosci/wszystkie/ | html_links | wdrożone |
| 5 | Policja – KPP (KSP) | https://ksp.policja.gov.pl/pl/aktualnosci/?ida[1]=1831 | ? | strona nie dała się odczytać; adres do ustalenia |
| 6 | Straż Pożarna – KP PSP | https://www.gov.pl/web/kppsp-grodzisk-mazowiecki/aktualnosci | html_links + require_date | wdrożone (ok. 1 wpis/tydz.) |
| 7 | Grodziskie Przewozy Autobusowe | https://gpagrodzisk.pl/aktualnosci/wszystkie/ | html_links | wdrożone |
| 8 | Szpital Zachodni | https://szpitalzachodni.pl/aktualnosci/ | ? | struktura niesprawdzona |
| 9 | Sołectwa | np. https://kludzienko.grodzisk.pl , https://opypy.grodzisk.pl | rss | pełna lista do zebrania |

## B. Adresy do znalezienia
OSiR / pływalnia, Straż Miejska, ZWiK (awarie wody), OPS, WKD (utrudnienia), PGE (wyłączenia prądu),
BIP i eSesja Rady Miejskiej, PUP, sanepid, kluby sportowe, dyżury aptek.

## C. Media komercyjne – nie pobieramy
grodzisknews.pl, wpr24.pl, grodziskmazowiecki.naszemiasto.pl, 24grodziskmazowiecki.pl
