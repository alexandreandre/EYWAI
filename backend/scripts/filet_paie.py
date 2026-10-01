"""Filet avant/après de la paie : photographier les entrées, rejouer, comparer au centime.

Pourquoi : toute modification du moteur doit laisser les bulletins identiques,
sauf écart annoncé et validé. Comparer deux calculs faits à des moments
différents ne prouve rien si les saisies ont bougé entre-temps. Le filet
photographie donc une fois toutes les lectures faites en base pendant le
calcul, puis fait rejouer cette même photo par n'importe quelle version du
code, sans réseau.

Rien n'est jamais écrit : les bulletins sont calculés en bac à sable
(`payslip_generator_provider.generate_en_bac_a_sable`), et toute requête
d'écriture vers Supabase est refusée avant de partir, à la photo comme au
rejeu. La photo lit la base désignée par le `.env` (la base de test).

Usage, depuis backend/ :
  .venv/bin/python scripts/filet_paie.py photo --siren 802485169 --de 2026-08 --a 2026-08 \\
      --dossier ../data/_filet/colorplast-aout
  .venv/bin/python scripts/filet_paie.py rejouer --dossier ../data/_filet/colorplast-aout

Déroulé type :
  1. avant de modifier le moteur : `photo` (calcule avec le code actuel et garde
     le résultat comme référence) ;
  2. après la modification : `rejouer` ; « zéro écart », ou la liste des lignes
     qui ont bougé, dans `rapport.md` du dossier.

Si le nouveau code lit en base quelque chose que la photo ne contient pas, le
rejeu s'arrête et le dit : il faut alors reprendre la photo avec l'ancien code.

La photo contient des données de paie nominatives : le dossier doit rester
sous `data/`, qui n'est pas versionné.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

TOLERANCE = 0.005  # un demi-centime

# Champs qui changent à chaque calcul sans rien dire du bulletin. Complétée en
# rejouant une photo avec le code qui l'a prise : l'écart doit alors être nul.
CLES_VOLATILES: frozenset[str] = frozenset(
    {
        "date_generation",
        "generated_at",
        "simulation_date",
        "calculation_date",
        # Métadonnée d'entrée, pas un montant : le filet ne la compare pas.
        "empreinte_entrees",
    }
)


# ---------------------------------------------------------------------------
# Interception des requêtes HTTP (Supabase passe par httpx)
# ---------------------------------------------------------------------------


class EcritureInterdite(RuntimeError):
    pass


class RequeteInconnue(RuntimeError):
    pass


def _est_une_lecture(request: httpx.Request) -> bool:
    if request.method in ("GET", "HEAD"):
        return True
    # Les appels de fonctions Postgres passent en POST ; ceux du calcul lisent.
    return request.method == "POST" and "/rest/v1/rpc/" in request.url.path


def _cle(request: httpx.Request) -> str:
    corps = request.content or b""
    return f"{request.method} {request.url} {hashlib.sha1(corps).hexdigest()}"


def _encoder(contenu: bytes) -> dict[str, str]:
    try:
        return {"texte": contenu.decode("utf-8")}
    except UnicodeDecodeError:
        return {"base64": base64.b64encode(contenu).decode("ascii")}


def _decoder(bloc: dict[str, str]) -> bytes:
    if "texte" in bloc:
        return bloc["texte"].encode("utf-8")
    return base64.b64decode(bloc["base64"])


class Interception:
    """Remplace `httpx.Client.send` : enregistre (photo) ou rejoue (rejeu)."""

    def __init__(
        self,
        mode: str,
        cassette: dict[str, list[dict]] | None = None,
        *,
        ecritures_simulees: bool = False,
        completer: bool = False,
    ):
        self.mode = mode
        self.cassette: dict[str, list[dict]] = cassette or {}
        self._rang: dict[str, int] = {}
        self._original = httpx.Client.send
        self.nombre = 0
        # Une ancienne version du code peut tenter d'écrire (défaut corrigé
        # depuis) : on lui répond « fait » sans rien envoyer, et on le note.
        self.ecritures_simulees = ecritures_simulees
        self.ecritures_evitees: list[str] = []
        # Au rejeu, une lecture absente de la photo peut être faite en direct
        # (toujours sans écriture) ; elle est notée dans le rapport.
        self.completer = completer
        self.lectures_completees: list[str] = []

    def __enter__(self) -> "Interception":
        interception = self

        def send(client: httpx.Client, request: httpx.Request, *args: Any, **kwargs: Any):
            return interception._send(client, request, *args, **kwargs)

        httpx.Client.send = send  # type: ignore[method-assign]
        return self

    def __exit__(self, *exc: Any) -> None:
        httpx.Client.send = self._original  # type: ignore[method-assign]

    def _send(self, client: httpx.Client, request: httpx.Request, *args: Any, **kwargs: Any):
        if not _est_une_lecture(request):
            if self.ecritures_simulees:
                self.ecritures_evitees.append(f"{request.method} {request.url.path}")
                return httpx.Response(204, request=request)
            raise EcritureInterdite(
                f"Écriture refusée par le filet : {request.method} {request.url.path}"
            )
        self.nombre += 1
        cle = _cle(request)
        if self.mode == "photo":
            reponse = self._original(client, request, *args, **kwargs)
            reponse.read()
            self.cassette.setdefault(cle, []).append(
                {
                    "statut": reponse.status_code,
                    "entetes": {
                        k: v
                        for k, v in reponse.headers.items()
                        if k.lower() in ("content-type", "content-range")
                    },
                    "contenu": _encoder(reponse.content),
                }
            )
            return reponse
        enregistrees = self.cassette.get(cle)
        if not enregistrees and self.completer:
            self.lectures_completees.append(f"{request.method} {request.url.path}")
            return self._original(client, request, *args, **kwargs)
        if not enregistrees:
            raise RequeteInconnue(
                f"Lecture absente de la photo : {request.method} {request.url.path}"
                f"?{request.url.query.decode() if isinstance(request.url.query, bytes) else request.url.query}"
            )
        rang = self._rang.get(cle, 0)
        bloc = enregistrees[min(rang, len(enregistrees) - 1)]
        self._rang[cle] = rang + 1
        return httpx.Response(
            status_code=bloc["statut"],
            headers=bloc["entetes"],
            content=_decoder(bloc["contenu"]),
            request=request,
        )


# ---------------------------------------------------------------------------
# Calcul des bulletins en bac à sable
# ---------------------------------------------------------------------------


def _mois(texte: str) -> tuple[int, int]:
    annee, mois = texte.split("-")
    return int(annee), int(mois)


def _bulletins_a_calculer(siren: str, de: tuple[int, int], a: tuple[int, int]) -> list[dict]:
    """Salariés et mois qui ont un bulletin enregistré dans la période."""
    from app.core.database import supabase

    societe = (
        supabase.table("companies").select("id").eq("siren", siren).limit(1).execute().data
    )
    if not societe:
        raise SystemExit(f"Aucune société de SIREN {siren}.")
    company_id = societe[0]["id"]
    lignes = (
        supabase.table("payslips")
        .select("employee_id, year, month")
        .eq("company_id", company_id)
        .gte("year", de[0])
        .lte("year", a[0])
        .execute()
        .data
    )
    retenus = sorted(
        {
            (l["employee_id"], l["year"], l["month"])
            for l in lignes
            if de <= (l["year"], l["month"]) <= a
        },
        key=lambda t: (t[0], t[1], t[2]),
    )
    return [{"employee_id": e, "year": y, "month": m} for e, y, m in retenus]


def _cumuls_du_mois_precedent(employee_id: str, year: int, month: int) -> dict | None:
    """Ce que le générateur aurait lu en base pour le mois d'avant."""
    if month == 1:
        return None
    from app.core.database import supabase

    lignes = (
        supabase.table("employee_schedules")
        .select("cumuls")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .eq("month", month - 1)
        .limit(1)
        .execute()
        .data
    )
    return (lignes[0].get("cumuls") if lignes else None) or None


