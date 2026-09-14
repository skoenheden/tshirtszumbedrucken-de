# tshirtszumbedrucken.de

Deutscher SEO/GEO-Ratgeber zu "T-Shirts zum Bedrucken" (ca. 49.500 Suchanfragen/Monat in DE laut Google Ads Keyword Planner, Sep 2026).
Schickt Traffic zu **marmaladeco.com** (UTM `utm_source=tshirtszumbedrucken.de&utm_campaign=seo-de`).
Die Seite ist **offen** ein Ratgeber von Marmalade Co. (UWG: keine verdeckte Werbung; Impressumspflicht nach § 5 DDG).

- `content/site.json`: Marmalade-Fakten, Navigation, Impressumsdaten (`managing_director` vor Livegang ausfüllen!)
- `content/prices.json`: Marmalade-Preise für Preistabelle und Mengenrechner (gleiches Format wie fruitotl.com)
- `content/brands.json`: Vergleichstabelle. Nur Werte von der Produktseite des Shops, Nettopreise markieren
- `content/articles/*.html`: eine Datei pro Seite, JSON-Front-Matter im ersten HTML-Kommentar
- `scripts/make_assets.py`: Logo, Favicons, og-image
- `python3 build.py` baut nach `docs/`, `--check` validiert nur

## Regeln
1. Keine langen Gedankenstriche (U+2013/U+2014) im sichtbaren Text. Der Build schlägt sonst fehl.
2. Keine externen Schriften, Skripte oder Tracker (DSGVO, Google-Fonts-Abmahnungen). Der Build prüft das.
3. Marmalade Co. nie "offizieller/autorisierter Händler" oder "direkt aus der Fabrik" nennen, solange kein schriftlicher Nachweis vorliegt (siehe Google-Ads-Audit 2026-09-07).
4. Keine erfundenen Zahlen. Unbekannt = "nicht angegeben".
5. Keine Überschneidung mit fruitotl.com/de (dort: "Fruit of the Loom bedrucken", "T-Shirts in Mengen"). Hier: generische Suchintention "T-Shirts zum Bedrucken".

## Deploy
GitHub Pages aus `main` /docs mit CNAME `tshirtszumbedrucken.de`. DNS bei YayHosting (cPanel Zone Editor): Apex A auf 185.199.108.153/109/110/111, `www` CNAME auf `skoenheden.github.io`.
