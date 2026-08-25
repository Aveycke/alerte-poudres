#!/usr/bin/env python3
# Surveille trois poudres sur armurerie.lu (Armurerie Freylinger).
# Se termine volontairement en erreur quand une poudre revient en stock :
# c'est ce qui declenche l'e-mail "Run failed" envoye par GitHub.

import html
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

PRODUITS = [
    ("Vihtavuori N150 - 1 kg",   "https://armurerie.lu/9827-vihtavuori-n150.html"),
    ("Vihtavuori N150 - 3,5 kg", "https://armurerie.lu/9828-vihtavuori-n150-35kg.html"),
    ("Vihtavuori N555 - 1 kg",   "https://armurerie.lu/9843-vihtavuori-n555.html"),
]

FICHIER_ETAT = Path(__file__).with_name("etat.json")
NAVIGATEUR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def charger(url):
    """Telecharge une page, avec trois tentatives espacees."""
    for essai in range(3):
        try:
            requete = Request(url, headers={"User-Agent": NAVIGATEUR})
            with urlopen(requete, timeout=30) as reponse:
                return reponse.read().decode("utf-8", errors="replace")
        except Exception:
            if essai == 2:
                raise
            time.sleep(5)


def analyser(page):
    """Retourne 'disponible', 'rupture' ou 'inconnu'."""
    texte = re.sub(r"<(script|style).*?</\1>", " ", page, flags=re.S | re.I)
    texte = html.unescape(re.sub(r"<[^>]+>", " ", texte))
    texte = re.sub(r"\s+", " ", texte).lower()
    # Le bloc "autres produits dans la meme categorie" affiche les ruptures
    # d'AUTRES poudres : on ignore donc tout ce qui suit ce titre.
    fin = texte.find("autres produits dans la m")
    if fin == -1:
        return "inconnu"
    return "rupture" if "rupture de stock" in texte[:fin] else "disponible"


def main():
    try:
        etat = json.loads(FICHIER_ETAT.read_text(encoding="utf-8"))
    except Exception:
        etat = {}

    aujourdhui = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    alertes = []
    soucis = []

    for nom, url in PRODUITS:
        try:
            statut = analyser(charger(url))
        except Exception as erreur:
            statut = "inconnu"
            print(f"   probleme de chargement : {erreur}")

        precedent = etat.get(url, "-")
        print(f"{nom:26} {precedent:>11}  ->  {statut}")

        if statut == "disponible" and precedent != "disponible":
            alertes.append(f"{nom}\n{url}")
        if statut == "inconnu":
            soucis.append(nom)
        else:
            etat[url] = statut
        time.sleep(2)

    # Une modification par jour au minimum : garde le depot GitHub actif,
    # sinon GitHub suspend les taches planifiees apres 60 jours d'inactivite.
    etat["derniere_verification"] = aujourdhui

    if soucis and etat.get("dernier_souci") != aujourdhui:
        etat["dernier_souci"] = aujourdhui
        signaler_souci = True
    else:
        signaler_souci = False

    FICHIER_ETAT.write_text(json.dumps(etat, indent=2) + "\n", encoding="utf-8")

    if alertes:
        print("\n" + "=" * 55)
        print("POUDRE DISPONIBLE")
        print("=" * 55)
        for ligne in alertes:
            print(ligne)
        print("\nRetrait en magasin uniquement, avec vos documents :")
        print("26 rue Geespelt, Livange  -  tel. +352 52 00 15")
        sys.exit(1)

    if signaler_souci:
        print("\nPages illisibles : " + ", ".join(soucis))
        print("Le site a peut-etre change. A verifier a la main.")
        sys.exit(2)


main()