def _calculer(bulletins: list[dict]) -> dict[str, Any]:
    """Calcule chaque bulletin en bac à sable, en chaînant les mois par salarié."""
    from app.modules.payslips.infrastructure.providers import payslip_generator_provider

    resultats: dict[str, Any] = {}
    chaine: dict[str, dict | None] = {}
    for b in bulletins:
        emp, year, month = b["employee_id"], b["year"], b["month"]
        etiquette = f"{emp}/{year}-{month:02d}"
        if emp not in chaine:
            chaine[emp] = _cumuls_du_mois_precedent(emp, year, month)
        debut = time.monotonic()
        try:
            res = payslip_generator_provider.generate_en_bac_a_sable(
                emp, year, month, cumuls_precedents=chaine[emp]
            )
        except (EcritureInterdite, RequeteInconnue):
            raise
        except Exception as exc:  # le refus d'un bulletin fait partie du résultat
            resultats[etiquette] = {"erreur": f"{type(exc).__name__}: {exc}"}
            print(f"  {etiquette} : refusé ({type(exc).__name__})", flush=True)
            continue
        chaine[emp] = res.get("cumuls") or None
        resultats[etiquette] = {
            "payslip_data": res.get("payslip_data"),
            "cumuls": res.get("cumuls"),
            "warnings": res.get("warnings"),
        }
        print(f"  {etiquette} : calculé en {time.monotonic() - debut:.1f} s", flush=True)
    return resultats


