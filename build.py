#!/usr/bin/env python3
"""
build.py - statischer Site-Generator für tshirtszumbedrucken.de

Liest content/site.json, content/brands.json, content/prices.json und content/articles/*.html
und schreibt eine komplette statische Website nach docs/ (GitHub Pages, funktioniert auch auf cPanel).

    python3 build.py            # alles bauen
    python3 build.py --check    # nur validieren, nichts schreiben

Ein Artikel ist eine .html-Datei in content/articles/, die mit einem HTML-Kommentar mit
JSON-Front-Matter beginnt, danach folgt der Text:

    <!--
    { "slug": "dtf-druck-t-shirts", "title": "...", "description": "...", ... }
    -->
    <h2>...</h2>

Platzhalter in Text, intro und quick_answer:
    {{SHOP}} / {{SHOP:/pfad}}            -> URL auf marmaladeco.com mit UTM
    {{SHOP|Ankertext}} / {{SHOP:/pfad|Ankertext}} -> fertiger Link
    {{CTA|Leadtext|Button}} / {{CTA:/pfad|Leadtext|Button}} -> CTA-Box
    {{LINK:slug|Ankertext}}              -> interner Link (wird validiert)
    {{PRICES}} / {{PRICES:t-shirt,hoodie}} -> Preistabelle 1/10/50/100/250 Stück inkl. Versand
    {{CALCULATOR}}                       -> interaktiver Mengenrechner
    {{COMPARE}} / {{COMPARE:tag}}        -> Vergleichstabelle aus brands.json
    {{FACTS}}                            -> Faktenbox Marmalade Co.
    {{ARTICLES}}                         -> Kartenraster aller gelisteten Artikel

Hausregeln (Build schlägt fehl): keine langen Gedankenstriche (U+2013/U+2014) im sichtbaren Text,
keine externen Schriften/Tracker (DSGVO), Pflichtseiten impressum, datenschutz, ueber-uns.
"""
import datetime
from decimal import Decimal, ROUND_HALF_UP
import html
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(ROOT, "content")
ASSETS = os.path.join(ROOT, "assets")
OUT = os.path.join(ROOT, "docs")
CHECK_ONLY = "--check" in sys.argv

MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember"]
REQUIRED = ["index", "ueber-uns", "impressum", "datenschutz"]

errors, warnings = [], []


# ---------------------------------------------------------------- helpers
def read_json(path):
    with open(path, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            sys.exit(f"JSON-Fehler in {path}: {e}")


def esc(s):
    return html.escape(str(s), quote=True)


def strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def jsonld(obj):
    return ('<script type="application/ld+json">'
            + json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
            + "</script>")


def de_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day}. {MONATE[d.month - 1]} {d.year}"


