"""Test du théorème de la correction à la main, au bac à sable.

Pour chaque bulletin d'une société et d'un mois, et pour chaque cotisation
régularisable qu'il porte, injecte en mémoire une régularisation (base de 10 €
au taux de la ligne, ou 1 € pour une cotisation sans taux), recalcule sans rien
écrire, et vérifie la ligne, le total salarial, le net, le cumul de la
réduction générale et la DSN. Puis un gain soumis et une retenue sur le net.

Étape 2 (correction directe) : chaque ligne du bulletin doit avoir un code ;
pour chaque famille de ligne, une correction permise par la règle 3 (base + 1
ou + 10, montant + 10 ou ± 1, taux d'impôt + 1 point) est injectée en mémoire,
et l'on vérifie la ligne, les totaux, les copies, le net, les cumuls, la DSN et
le mois suivant. Puis une correction sans ligne : elle reste en attente et
bloque la validation. Le dernier argument choisit la partie : tout (défaut),
regularisations, directes.

Doublons : chaque ligne numérotée (« code#2 ») est corrigée elle aussi, et la
correction doit se poser sur la ligne que le bulletin lit sous ce code, et sur
elle seule (la numérotation du calcul et celle du bulletin concordent). Les
doublons du bulletin enregistré sont comparés à ceux du recalcul.

Le rapport JSON reste hors du dépôt. Depuis backend/ :

    PYTHONPATH=. .venv/bin/python scripts/theoreme_correction_a_la_main.py "<Société>" 2026 9 <sortie.json> [tout|regularisations|directes]
"""

from __future__ import annotations

import json
import sys
import traceback

sys.path.insert(0, "scripts/verification_rgdu")
from piege import poser_le_piege  # noqa: E402

poser_le_piege()

from fastapi import HTTPException  # noqa: E402

from app.core.database import supabase  # noqa: E402
from app.core.lecture_seule import lecture_seule  # noqa: E402
from app.modules.dsn_export.domain.cotisation_mapping import (  # noqa: E402
    REGLES,
    _traduire,
    build_bases_and_cotisations,
)
from app.modules.exports.domain.controle_comptable import residu_du_bulletin  # noqa: E402
from app.modules.exports.infrastructure.export_ecritures_comptables import ligne_od_du_bulletin  # noqa: E402
from app.modules.payroll.engine.corrections_manuelles import RegularisationCotisation  # noqa: E402
from app.modules.payslips.infrastructure.providers import payslip_generator_provider  # noqa: E402
from app.modules.dsn_export.application.builder import _pas_details  # noqa: E402
from app.modules.payroll.engine.codes_des_lignes import (  # noqa: E402
    BLOC_BRUT,
    BLOC_COTISATIONS,
    BLOC_IMPOT,
    MODE_BASE_OU_TAUX,
    MODE_TAUX,
    code_de_ligne,
    famille_du_code,
    numeroter,
)
from app.modules.payroll.engine.corrections_du_bulletin import (  # noqa: E402
    BLOCS_DE_GAINS,
    LigneCorrigeable,
    lignes_corrigeables,
)
from app.modules.payroll.engine.corrections_manuelles import CorrectionDeLigne, CorrectionInvalide  # noqa: E402
from app.modules.payslips.domain.coherence import (  # noqa: E402
    MESSAGE_CORRECTION_EN_ATTENTE,
    raisons_de_ne_pas_valider,
)


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


def _dsn_a_bouge(
    avant: dict[str, float],
    apres: dict[str, float],
    ligne: dict,
    salarial: float,
    patronal: float,
) -> bool:
    """La somme des codes DSN bouge du montant de la régularisation.

    Agirc-Arrco déclare le total sur le code 131 et redéclare la part patronale
    sur 142 ou 146. Les deux bougent, donc la somme bouge du total plus cette part.
    Une cotisation que la DSN individuelle ne traduit pas (l'exonération apprenti)
    ne doit pas non plus apparaître via sa régularisation.
    """
    ecart = round(sum(apres.values()) - sum(avant.values()), 2)
    if not _traduire(ligne, 0.0, 0.0, 0.0):
        return abs(ecart) <= 0.02
    attendu = round(salarial + patronal, 2)
    regle = REGLES.get(str(ligne.get("coti_id") or ""))
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


