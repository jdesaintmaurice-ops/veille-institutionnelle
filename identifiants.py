# -*- coding: utf-8 -*-
"""
GESTION DES IDENTIFIANTS — fonctionne sur PC (local) ET sur GitHub Actions.
==========================================================================
Priorité :
  1) variables d'environnement (les Secrets GitHub), si présentes ;
  2) sinon, le fichier local config_piste.py (votre PC).

Ainsi le MÊME code marche aux deux endroits, sans rien changer.
"""
import os

def _depuis_env_ou_config():
    # 1) Essayer les variables d'environnement (GitHub Actions)
    cid = os.environ.get("PISTE_CLIENT_ID")
    csecret = os.environ.get("PISTE_CLIENT_SECRET")
    gmail_user = os.environ.get("GMAIL_UTILISATEUR")
    gmail_pass = os.environ.get("GMAIL_MOT_DE_PASSE")
    mail_dest = os.environ.get("MAIL_DESTINATAIRE")

    # 2) Compléter avec config_piste.py si des valeurs manquent (PC local)
    if not cid or not csecret:
        try:
            import config_piste
            cid = cid or getattr(config_piste, "PISTE_CLIENT_ID", None)
            csecret = csecret or getattr(config_piste, "PISTE_CLIENT_SECRET", None)
        except ImportError:
            pass

    return {
        "PISTE_CLIENT_ID": cid,
        "PISTE_CLIENT_SECRET": csecret,
        "GMAIL_UTILISATEUR": gmail_user,
        "GMAIL_MOT_DE_PASSE": gmail_pass,
        "MAIL_DESTINATAIRE": mail_dest,
    }

_ids = _depuis_env_ou_config()

PISTE_CLIENT_ID     = _ids["PISTE_CLIENT_ID"]
PISTE_CLIENT_SECRET = _ids["PISTE_CLIENT_SECRET"]
GMAIL_UTILISATEUR   = _ids["GMAIL_UTILISATEUR"]
GMAIL_MOT_DE_PASSE  = _ids["GMAIL_MOT_DE_PASSE"]
MAIL_DESTINATAIRE   = _ids["MAIL_DESTINATAIRE"]
