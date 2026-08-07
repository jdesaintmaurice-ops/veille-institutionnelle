#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VEILLE INSTITUTIONNELLE — version Playwright v3
===============================================
Nouveautés v3 :
  • Source JORF intégrée (via l'API Légifrance, module jorf_veille.py)
  • Liste de mots-clés DÉDIÉE au JO (distincte des autres sources)
  • Intègre les correctifs : chargement domcontentloaded, sélecteur IGF nettoyé,
    source Franceinfo.

Prérequis :
    pip install playwright beautifulsoup4 requests
    python3 -m playwright install chromium
    config_piste.py rempli avec vos identifiants (pour le JORF).

Lancement :
    python3 veille_playwright_v3.py
"""

# =============================================================================
#  ⬇⬇⬇   MOTS-CLÉS — SOURCES WEB (Playwright)   ⬇⬇⬇
# =============================================================================
#  Appliqués à toutes les sources SAUF le JORF (qui a sa propre liste plus bas).
#  Liste VIDE ( [] ) => tout afficher.
# -----------------------------------------------------------------------------
MOTS_CLES_GLOBAUX = [
    "INA",
    "Institut national de l'audiovisuel",
    "Inathèque",
    "audiovisuel",
    "archives audiovisuelles",
    "patrimoine audiovisuel",
    "dépôt légal",
    "numérisation",
    "audiovisuel public",
    "France Télévisions",
    "Radio France",
    "France Médias Monde",
    "ARCOM",
    "réforme de l'audiovisuel",
    "holding audiovisuel",
    "ministère de la Culture",
    "politique culturelle",
    "financement de la culture",
    "CNC",
]

MOTS_CLES_PAR_SOURCE = {
    # "Acteurs Publics": ["fonction publique", "cour des comptes"],
}

# =============================================================================
#  ⬇⬇⬇   MOTS-CLÉS DÉDIÉS AU JORF (plus stricts)   ⬇⬇⬇
# =============================================================================
#  Le JO est très juridique/volumineux : on y met des termes précis pour
#  éviter les faux positifs (ex. "communication" attrape des conventions
#  collectives sans rapport). Liste VIDE => tout le JO passe (déconseillé).
# -----------------------------------------------------------------------------
MOTS_CLES_JORF = [
    "audiovisuel",
    "Institut national de l'audiovisuel",
    "France Télévisions",
    "Radio France",
    "France Médias Monde",
    "ARCOM",
    "dépôt légal",
    "cinéma",
    "cinématographique",
    "patrimoine",
    "propriété littéraire et artistique",
    "droit d'auteur",
]

# =============================================================================
#  ⬇⬇⬇   RÉGLAGES DE L'ENVOI DU MAIL   ⬇⬇⬇
# =============================================================================
import os as _os
from identifiants import (GMAIL_UTILISATEUR as _GU, GMAIL_MOT_DE_PASSE as _GP,
                          MAIL_DESTINATAIRE as _MD)

# Envoi activé automatiquement sur GitHub (variable CI présente), sinon False en local.
ENVOI_ACTIF = bool(_os.environ.get("GITHUB_ACTIONS")) or False

SMTP_SERVEUR   = "smtp.gmail.com"
SMTP_PORT      = 587
SMTP_UTILISATEUR = _GU or "votre.adresse@gmail.com"
SMTP_MOT_DE_PASSE = _GP or "xxxx xxxx xxxx xxxx"
MAIL_EXPEDITEUR   = _GU or "votre.adresse@gmail.com"
MAIL_DESTINATAIRE = _MD or _GU or "votre.adresse@gmail.com"

# =============================================================================
#  ⬆⬆⬆   FIN DES ZONES À REMPLIR   ⬆⬆⬆
# =============================================================================

FENETRE_HEURES = 24
FICHIER_MEMOIRE = "deja_vus.json"
AFFICHER_ECARTES = True

# -----------------------------------------------------------------------------
#  SOURCES WEB (Playwright)
# -----------------------------------------------------------------------------
SOURCES = [
    {
        "nom": "Acteurs Publics",
        "url": "https://acteurspublics.fr/actualites/",
        "selecteur": 'a[href*="/articles/"]',
        "attribut_titre": "title",
        "priorite": 1, "actif": True,
    },
    {
        "nom": "Vie-publique — Rapports",
        "url": "https://www.vie-publique.fr/rapports",
        "selecteur": "article a, .fr-card__title a, h2 a, h3 a",
        "attribut_titre": None,
        "priorite": 1, "actif": True,
    },
    {
        "nom": "La Lettre A — Médias",
        "url": "https://www.lalettre.fr/fr/rub/medias",
        "selecteur": "article a, h2 a, h3 a",
        "attribut_titre": None,
        "priorite": 2, "actif": True,
    },
    {
        "nom": "IGF — Rapports",
        "url": "https://www.igf.finances.gouv.fr/liste-de-tous-les-rapports-de-mi.html",
        "selecteur": ".newsListItem h3 a",
        "attribut_titre": None,
        "priorite": 2, "actif": True,
    },
    {
        "nom": "Culture.gouv — Espace doc",
        "url": "https://www.culture.gouv.fr/espace-documentation",
        "selecteur": "article a, .teaser a",
        "attribut_titre": None,
        "priorite": 2, "actif": True,
    },
    {
        "nom": "Franceinfo — Médias",
        "url": "https://www.franceinfo.fr/economie/medias/",
        "selecteur": "article a.card-article-link, article a, h2 a",
        "attribut_titre": None,
        "priorite": 2, "actif": True,
    },
    # --- Désactivées ---
    {"nom": "Cour des comptes", "url": "https://www.ccomptes.fr/fr/publications",
     "selecteur": "", "attribut_titre": None, "priorite": 1, "actif": False},
    {"nom": "Contexte — Médias", "url": "https://www.contexte.com/recherche",
     "selecteur": "", "attribut_titre": None, "priorite": 2, "actif": False},
    {"nom": "Le Monde — Médias", "url": "https://www.lemonde.fr/actualite-medias/",
     "selecteur": "", "attribut_titre": None, "priorite": 3, "actif": False},
]


# =============================================================================
#  MOTEUR
# =============================================================================
import unicodedata
import datetime as dt
import json
import os
import sys

# Module JORF (API Légifrance). Import protégé : si absent, le JORF est ignoré.
try:
    from jorf_veille import collecter_jorf
    JORF_DISPO = True
except Exception:
    JORF_DISPO = False

try:
    from jorf_commissions import collecter_commissions
    COMMISSIONS_DISPO = True
except Exception:
    COMMISSIONS_DISPO = False


def normaliser(texte: str) -> str:
    texte = (texte or "").lower()
    texte = unicodedata.normalize("NFD", texte)
    return "".join(c for c in texte if unicodedata.category(c) != "Mn")


def mots_cles_pour(nom: str):
    return MOTS_CLES_PAR_SOURCE.get(nom, MOTS_CLES_GLOBAUX)


def intitule_retenu(titre: str, mots_cles) -> bool:
    if not mots_cles:
        return True
    t = normaliser(titre)
    return any(normaliser(m) in t for m in mots_cles)


def charger_memoire():
    if os.path.exists(FICHIER_MEMOIRE):
        try:
            with open(FICHIER_MEMOIRE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def sauver_memoire(memoire):
    with open(FICHIER_MEMOIRE, "w", encoding="utf-8") as f:
        json.dump(memoire, f, ensure_ascii=False, indent=2)


def purger_memoire(memoire, jours=30):
    limite = dt.datetime.now() - dt.timedelta(days=jours)
    return {lien: d for lien, d in memoire.items()
            if dt.datetime.fromisoformat(d) > limite}


def collecter_source(page, source):
    page.goto(source["url"], timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    attr = source["attribut_titre"]
    if attr:
        js = ("els => els.map(e => ({t: e.getAttribute('%s'), l: e.href}))" % attr)
    else:
        js = "els => els.map(e => ({t: e.innerText, l: e.href}))"
    bruts = page.eval_on_selector_all(source["selecteur"], js)
    vus, uniques = set(), []
    for b in bruts:
        titre = (b.get("t") or "").strip()
        lien = b.get("l") or ""
        if titre and lien and lien not in vus:
            vus.add(lien)
            uniques.append({"titre": titre, "lien": lien})
    return uniques


def traiter_source(nom, bruts, mots, memoire, resultats):
    """Applique filtre mots-clés + nouveauté, affiche le bilan, stocke le résultat."""
    retenus_mots, ecartes_mots = [], []
    for a in bruts:
        (retenus_mots if intitule_retenu(a["titre"], mots) else ecartes_mots).append(a)
    nouveaux = [a for a in retenus_mots if a["lien"] not in memoire]
    print(f"[OK]   {nom} — {len(bruts)} trouvés, "
          f"{len(retenus_mots)} passent les mots-clés, "
          f"{len(nouveaux)} nouveaux (24h).")
    if AFFICHER_ECARTES and ecartes_mots:
        print(f"       — écartés par les mots-clés ({len(ecartes_mots)}) :")
        for a in ecartes_mots[:15]:
            print(f"           · {a['titre'][:75]}")
        if len(ecartes_mots) > 15:
            print(f"           … et {len(ecartes_mots) - 15} autres")
    resultats.append((nom, nouveaux))


def generer_mail_html(resultats):
    date_jour = dt.date.today().strftime("%d/%m/%Y")
    out = [
        "<html><body style='font-family:Arial,sans-serif;color:#1a1a1a;'>",
        f"<h1 style='font-size:20px;'>Veille institutionnelle — {date_jour}</h1>",
        f"<p style='color:#555;'>Nouvelles publications des dernières {FENETRE_HEURES} h "
        "correspondant à vos mots-clés.</p>",
    ]
    total = 0
    for nom, articles in resultats:
        if not articles:
            continue
        out.append(f"<h2 style='font-size:16px;border-bottom:2px solid #ccc;'>{nom}</h2><ul>")
        for a in articles:
            total += 1
            out.append(f"<li style='margin:6px 0;'><a href='{a['lien']}' "
                       f"style='color:#0b57d0;text-decoration:none;'>{a['titre']}</a></li>")
        out.append("</ul>")
    if total == 0:
        out.append("<p><em>Aucune nouvelle publication ne correspond à vos mots-clés aujourd'hui.</em></p>")
    out.append("</body></html>")
    return "\n".join(out), total


def envoyer_mail(sujet, corps_html):
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    msg = MIMEMultipart("alternative")
    msg["Subject"] = sujet
    msg["From"] = MAIL_EXPEDITEUR
    msg["To"] = MAIL_DESTINATAIRE
    msg.attach(MIMEText(corps_html, "html", "utf-8"))
    with smtplib.SMTP(SMTP_SERVEUR, SMTP_PORT) as serveur:
        serveur.starttls()
        serveur.login(SMTP_UTILISATEUR, SMTP_MOT_DE_PASSE)
        serveur.sendmail(MAIL_EXPEDITEUR, [MAIL_DESTINATAIRE], msg.as_string())


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Installez Playwright : pip install playwright && python3 -m playwright install chromium")
        sys.exit(1)

    print("=== Veille institutionnelle (Playwright) v3 ===\n")
    memoire = charger_memoire()
    resultats = []

    # --- 1) Sources web (Playwright) ---
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
            locale="fr-FR",
        )
        page = ctx.new_page()
        for source in sorted(SOURCES, key=lambda s: s["priorite"]):
            nom = source["nom"]
            if not source["actif"]:
                print(f"[SKIP] {nom} — désactivée.")
                continue
            try:
                bruts = collecter_source(page, source)
            except Exception as e:
                print(f"[ERREUR] {nom} — {e}")
                continue
            traiter_source(nom, bruts, mots_cles_pour(nom), memoire, resultats)
        browser.close()

    # --- 2) Source JORF (API Légifrance) ---
    if JORF_DISPO:
        try:
            # On récupère le JO déjà filtré par la liste dédiée MOTS_CLES_JORF.
            bruts_jorf = collecter_jorf(mots_cles=MOTS_CLES_JORF)
            # Filtre "nouveauté" appliqué comme aux autres sources.
            nouveaux = [a for a in bruts_jorf if a["lien"] not in memoire]
            print(f"[OK]   Journal Officiel (JORF) — {len(bruts_jorf)} retenus (mots-clés JO), "
                  f"{len(nouveaux)} nouveaux (24h).")
            resultats.append(("Journal Officiel (JORF)", nouveaux))
        except Exception as e:
            print(f"[ERREUR] JORF — {e}")
    else:
        print("[SKIP] JORF — module jorf_veille.py indisponible.")

    # --- 3) Réunions de commissions culture (parlementaires) ---
    if COMMISSIONS_DISPO:
        try:
            bruts_com = collecter_commissions()
            nouveaux = [a for a in bruts_com if a["lien"] + a["titre"] not in memoire]
            print(f"[OK]   Commissions culture — {len(bruts_com)} réunion(s), "
                  f"{len(nouveaux)} nouvelle(s).")
            # Clé mémoire = lien+titre (plusieurs réunions partagent le même lien)
            resultats.append(("Réunions commissions culture", nouveaux))
            for a in nouveaux:
                a["_cle"] = a["lien"] + a["titre"]
        except Exception as e:
            print(f"[ERREUR] Commissions — {e}")
    else:
        print("[SKIP] Commissions — module indisponible.")

    # --- Mise à jour mémoire ---
    maintenant = dt.datetime.now().isoformat()
    for _, articles in resultats:
        for a in articles:
            cle = a.get("_cle", a["lien"])
            memoire[cle] = maintenant
    memoire = purger_memoire(memoire, jours=30)
    sauver_memoire(memoire)

    # --- Génération / envoi ---
    html, total = generer_mail_html(resultats)
    with open("mail_veille.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nMail généré => mail_veille.html ({total} nouvelles publications retenues)")

    if ENVOI_ACTIF:
        if total == 0:
            print("Envoi : rien de neuf, pas de mail envoyé.")
        else:
            try:
                sujet = f"Veille institutionnelle — {dt.date.today().strftime('%d/%m/%Y')} ({total})"
                envoyer_mail(sujet, html)
                print(f"Mail ENVOYÉ à {MAIL_DESTINATAIRE}.")
            except Exception as e:
                print(f"[ERREUR ENVOI] {e}")
    else:
        print("Envoi désactivé (ENVOI_ACTIF = False). Ouvrez mail_veille.html pour prévisualiser.")


if __name__ == "__main__":
    main()
