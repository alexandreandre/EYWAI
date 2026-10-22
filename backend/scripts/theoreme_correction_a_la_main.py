"""Test du théorème de la correction à la main, au bac à sable.

Pour chaque bulletin d'une société et d'un mois, et pour chaque cotisation
régularisable qu'il porte, injecte en mémoire une régularisation (base de 10 €
au taux de la ligne, ou 1 € pour une cotisation sans taux), recalcule sans rien
écrire, et vérifie la ligne, le total salarial, le net, le cumul de la
réduction générale et la DSN. Puis un gain soumis et une retenue sur le net.

Le rapport JSON reste hors du dépôt. Depuis backend/ :

    PYTHONPATH=. .venv/bin/python scripts/theoreme_correction_a_la_main.py "<Société>" 2026 9 <sortie.json>
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, "scripts/verification_rgdu")
from piege import poser_le_piege  # noqa: E402

poser_le_piege()

from app.core.database import supabase  # noqa: E402
from app.core.lecture_seule import lecture_seule  # noqa: E402
from app.modules.dsn_export.domain.cotisation_mapping import REGLES, build_bases_and_cotisations  # noqa: E402
from app.modules.exports.domain.controle_comptable import residu_du_bulletin  # noqa: E402
from app.modules.exports.infrastructure.export_ecritures_comptables import ligne_od_du_bulletin  # noqa: E402
from app.modules.payroll.engine.corrections_manuelles import RegularisationCotisation  # noqa: E402
from app.modules.payslips.infrastructure.providers import payslip_generator_provider  # noqa: E402


def _cumuls_precedents(employee_id: str, year: int, month: int) -> dict | None:
    annee, mois = (year, month - 1) if month > 1 else (year - 1, 12)
    res = (
        supabase.table("employee_schedules")
        .select("cumuls")
        .match({"employee_id": employee_id, "year": annee, "month": mois})
        .maybe_single()
        .execute()
    )
    return (res.data or {}).get("cumuls") if res else None


def _lignes(payslip_data: dict) -> list[dict]:
    return [
        ligne
        for rubrique in payslip_data.get("cotisations_officielles") or []
        for ligne in rubrique.get("lignes") or []
    ]


def _montants_dsn(payslip_data: dict) -> dict[str, float]:
    _, cotisations, _ = build_bases_and_cotisations(
        _lignes(payslip_data),
        brut=float(payslip_data.get("salaire_brut") or 0),
        period_start="2026-01-01",
        period_end="2026-01-31",
    )
    sortie: dict[str, float] = {}
    for cotisation in cotisations:
        sortie[cotisation.code] = round(sortie.get(cotisation.code, 0.0) + float(cotisation.montant_patronal or 0), 2)
    return sortie


def _dsn_a_bouge(avant: dict[str, float], apres: dict[str, float], coti_id: str, salarial: float, patronal: float) -> bool:
    """La somme des codes DSN bouge du montant de la régularisation.

    Agirc-Arrco déclare le total sur le code 131 et redéclare la part patronale
    sur 142 ou 146. Les deux bougent, donc la somme bouge du total plus cette part.
    """
    ecart = round(sum(apres.values()) - sum(avant.values()), 2)
    attendu = round(salarial + patronal, 2)
    regle = REGLES.get(coti_id)
    if regle is not None and regle.code_patronal:
        attendu = round(attendu + patronal, 2)
    return abs(ecart - attendu) <= 0.02


def _indemnites_suivies(payslip_data: dict) -> float:
    """Primes que le moteur recalcule à partir du brut : précarité, IFM, congés de CDD."""
    total = 0.0
    for ligne in payslip_data.get("calcul_du_brut") or []:
        if not isinstance(ligne, dict):
            continue
        libelle = str(ligne.get("libelle") or "").lower()
        if "précarité" in libelle or "precarite" in libelle or "fin de mission" in libelle:
            total += float(ligne.get("gain") or 0)
    for ligne in payslip_data.get("details_conges") or []:
        if not isinstance(ligne, dict):
            continue
        libelle = str(ligne.get("libelle") or "").lower()
        if "indemnité compensatrice" in libelle or "indemnite compensatrice" in libelle:
            total += float(ligne.get("gain") or 0)
    return round(total, 2)


def _residu(payslip_data: dict, employee: dict) -> float:
    ligne = ligne_od_du_bulletin(
        payslip_id="theoreme",
        employee=employee,
        payslip_data=payslip_data,
        saisies_du_salarie=[],
        compte_de_saisie=lambda _type: "421000",
    )
    return residu_du_bulletin(ligne)


def _regularisation(ligne: dict) -> RegularisationCotisation:
    taux_salarial = ligne.get("taux_salarial") or None
    taux_patronal = ligne.get("taux_patronal") or None
    commun = dict(coti_id=ligne["coti_id"], libelle=ligne["libelle"], motif="Test du théorème")
    if taux_salarial or taux_patronal:
        return RegularisationCotisation(
            **commun, base=10.0, taux_salarial=taux_salarial, taux_patronal=taux_patronal
        )
    montant = -1.0 if ligne["coti_id"] == "reduction_generale" else 1.0
    return RegularisationCotisation(**commun, montant_patronal=montant)


def main(societe: str, year: int, month: int, sortie: str) -> int:
    company = supabase.table("companies").select("id").eq("company_name", societe).single().execute().data
    bulletins = (
        supabase.table("payslips")
        .select("employee_id")
        .match({"company_id": company["id"], "year": year, "month": month})
        .execute()
        .data
    )
    rapport: list[dict] = []
    echecs = 0
    for bulletin in bulletins:
        employee_id = bulletin["employee_id"]
        print(f"salarie {employee_id[:8]}", flush=True)
        with lecture_seule():
            _un_salarie(company["id"], employee_id, year, month, rapport)
    echecs = sum(1 for cas in rapport if not cas["ok"])
    with open(sortie, "w", encoding="utf-8") as fichier:
        json.dump(rapport, fichier, ensure_ascii=False, indent=1)
    print(f"{len(rapport)} cas, {echecs} échec(s)", flush=True)
    return 1 if echecs else 0


def _noter(rapport: list[dict], employee_id: str, ok: bool, **constats: object) -> None:
    rapport.append({"salarie": employee_id, "ok": ok, **constats})
    print(("OK  " if ok else "ECHEC"), employee_id[:8], constats.get("coti_id") or constats.get("cas"), constats if not ok else "", flush=True)


def _un_salarie(company_id: str, employee_id: str, year: int, month: int, rapport: list[dict]) -> None:
    employee = supabase.table("employees").select("*").eq("id", employee_id).single().execute().data
    cumuls = _cumuls_precedents(employee_id, year, month)
    base = payslip_generator_provider.generate_en_bac_a_sable(
        employee_id, year, month, cumuls_precedents=cumuls
    )
    data0 = base["payslip_data"]
    dsn0, residu0 = _montants_dsn(data0), _residu(data0, employee)
    vus: set[str] = set()
    for ligne in _lignes(data0):
        if not ligne.get("coti_id") or ligne.get("is_participation") or ligne.get("is_ppv"):
            continue
        if ligne["coti_id"] in vus:
            continue
        vus.add(ligne["coti_id"])
        regul = _regularisation(ligne)
        saisie = {
            **regul.saisie_du_mois(
                {"employee_id": employee_id, "company_id": company_id, "year": year, "month": month}
            ),
            "id": "theoreme",
        }
        res = payslip_generator_provider.generate_en_bac_a_sable(
            employee_id, year, month, cumuls_precedents=cumuls, saisies_en_plus=(saisie,)
        )
        data1 = res["payslip_data"]
        salarial, patronal = regul.montants()
        constats = {
            "ligne": any(item.get("regularisation") for item in _lignes(data1)),
            "total_salarial": abs(
                data1["structure_cotisations"]["total_salarial"]
                - data0["structure_cotisations"]["total_salarial"]
                - salarial
            )
            < 0.005,
            "residu": abs(_residu(data1, employee) - residu0) < 0.005,
        }
        if ligne["coti_id"] == "reduction_generale":
            cumul0 = (base.get("cumuls") or {}).get("cumuls", {}).get("reduction_generale_patronale", 0)
            cumul1 = (res.get("cumuls") or {}).get("cumuls", {}).get("reduction_generale_patronale", 0)
            constats["cumul_reduction"] = abs(cumul1 - cumul0 - patronal) < 0.005
        constats["dsn"] = _dsn_a_bouge(_montants_dsn(data0), _montants_dsn(data1), ligne["coti_id"], salarial, patronal)
        _noter(rapport, employee_id, all(constats.values()), coti_id=ligne["coti_id"], **constats)
    periode = {"employee_id": employee_id, "company_id": company_id, "year": year, "month": month}
    cas = {
        "gain soumis": (
            {
                **periode,
                "id": "theoreme-gain",
                "name": "Régularisation – gain",
                "amount": 10.0,
                "is_socially_taxed": True,
                "is_taxable": True,
            },
            "brut",
            10.0,
        ),
        "retenue sur le net": (
            {
                **periode,
                "id": "theoreme-retenue",
                "name": "Régularisation – retenue",
                "amount": -10.0,
                "sur_le_net": True,
                "is_socially_taxed": False,
                "is_taxable": False,
            },
            "net",
            -10.0,
        ),
    }
    for nom, (saisie, cle, attendu) in cas.items():
        res = payslip_generator_provider.generate_en_bac_a_sable(
            employee_id, year, month, cumuls_precedents=cumuls, saisies_en_plus=(saisie,)
        )
        data1 = res["payslip_data"]
        champ = "salaire_brut" if cle == "brut" else "net_a_payer"
        mouvement = attendu
        if cle == "brut":
            # Un CDD recalcule la précarité et l'indemnité de congés sur ce gain.
            mouvement = round(attendu + _indemnites_suivies(data1) - _indemnites_suivies(data0), 2)
        constats = {
            cle: abs(float(data1[champ]) - float(data0[champ]) - mouvement) < 0.005,
            "residu": abs(_residu(data1, employee) - residu0) < 0.005,
        }
        if cle == "brut":
            brut0 = (base.get("cumuls") or {}).get("cumuls", {}).get("brut_total", 0)
            brut1 = (res.get("cumuls") or {}).get("cumuls", {}).get("brut_total", 0)
            constats["cumul_brut"] = abs(brut1 - brut0 - (float(data1[champ]) - float(data0[champ]))) < 0.005
        _noter(rapport, employee_id, all(constats.values()), cas=nom, **constats)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]))