def _noter(rapport: list[dict], employee_id: str, ok: bool, **constats: object) -> None:
    rapport.append({"salarie": employee_id, "ok": ok, **constats})
    nom = constats.get("coti_id") or constats.get("code") or constats.get("cas")
    print(("OK  " if ok else "ECHEC"), employee_id[:8], nom, constats if not ok else "", flush=True)


def _generer(employee_id: str, year: int, month: int, cumuls: dict | None, saisies_en_plus: tuple = ()):
    """Recalcule. Un délai de la base se rejoue ; un refus du bulletin, non."""
    for essai in range(3):
        try:
            return payslip_generator_provider.generate_en_bac_a_sable(
                employee_id,
                year,
                month,
                cumuls_precedents=cumuls,
                saisies_en_plus=saisies_en_plus,
            )
        except HTTPException as exc:
            if exc.status_code not in (500, 503) or essai == 2:
                raise
            print(f"REESSAI {employee_id[:8]} ({exc.status_code})", flush=True)


def _un_salarie(company_id: str, employee_id: str, year: int, month: int, rapport: list[dict]) -> None:
    employee = supabase.table("employees").select("*").eq("id", employee_id).single().execute().data
    cumuls = _cumuls_precedents(employee_id, year, month)
    try:
        base = _generer(employee_id, year, month, cumuls)
    except HTTPException as exc:
        if exc.status_code not in (400, 422):
            raise
        # Le bulletin est déjà refusé (solde d'ouverture incomplet, cumul
        # manquant). Aucune correction n'est en cause.
        rapport.append({"salarie": employee_id, "ok": True, "cas": "bulletin de départ refusé", "saute": True})
        print("SAUTE", employee_id[:8], "bulletin de départ refusé", flush=True)
        return
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
        res = _generer(employee_id, year, month, cumuls, (saisie,))
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
        constats["dsn"] = _dsn_a_bouge(_montants_dsn(data0), _montants_dsn(data1), ligne, salarial, patronal)
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
        res = _generer(employee_id, year, month, cumuls, (saisie,))
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


#: Les cumuls d'heures qu'une base corrigée d'une heure doit faire monter d'une heure (spec § 6).
HEURES_SUIVIES = {
    "brut:heures_sup": ("heures_supplementaires_remunerees", "heures_remunerees"),
    "brut:salaire_base": ("heures_remunerees",),
}


def _ecart(avant: object, apres: object) -> float:
    return round(float(apres or 0.0) - float(avant or 0.0), 2)


def _cumul(resultat: dict, cle: str) -> float:
    return float(((resultat.get("cumuls") or {}).get("cumuls") or {}).get(cle) or 0.0)


def _synthese(data: dict, cle: str) -> float:
    return float((data.get("synthese_net") or {}).get(cle) or 0.0)


def _impot(data: dict) -> dict:
    return (data.get("synthese_net") or {}).get("impot_prelevement_a_la_source") or {}


def _somme_du_brut(data: dict) -> float:
    total = 0.0
    for bloc in BLOCS_DE_GAINS:
        for ligne in data.get(bloc) or []:
            if isinstance(ligne, dict) and not ligne.get("is_sous_total") and not ligne.get("is_informative"):
                total += float(ligne.get("gain") or 0.0) - float(ligne.get("perte") or 0.0)
    return round(total, 2)


def _totaux(data: dict) -> dict[str, float]:
    structure = data.get("structure_cotisations") or {}
    officielles = [r for r in data.get("cotisations_officielles") or [] if isinstance(r, dict)]
    lignes = _lignes(data)
    return {
        "brut": float(data.get("salaire_brut") or 0.0),
        "somme_du_brut": _somme_du_brut(data),
        "salarial": float(structure.get("total_salarial") or 0.0),
        "patronal": float(structure.get("total_patronal") or 0.0),
        "salarial_officiel": round(sum(float(r.get("total_salarial") or 0.0) for r in officielles), 2),
        "patronal_officiel": round(sum(float(r.get("total_patronal") or 0.0) for r in officielles), 2),
        "lignes_salariales": round(sum(float(l.get("montant_salarial") or 0.0) for l in lignes), 2),
        "lignes_patronales": round(sum(float(l.get("montant_patronal") or 0.0) for l in lignes), 2),
    }


def _lignes_par_code(data: dict) -> dict[str, dict]:
    lignes = _lignes(data)
    return {code: ligne for code, ligne in zip(numeroter(code_de_ligne(BLOC_COTISATIONS, l) for l in lignes), lignes) if code}


