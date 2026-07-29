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

import base64
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

PROD_URL = os.environ["SUPABASE_PROD_URL"].rstrip("/")
PROD_KEY = os.environ["SUPABASE_PROD_SERVICE_KEY"]
TEST_URL = os.environ["SUPABASE_TEST_URL"].rstrip("/")
TEST_KEY = os.environ["SUPABASE_TEST_SERVICE_KEY"]

TIMEOUT = 120
PAGE = 1000
PARALLELISME = int(os.getenv("STORAGE_COPY_WORKERS", "12"))


def _headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}", "apikey": key}


def _role_de_cle(key: str) -> str:
    """Rôle porté par une clé Supabase (JWT), ou 'inconnu'."""
    parts = key.split(".")
    if len(parts) < 2:
        return "inconnu"
    charge = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(charge)).get("role", "inconnu")
    except Exception:
        return "inconnu"


def verifier_cles() -> None:
    """
    Refuse de continuer si une clé n'est pas service_role.

    Une clé anon liste zéro bucket sans lever d'erreur : la copie se terminerait
    sur « Total copié : 0 » en paraissant réussie. Les noms de variables ne sont
    pas fiables — dans backend/.env, SUPABASE_SERVICE_KEY porte la clé anon et
    SUPABASE_KEY la service_role. On vérifie donc le contenu, pas le nom.
    """
    for nom, cle in (("production", PROD_KEY), ("test", TEST_KEY)):
        role = _role_de_cle(cle)
        if role != "service_role":
            print(
                f"ERREUR : la clé {nom} porte le rôle '{role}' au lieu de "
                "'service_role'. La copie Storage serait silencieusement vide.",
                file=sys.stderr,
            )
            sys.exit(1)


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
    if r.status_code in (200, 201):
        return
    # Bucket déjà présent : cas normal d'une resynchro répétée. Supabase répond
    # HTTP 400 avec un corps qui annonce 409/BucketAlreadyExists — se fier au
    # seul code HTTP ferait échouer toute resynchro après la première.
    try:
        corps = r.json()
    except ValueError:
        corps = {}
    if corps.get("code") == "BucketAlreadyExists" or str(corps.get("statusCode")) == "409":
        return
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


def supprimer_objets(bucket_id: str, chemins: list[str]) -> None:
    """Supprime côté test des objets absents de la production."""
    if not chemins:
        return
    r = requests.delete(
        f"{TEST_URL}/storage/v1/object/{bucket_id}",
        headers={**_headers(TEST_KEY), "Content-Type": "application/json"},
        json={"prefixes": chemins},
        timeout=TIMEOUT,
    )
    r.raise_for_status()


def main() -> int:
    verifier_cles()

    total = 0
    ecarts: list[str] = []

    for bucket in lister_buckets(PROD_URL, PROD_KEY):
        bucket_id = bucket["id"]
        creer_bucket(TEST_URL, TEST_KEY, bucket)

        objets = lister_objets(PROD_URL, PROD_KEY, bucket_id)

        # Téléversements en parallèle : 1947 fichiers en série dépassent le
        # quart d'heure, l'essentiel du temps étant de l'attente réseau.
        erreurs: list[str] = []
        with ThreadPoolExecutor(max_workers=PARALLELISME) as pool:
            futurs = {
                pool.submit(copier_objet, bucket_id, chemin): chemin
                for chemin in objets
            }
            for futur in as_completed(futurs):
                try:
                    futur.result()
                    total += 1
                except Exception as e:  # noqa: BLE001
                    erreurs.append(f"{futurs[futur]} : {e}")

        if erreurs:
            print(f"ERREUR : {len(erreurs)} objet(s) non copié(s) :", file=sys.stderr)
            for e in erreurs[:10]:
                print(f"  - {e}", file=sys.stderr)
            return 1

        # Un fichier supprimé en production doit disparaître du test, sans quoi
        # le bac à sable accumulerait indéfiniment d'anciens documents.
        copies = lister_objets(TEST_URL, TEST_KEY, bucket_id)
        en_trop = sorted(set(copies) - set(objets))
        if en_trop:
            supprimer_objets(bucket_id, en_trop)
            print(f"{bucket_id} : {len(en_trop)} objet(s) obsolète(s) supprimé(s)")
            copies = lister_objets(TEST_URL, TEST_KEY, bucket_id)

        # Contrôle de cohérence : fichiers et métadonnées doivent concorder.
        if len(copies) != len(objets):
            ecarts.append(f"{bucket_id} : {len(objets)} en prod, {len(copies)} en test")
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