def eur(v):
    # Kaufmännisch runden (6,255 -> 6,26 wie im Shop), nicht Float-Rundung (6,2549999 -> 6,25)
    d = Decimal(repr(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    s = f"{d:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s + " €"


SITE = read_json(os.path.join(CONTENT, "site.json"))
BRANDS = read_json(os.path.join(CONTENT, "brands.json"))
PRICES = read_json(os.path.join(CONTENT, "prices.json"))
DOMAIN = SITE["domain"].rstrip("/")
HOST = DOMAIN.split("//", 1)[1]
SHOP = SITE["shop"].rstrip("/")
MM = SITE["marmalade"]

PRODUCT_NAMES = {"t-shirt": "T-Shirt", "v-neck": "V-Neck-T-Shirt", "long-sleeve": "Langarmshirt",
                 "tank-top": "Tanktop", "polo": "Poloshirt", "shorts": "Shorts",
                 "sweatshirt": "Sweatshirt", "sweatpants": "Jogginghose", "hoodie": "Hoodie",
                 "zip-hoodie": "Zip-Hoodie"}


def unit_price(pid, qty):
    p = next(x for x in PRICES["products"] if x["id"] == pid)
    pct = 0
    for d in PRICES["discounts"]:
        if qty >= d["min_qty"]:
            pct = d["pct"]
    return p["price"] * (1 - pct / 100)


TSHIRT = unit_price("t-shirt", 1)
TSHIRT_BULK = unit_price("t-shirt", 5)


def shop_url(path=None, content="inline", slug="home"):
    path = path or "/products/fruit-of-the-loom-t-shirt"
    path = path if path.startswith("/") else "/" + path
    sep = "&" if "?" in path else "?"
    return (f"{SHOP}{path}{sep}utm_source={HOST}&utm_medium=referral"
            f"&utm_campaign=seo-de&utm_content={slug}-{content}")


def page_url(slug):
    return f"{DOMAIN}/" if slug == "index" else f"{DOMAIN}/{slug}"


def href(slug):
    return "/" if slug == "index" else f"/{slug}"


# ---------------------------------------------------------------- articles
def load_articles():
    arts = []
    d = os.path.join(CONTENT, "articles")
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".html"):
            continue
        raw = open(os.path.join(d, fn), encoding="utf-8").read()
        m = re.match(r"\s*<!--(.*?)-->(.*)", raw, re.S)
        if not m:
            errors.append(f"{fn}: Front-Matter-Kommentar fehlt")
            continue
        try:
            meta = json.loads(m.group(1))
        except json.JSONDecodeError as e:
            errors.append(f"{fn}: Front-Matter ist kein gültiges JSON ({e})")
            continue
        meta["body"] = m.group(2).strip()
        for k in ("slug", "title", "description", "h1", "date_published", "date_modified"):
            if not meta.get(k):
                errors.append(f"{fn}: Feld '{k}' fehlt")
        if meta.get("slug") and meta["slug"] + ".html" != fn:
            errors.append(f"{fn}: slug '{meta.get('slug')}' passt nicht zum Dateinamen")
        meta.setdefault("layout", "article")
        meta.setdefault("listed", meta["layout"] == "article")
        meta.setdefault("faq", [])
        meta.setdefault("related", [])
        meta.setdefault("category", "Ratgeber")
        meta.setdefault("noindex", False)
        arts.append(meta)
    return arts


ARTICLES = load_articles()
BY_SLUG = {a["slug"]: a for a in ARTICLES if a.get("slug")}


# ---------------------------------------------------------------- components
def cta_box(path, lead, btn, slug):
    return (f'<div class="cta-box"><p>{lead}</p>'
            f'<a class="btn" href="{esc(shop_url(path, "cta", slug))}">{btn} →</a></div>')


def facts_box():
    return f'''<div class="facts">
  <div><b>{eur(TSHIRT)}</b><span>T-Shirt, Einzelpreis</span></div>
  <div><b>{eur(TSHIRT_BULK)}</b><span>ab 5 Stück (-{PRICES["discounts"][-1]["pct"]} %)</span></div>
  <div><b>{eur(PRICES["shipping_eur"])}</b><span>DHL-Versand nach DE</span></div>
  <div><b>{esc(MM["delivery_days"])}</b><span>Werktage Lieferzeit</span></div>
  <div><b>{esc(MM["sizes"])}</b><span>Größen, {esc(MM["tshirt_colours"])} Farben</span></div>
</div>'''


def price_table(ids):
    ship = PRICES["shipping_eur"]
    prods = [p for p in PRICES["products"] if not ids or p["id"] in ids]
    head = "".join(f"<th>{q} Stk.</th>" for q in PRICES["quantities"])
    rows = []
    for p in prods:
        cells = []
        for q in PRICES["quantities"]:
            total = unit_price(p["id"], q) * q + ship
            cells.append(f"<td><b>{eur(total)}</b><small>{eur(total / q)} / Stk.</small></td>")
        rows.append(f"<tr><td><b>{esc(PRODUCT_NAMES.get(p['id'], p['id']))}</b></td>{''.join(cells)}</tr>")
    cap = (f"Gesamtpreis inkl. MwSt. und {eur(ship)} DHL-Versand nach Deutschland, Mengenrabatt eingerechnet. "
           f"Preise von marmaladeco.com, geprüft am {de_date(PRICES['checked'])}.")
    return (f'<div class="table-scroll"><table class="price-table"><caption>{esc(cap)}</caption>'
            f'<thead><tr><th>Produkt</th>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def calculator(slug):
    ship = PRICES["shipping_eur"]
    opts = "".join(f'<option value="{p["price"]}" data-path="{esc(p["path"])}">'
                   f'{esc(PRODUCT_NAMES.get(p["id"], p["id"]))} · {eur(p["price"])}</option>'
                   for p in PRICES["products"])
    disc = esc(json.dumps(PRICES["discounts"]))
    base = esc(shop_url("/__PATH__", "rechner", slug))
    return f'''<div class="calc" data-ship="{ship}" data-disc="{disc}" data-base="{base}">
<h3>Mengenrechner: Was kosten deine Rohlinge?</h3>
<p>Einzelpreis, Mengenrabatt und {eur(ship)} Versand nach Deutschland sind eingerechnet.</p>
<div class="calc-row"><label>Produkt<select class="calc-p">{opts}</select></label>
<label>Stückzahl<input class="calc-q" type="number" min="1" max="10000" value="25" inputmode="numeric"></label></div>
<div class="calc-out"><div><span>Gesamt inkl. Versand</span><b class="calc-t">-</b></div><div><span>Pro Stück</span><b class="calc-u">-</b></div></div>
<a class="btn calc-go" href="{esc(shop_url("/products/fruit-of-the-loom-t-shirt", "rechner", slug))}">Rohlinge ansehen →</a>
</div>'''


CALC_JS = """<script>
document.querySelectorAll('.calc').forEach(function(c){
 var ship=parseFloat(c.dataset.ship),disc=JSON.parse(c.dataset.disc),base=c.dataset.base;
 var sel=c.querySelector('.calc-p'),q=c.querySelector('.calc-q'),t=c.querySelector('.calc-t'),u=c.querySelector('.calc-u'),go=c.querySelector('.calc-go');
 var f=new Intl.NumberFormat('de-DE',{style:'currency',currency:'EUR'});
 function run(){var n=Math.max(1,parseInt(q.value||'1',10)),p=parseFloat(sel.value),pct=0;
  disc.forEach(function(d){if(n>=d.min_qty)pct=d.pct;});
  var tot=p*(1-pct/100)*n+ship;t.textContent=f.format(tot);u.textContent=f.format(tot/n);
  go.href=base.replace('/__PATH__',sel.options[sel.selectedIndex].dataset.path);}
 sel.addEventListener('change',run);q.addEventListener('input',run);run();});
</script>"""


def compare_table(tag, slug):
    rows = [r for r in BRANDS["rows"] if not tag or tag in r.get("tags", []) or r.get("marmalade")]
    out = ['<div class="compare-wrap"><table class="compare">',
           "<thead><tr><th>Rohling</th><th>Stoff</th><th>Preis pro Stück</th>"
           "<th>Wer kann kaufen</th><th>Versand</th><th></th></tr></thead><tbody>"]
    for r in rows:
        mm = r.get("marmalade")
        link = shop_url(r["path"], "vergleich", slug) if mm else r["url"]
        rel = "" if mm else ' rel="nofollow noopener" target="_blank"'
        badge = '<span class="pill">Unsere Empfehlung</span>' if mm else ""
        out.append(
            f'<tr class="{"is-mm" if mm else ""}">'
            f'<td data-label="Rohling">{badge}<b>{esc(r["model"])}</b><span class="sub">{esc(r["shop"])}</span></td>'
            f'<td data-label="Stoff">{esc(r["fabric"])}</td>'
            f'<td data-label="Preis"><b>{esc(r["price"])}</b><span class="sub">{esc(r.get("price_note", ""))}</span></td>'
            f'<td data-label="Kunden">{esc(r["buyers"])}</td>'
            f'<td data-label="Versand">{esc(r["shipping"])}</td>'
            f'<td><a class="{"btn btn-sm" if mm else "out"}" href="{esc(link)}"{rel}>'
            f'{"Ansehen" if mm else "Zu " + esc(r["shop"])} →</a></td></tr>')
    out.append("</tbody></table></div>")
    out.append(f'<p class="source">Preise und Bedingungen auf den Seiten der Shops geprüft am {de_date(BRANDS["checked"])}. '
               "Preise ändern sich, prüfe vor dem Kauf immer den aktuellen Preis. "
               "{{LINK:ueber-uns|So vergleichen wir}}.</p>")
    return "\n".join(out)


def article_cards(exclude=None):
    items = [a for a in ARTICLES if a["listed"] and a["slug"] != exclude]
    items.sort(key=lambda a: (a.get("order", 999), a["title"]))
    cards = "".join(
        f'<a class="card" href="{href(a["slug"])}"><span class="card-tag">{esc(a["category"])}</span>'
        f'<strong>{esc(a.get("card_title") or a["h1"])}</strong></a>' for a in items)
    return f'<div class="cards">{cards}</div>'


def impressum_block():
    md = MM.get("managing_director", "").strip()
    if not md:
        warnings.append("impressum: 'managing_director' in site.json ist leer. Vor dem Livegang eintragen (§ 5 DDG).")
    vertreten = f"<br>Vertreten durch: {esc(md)} (Direktør)" if md else ""
    verantwortlich = esc(md) if md else "die Geschäftsführung"
    return f'''<h2>Angaben gemäß § 5 DDG</h2>
<p>{esc(MM["company"])} (handelnd als {esc(MM["brand"])})<br>{esc(MM["address"])}{vertreten}</p>
<h2>Kontakt</h2>
<p>E-Mail: <a href="mailto:{esc(MM["email"])}">{esc(MM["email"])}</a></p>
<h2>Register und Umsatzsteuer</h2>
<p>Eingetragen im dänischen Unternehmensregister (CVR) der Erhvervsstyrelsen, CVR-Nr. {esc(MM["vat"][2:])}<br>
Umsatzsteuer-Identifikationsnummer: {esc(MM["vat"])}</p>
<h2>Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV</h2>
<p>{verantwortlich}, Anschrift wie oben</p>'''


def expand(text, slug):
    if not isinstance(text, str):
        return text
    text = text.replace("{{IMPRESSUM}}", impressum_block()) if "{{IMPRESSUM}}" in text else text
    text = re.sub(r"\{\{COMPARE(?::([a-z\-]+))?\}\}", lambda m: compare_table(m.group(1), slug), text)
    text = re.sub(r"\{\{PRICES(?::([a-z0-9,\-]+))?\}\}",
                  lambda m: price_table(m.group(1).split(",") if m.group(1) else None), text)
    text = text.replace("{{CALCULATOR}}", calculator(slug)).replace("{{FACTS}}", facts_box())
    text = text.replace("{{ARTICLES}}", article_cards(exclude=slug))
    text = re.sub(r"\{\{CTA(?::([^|}]+))?\|([^|}]+)\|([^}]+)\}\}",
                  lambda m: cta_box(m.group(1), m.group(2), m.group(3), slug), text)
    text = re.sub(r"\{\{SHOP(?::([^|}]+))?\|([^}]+)\}\}",
                  lambda m: f'<a href="{esc(shop_url(m.group(1), "inline", slug))}">{m.group(2)}</a>', text)
    text = re.sub(r"\{\{SHOP(?::([^}]+))?\}\}", lambda m: esc(shop_url(m.group(1), "inline", slug)), text)

    def link(m):
        target, anchor = m.group(1), m.group(2)
        if target not in BY_SLUG:
            errors.append(f"{slug}: {{{{LINK:{target}}}}} zeigt auf einen Artikel, der nicht existiert")
        return f'<a href="{href(target)}">{anchor}</a>'
    text = re.sub(r"\{\{LINK:([a-z0-9\-]+)\|([^}]+)\}\}", link, text)
    if "{{" in text:
        i = text.index("{{")
        errors.append(f"{slug}: unbekannter Platzhalter: {text[i:i + 40]}")
    return text


# ---------------------------------------------------------------- page shell
CSS = open(os.path.join(ASSETS, "site.css"), encoding="utf-8").read()


def head(a, canonical):
    og_type = "website" if a["slug"] == "index" else "article"
    robots = "noindex, follow" if a.get("noindex") else "index, follow, max-image-preview:large"
    return f'''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(a["title"])}</title>
<meta name="description" content="{esc(a["description"])}">
<link rel="canonical" href="{canonical}">
<meta name="robots" content="{robots}">
<meta name="geo.region" content="DE">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" href="/favicon.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta property="og:site_name" content="{HOST}">
<meta property="og:locale" content="de_DE">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{esc(a["title"])}">
<meta property="og:description" content="{esc(a["description"])}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{DOMAIN}/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<style>{CSS}</style>
'''


def header():
    nav = "".join(f'<a href="{esc(u)}">{esc(t)}</a>' for t, u in SITE["nav"])
    return f'''<header class="site-header">
  <div class="wrap header-inner">
    <a class="logo" href="/" aria-label="{HOST} Startseite">
      <img src="/logo-icon.png" alt="" width="34" height="34">
      <span class="logo-text"><b>{HOST}</b><small>Ratgeber von Marmalade Co.</small></span>
    </a>
    <nav class="main-nav" id="nav">{nav}</nav>
    <button class="nav-toggle" aria-label="Menü" aria-expanded="false" onclick="var n=document.getElementById('nav');n.classList.toggle('open');this.setAttribute('aria-expanded',n.classList.contains('open'))">☰</button>
  </div>
</header>'''


def footer(slug):
    links = "".join(f'<a href="{esc(u)}">{esc(t)}</a>' for t, u in SITE["nav"])
    return f'''<footer class="site-footer">
  <div class="wrap">
    <div class="footer-top">
      <div><b>{HOST}</b><p>{esc(SITE["disclosure_short"])}</p></div>
      <nav>{links}<a href="/ueber-uns">Über uns</a><a href="/impressum">Impressum</a><a href="/datenschutz">Datenschutz</a></nav>
    </div>
    <p class="footer-copy">© {datetime.date.today().year} {esc(MM["company"])}. {HOST} ist ein Ratgeber von Marmalade Co. Fruit of the Loom und andere Marken gehören ihren jeweiligen Inhabern; diese Seite ist nicht mit ihnen verbunden.</p>
  </div>
</footer>
<div class="mobile-cta"><a href="{esc(shop_url(None, "mobile-sticky", slug))}">T-Shirt-Rohlinge ab {eur(TSHIRT_BULK)} →</a></div>'''


def breadcrumb(a):
    if a["slug"] == "index":
        return "", None
    trail = [("Startseite", "/")]
    if a["layout"] == "article":
        trail.append(("Ratgeber", "/ratgeber"))
    trail.append((a.get("card_title") or a["h1"], None))
    items = [f'<a href="{u}">{esc(t)}</a>' if u else f"<span>{esc(t)}</span>" for t, u in trail]
    schema = {"@context": "https://schema.org", "@type": "BreadcrumbList",
              "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": t,
                                   "item": (DOMAIN + u) if u else page_url(a["slug"])}
                                  for i, (t, u) in enumerate(trail)]}
    return f'<nav class="crumbs" aria-label="Brotkrümel">{" / ".join(items)}</nav>', schema