def _dsn_suit_les_lignes(dsn0: dict[str, float], dsn1: dict[str, float], data0: dict, data1: dict) -> bool:
    """La DSN bouge comme toutes les lignes du bulletin qui ont bougé, au centime.

    Une correction directe fait suivre ce qui dérive de la ligne (le forfait
    social d'une prévoyance, d'une mutuelle ou d'une retraite supplémentaire) :
    chaque ligne traduite compte, avec la part patronale redéclarée
    d'Agirc-Arrco comme dans `_dsn_a_bouge`.
    """
    avant, apres = _lignes_par_code(data0), _lignes_par_code(data1)
    attendu = 0.0
    for code in set(avant) | set(apres):
        l0, l1 = avant.get(code) or {}, apres.get(code) or {}
        ligne = l1 or l0
        salarial = _ecart(l0.get("montant_salarial"), l1.get("montant_salarial"))
        patronal = _ecart(l0.get("montant_patronal"), l1.get("montant_patronal"))
        if not (salarial or patronal) or not _traduire(ligne, 0.0, 0.0, 0.0):
            continue
        attendu += salarial + patronal
        regle = REGLES.get(str(ligne.get("coti_id") or ""))
        if regle is not None and regle.code_patronal:
            attendu += patronal
    ecart = round(sum(dsn1.values()) - sum(dsn0.values()), 2)
    return abs(ecart - round(attendu, 2)) <= 0.02


def _correction_pour(ligne: LigneCorrigeable) -> CorrectionDeLigne:
    """Une correction permise par la règle 3, assez petite pour ne rien faire basculer."""
    commun = dict(ligne=ligne.code, libelle=ligne.libelle, motif="Test du théorème")
    if ligne.mode == MODE_TAUX:
        return CorrectionDeLigne(**commun, taux=round(float(ligne.taux or 0.0) + 1.0, 2))
    if ligne.bloc == BLOC_BRUT:
        if ligne.mode == MODE_BASE_OU_TAUX:
            return CorrectionDeLigne(**commun, base=round(float(ligne.base or 0.0) + 1.0, 2))
        return CorrectionDeLigne(**commun, montant=round(float(ligne.montant or 0.0) + 10.0, 2))
    if ligne.mode == MODE_BASE_OU_TAUX:
        return CorrectionDeLigne(**commun, base=round(float(ligne.base or 0.0) + 10.0, 2))
    if famille_du_code(ligne.code) == "cotisation:reduction_generale":
        # Un euro de réduction en plus : la réduction de l'année ne peut pas devenir négative.
        return CorrectionDeLigne(**commun, montant_patronal=round(float(ligne.montant_patronal or 0.0) - 1.0, 2))
    if ligne.montant_patronal:
        return CorrectionDeLigne(**commun, montant_patronal=round(float(ligne.montant_patronal) + 1.0, 2))
    return CorrectionDeLigne(**commun, montant_salarial=round(float(ligne.montant_salarial or 0.0) + 1.0, 2))


def _attendu(ligne: LigneCorrigeable, correction: CorrectionDeLigne) -> dict[str, float]:
    """Ce que la ligne doit porter après la correction, au centime comme le moteur."""
    if ligne.bloc == BLOC_IMPOT:
        taux = float(correction.taux)
        return {"taux": taux, "montant": round(float(ligne.base or 0.0) * (taux / 100.0), 2)}
    if ligne.bloc == BLOC_BRUT:
        if correction.montant is not None:
            return {"montant": round(correction.montant, 2)}
        return {"base": float(correction.base), "montant": round(float(correction.base) * float(ligne.taux or 0.0), 2)}
    if correction.par_montant:
        return {
            cle: round(float(getattr(correction, cle)), 2)
            for cle in ("montant_salarial", "montant_patronal")
            if getattr(correction, cle) is not None
        }
    base = float(correction.base)
    attendu = {"base": base}
    if ligne.taux_salarial is not None:
        attendu["montant_salarial"] = round(base * ligne.taux_salarial, 2)
    if ligne.taux_patronal is not None:
        attendu["montant_patronal"] = round(base * ligne.taux_patronal, 2)
    return attendu


def _porte(ligne: LigneCorrigeable | None, attendu: dict[str, float]) -> bool:
    return (
        ligne is not None
        and ligne.correction is not None
        and all(abs(float(getattr(ligne, cle) or 0.0) - valeur) < 0.005 for cle, valeur in attendu.items())
    )


