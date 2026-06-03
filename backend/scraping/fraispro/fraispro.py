# scripts/fraispro/fraispro.py

import json
import re
import sys
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

URL_URSSAF = "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/frais-professionnels.html"

# --- FONCTIONS UTILITAIRES ---


def iso_now() -> str:
    """Retourne la date et l'heure actuelles au format ISO 8601 UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_robust_request(url, retries=3, delay=5):
    """Tente de se connecter à une URL plusieurs fois en cas d'échec."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept-Language": "fr-FR,fr;q=0.9",
    }
    for i in range(retries):
        try:
            print(
                f"Tentative de connexion n°{i + 1}/{retries} à {url}...",
                file=sys.stderr,
            )
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            print("Connexion réussie.", file=sys.stderr)
            return response
        except requests.exceptions.RequestException as e:
            print(f"Échec de la tentative n°{i + 1}: {e}", file=sys.stderr)
            if i < retries - 1:
                print(f"Nouvelle tentative dans {delay} secondes...", file=sys.stderr)
                time.sleep(delay)
    return None


def parse_valeur_numerique(text):
    """Nettoie et convertit un texte en nombre (float)."""
    if not text:
        return 0.0
    cleaned = (
        text.replace("€", "")
        .replace("\xa0", "")
        .replace("\u202f", "")
        .replace(" ", "")
        .replace(",", ".")
    )
    match = re.search(r"([0-9]+\.?[0-9]*)", cleaned)
    return float(match.group(1)) if match else 0.0


# --- FONCTIONS DE SCRAPING DÉDIÉES PAR SECTION ---