def faq_html(faq, slug):
    if not faq:
        return ""
    items = "".join(f'<details class="faq-item"><summary>{esc(q["q"])}</summary><div>{expand(q["a"], slug)}</div></details>'
                    for q in faq)
    return f'<section class="faq" id="faq"><h2>Häufige Fragen</h2>{items}</section>'


def related_html(a):
    for s in a["related"]:
        if s not in BY_SLUG:
            errors.append(f"{a['slug']}: related '{s}' existiert nicht")
    rel = [BY_SLUG[s] for s in a["related"] if s in BY_SLUG]
    if not rel:
        return ""
    lis = "".join(f'<li><a href="{href(r["slug"])}">{esc(r.get("card_title") or r["h1"])}</a></li>' for r in rel)
    return f'<aside class="related"><h2>Weiterlesen</h2><ul>{lis}</ul></aside>'


def schemas(a, canonical):
    out = []
    publisher = {"@type": "Organization", "name": "Marmalade Co.", "legalName": MM["company"],
                 "url": SHOP + "/", "logo": f"{DOMAIN}/logo.png"}
    if a["slug"] == "index":
        out.append({"@context": "https://schema.org", "@type": "WebSite", "name": HOST,
                    "url": DOMAIN + "/", "inLanguage": "de", "description": SITE["description"],
                    "publisher": publisher})
        out.append({"@context": "https://schema.org", "@type": "ItemList",
                    "name": "T-Shirts zum Bedrucken im Vergleich",
                    "itemListElement": [{"@type": "ListItem", "position": i + 1,
                                         "name": f'{r["model"]} ({r["shop"]})',
                                         "url": (SHOP + r["path"]) if r.get("marmalade") else r["url"]}
                                        for i, r in enumerate(BRANDS["rows"])]})
    elif not a.get("noindex"):
        typ = "Article" if a["layout"] == "article" else "WebPage"
        out.append({"@context": "https://schema.org", "@type": typ, "headline": a["h1"],
                    "description": a["description"], "url": canonical, "inLanguage": "de",
                    "datePublished": a["date_published"], "dateModified": a["date_modified"],
                    "image": f"{DOMAIN}/og-image.png",
                    "author": {"@type": "Organization", "name": "Marmalade Co.", "url": SHOP + "/"},
                    "publisher": publisher, "mainEntityOfPage": canonical})
    if a["faq"]:
        out.append({"@context": "https://schema.org", "@type": "FAQPage",
                    "mainEntity": [{"@type": "Question", "name": q["q"],
                                    "acceptedAnswer": {"@type": "Answer", "text": strip_tags(expand(q["a"], a["slug"]))}}
                                   for q in a["faq"]]})
    return out


