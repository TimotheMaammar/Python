#!/usr/bin/env python3
"""
Récupération des données de population communale - API Melodi INSEE
Dataset : DS_RP_POPULATION_PRINC (Recensement de la Population)

Endpoint : https://api.insee.fr/melodi/data/DS_RP_POPULATION_PRINC
Pas d'authentification requise (données ouvertes).

Dimensions :
  GEO         : Code géographique (format COM-CODEINSEE)
  SEX         : _T=total  M=hommes  F=femmes
  AGE         : _T=total  Y_LT15  Y15T24  Y25T39  Y40T54  Y55T64  Y65T79  Y_GE80
  TIME_PERIOD : Année du recensement (2011, 2016, 2022...)
  RP_MEASURE  : POP=population

Usage :
  # Une ou plusieurs communes
  python insee_population.py --communes 51454 75056 69123

  # Département complet (filtre côté client sur le préfixe du code commune)
  python insee_population.py --dept 51

  # Toutes les communes (attention : très volumineux)
  python insee_population.py --all

  # Par sexe + export JSON
  python insee_population.py --communes 51454 --sexe F --json
"""

import argparse
import csv
import json
import sys
import time
from collections import defaultdict
from typing import Optional

import requests

BASE_URL     = "https://api.insee.fr/melodi/data/DS_RP_POPULATION_PRINC"
GEO_API_URL  = "https://geo.api.gouv.fr"
MAX_PER_PAGE = 1000
RATE_LIMIT_DELAY = 1.0        # secondes entre pages
RETRY_DELAYS     = [5, 15, 30, 60]  # backoff sur 429 (4 tentatives)


# ---------------------------------------------------------------------------
# Résolution géographique
# ---------------------------------------------------------------------------

def get_communes_for_dept(dept: str) -> list:
    """
    Retourne la liste des codes INSEE des communes d'un département
    via l'API geo.api.gouv.fr.
    """
    url = f"{GEO_API_URL}/departements/{dept}/communes"
    resp = requests.get(url, params={"fields": "code", "format": "json",
                                     "geometry": "none"}, timeout=15)
    resp.raise_for_status()
    codes = [c["code"] for c in resp.json()]
    print(f"  Département {dept} : {len(codes)} communes")
    return codes


def get_all_dept_codes() -> list:
    """Retourne tous les codes département via l'API geo."""
    url = f"{GEO_API_URL}/departements"
    resp = requests.get(url, params={"fields": "code", "format": "json"}, timeout=15)
    resp.raise_for_status()
    return [d["code"] for d in resp.json()]


# ---------------------------------------------------------------------------
# Couche réseau
# ---------------------------------------------------------------------------

def build_params(
    codes_communes: Optional[list],
    sex: str,
    age: str,
    measure: str,
    page: int,
) -> list:
    """
    Construit la liste de tuples (clé, valeur) pour requests.
    Les params GEO répétés permettent le multi-communes.
    La pagination utilise page=N (pas offset).
    """
    params = [
        ("maxResult", MAX_PER_PAGE),
        ("SEX", sex),
        ("AGE", age),
        ("RP_MEASURE", measure),
        ("page", page),
    ]

    if codes_communes:
        for code in codes_communes:
            params.append(("GEO", f"COM-{code}"))

    return params


def fetch_page(session: requests.Session, params: list) -> dict:
    for attempt, wait in enumerate([0] + RETRY_DELAYS):
        if wait:
            print(f"  Rate limit, attente {wait}s...", flush=True)
            time.sleep(wait)
        resp = session.get(BASE_URL, params=params, timeout=30)
        if resp.status_code == 429:
            if attempt < len(RETRY_DELAYS):
                continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()  # epuise les tentatives


def fetch_observations(
    session: requests.Session,
    codes_communes: Optional[list] = None,
    dept: Optional[str] = None,
    sex: str = "_T",
    age: str = "_T",
    measure: str = "POP",
) -> Optional[list]:
    """
    Récupère toutes les observations avec pagination automatique (page=N).
    Retourne None si l'API rejette les paramètres (signal de fallback).
    """
    all_obs = []
    page = 1

    while True:
        params = build_params(codes_communes, sex, age, measure, page)

        print(f"  Page {page}...", end=" ", flush=True)

        try:
            data = fetch_page(session, params)
        except requests.HTTPError as e:
            status = e.response.status_code
            print(f"Erreur HTTP {status}")
            if status in (400, 404) and age == "_T":
                return None  # AGE=_T refusé : déclenche le fallback par tranche
            raise

        obs = data.get("observations", [])
        paging = data.get("paging", {})
        count = len(obs)
        print(f"{count} résultats")

        if not obs:
            break

        # Filtre département côté client si demandé sans liste de communes
        if dept and not codes_communes:
            obs = [o for o in obs if _extract_code(o).startswith(dept)]

        all_obs.extend(obs)

        # Arrêt si dernière page (champ isLast ou absence de next)
        if paging.get("isLast", False) or "next" not in paging:
            break

        page += 1
        time.sleep(RATE_LIMIT_DELAY)

    return all_obs


def _extract_code(observation: dict) -> str:
    """Extrait le code INSEE depuis GEO (format YYYY-COM-XXXXX ou COM-XXXXX)."""
    geo = observation.get("dimensions", {}).get("GEO", "")
    return geo.split("-COM-")[-1] if "-COM-" in geo else geo


# ---------------------------------------------------------------------------
# Agrégation
# ---------------------------------------------------------------------------