# ---------------------------------------------------------------------------
# Comparaison au centime
# ---------------------------------------------------------------------------


def _aplatir(valeur: Any, chemin: str = "") -> dict[str, Any]:
    """Dictionnaire à plat `chemin → valeur`. Les listes de lignes sont indexées
    par libellé, pour qu'une ligne ajoutée ne décale pas toutes les suivantes."""
    plat: dict[str, Any] = {}
    if isinstance(valeur, dict):
        for cle, sous in valeur.items():
            if cle in CLES_VOLATILES:
                continue
            plat.update(_aplatir(sous, f"{chemin}.{cle}" if chemin else str(cle)))
    elif isinstance(valeur, list):
        vus: dict[str, int] = {}
        for i, sous in enumerate(valeur):
            libelle = sous.get("libelle") if isinstance(sous, dict) else None
            if isinstance(libelle, str) and libelle:
                n = vus.get(libelle, 0)
                vus[libelle] = n + 1
                nom = f"[{libelle}]" if n == 0 else f"[{libelle}#{n + 1}]"
                # Le libellé est déjà dans le chemin : inutile de le comparer.
                sous = {k: v for k, v in sous.items() if k != "libelle"}
            else:
                nom = f"[{i}]"
            plat.update(_aplatir(sous, f"{chemin}{nom}"))
    else:
        plat[chemin] = valeur
    return plat


def _differe(avant: Any, apres: Any) -> bool:
    nombres = (int, float)
    if isinstance(avant, bool) or isinstance(apres, bool):
        return avant != apres
    if isinstance(avant, nombres) and isinstance(apres, nombres):
        return abs(float(avant) - float(apres)) > TOLERANCE
    return avant != apres


def comparer(reference: dict[str, Any], nouveau: dict[str, Any]) -> dict[str, list[tuple]]:
    ecarts: dict[str, list[tuple]] = {}
    for etiquette in sorted(set(reference) | set(nouveau)):
        a = _aplatir(reference.get(etiquette, {"absent": True}))
        b = _aplatir(nouveau.get(etiquette, {"absent": True}))
        lignes = [
            (chemin, a.get(chemin, "—"), b.get(chemin, "—"))
            for chemin in sorted(set(a) | set(b))
            if chemin not in a or chemin not in b or _differe(a[chemin], b[chemin])
        ]
        if lignes:
            ecarts[etiquette] = lignes
    return ecarts


def _rapport(dossier: Path, ecarts: dict[str, list[tuple]], nb: int, meta: dict) -> Path:
    lignes = [
        "# Filet avant/après",
        "",
        f"- Photo du {meta['date']} (code `{meta['commit']}`), rejouée le "
        f"{datetime.now():%d/%m/%Y %H:%M} (code `{_commit()}`).",
        f"- Bulletins comparés : {nb}.",
        f"- Bulletins avec écart : {len(ecarts)}.",
        f"- Écritures évitées (jamais envoyées) : photo {len(meta.get('ecritures_evitees', []))}, "
        f"rejeu {len(meta.get('rejeu_ecritures_evitees', []))}.",
        f"- Lectures absentes de la photo, faites en direct au rejeu : "
        f"{len(meta.get('rejeu_lectures_completees', []))}.",
        "",
    ]
    if not ecarts:
        lignes.append("**Zéro écart.**")
    for etiquette, diff in ecarts.items():
        lignes += ["", f"## {etiquette} — {len(diff)} écart(s)", "", "| Ligne | Avant | Après |", "|---|---|---|"]
        for chemin, avant, apres in diff[:200]:
            lignes.append(f"| `{chemin}` | {avant} | {apres} |")
        if len(diff) > 200:
            lignes.append(f"| … | {len(diff) - 200} autres | |")
    chemin = dossier / "rapport.md"
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return chemin