def _garde_la_valeur_de_martine(avant: LigneCorrigeable, apres: LigneCorrigeable | None) -> bool:
    if apres is None or not apres.valeur_calculee:
        return False
    calcule = apres.valeur_calculee
    if avant.bloc == BLOC_IMPOT:
        return abs(float(calcule.get("taux") or 0.0) - float(avant.taux or 0.0)) < 1e-6
    if avant.bloc == BLOC_BRUT:
        montant = calcule.get("gain") if calcule.get("gain") is not None else calcule.get("perte")
        return abs(float(montant or 0.0) - float(avant.montant or 0.0)) < 0.005
    return all(
        abs(float(calcule.get(cle) or 0.0) - float(getattr(avant, cle) or 0.0)) < 0.005
        for cle in ("montant_salarial", "montant_patronal")
    )


def _cumuls_suivent(
    base: dict, res: dict, ligne: LigneCorrigeable, apres: LigneCorrigeable | None, cumuls: dict | None = None
) -> dict[str, bool]:
    data0, data1 = base["payslip_data"], res["payslip_data"]

    def mouvement(cle: str) -> float:
        return _ecart(_cumul(base, cle), _cumul(res, cle))

    constats = {
        "cumul_brut": abs(mouvement("brut_total") - _ecart(data0.get("salaire_brut"), data1.get("salaire_brut"))) < 0.011,
        "cumul_net_imposable": abs(
            mouvement("net_imposable") - _ecart(_synthese(data0, "net_imposable"), _synthese(data1, "net_imposable"))
        ) < 0.011,
        "cumul_impot": abs(
            mouvement("impot_preleve_a_la_source") - _ecart(_impot(data0).get("montant"), _impot(data1).get("montant"))
        ) < 0.011,
    }
    famille = famille_du_code(ligne.code)
    if famille == "cotisation:reduction_generale" and apres is not None:
        constats["cumul_reduction"] = abs(
            mouvement("reduction_generale_patronale") - _ecart(ligne.montant_patronal, apres.montant_patronal)
        ) < 0.011
    if ligne.mode == MODE_BASE_OU_TAUX and famille in HEURES_SUIVIES and "forfait" not in ligne.libelle.lower():
        for cle in HEURES_SUIVIES[famille]:
            if _ecart(_cumul({"cumuls": cumuls or {}}, cle), _cumul(base, cle)) > 0.005:
                constats[f"cumul_{cle}"] = abs(mouvement(cle) - 1.0) < 0.011
            else:
                # Mois sans heure rémunérée (arrêt non maintenu ou absence sur
                # tout le mois) : le moteur borne les heures du mois à zéro, et
                # une heure de base en plus peut rester sous la borne.
                constats[f"cumul_{cle}_borne_a_zero"] = -0.011 < mouvement(cle) < 1.011
    return constats


def _le_mois_suivant_part_des_cumuls(employee_id: str, year: int, month: int, res: dict) -> bool | None:
    """Le mois suivant, recalculé sur les cumuls corrigés, en repart. None s'il n'est pas calculable."""
    annee, mois = (year, month + 1) if month < 12 else (year + 1, 1)
    try:
        suivant = _generer(employee_id, annee, mois, res.get("cumuls"))
    except HTTPException as exc:
        if exc.status_code in (400, 422):
            return None
        raise
    brut = float(suivant["payslip_data"].get("salaire_brut") or 0.0)
    return abs((_cumul(suivant, "brut_total") - brut) - _cumul(res, "brut_total")) < 0.011


def _racine(code: str | None) -> str:
    """« cotisation:mutuelle:x#2 » → « cotisation:mutuelle:x »."""
    return (code or "").split("#", 1)[0]


def _doublons(data: dict) -> list[dict]:
    """Les lignes d'un code porté plusieurs fois, dans l'ordre où le bulletin les lit."""
    lignes = lignes_corrigeables(data)
    doublees = {_racine(l.code) for l in lignes if l.code and "#" in l.code}
    return [
        {
            "code": l.code,
            "libelle": l.libelle,
            "montants": [l.montant, l.base, l.montant_salarial, l.montant_patronal],
        }
        for l in lignes
        if l.code and _racine(l.code) in doublees
    ]