def scrape_repas(soup) -> dict:
    """Scrape la section des indemnités de repas."""
    print("Scraping de la section 'Repas'...", file=sys.stderr)
    header = soup.find("h2", id="ancre-repas")
    if not header:
        return {}
    table = header.find_next("table", class_="d-none d-md-table")
    if not table or not table.find("tbody"):
        return {}
    data = {}
    for row in table.find("tbody").find_all("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) == 2:
            situation = cells[0].get_text(strip=True)
            montant = parse_valeur_numerique(cells[1].get_text())
            if "sur le lieu de travail" in situation:
                data["sur_lieu_travail"] = montant
            elif "non contraint" in situation:
                data["hors_locaux_sans_restaurant"] = montant
            elif "au restaurant" in situation:
                data["hors_locaux_avec_restaurant"] = montant
    return data


def scrape_petit_deplacement(soup) -> list:
    """Scrape la section des indemnités de petit déplacement."""
    print("Scraping de la section 'Petit déplacement'...", file=sys.stderr)
    header = soup.find("h2", id="ancre-petit-deplacement")
    if not header:
        return []
    table = header.find_next("table", class_="d-none d-md-table")
    if not table or not table.find("tbody"):
        return []
    data = []
    for row in table.find("tbody").find_all("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) == 2:
            distance_str = cells[0].get_text(strip=True)
            montant = parse_valeur_numerique(cells[1].get_text())
            distances = re.findall(r"(\d+)", distance_str)
            if len(distances) == 2:
                data.append(
                    {
                        "km_min": int(distances[0]),
                        "km_max": int(distances[1]),
                        "montant": montant,
                    }
                )
    return data


def scrape_grand_deplacement(soup) -> dict:
    """Scrape la section des indemnités de grand déplacement."""
    print("Scraping de la section 'Grand déplacement'...", file=sys.stderr)
    header = soup.find("h2", id="ancre-grand-deplacement")
    if not header:
        return {}
    data = {"metropole": [], "outre_mer_groupe1": [], "outre_mer_groupe2": []}
    metropole_header = header.find_next(
        "h3", string=re.compile("Déplacements en métropole")
    )
    if metropole_header:
        table = metropole_header.find_next("table", class_="d-none d-md-table")
        if table and table.find("tbody"):
            for row in table.find("tbody").find_all("tr"):
                cells = row.find_all(["th", "td"])
                if len(cells) == 4:
                    data["metropole"].append(
                        {
                            "periode_sejour": cells[0].get_text(strip=True),
                            "repas": parse_valeur_numerique(cells[1].get_text()),
                            "logement_paris_banlieue": parse_valeur_numerique(
                                cells[2].get_text()
                            ),
                            "logement_province": parse_valeur_numerique(
                                cells[3].get_text()
                            ),
                        }
                    )

    om_patterns = (
        ("outre_mer_groupe1", r"Martinique, Guadeloupe"),
        ("outre_mer_groupe2", r"Nouvelle-Calédonie"),
    )
    for key, pattern in om_patterns:
        om_header = header.find_next("h4", string=re.compile(pattern))
        if not om_header:
            continue
        table = om_header.find_next("table", class_="d-none d-md-table")
        if not table or not table.find("tbody"):
            continue
        for row in table.find("tbody").find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) == 3:
                data[key].append(
                    {
                        "periode_sejour": cells[0].get_text(strip=True),
                        "hebergement": parse_valeur_numerique(cells[1].get_text()),
                        "repas": parse_valeur_numerique(cells[2].get_text()),
                    }
                )
    return data


def scrape_mutation(soup) -> dict:
    """Scrape la section des frais de mutation professionnelle."""
    print("Scraping de la section 'Mutation professionnelle'...", file=sys.stderr)
    header = soup.find("h2", id="ancre-mutation-professionnelle")
    if not header:
        return {}

    data = {"hebergement_provisoire": {}, "hebergement_definitif": {}}
    tabs_container = header.find_next("div", class_="tabs_custom_2")
    if not tabs_container:
        return data

    buttons = tabs_container.find("div", role="tablist").find_all("button")
    for button in buttons:
        button_text = button.get_text(strip=True)
        panel_id = button.get("aria-controls")
        if not panel_id:
            continue

        panel = tabs_container.find("div", id=panel_id)
        if not panel:
            continue

        table = panel.find("table", class_="d-none d-md-table")
        if not table or not table.find("tbody"):
            continue

        if "Hébergement provisoire" in button_text:
            row = table.find("tr", class_="table_custom__tbody")
            if row and len(row.find_all("td")) == 2:
                data["hebergement_provisoire"]["montant_par_jour"] = (
                    parse_valeur_numerique(row.find_all("td")[1].get_text())
                )

        elif "Hébergement définitif" in button_text:
            for row in table.find("tbody").find_all("tr"):
                cells = row.find_all("td")
                if len(cells) == 2:
                    libelle = cells[0].get_text(strip=True)
                    montant = parse_valeur_numerique(cells[1].get_text())
                    if "installation dans le nouveau logement" in libelle:
                        data["hebergement_definitif"]["frais_installation"] = montant
                    elif "Majoration" in libelle:
                        data["hebergement_definitif"]["majoration_par_enfant"] = montant
                    elif "maximum" in libelle:
                        data["hebergement_definitif"]["plafond_total"] = montant
    return data


def scrape_mobilite_durable(soup) -> dict:
    """Scrape la section du forfait mobilités durables."""
    print("Scraping de la section 'Mobilité durable'...", file=sys.stderr)
    header = soup.find("h2", id="ancre-forfait-mobilites-durables")
    if not header:
        return {}

    data = {"employeurs_prives": {}, "employeurs_publics": []}
    tabs_container = header.find_next("div", class_="tabs_custom_2")
    if not tabs_container:
        return data

    buttons = tabs_container.find("div", role="tablist").find_all("button")
    for button in buttons:
        button_text = button.get_text(strip=True)
        panel_id = button.get("aria-controls")
        if not panel_id:
            continue

        panel = tabs_container.find("div", id=panel_id)
        if not panel:
            continue

        table = panel.find("table", class_="d-none d-md-table")
        if not table or not table.find("tbody"):
            continue

        if "Employeurs privés" in button_text:
            for row in table.find("tbody").find_all("tr"):
                cells = row.find_all("td")
                if len(cells) == 2:
                    situation = cells[0].get_text(strip=True)
                    montant_str = cells[1].get_text()
                    if "FMD" == situation:
                        data["employeurs_prives"]["limite_base"] = (
                            parse_valeur_numerique(montant_str)
                        )
                    elif "transports publics" in situation:
                        data["employeurs_prives"]["limite_cumul_transport_public"] = (
                            parse_valeur_numerique(montant_str)
                        )
                    elif "carburant" in situation:
                        montants = re.findall(r"([0-9,]+)", montant_str)
                        if len(montants) == 2:
                            data["employeurs_prives"][
                                "limite_cumul_carburant_total"
                            ] = parse_valeur_numerique(montants[0])
                            data["employeurs_prives"][
                                "limite_cumul_carburant_part_carburant"
                            ] = parse_valeur_numerique(montants[1])

        elif "Employeurs publics" in button_text:
            for row in table.find("tbody").find_all("tr"):
                cells = row.find_all("td")
                if len(cells) == 2:
                    jours = cells[0].get_text(strip=True)
                    montant = parse_valeur_numerique(cells[1].get_text())
                    data["employeurs_publics"].append(
                        {"jours_utilises": jours, "montant_annuel": montant}
                    )
    return data


def scrape_teletravail(soup) -> dict:
    """Scrape la section complète des indemnités de télétravail."""
    print("Scraping de la section 'Télétravail'...", file=sys.stderr)
    header = soup.find("h2", id="ancre-teletravail-utilisation-de-mater")
    if not header:
        return {}

    data = {
        "indemnite_sans_accord": {},
        "indemnite_avec_accord": {},
        "materiel_informatique_perso": {},
    }

    indemnite_header = header.find_next(
        "h3", string=re.compile("Indemnité forfaitaire de télétravail")
    )
    if indemnite_header:
        tabs_container = indemnite_header.find_next("div", class_="tabs_custom_2")
        if tabs_container:
            buttons = tabs_container.find("div", role="tablist").find_all("button")
            for button in buttons:
                button_text = button.get_text(strip=True)
                panel_id = button.get("aria-controls")
                if not panel_id:
                    continue

                panel = tabs_container.find("div", id=panel_id)
                if not panel:
                    continue

                target_dict = None
                if "non prévue" in button_text:
                    target_dict = data["indemnite_sans_accord"]
                elif "prévue par une convention" in button_text:
                    target_dict = data["indemnite_avec_accord"]

                if target_dict is not None:
                    table = panel.find("table", class_="d-none d-md-table")
                    if table and table.find("tbody"):
                        for row in table.find("tbody").find_all("tr"):
                            cells = row.find_all("td")
                            if len(cells) == 2:
                                modalite = cells[0].get_text(strip=True)
                                valeurs_str = cells[1].get_text()
                                if "Par jour de télétravail" in modalite:
                                    matches = re.findall(r"([0-9,]+)", valeurs_str)
                                    if len(matches) == 2:
                                        target_dict["par_jour"] = (
                                            parse_valeur_numerique(matches[0])
                                        )
                                        target_dict["limite_mensuelle"] = (
                                            parse_valeur_numerique(matches[1])
                                        )
                                elif "Par mois" in modalite:
                                    target_dict["par_mois_pour_1_jour_semaine"] = (
                                        parse_valeur_numerique(valeurs_str)
                                    )

    materiel_header = soup.find(
        "h3",
        string=re.compile(
            "Indemnité forfaitaire liée à l’utilisation de matériels informatiques"
        ),
    )
    if materiel_header:
        table = materiel_header.find_next("table", class_="d-none d-md-table")
        if table and table.find("tbody"):
            row = table.find("tr", class_="table_custom__tbody")
            if row and len(row.find_all("td")) == 2:
                data["materiel_informatique_perso"]["montant_mensuel"] = (
                    parse_valeur_numerique(row.find_all("td")[1].get_text())
                )

    return data


def fetch_soup(url: str = URL_URSSAF):
    """Télécharge et parse la page URSSAF frais professionnels."""
    response = make_robust_request(url)
    if not response:
        raise RuntimeError(
            "Impossible de récupérer la page URSSAF frais professionnels."
        )
    return BeautifulSoup(response.text, "html.parser")


def scrape_all_sections(soup) -> dict:
    """Extrait toutes les sections (primary)."""
    return {
        "repas": scrape_repas(soup),
        "petit_deplacement": scrape_petit_deplacement(soup),
        "grand_deplacement": scrape_grand_deplacement(soup),
        "mutation_professionnelle": scrape_mutation(soup),
        "mobilite_durable": scrape_mobilite_durable(soup),
        "teletravail": scrape_teletravail(soup),
    }


def section_text(soup, anchor_id: str) -> str:
    """Texte des tableaux et titres d'une section (contexte Sonar)."""
    header = soup.find("h2", id=anchor_id)
    if not header:
        raise ValueError(f"Section URSSAF introuvable : {anchor_id}")
    return _text_from_header_until_next_h2(header)


def _text_from_header_until_next_h2(header) -> str:
    lines: list[str] = [header.get_text(" ", strip=True)]
    for tag in header.find_all_next():
        if tag.name == "h2" and tag is not header:
            break
        if tag.name == "table":
            for tr in tag.find_all("tr"):
                cells = [
                    c.get_text(" ", strip=True)
                    for c in tr.find_all(["th", "td"])
                ]
                if cells:
                    lines.append(" | ".join(cells))
        elif tag.name in ("h3", "h4"):
            text = tag.get_text(" ", strip=True)
            if text:
                lines.append(text)
    return "\n".join(line for line in lines if line)


def subsection_text(soup, start_pattern: str, stop_pattern: str | None = None) -> str:
    """Texte ciblé entre deux titres h3/h4 (sous-section grand déplacement)."""
    header = soup.find("h2", id="ancre-grand-deplacement")
    if not header:
        raise ValueError("Section grand déplacement introuvable.")
    start = header.find_next(
        ["h3", "h4"], string=re.compile(start_pattern, re.I)
    )
    if not start:
        raise ValueError(f"Sous-section introuvable : {start_pattern}")
    stop = (
        header.find_next(["h3", "h4"], string=re.compile(stop_pattern, re.I))
        if stop_pattern
        else header.find_next("h2")
    )
    lines = [start.get_text(" ", strip=True)]
    for tag in start.find_all_next():
        if tag is stop:
            break
        if tag.name == "table":
            for tr in tag.find_all("tr"):
                cells = [
                    c.get_text(" ", strip=True)
                    for c in tr.find_all(["th", "td"])
                ]
                if cells:
                    lines.append(" | ".join(cells))
    return "\n".join(line for line in lines if line)


# --- FONCTION PRINCIPALE ---


def main():
    """Orchestre le scraping et génère la sortie JSON pour l'orchestrateur."""
    try:
        soup = fetch_soup(URL_URSSAF)
    except RuntimeError as e:
        print(f"ERREUR CRITIQUE: {e}", file=sys.stderr)
        sys.exit(1)

    print("\nDébut de l'extraction des données...", file=sys.stderr)
    sections_data = scrape_all_sections(soup)
    print("Extraction des données terminée.", file=sys.stderr)

    # Assemblage du payload final conforme à la structure de l'orchestrateur
    payload = {
        "id": "frais_pro",
        "type": "frais_professionnels",
        "libelle": "Frais professionnels (URSSAF)",
        "sections": sections_data,
        "meta": {
            "source": [
                {
                    "url": URL_URSSAF,
                    "label": "URSSAF — Frais professionnels",
                    "date_doc": "",
                }
            ],
            "scraped_at": iso_now(),
            "generator": "scripts/fraispro/fraispro.py",
            "method": "primary",
        },
    }

    # Impression du JSON final sur la sortie standard
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