def _commit() -> str:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        sale = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return f"{sha}{' + modifications non commitées' if sale else ''}"
    except Exception:
        return "inconnu"


# ---------------------------------------------------------------------------
# Commandes
# ---------------------------------------------------------------------------


def photo(args: argparse.Namespace) -> int:
    dossier = Path(args.dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    debut = time.monotonic()
    # Version du code relevée AVANT le calcul : c'est celle que Python charge.
    commit = _commit()
    with Interception("photo", ecritures_simulees=args.ecritures_simulees) as capture:
        bulletins = _bulletins_a_calculer(args.siren, _mois(args.de), _mois(args.a))
        print(f"{len(bulletins)} bulletin(s) à calculer.", flush=True)
        resultats = _calculer(bulletins)
    meta = {
        "date": f"{datetime.now():%d/%m/%Y %H:%M}",
        "commit": commit,
        "siren": args.siren,
        "de": args.de,
        "a": args.a,
        "bulletins": bulletins,
        "lectures": capture.nombre,
        "ecritures_evitees": capture.ecritures_evitees,
        "duree_s": round(time.monotonic() - debut, 1),
    }
    (dossier / "cassette.json").write_text(json.dumps(capture.cassette), encoding="utf-8")
    (dossier / "reference.json").write_text(
        json.dumps(resultats, ensure_ascii=False, default=str), encoding="utf-8"
    )
    (dossier / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Photo prise : {len(bulletins)} bulletin(s), {capture.nombre} lecture(s), "
        f"{meta['duree_s']} s. Dossier : {dossier}",
        flush=True,
    )
    return 0


def rejouer(args: argparse.Namespace) -> int:
    dossier = Path(args.dossier)
    meta = json.loads((dossier / "meta.json").read_text(encoding="utf-8"))
    cassette = json.loads((dossier / "cassette.json").read_text(encoding="utf-8"))
    reference = json.loads((dossier / "reference.json").read_text(encoding="utf-8"))
    debut = time.monotonic()
    with Interception(
        "rejeu", cassette, ecritures_simulees=args.ecritures_simulees, completer=args.completer
    ) as rejeu:
        nouveau = _calculer(meta["bulletins"])
    nouveau = json.loads(json.dumps(nouveau, ensure_ascii=False, default=str))
    ecarts = comparer(reference, nouveau)
    meta_rejeu = dict(meta)
    meta_rejeu["rejeu_ecritures_evitees"] = rejeu.ecritures_evitees
    meta_rejeu["rejeu_lectures_completees"] = rejeu.lectures_completees
    chemin = _rapport(dossier, ecarts, len(meta["bulletins"]), meta_rejeu)
    duree = round(time.monotonic() - debut, 1)
    if ecarts:
        total = sum(len(v) for v in ecarts.values())
        print(f"ÉCARTS : {total} ligne(s) sur {len(ecarts)} bulletin(s), en {duree} s. Voir {chemin}")
        return 1
    print(f"Zéro écart sur {len(meta['bulletins'])} bulletin(s), en {duree} s. Voir {chemin}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sous = parser.add_subparsers(dest="commande", required=True)
    p = sous.add_parser("photo", help="calculer avec le code actuel et photographier les entrées")
    p.add_argument("--siren", required=True)
    p.add_argument("--de", required=True, help="premier mois, AAAA-MM")
    p.add_argument("--a", required=True, help="dernier mois, AAAA-MM")
    p.add_argument("--dossier", required=True, help="sous data/, jamais versionné")
    p.add_argument(
        "--ecritures-simulees",
        action="store_true",
        help="répondre « fait » aux écritures sans les envoyer (ancienne version du code)",
    )
    r = sous.add_parser("rejouer", help="recalculer sur la photo et comparer")
    r.add_argument("--dossier", required=True)
    r.add_argument("--ecritures-simulees", action="store_true")
    r.add_argument(
        "--completer",
        action="store_true",
        help="faire en direct les lectures absentes de la photo (sans écriture)",
    )
    args = parser.parse_args()
    return photo(args) if args.commande == "photo" else rejouer(args)


if __name__ == "__main__":
    raise SystemExit(main())