def render(a):
    slug = a["slug"]
    canonical = page_url(slug)
    crumbs, crumb_schema = breadcrumb(a)
    body = expand(a["body"], slug)
    qa = a.get("quick_answer")
    qa_html = f'<div class="quick-answer"><span>Kurz gesagt</span><p>{expand(qa, slug)}</p></div>' if qa else ""
    intro = f'<p class="lede">{expand(a["intro"], slug)}</p>' if a.get("intro") else ""
    updated = f'<p class="meta">Aktualisiert am {de_date(a["date_modified"])} · Von Marmalade Co.</p>'

    if a["layout"] == "home":
        top = f'''<section class="hero">
  <div class="wrap">
    <p class="eyebrow">{esc(a.get("eyebrow", ""))}</p>
    <h1>{a["h1"]}</h1>
    {intro}
    {updated}
  </div>
</section>
<div class="wrap narrow">{qa_html}</div>'''
        main = f'<main class="home">{body}</main>'
        if a["faq"]:
            main += f'<div class="wrap narrow">{faq_html(a["faq"], slug)}</div>'
    else:
        top = ""
        disclosure = "" if a["layout"] == "legal" else (
            f'<aside class="disclosure">{esc(SITE["disclosure_short"])} <a href="/ueber-uns">Mehr über uns</a>.</aside>')
        main = f'''<main class="wrap narrow article">
  {crumbs}
  <p class="eyebrow">{esc(a.get("eyebrow") or a["category"])}</p>
  <h1>{a["h1"]}</h1>
  {"" if a["layout"] == "legal" else updated}
  {intro}
  {qa_html}
  <div class="prose">{body}</div>
  {faq_html(a["faq"], slug)}
  {related_html(a)}
  {disclosure}
</main>'''

    sch = schemas(a, canonical)
    if crumb_schema:
        sch.append(crumb_schema)
    js = CALC_JS if 'class="calc"' in body else ""
    return (head(a, canonical) + "".join(jsonld(s) for s in sch) + "\n</head>\n<body>\n"
            + header() + "\n" + top + "\n" + main + "\n" + footer(slug) + js + "\n</body>\n</html>\n")