def aggregate(observations: list) -> dict:
    """
    Agrège par (code_commune, annee).
    Somme les tranches d'âge si le fallback par tranche a été utilisé.

    Retourne : {(code_commune, annee): population}
    """
    pop = defaultdict(float)

    for obs in observations:
        code = _extract_code(obs)
        year = obs.get("dimensions", {}).get("TIME_PERIOD", "")
        value = (
            obs.get("measures", {})
               .get("OBS_VALUE_NIVEAU", {})
               .get("value", 0)
        )
        if code and year:
            pop[(code, year)] += value

    return dict(pop)


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

def save_csv(pop_data: dict, path: str):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["code_commune", "annee", "population"])
        for (code, year), pop in sorted(pop_data.items()):
            writer.writerow([code, year, round(pop)])
    print(f"CSV enregistré : {path}")


def save_json(pop_data: dict, path: str):
    """
    Structure : { "51454": { "2011": 183113, "2016": 182100, "2022": 179992 }, ... }
    """
    nested = defaultdict(dict)
    for (code, year), pop in sorted(pop_data.items()):
        nested[code][year] = round(pop)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(nested), f, ensure_ascii=False, indent=2)
    print(f"JSON enregistré : {path}")


def print_summary(pop_data: dict):
    if not pop_data:
        print("Aucune donnée.")
        return

    years = sorted({y for _, y in pop_data})
    communes = sorted({c for c, _ in pop_data})

    print(f"\n{'='*52}")
    print(f"  Communes  : {len(communes)}")
    print(f"  Années    : {', '.join(years)}")
    print(f"  Lignes    : {len(pop_data)}")
    print(f"{'='*52}")

    if len(communes) <= 20:
        for commune in communes:
            print(f"\n  Commune {commune} :")
            for year in years:
                val = pop_data.get((commune, year))
                if val is not None:
                    print(f"    {year} : {round(val):>12,} habitants")


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Télécharge la population des communes françaises (API Melodi INSEE)",
    )

    geo_group = parser.add_mutually_exclusive_group(required=True)
    geo_group.add_argument(
        "--communes", nargs="+", metavar="CODE",
        help="Codes INSEE des communes (ex: 51454 75056 69123)",
    )
    geo_group.add_argument(
        "--dept", metavar="DEPT",
        help="Département (ex: 51) - filtre côté client",
    )
    geo_group.add_argument(
        "--all", action="store_true", dest="all_communes",
        help="Toutes les communes (très volumineux)",
    )

    parser.add_argument(
        "--sexe", default="_T", choices=["_T", "M", "F"],
        help="Sexe : _T=total (défaut), M=hommes, F=femmes",
    )
    parser.add_argument(
        "--output", default="population_communes.csv", metavar="FICHIER",
        help="Fichier CSV de sortie (défaut: population_communes.csv)",
    )
    parser.add_argument(
        "--json", action="store_true", dest="export_json",
        help="Exporte aussi en JSON (même chemin, extension .json)",
    )

    args = parser.parse_args()

    if args.all_communes:
        print("ATTENTION : téléchargement de toutes les communes (très long).")
        try:
            confirm = input("Continuer ? (o/N) : ").strip().lower()
        except EOFError:
            confirm = "n"
        if confirm != "o":
            sys.exit(0)

    # Résolution des codes communes AVANT les requêtes Melodi
    # -> filtre GEO côté serveur = beaucoup moins de pages
    print("\nRésolution des communes...")
    if args.communes:
        communes = args.communes
    elif args.dept:
        communes = get_communes_for_dept(args.dept)
    else:
        # --all : itérer par département pour éviter les 429
        print("  Récupération de la liste des départements...")
        depts = get_all_dept_codes()
        communes = []
        for dept_code in depts:
            communes.extend(get_communes_for_dept(dept_code))
        print(f"  Total : {len(communes)} communes")

    print(f"\nConnexion à l'API Melodi INSEE...")

    # On passe toujours les codes communes comme filtre GEO
    # Par lots de 500 si > 500 (URL trop longue sinon)
    BATCH = 50

    with requests.Session() as session:
        session.headers["Accept"] = "application/json"

        all_obs = []
        batches = [communes[i:i+BATCH] for i in range(0, len(communes), BATCH)]

        for b_idx, batch_codes in enumerate(batches):
            if len(batches) > 1:
                print(f"Lot {b_idx+1}/{len(batches)} ({len(batch_codes)} communes)...")

            # Tentative avec AGE=_T (total toutes tranches)
            obs = fetch_observations(session, codes_communes=batch_codes,
                                     dept=None, sex=args.sexe, age="_T")

            # Fallback : récupération tranche par tranche et sommation
            if obs is None:
                print("AGE=_T non disponible, récupération par tranche d'âge...")
                AGE_GROUPS = [
                    "Y_LT15", "Y15T24", "Y25T39", "Y40T54",
                    "Y55T64", "Y65T79", "Y_GE80",
                ]
                obs = []
                for age_group in AGE_GROUPS:
                    print(f"  Tranche {age_group} :")
                    batch_obs = fetch_observations(session, codes_communes=batch_codes,
                                                   dept=None, sex=args.sexe, age=age_group)
                    if batch_obs:
                        obs.extend(batch_obs)
                    time.sleep(RATE_LIMIT_DELAY)

            if obs:
                all_obs.extend(obs)

    if not all_obs:
        print("Aucune observation récupérée. Vérifiez les codes communes.")
        sys.exit(1)

    print(f"\nObservations brutes : {len(all_obs)}")
    pop_data = aggregate(all_obs)

    save_csv(pop_data, args.output)

    if args.export_json:
        json_path = args.output.rsplit(".", 1)[0] + ".json"
        save_json(pop_data, json_path)

    print_summary(pop_data)


if __name__ == "__main__":
    main()
