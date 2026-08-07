#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODULE COMMISSIONS PARLEMENTAIRES — extension de la veille JORF
===============================================================
Récupère, dans les textes "Informations parlementaires" du JO, les RÉUNIONS
des commissions CULTURE (au sens large : culture, éducation, communication,
médias) de l'Assemblée nationale ET du Sénat.

Sortie : une ligne compacte par réunion -> intitulé commission + jour + heure.

Principe technique :
  1) chercher dans le JO les textes parlementaires (NOR commençant par INP...)
  2) récupérer le CONTENU de chaque texte via /consult/jorf
  3) repérer les blocs de commission dont le nom matche CULTURE
  4) en extraire le jour et l'heure

Dépend de config_piste.py (mêmes identifiants que jorf_veille.py).
Test : python3 jorf_commissions.py
"""

# =============================================================================
#  VVV   RÉGLAGES   VVV
# =============================================================================
# Mots qui identifient une commission "culture" au sens large.
# Un bloc de commission est retenu si son nom contient l'un de ces termes.
TERMES_COMMISSION_CULTURE = [
    "culture",
    "education",       # éducation
    "communication",
    "affaires culturelles",
    "medias",          # médias
]

# Préfixes NOR des informations parlementaires (à confirmer via diagnostic).
PREFIXES_PARLEMENTAIRES = ["INP"]   # ex vu : INPS, INPA...
# =============================================================================
#  ^^^   FIN RÉGLAGES   ^^^
# =============================================================================

import re
import unicodedata
import datetime as dt

import requests

from identifiants import PISTE_CLIENT_ID, PISTE_CLIENT_SECRET

TOKEN_URL = "https://oauth.piste.gouv.fr/api/oauth/token"
API_BASE  = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"
JOURS = 1


def _norm(t):
    t = (t or "").lower()
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _token():
    r = requests.post(TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": PISTE_CLIENT_ID,
        "client_secret": PISTE_CLIENT_SECRET,
    }, timeout=20)
    r.raise_for_status()
    return r.json()["access_token"]


def _rechercher_textes_parlementaires(token):
    """Renvoie les textes du JO dont le NOR est parlementaire (INP...)."""
    auj = dt.date.today()
    debut = auj - dt.timedelta(days=JOURS)
    payload = {
        "recherche": {
            "champs": [{"typeChamp": "TITLE", "criteres": [{
                "typeRecherche": "TOUS_LES_MOTS_DANS_UN_CHAMP",
                "valeur": "", "operateur": "ET"}], "operateur": "ET"}],
            "filtres": [{"facette": "DATE_PUBLICATION",
                         "dates": {"start": debut.strftime("%Y-%m-%d"),
                                   "end": auj.strftime("%Y-%m-%d")}}],
            "pageNumber": 1, "pageSize": 100, "operateur": "ET",
            "sort": "PUBLICATION_DATE_DESC", "typePagination": "DEFAUT",
        },
        "fond": "JORF",
    }
    headers = {"Authorization": "Bearer " + token,
               "Content-Type": "application/json", "accept": "application/json"}
    r = requests.post(API_BASE + "/search", json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    textes = []
    for res in r.json().get("results", []):
        for t in res.get("titles", []):
            nor = (t.get("nor") or res.get("nor") or "").strip().upper()
            cid = t.get("cid") or t.get("id") or ""
            titre = (t.get("title") or "").strip()
            if nor and any(nor.startswith(p) for p in PREFIXES_PARLEMENTAIRES) and cid:
                textes.append({"cid": cid, "titre": titre, "nor": nor})
    return textes


def _contenu_texte(token, cid):
    """Récupère le contenu HTML/texte d'un texte JORF via /consult/jorf."""
    headers = {"Authorization": "Bearer " + token,
               "Content-Type": "application/json", "accept": "application/json"}
    r = requests.post(API_BASE + "/consult/jorf", json={"textCid": cid},
                      headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


def _extraire_texte_brut(obj):
    """Aplati récursivement le JSON de contenu pour récupérer tout le texte."""
    morceaux = []
    def visiter(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("content", "titre", "titreTexte", "texte") and isinstance(v, str):
                    morceaux.append(v)
                else:
                    visiter(v)
        elif isinstance(x, list):
            for e in x:
                visiter(e)
    visiter(obj)
    # Nettoyage HTML basique
    texte = "\n".join(morceaux)
    texte = re.sub(r"<[^>]+>", " ", texte)
    texte = re.sub(r"&nbsp;", " ", texte)
    return texte


def _extraire_reunions(texte_brut):
    """Cherche des blocs 'Commission ... culture ...' suivis d'un horaire.
    Renvoie [{commission, jour, heure}]. Heuristique, ajustable."""
    reunions = []
    # Découpe en lignes nettoyées
    lignes = [l.strip() for l in re.split(r"[\n\r]+", texte_brut) if l.strip()]

    jour_courant = ""
    # motif de jour : "Mardi 19 mai 2026", "Mercredi 3 septembre 2026"...
    motif_jour = re.compile(
        r"\b(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+\d{1,2}\s+"
        r"(janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre)",
        re.IGNORECASE)
    # motif d'heure : "A 14 h 30", "A 15 heures", "à 9 h"
    motif_heure = re.compile(r"\b[àa]\s*(\d{1,2})\s*(?:h|heures?)\s*(\d{0,2})", re.IGNORECASE)

    for i, ligne in enumerate(lignes):
        if motif_jour.search(_norm(ligne)):
            jour_courant = ligne
            continue
        # Est-ce un intitulé de commission culture ?
        if "commission" in _norm(ligne) and any(t in _norm(ligne) for t in TERMES_COMMISSION_CULTURE):
            # chercher l'heure dans les 3 lignes suivantes
            heure = ""
            for j in range(i, min(i + 4, len(lignes))):
                m = motif_heure.search(lignes[j])
                if m:
                    h = m.group(1)
                    mn = m.group(2) or "00"
                    heure = f"{h}h{mn.zfill(2)}" if mn else f"{h}h"
                    break
            reunions.append({
                "commission": ligne,
                "jour": jour_courant,
                "heure": heure,
            })
    return reunions


def collecter_commissions():
    """Point d'entrée. Renvoie une liste de dicts {titre, lien} prête à intégrer
    dans le mail (titre = 'Commission ... — jour — heure')."""
    if not PISTE_CLIENT_ID or PISTE_CLIENT_ID.startswith("COLLEZ"):
        print("[Commissions] Identifiants PISTE manquants")
        return []
    try:
        token = _token()
        textes = _rechercher_textes_parlementaires(token)
    except Exception as e:
        print("[Commissions] Erreur API (recherche) : " + str(e))
        return []

    sorties = []
    for t in textes:
        try:
            contenu = _contenu_texte(token, t["cid"])
            brut = _extraire_texte_brut(contenu)
            for r in _extraire_reunions(brut):
                libelle = r["commission"]
                if r["jour"]:
                    libelle += " — " + r["jour"]
                if r["heure"]:
                    libelle += " — " + r["heure"]
                lien = "https://www.legifrance.gouv.fr/jorf/id/" + t["cid"]
                sorties.append({"titre": libelle, "lien": lien})
        except Exception as e:
            print("[Commissions] Erreur contenu " + t["cid"] + " : " + str(e))
    return sorties


if __name__ == "__main__":
    print("=== Test module Commissions parlementaires ===\n")
    if not PISTE_CLIENT_ID or PISTE_CLIENT_ID.startswith("COLLEZ"):
        print("Identifiants PISTE manquants dans config_piste.py")
    else:
        try:
            token = _token()
            textes = _rechercher_textes_parlementaires(token)
            print(str(len(textes)) + " texte(s) parlementaire(s) (INP...) trouvé(s) :")
            for t in textes:
                print("   [" + t["nor"][:4] + "] " + t["titre"][:70])
            print()
            res = collecter_commissions()
            print("-> " + str(len(res)) + " réunion(s) commission culture extraite(s) :")
            for r in res:
                print("   . " + r["titre"])
            if not res and textes:
                print("\n(Aucune réunion culture aujourd'hui, ou format à ajuster.)")
        except Exception as e:
            print("Erreur : " + str(e))