def _doublons_du_bulletin_enregistre(rapport: list[dict], employee_id: str, enregistre: dict | None, data0: dict) -> None:
    """Les doublons du bulletin enregistré sont ceux du recalcul : mêmes codes, mêmes libellés, même ordre.

    Si le bulletin enregistré est à jour (même brut, même net), leurs montants aussi.
    """
    stockes, calcules = _doublons(enregistre or {}), _doublons(data0)
    if not stockes and not calcules:
        return
    enregistre = enregistre or {}
    if enregistre.get("reprise"):
        # Un bulletin repris de l'ancien logiciel porte ses lignes, pas celles de Martine.
        _noter(rapport, employee_id, True, cas="doublons du bulletin enregistré", saute=True,
               cause="bulletin repris : ses lignes ne sont pas celles du calcul", calcules=calcules)
        return
    a_jour = all(
        abs(_ecart(enregistre.get(cle), data0.get(cle))) < 0.005 for cle in ("salaire_brut", "net_a_payer")
    )
    memes_lignes = [(d["code"], d["libelle"]) for d in stockes] == [(d["code"], d["libelle"]) for d in calcules]
    memes_montants = stockes == calcules
    ok = memes_lignes and (memes_montants or not a_jour)
    _noter(
        rapport,
        employee_id,
        ok,
        cas="doublons du bulletin enregistré",
        memes_lignes=memes_lignes,
        memes_montants=memes_montants,
        enregistre_a_jour=a_jour,
        enregistres=stockes,
        calcules=calcules,
    )


def _corrections_directes(
    company_id: str, employee_id: str, year: int, month: int, rapport: list[dict], enregistre: dict | None = None
) -> None:
    """Étape 2 : chaque famille de ligne du bulletin, corrigée directement ; et chaque doublon."""
    employee = supabase.table("employees").select("*").eq("id", employee_id).single().execute().data
    cumuls = _cumuls_precedents(employee_id, year, month)
    try:
        base = _generer(employee_id, year, month, cumuls)
    except HTTPException as exc:
        if exc.status_code not in (400, 422):
            raise
        rapport.append({"salarie": employee_id, "ok": True, "cas": "bulletin de départ refusé", "saute": True})
        return
    data0 = base["payslip_data"]
    lignes0 = lignes_corrigeables(data0)
    for ligne in lignes0:
        if ligne.code is None:
            _noter(rapport, employee_id, False, cas="type de ligne non couvert", libelle=ligne.libelle)
    _doublons_du_bulletin_enregistre(rapport, employee_id, enregistre, data0)
    periode = {"employee_id": employee_id, "company_id": company_id, "year": year, "month": month}
    dsn0, residu0, totaux0, cotisations0 = _montants_dsn(data0), _residu(data0, employee), _totaux(data0), _lignes_par_code(data0)
    familles: set[str] = set()
    mois_suivant_verifie = False
    for ligne in lignes0:
        if not ligne.code or not ligne.mode:
            continue
        doublon = "#" in ligne.code
        if famille_du_code(ligne.code) in familles and not doublon:
            continue
        familles.add(famille_du_code(ligne.code))
        try:
            correction = _correction_pour(ligne)
        except CorrectionInvalide as exc:
            _noter(rapport, employee_id, False, code=ligne.code, correction_impossible=str(exc))
            continue
        saisie = {**correction.saisie_du_mois(periode), "id": "theoreme-ligne"}
        try:
            res = _generer(employee_id, year, month, cumuls, (saisie,))
        except HTTPException as exc:
            _noter(rapport, employee_id, False, code=ligne.code, refus=str(exc.detail)[:300])
            continue
        data1 = res["payslip_data"]
        lignes1 = lignes_corrigeables(data1)
        apres = {l.code: l for l in lignes1}.get(ligne.code)
        attendu = _attendu(ligne, correction)
        totaux1 = _totaux(data1)
        constats = {
            "valeur_posee": _porte(apres, attendu),
            "valeur_de_martine": _garde_la_valeur_de_martine(ligne, apres),
            "brut_somme_des_lignes": abs(
                _ecart(totaux0["brut"], totaux1["brut"]) - _ecart(totaux0["somme_du_brut"], totaux1["somme_du_brut"])
            ) < 0.011,
            "copies": all(
                abs(_ecart(totaux0[a], totaux1[a]) - _ecart(totaux0[b], totaux1[b])) < 0.011
                for a, b in (
                    ("salarial", "salarial_officiel"),
                    ("salarial", "lignes_salariales"),
                    ("patronal", "patronal_officiel"),
                    ("patronal", "lignes_patronales"),
                )
            ),
            "residu": abs(_residu(data1, employee) - residu0) < 0.005,
            "rien_en_attente": not data1.get("corrections_en_attente"),
            **_cumuls_suivent(base, res, ligne, apres, cumuls),
        }
        if doublon:
            # La numérotation du calcul et celle du bulletin concordent : la
            # correction de « code#n » se pose sur la ligne que le bulletin lit
            # sous ce code, et sur elle seule.
            constats["doublon_a_sa_place"] = [l.code for l in lignes1 if l.correction] == [ligne.code]
        if ligne.bloc == BLOC_COTISATIONS and ligne.code in cotisations0 and apres is not None:
            constats["dsn"] = _dsn_suit_les_lignes(dsn0, _montants_dsn(data1), data0, data1)
        if ligne.bloc == BLOC_IMPOT:
            montant, taux, _assiette = _pas_details(data1)
            constats["dsn_impot"] = abs(montant - attendu["montant"]) < 0.005 and abs(taux - attendu["taux"]) < 1e-6
        if ligne.bloc == BLOC_BRUT and not mois_suivant_verifie:
            mois_suivant_verifie = True
            suivant = _le_mois_suivant_part_des_cumuls(employee_id, year, month, res)
            if suivant is not None:
                constats["mois_suivant"] = suivant
            else:
                constats["mois_suivant_non_calculable"] = True
        echec = [cle for cle, valeur in constats.items() if valeur is False]
        _noter(rapport, employee_id, not echec, code=ligne.code, doublon=doublon, echecs=echec, **constats)
    orpheline = CorrectionDeLigne(
        ligne="brut:ligne_disparue", libelle="Ligne disparue", motif="Test du théorème", montant=1.0
    )
    res = _generer(employee_id, year, month, cumuls, ({**orpheline.saisie_du_mois(periode), "id": "theoreme-orpheline"},))
    data1 = res["payslip_data"]
    constats = {
        "en_attente": [e.get("saisie_id") for e in data1.get("corrections_en_attente") or []] == ["theoreme-orpheline"],
        "validation_bloquee": MESSAGE_CORRECTION_EN_ATTENTE in raisons_de_ne_pas_valider(data1),
        "brut_inchange": abs(_ecart(data0.get("salaire_brut"), data1.get("salaire_brut"))) < 0.005,
    }
    _noter(rapport, employee_id, all(constats.values()), cas="correction orpheline", **constats)


