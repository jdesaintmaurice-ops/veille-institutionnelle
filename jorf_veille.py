#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODULE JORF v2 — Veille du Journal Officiel via l'API Légifrance (PISTE)
=======================================================================
MINISTÈRES CIBLÉS : tout ce qui émane du ministère de la Culture, repéré
via le PRÉFIXE du code NOR (4 lettres = l'émetteur). Le Premier ministre
est volontairement exclu (trop de bruit : nominations, décrets divers...).

Prérequis :  pip install requests   + config_piste.py rempli.

Test / diagnostic :  python3 jorf_veille.py
  -> affiche les textes retenus ET un diagnostic des prefixes NOR du jour,
    pour verifier/completer la liste des ministeres cibles.
"""

# =============================================================================
#  VVV   MINISTERES CIBLES (par prefixe de code NOR)   VVV
# =============================================================================
#  Les 4 premieres lettres du NOR identifient l'emetteur. On garde un texte si
#  son NOR COMMENCE par l'un de ces prefixes.
#  /!\ Les prefixes ci-dessous sont a CONFIRMER au 1er lancement grace au
#     diagnostic en bas d'ecran (il liste les prefixes reels du JO du jour).
#  Pour ajouter un ministere : ajoutez une ligne "XXX" (prefixe), une virgule.
#  Le Premier ministre (prefixe "PRM") est exclu delibérement.
# -----------------------------------------------------------------------------
PREFIXES_NOR_CIBLES = [
    "MIC",   # Ministere de la Culture
    # "MICB", # (variante possible Culture - a verifier au diagnostic)
]

# =============================================================================
#  ^^^   FIN DES ZONES A REMPLIR   ^^^
# =============================================================================

import requests
import datetime as dt

from identifiants import PISTE_CLIENT_ID, PISTE_CLIENT_SECRET

TOKEN_URL = "https://oauth.piste.gouv.fr/api/oauth/token"
API_BASE  = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"
JORF_JOURS = 1


def obtenir_token():
    donnees = {
        "grant_type": "client_credentials",
        "client_id": PISTE_CLIENT_ID,
        "client_secret": PISTE_CLIENT_SECRET,
    }
    r = requests.post(TOKEN_URL, data=donnees, timeout=20)
    r.raise_for_status()
    return r.json()["access_token"]


def rechercher_jorf(token, jours=JORF_JOURS):
    aujourdhui = dt.date.today()
    debut = aujourdhui - dt.timedelta(days=jours)
    payload = {
        "recherche": {
            "champs": [{
                "typeChamp": "TITLE",
                "criteres": [{
                    "typeRecherche": "TOUS_LES_MOTS_DANS_UN_CHAMP",
                    "valeur": "",
                    "operateur": "ET",
                }],
                "operateur": "ET",
            }],
            "filtres": [{
                "facette": "DATE_PUBLICATION",
                "dates": {
                    "start": debut.strftime("%Y-%m-%d"),
                    "end": aujourdhui.strftime("%Y-%m-%d"),
                },
            }],
            "pageNumber": 1,
            "pageSize": 100,
            "operateur": "ET",
            "sort": "PUBLICATION_DATE_DESC",
            "typePagination": "DEFAUT",
        },
        "fond": "JORF",
    }
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "accept": "application/json",
    }
    r = requests.post(API_BASE + "/search", json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    articles = []
    for res in data.get("results", []):
        for t in res.get("titles", []):
            titre = (t.get("title") or "").strip()
            cid = t.get("cid") or t.get("id") or ""
            nor = (t.get("nor") or res.get("nor") or "").strip().upper()
            lien = "https://www.legifrance.gouv.fr/jorf/id/" + cid if cid else ""
            if titre:
                articles.append({"titre": titre, "lien": lien, "nor": nor})
    return articles


def _retenu(article):
    nor = article.get("nor", "")
    return bool(nor and any(nor.startswith(p.upper()) for p in PREFIXES_NOR_CIBLES))


def collecter_jorf():
    if not PISTE_CLIENT_ID or PISTE_CLIENT_ID.startswith("COLLEZ"):
        print("[JORF] Identifiants PISTE manquants dans config_piste.py")
        return []
    try:
        token = obtenir_token()
        bruts = rechercher_jorf(token)
    except Exception as e:
        print("[JORF] Erreur API : " + str(e))
        return []
    return [{"titre": a["titre"], "lien": a["lien"]} for a in bruts if _retenu(a)]


if __name__ == "__main__":
    print("=== Test module JORF v2 ===\n")
    if not PISTE_CLIENT_ID or PISTE_CLIENT_ID.startswith("COLLEZ"):
        print("Identifiants PISTE manquants dans config_piste.py")
    else:
        try:
            token = obtenir_token()
            bruts = rechercher_jorf(token)
            print(str(len(bruts)) + " textes au JO sur les " + str(JORF_JOURS) + " dernier(s) jour(s).\n")
            retenus = [a for a in bruts if _retenu(a)]
            print("-> " + str(len(retenus)) + " retenus (ministeres cibles) :")
            for a in retenus[:25]:
                print("   . [" + (a.get('nor','????')[:4]) + "] " + a['titre'][:75])
            print("\n--- Diagnostic prefixes NOR du jour (pour completer la liste) ---")
            from collections import Counter
            prefixes = Counter(a["nor"][:4] for a in bruts if a.get("nor"))
            if not prefixes:
                print("  (aucun NOR renvoye par l'API - on ajustera la lecture du champ)")
            for pref, n in prefixes.most_common(20):
                print("   " + pref + " : " + str(n) + " texte(s)")
        except Exception as e:
            print("Erreur : " + str(e))
