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
OPEN_DATA_CSV_URL = (
    "https://open.urssaf.fr/api/explore/v2.1/catalog/datasets/table_taux_vmrr/exports/csv"
)
OPEN_DATA_PAGE_URL = "https://open.urssaf.fr/explore/dataset/table_taux_vmrr/"
FICHIERDIRECT_PROBE_TIMEOUT = 8
FICHIERDIRECT_DOWNLOAD_TIMEOUT = 20
FICHIERDIRECT_PAGE_TIMEOUT = 20


def _today_yyyymmdd() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _direct_vmrr_urls() -> list[str]:
    year = datetime.now(timezone.utc).year
    return [
        f"https://fichierdirect.declaration.urssaf.fr/static/tauxVMRR-0101{year}.xlsx",
        "https://fichierdirect.declaration.urssaf.fr/static/tauxVMRR-01012026.xlsx",
    ]


def _pct_to_decimal(value: object) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        raw = float(str(value).replace(",", "."))
    except ValueError:
        return None
    if abs(raw) > 1:
        return raw / 100.0
    if raw > 0.05:
        return raw / 100.0
    return raw


def _normalize_open_data_row(row: dict[str, object]) -> dict[str, object]:
    taux_vm = _pct_to_decimal(row.get("taux_vm"))
    taux_vma = _pct_to_decimal(row.get("taux_vma")) or 0.0
    taux_vmr = _pct_to_decimal(row.get("taux_vmr")) or 0.0
    total = (taux_vm or 0.0) + taux_vma + taux_vmr
    nom = str(row.get("nom_commune") or "").strip()
    return {
        "code_commune": row.get("code_commune"),
        "nom_commune": nom,
        "commune": nom,
        "region": row.get("region"),
        "date_debut": row.get("date_debut"),
        "date_fin": row.get("date_fin"),
        "taux_vm": total if total > 0 else taux_vm,
        "taux": total if total > 0 else taux_vm,
    }


def _row_active(row: dict[str, object], today: str) -> bool:
    debut = str(row.get("date_debut") or "").strip()
    fin = str(row.get("date_fin") or "").strip()
    if debut and debut > today:
        return False
    if fin and fin < today:
        return False
    return True


def _select_current_open_data_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    today = _today_yyyymmdd()
    active = [row for row in rows if _row_active(row, today)]
    by_commune: dict[str, dict[str, object]] = {}
    for row in active:
        code = str(row.get("code_commune") or row.get("nom_commune") or "").strip()
        if not code:
            continue
        previous = by_commune.get(code)
        if not previous or str(row.get("date_debut") or "") >= str(
            previous.get("date_debut") or ""
        ):
            by_commune[code] = row
    return [_normalize_open_data_row(row) for row in by_commune.values()]


def fetch_vmrr_from_open_data() -> list[dict] | None:
    """Repli Open Data URSSAF si fichierdirect est inaccessible."""
    print(f"Repli Open Data URSSAF : {OPEN_DATA_CSV_URL}")
    try:
        response = requests.get(OPEN_DATA_CSV_URL, headers=HEADERS, timeout=120)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        print(f"❌ Open Data URSSAF inaccessible : {exc}")
        return None

    raw_rows: list[dict[str, object]] = []
    text = response.content.decode("utf-8-sig", errors="replace")
    for row in csv.DictReader(text.splitlines(), delimiter=";"):
        raw_rows.append(dict(row))

    data = _select_current_open_data_rows(raw_rows)
    if len(data) < 100:
        print(f"❌ Open Data URSSAF : seulement {len(data)} communes actives.")
        return None

    print(f"✅ {len(data)} communes actives via Open Data URSSAF.")
    return data


def _try_download_vmrr_xlsx(url: str, download_folder: str) -> list[dict] | None:
    downloaded_file_path = download_file(url, download_folder, HEADERS)
    if not downloaded_file_path:
        return None
    if not downloaded_file_path.lower().endswith(".xlsx"):
        print(f"❌ Format VMRR non géré: {downloaded_file_path}")
        return None
    data = convert_xlsx_to_data(downloaded_file_path)
    if not data:
        return None
    return data


def _scrape_vmrr_from_reference_page(
    download_folder: str,
) -> tuple[list[dict] | None, list[str]]:
    print(f"Scraping VMRR : {PAGE_URL}")
    last_error: Exception | None = None
    response = None
    for attempt in range(1, 3):
        try:
            response = requests.get(
                PAGE_URL,
                headers=HEADERS,
                timeout=FICHIERDIRECT_PAGE_TIMEOUT,
            )
            response.raise_for_status()
            break
        except requests.exceptions.RequestException as exc:
            last_error = exc
            if attempt < 2:
                print(f"Tentative {attempt}/2 échouée, nouvel essai… ({exc})")
            continue
    else:
        print(f"Impossible d'accéder à la page URSSAF. Erreur : {last_error}")
        return None, []

    soup = BeautifulSoup(response.text, "html.parser")
    link_tag = soup.find("a", id="url_vmrr")
    if not link_tag or not link_tag.has_attr("href"):
        print("❌ Lien 'url_vmrr' introuvable sur la page URSSAF.")
        return None, []

    absolute_url = urljoin(PAGE_URL, link_tag["href"])
    data = _try_download_vmrr_xlsx(absolute_url, download_folder)
    if not data:
        return None, []
    return data, [PAGE_URL, absolute_url]


def get_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL et SUPABASE_SERVICE_KEY (ou SUPABASE_KEY) requis."
        )
    return create_client(url, key)