# ---------------------------------------------------------------- site files
def sitemap():
    urls = []
    for a in sorted(ARTICLES, key=lambda x: (x["slug"] != "index", x["slug"])):
        if a.get("noindex"):
            continue
        pr = "1.0" if a["slug"] == "index" else ("0.8" if a["layout"] == "article" else "0.4")
        urls.append(f"  <url><loc>{page_url(a['slug'])}</loc><lastmod>{a['date_modified']}</lastmod>"
                    f"<changefreq>weekly</changefreq><priority>{pr}</priority></url>")
    urls.append(f"  <url><loc>{DOMAIN}/ratgeber</loc><lastmod>{max(a['date_modified'] for a in ARTICLES)}</lastmod>"
                f"<changefreq>weekly</changefreq><priority>0.7</priority></url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>\n")


def robots():
    bots = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "PerplexityBot", "Perplexity-User",
            "ClaudeBot", "Claude-User", "Claude-SearchBot", "Google-Extended", "Applebot",
            "Applebot-Extended", "Bingbot", "CCBot"]
    s = f"# robots.txt - {HOST}\nUser-agent: *\nAllow: /\n\n# KI-Suchmaschinen (GEO) - ausdrücklich erlaubt\n"
    s += "".join(f"User-agent: {b}\nAllow: /\n\n" for b in bots)
    return s + f"Sitemap: {DOMAIN}/sitemap.xml\n"


