#!/usr/bin/env python3
"""
Copie les objets Storage de la production vers le projet de test.

Les objets ont deux faces : les fichiers stockés et les lignes storage.objects
en base. Les lignes arrivent avec le dump ; ce script apporte les fichiers, puis
compare les décomptes — copier l'une sans l'autre produit soit des liens morts,
soit des fichiers orphelins.

Variables requises :
  SUPABASE_PROD_URL, SUPABASE_PROD_SERVICE_KEY
  SUPABASE_TEST_URL, SUPABASE_TEST_SERVICE_KEY
"""

import os
import sys

import requests

PROD_URL = os.environ["SUPABASE_PROD_URL"].rstrip("/")
PROD_KEY = os.environ["SUPABASE_PROD_SERVICE_KEY"]
TEST_URL = os.environ["SUPABASE_TEST_URL"].rstrip("/")
TEST_KEY = os.environ["SUPABASE_TEST_SERVICE_KEY"]

TIMEOUT = 120
PAGE = 1000


def _headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}", "apikey": key}


def lister_buckets(base: str, key: str) -> list[dict]:
    r = requests.get(f"{base}/storage/v1/bucket", headers=_headers(key), timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def creer_bucket(base: str, key: str, bucket: dict) -> None:
    payload = {
        "id": bucket["id"],
        "name": bucket["name"],
        "public": bucket.get("public", False),
    }
    r = requests.post(
        f"{base}/storage/v1/bucket", headers=_headers(key), json=payload, timeout=TIMEOUT
    )
    # 409 = bucket déjà présent, cas normal d'une resynchro répétée.
    if r.status_code not in (200, 201, 409):
        r.raise_for_status()


def lister_objets(base: str, key: str, bucket_id: str, prefix: str = "") -> list[str]:
    """Liste récursivement les chemins d'objets d'un bucket."""
    chemins: list[str] = []
    offset = 0
    while True:
        r = requests.post(
            f"{base}/storage/v1/object/list/{bucket_id}",
            headers=_headers(key),
            json={"prefix": prefix, "limit": PAGE, "offset": offset},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        lot = r.json()
        if not lot:
            break
        for entree in lot:
            nom = entree.get("name")
            if not nom:
                continue
            chemin = f"{prefix}{nom}" if prefix else nom
            # Un dossier n'a pas de métadonnées d'objet : on descend dedans.
            if entree.get("id") is None:
                chemins.extend(lister_objets(base, key, bucket_id, f"{chemin}/"))
            else:
                chemins.append(chemin)
        if len(lot) < PAGE:
            break
        offset += len(lot)
    return chemins


def copier_objet(bucket_id: str, chemin: str) -> None:
    src = requests.get(
        f"{PROD_URL}/storage/v1/object/{bucket_id}/{chemin}",
        headers=_headers(PROD_KEY),
        timeout=TIMEOUT,
    )
    src.raise_for_status()
    dst = requests.post(
        f"{TEST_URL}/storage/v1/object/{bucket_id}/{chemin}",
        headers={
            **_headers(TEST_KEY),
            "Content-Type": src.headers.get("Content-Type", "application/octet-stream"),
            "x-upsert": "true",
        },
        data=src.content,
        timeout=TIMEOUT,
    )
    dst.raise_for_status()


def main() -> int:
    total = 0
    ecarts: list[str] = []

    for bucket in lister_buckets(PROD_URL, PROD_KEY):
        bucket_id = bucket["id"]
        creer_bucket(TEST_URL, TEST_KEY, bucket)

        objets = lister_objets(PROD_URL, PROD_KEY, bucket_id)
        for chemin in objets:
            copier_objet(bucket_id, chemin)
            total += 1

        # Contrôle de cohérence : fichiers et métadonnées doivent concorder.
        copies = lister_objets(TEST_URL, TEST_KEY, bucket_id)
        if len(copies) != len(objets):
            ecarts.append(
                f"{bucket_id} : {len(objets)} en prod, {len(copies)} en test"
            )
        print(f"{bucket_id} : {len(objets)} objet(s)")

    if ecarts:
        print("ERREUR : décomptes Storage incohérents :", file=sys.stderr)
        for e in ecarts:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"Total copié : {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
