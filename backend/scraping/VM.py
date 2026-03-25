# VM.py

import os
import csv
from datetime import datetime, timezone
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from supabase import create_client

# Charger .env depuis la racine backend_api
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(REPO_ROOT, ".env"))

PAGE_URL = "https://fichierdirect.declaration.urssaf.fr/TablesReference.htm"


def get_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL et SUPABASE_SERVICE_KEY (ou SUPABASE_KEY) requis.")
    return create_client(url, key)


def iso_now():
    return datetime.now(timezone.utc).isoformat()


def upsert_payroll_config(config_key: str, config_data: dict | list, source_links: list[str] | None = None):
    """Insère ou met à jour une entrée payroll_config (une seule active par config_key, company_id NULL)."""
    supabase = get_supabase()
    source_links = source_links or [PAGE_URL]
    try:
        r = (
            supabase.table("payroll_config")
            .select("id, version, config_data")
            .eq("config_key", config_key)
            .is_("company_id", "null")
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        row = (r.data or [None])[0]
    except Exception as e:
        print(f"❌ Lecture config existante: {e}")
        raise

    new_row = {
        "config_key": config_key,
        "config_data": config_data,
        "version": 1 if not row else row["version"] + 1,
        "is_active": True,
        "comment": f"Mise à jour VM: {config_key}",
        "last_checked_at": iso_now(),
        "source_links": source_links,
        "company_id": None,
    }

    if row is None:
        supabase.table("payroll_config").insert(new_row).execute()
        print(f"✅ {config_key}: v1 créée dans payroll_config.")
        return

    if row.get("config_data") == config_data:
        supabase.table("payroll_config").update({
            "last_checked_at": iso_now(),
            "source_links": source_links,
        }).eq("id", row["id"]).execute()
        print(f"✅ {config_key}: inchangé, last_checked_at mis à jour.")
        return

    supabase.table("payroll_config").update({"is_active": False}).eq("id", row["id"]).execute()
    supabase.table("payroll_config").insert(new_row).execute()
    print(f"✅ {config_key}: v{new_row['version']} créée dans payroll_config.")


def download_file(url, folder, headers):
    """
    Télécharge un fichier depuis une URL et le sauvegarde dans le dossier spécifié.
    Retourne le chemin du fichier téléchargé en cas de succès, sinon None.
    """
    try:
        local_filename = os.path.basename(url.split('?')[0])
        path_to_save = os.path.join(folder, local_filename)
        
        print(f"Téléchargement de : {url}")
        # Utilise les en-têtes (headers) pour la requête de téléchargement aussi
        with requests.get(url, stream=True, headers=headers) as r:
            r.raise_for_status()
            with open(path_to_save, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"-> Fichier brut sauvegardé sous : {path_to_save}")
        return path_to_save
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur lors du téléchargement de {url}: {e}\n")
        return None

def convert_csv_to_data(csv_path):
    """Convertit un CSV (point-virgule) en liste de dicts."""
    print(f"Conversion de '{os.path.basename(csv_path)}'...")
    records = []
    with open(csv_path, mode='r', encoding='latin-1', newline='') as f:
        for row in csv.DictReader(f, delimiter=';'):
            records.append(row)
    print(f"✅ {len(records)} enregistrements.")
    return records


def convert_xlsx_to_data(xlsx_path):
    """Convertit un XLSX en liste de dicts."""
    print(f"Conversion de '{os.path.basename(xlsx_path)}'...")
    df = pd.read_excel(xlsx_path)
    data = df.to_dict(orient="records")
    # Normaliser pour JSON (NaN -> None)
    for row in data:
        for k, v in list(row.items()):
            if pd.isna(v):
                row[k] = None
    print(f"✅ {len(data)} enregistrements.")
    return data

def main():
    """
    Télécharge les fichiers URSSAF (transport, VM), les convertit en JSON et pousse dans Supabase (payroll_config).
    """
    DOWNLOAD_FOLDER = "fichiers_urssaf"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
    }

    if not os.path.exists(DOWNLOAD_FOLDER):
        os.makedirs(DOWNLOAD_FOLDER)
        print(f"Dossier '{DOWNLOAD_FOLDER}' créé.")

    print(f"\nScraping de la page : {PAGE_URL}")
    try:
        response = requests.get(PAGE_URL, headers=HEADERS)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Impossible d'accéder à la page. Erreur : {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    files_to_find = {
        'url_codcoms': ('Table des taux transport (.csv)', 'taux_transport'),
        'url_vmrr': ('Table des taux du Versement Mobilité (.xlsx)', 'taux_vmrr'),
    }

    for html_id, (description, config_key) in files_to_find.items():
        print(f"--- {description} ---")
        link_tag = soup.find('a', id=html_id)
        if not link_tag or not link_tag.has_attr('href'):
            print(f"❌ Lien '{html_id}' introuvable.\n")
            continue

        absolute_url = urljoin(PAGE_URL, link_tag['href'])
        downloaded_file_path = download_file(absolute_url, DOWNLOAD_FOLDER, HEADERS)
        if not downloaded_file_path:
            continue

        if downloaded_file_path.lower().endswith('.csv'):
            data = convert_csv_to_data(downloaded_file_path)
        elif downloaded_file_path.lower().endswith('.xlsx'):
            data = convert_xlsx_to_data(downloaded_file_path)
        else:
            print(f"❌ Format non géré: {downloaded_file_path}\n")
            continue

        try:
            upsert_payroll_config(config_key, data, source_links=[PAGE_URL, absolute_url])
        except Exception as e:
            print(f"❌ Erreur Supabase pour {config_key}: {e}\n")

if __name__ == "__main__":
    main()