def llms():
    lines = [f"# {HOST}", "", f"> {SITE['description']}", "", "## Kernfakten", ""]
    lines += [f"- {x}" for x in SITE["llms_facts"]]
    lines += ["", f"## Preise Marmalade Co. (inkl. MwSt., geprüft {PRICES['checked']})", ""]
    for p in PRICES["products"]:
        lines.append(f"- {PRODUCT_NAMES.get(p['id'], p['id'])}: {eur(p['price'])}, ab 5 Stück "
                     f"{eur(unit_price(p['id'], 5))}. {SHOP}{p['path']}")
    lines += ["", f"## Vergleich T-Shirt-Rohlinge (geprüft {BRANDS['checked']})", ""]
    for r in BRANDS["rows"]:
        lines.append(f'- {r["model"]} bei {r["shop"]}: {r["fabric"]}, {r["price"]} ({r.get("price_note", "")}), '
                     f'Kunden: {r["buyers"]}, Versand: {r["shipping"]}')
    groups = {}
    for a in ARTICLES:
        if a["listed"]:
            groups.setdefault(a["category"], []).append(a)
    for cat in sorted(groups):
        lines += ["", f"## {cat}", ""]
        for a in sorted(groups[cat], key=lambda x: x["slug"]):
            lines.append(f"- [{a['h1']}]({page_url(a['slug'])}): {a['description']}")
    lines += ["", "## Über die Seite", "", f"- [Über {HOST}]({DOMAIN}/ueber-uns): {SITE['disclosure_short']}"]
    return "\n".join(lines) + "\n"