def main(societe: str, year: int, month: int, sortie: str, partie: str = "tout") -> int:
    if partie not in ("tout", "regularisations", "directes"):
        raise SystemExit("partie : tout, regularisations ou directes")
    company = supabase.table("companies").select("id").eq("company_name", societe).single().execute().data
    bulletins = (
        supabase.table("payslips")
        .select("employee_id, payslip_data")
        .match({"company_id": company["id"], "year": year, "month": month})
        .execute()
        .data
    )
    rapport: list[dict] = []
    for bulletin in bulletins:
        employee_id = bulletin["employee_id"]
        print(f"salarie {employee_id[:8]}", flush=True)
        try:
            with lecture_seule():
                if partie in ("tout", "regularisations"):
                    _un_salarie(company["id"], employee_id, year, month, rapport)
                if partie in ("tout", "directes"):
                    _corrections_directes(
                        company["id"], employee_id, year, month, rapport, bulletin.get("payslip_data")
                    )
        except Exception as exc:  # noqa: BLE001 — une erreur d'un salarié n'arrête pas la société ; elle compte en échec
            _noter(
                rapport,
                employee_id,
                False,
                cas="exception",
                erreur=f"{type(exc).__name__}: {exc}"[:500],
                trace=traceback.format_exc()[-2000:],
            )
        # Le rapport s'écrit au fil de l'eau : un arrêt en route garde ce qui est fait.
        with open(sortie, "w", encoding="utf-8") as fichier:
            json.dump(rapport, fichier, ensure_ascii=False, indent=1)
    echecs = sum(1 for cas in rapport if not cas["ok"])
    with open(sortie, "w", encoding="utf-8") as fichier:
        json.dump(rapport, fichier, ensure_ascii=False, indent=1)
    print(f"{len(rapport)} cas, {echecs} échec(s)", flush=True)
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], *(sys.argv[5:6])))