def iso_now():
    return datetime.now(timezone.utc).isoformat()


def upsert_payroll_config(
    config_key: str, config_data: dict | list, source_links: list[str] | None = None
):
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
        supabase.table("payroll_config").update(
            {
                "last_checked_at": iso_now(),
                "source_links": source_links,
            }
        ).eq("id", row["id"]).execute()
        print(f"✅ {config_key}: inchangé, last_checked_at mis à jour.")
        return

    supabase.table("payroll_config").update({"is_active": False}).eq(
        "id", row["id"]
    ).execute()
    supabase.table("payroll_config").insert(new_row).execute()
    print(f"✅ {config_key}: v{new_row['version']} créée dans payroll_config.")


def download_file(url, folder, headers, timeout=FICHIERDIRECT_DOWNLOAD_TIMEOUT):
    """
    Télécharge un fichier depuis une URL et le sauvegarde dans le dossier spécifié.
    Retourne le chemin du fichier téléchargé en cas de succès, sinon None.
    """
    try:
        local_filename = os.path.basename(url.split("?")[0])
        path_to_save = os.path.join(folder, local_filename)

        print(f"Téléchargement de : {url}")
        with requests.get(url, stream=True, headers=headers, timeout=timeout) as r:
            r.raise_for_status()
            with open(path_to_save, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"-> Fichier brut sauvegardé sous : {path_to_save}")
        return path_to_save
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur lors du téléchargement de {url}: {e}\n")
        return None


def _fichierdirect_reachable() -> bool:
    probe_url = _direct_vmrr_urls()[0]
    try:
        response = requests.head(
            probe_url,
            headers=HEADERS,
            timeout=FICHIERDIRECT_PROBE_TIMEOUT,
            allow_redirects=True,
        )
        return response.status_code < 400
    except requests.exceptions.RequestException:
        try:
            response = requests.get(
                PAGE_URL,
                headers=HEADERS,
                timeout=FICHIERDIRECT_PROBE_TIMEOUT,
            )
            return response.status_code < 400
        except requests.exceptions.RequestException:
            return False


def convert_csv_to_data(csv_path):
    """Convertit un CSV (point-virgule) en liste de dicts."""
    print(f"Conversion de '{os.path.basename(csv_path)}'...")
    records = []
    with open(csv_path, mode="r", encoding="latin-1", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
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


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
}
DOWNLOAD_FOLDER = "fichiers_urssaf"


def scrape_vmrr_from_urssaf(
    download_folder: str = DOWNLOAD_FOLDER,
) -> tuple[list[dict] | None, list[str]]:
    """
    Télécharge et convertit la table nationale VMRR (Versement mobilité).
    Retourne (données, source_links) ou (None, []) en cas d'échec.
    """
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)

    if _fichierdirect_reachable():
        for direct_url in _direct_vmrr_urls():
            print(f"Tentative XLSX direct : {direct_url}")
            try:
                data = _try_download_vmrr_xlsx(direct_url, download_folder)
            except Exception as exc:
                print(f"❌ Échec XLSX direct ({direct_url}) : {exc}")
                data = None
            if data:
                return data, [direct_url]

        data, links = _scrape_vmrr_from_reference_page(download_folder)
        if data:
            return data, links
    else:
        print(
            "fichierdirect.declaration.urssaf.fr inaccessible — "
            "repli Open Data URSSAF."
        )

    data = fetch_vmrr_from_open_data()
    if data:
        return data, [OPEN_DATA_PAGE_URL, OPEN_DATA_CSV_URL]
    return None, []


def main():
    """
    Télécharge les fichiers URSSAF (transport, VM), les convertit en JSON et pousse dans Supabase (payroll_config).
    """
    if not os.path.exists(DOWNLOAD_FOLDER):
        os.makedirs(DOWNLOAD_FOLDER)
        print(f"Dossier '{DOWNLOAD_FOLDER}' créé.")

    print(f"\nScraping de la page : {PAGE_URL}")
    try:
        response = requests.get(PAGE_URL, headers=HEADERS, timeout=60)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Impossible d'accéder à la page. Erreur : {e}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    files_to_find = {
        "url_codcoms": ("Table des taux transport (.csv)", "taux_transport"),
        "url_vmrr": ("Table des taux du Versement Mobilité (.xlsx)", "taux_vmrr"),
    }

    for html_id, (description, config_key) in files_to_find.items():
        print(f"--- {description} ---")
        link_tag = soup.find("a", id=html_id)
        if not link_tag or not link_tag.has_attr("href"):
            print(f"❌ Lien '{html_id}' introuvable.\n")
            continue

        absolute_url = urljoin(PAGE_URL, link_tag["href"])
        downloaded_file_path = download_file(absolute_url, DOWNLOAD_FOLDER, HEADERS)
        if not downloaded_file_path:
            continue

        if downloaded_file_path.lower().endswith(".csv"):
            data = convert_csv_to_data(downloaded_file_path)
        elif downloaded_file_path.lower().endswith(".xlsx"):
            data = convert_xlsx_to_data(downloaded_file_path)
        else:
            print(f"❌ Format non géré: {downloaded_file_path}\n")
            continue

        try:
            upsert_payroll_config(
                config_key, data, source_links=[PAGE_URL, absolute_url]
            )
        except Exception as e:
            print(f"❌ Erreur Supabase pour {config_key}: {e}\n")


if __name__ == "__main__":
    main()