def ratgeber_page():
    groups = {}
    for a in ARTICLES:
        if a["listed"]:
            groups.setdefault(a["category"], []).append(a)
    order = SITE.get("category_order", [])
    cats = sorted(groups, key=lambda c: (order.index(c) if c in order else 99, c))
    body = ""
    for c in cats:
        items = sorted(groups[c], key=lambda a: (a.get("order", 999), a["title"]))
        cards = "".join(f'<a class="card" href="{href(a["slug"])}"><span class="card-tag">{esc(c)}</span>'
                        f'<strong>{esc(a.get("card_title") or a["h1"])}</strong><em>{esc(a["description"])}</em></a>'
                        for a in items)
        body += f"<h2>{esc(c)}</h2><div class='cards cards-lg'>{cards}</div>"
    return {"slug": "ratgeber", "layout": "page", "listed": False, "faq": [], "related": [],
            "title": "Ratgeber: T-Shirts bedrucken, Rohlinge, Druckverfahren",
            "description": "Alle Ratgeber zu T-Shirts zum Bedrucken: Druckverfahren, Rohlinge im Vergleich, Größen, Stoffgewicht und Preise für Mengen.",
            "h1": "Alle Ratgeber zum T-Shirt-Druck", "card_title": "Ratgeber", "category": "Übersicht",
            "intro": "Hier findest du alle unsere Ratgeber. Wir schreiben laufend neue und aktualisieren Preise, wenn sie sich ändern.",
            "date_published": "2026-09-14", "date_modified": max(a["date_modified"] for a in ARTICLES), "body": body}


def page_404():
    return {"slug": "404", "layout": "page", "listed": False, "noindex": True, "faq": [], "related": [],
            "title": f"Seite nicht gefunden | {HOST}",
            "description": "Diese Seite gibt es nicht. Zur Startseite mit dem Vergleich von T-Shirt-Rohlingen zum Bedrucken.",
            "h1": "Diese Seite gibt es leider nicht", "card_title": "404", "category": "Fehler",
            "date_published": "2026-09-14", "date_modified": "2026-09-14",
            "body": '<p>Versuch es auf der <a href="/">Startseite</a> oder in den <a href="/ratgeber">Ratgebern</a>.</p>'}


def htaccess():
    return f"""# {HOST} - LiteSpeed/Apache (cPanel). GitHub Pages ignoriert diese Datei.
Options -Indexes
DirectoryIndex index.html
ErrorDocument 404 /404.html
RewriteEngine On
RewriteCond %{{HTTPS}} off [OR]
RewriteCond %{{HTTP_HOST}} ^www\\. [NC]
RewriteRule ^ https://{HOST}%{{REQUEST_URI}} [L,R=301]
RewriteCond %{{THE_REQUEST}} \\s/+(.+?)\\.html[\\s?] [NC]
RewriteRule ^ /%1 [L,R=301]
RewriteCond %{{REQUEST_FILENAME}} !-f
RewriteCond %{{REQUEST_FILENAME}}.html -f
RewriteRule ^(.+?)/?$ $1.html [L]
"""


# ---------------------------------------------------------------- validation
DASHES = re.compile("[\u2013\u2014]")
EXTERNAL_ASSETS = re.compile(r'(src|href)="https?://(?!' + re.escape(HOST) + r')[^"]+\.(js|css|woff2?)(\?[^"]*)?"'
                             r'|fonts\.googleapis|googletagmanager|google-analytics', re.I)


def validate(name, doc):
    visible = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", doc, flags=re.S)
    m = DASHES.search(visible)
    if m:
        errors.append(f"{name}: langer Gedankenstrich im Text: ...{strip_tags(visible[max(0, m.start() - 50):m.start() + 20])}...")
    if EXTERNAL_ASSETS.search(doc):
        errors.append(f"{name}: externe Schrift/Skript/Tracker gefunden (DSGVO): {EXTERNAL_ASSETS.search(doc).group(0)[:80]}")
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', doc, re.S):
        try:
            json.loads(m.group(1))
        except json.JSONDecodeError as e:
            errors.append(f"{name}: ungültiges JSON-LD ({e})")
    for m in re.finditer(r'href="/([a-z0-9\-]*)(?:#[^"]*)?"', doc):
        s = m.group(1)
        if s and s not in BY_SLUG:
            errors.append(f"{name}: toter interner Link /{s}")
    if name == "404":
        return
    t = html.unescape(re.search(r"<title>(.*?)</title>", doc).group(1))
    d = html.unescape(re.search(r'<meta name="description" content="(.*?)">', doc).group(1))
    if len(t) > 65:
        warnings.append(f"{name}: title hat {len(t)} Zeichen (> 65)")
    if not 110 <= len(d) <= 165:
        warnings.append(f"{name}: meta description hat {len(d)} Zeichen")


# ---------------------------------------------------------------- main
def main():
    extra = [ratgeber_page(), page_404()]
    for p in extra:
        BY_SLUG.setdefault(p["slug"], p)
    pages = {a["slug"]: render(a) for a in ARTICLES + extra}
    for name, doc in pages.items():
        validate(name, doc)
    for s in REQUIRED:
        if s not in BY_SLUG:
            errors.append(f"Pflichtseite fehlt: {s}")

    for w in warnings:
        print("WARNUNG:", w)
    if errors:
        for e in errors:
            print("FEHLER:", e)
        sys.exit(1)
    print(f"OK: {len(pages)} Seiten, {sum(1 for a in ARTICLES if a['listed'])} Artikel")
    if CHECK_ONLY:
        return

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    for name, doc in pages.items():
        with open(os.path.join(OUT, f"{name}.html"), "w", encoding="utf-8") as f:
            f.write(doc)
    files = {"sitemap.xml": sitemap(), "robots.txt": robots(), "llms.txt": llms(),
             ".htaccess": htaccess(), "CNAME": HOST + "\n", ".nojekyll": ""}
    for fn, txt in files.items():
        with open(os.path.join(OUT, fn), "w", encoding="utf-8") as f:
            f.write(txt)
    for fn in os.listdir(ASSETS):
        if fn != "site.css" and not fn.startswith("."):
            shutil.copy(os.path.join(ASSETS, fn), os.path.join(OUT, fn))
    print(f"Geschrieben: {OUT}")


if __name__ == "__main__":
    main()
