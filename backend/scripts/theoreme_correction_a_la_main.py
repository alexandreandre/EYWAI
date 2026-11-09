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

Un test sans cas n'est pas vert : une société sans salarié joué, ou dont tous
les salariés sont sautés, sort en échec (code 1). Les salariés se lisent sur la
fiche, pas sur les bulletins : un mois sans bulletin se joue aussi. Un mois
repris de l'ancien logiciel, que l'écran refuse de corriger, est refusé (code 2).

Chaque correction est confrontée à une valeur attendue calculée à part du
moteur (taux du bulletin de départ, formules du registre) : cotisations, net
imposable, impôt, net, assiettes DSN, cumuls, compteurs. Une erreur injectée
(`theoreme_mutants.py`) doit faire rougir au moins un de ces constats.

Le rapport JSON reste hors du dépôt. Depuis backend/ :

    PYTHONPATH=. .venv/bin/python scripts/theoreme_correction_a_la_main.py "<Société>" 2026 9 <sortie.json> [tout|regularisations|directes]
"""

from __future__ import annotations

import copy
import json
import sys
import traceback

sys.path.insert(0, "scripts/verification_rgdu")
sys.path.insert(0, "scripts")
from piege import poser_le_piege  # noqa: E402

poser_le_piege()

from fastapi import HTTPException  # noqa: E402

from app.core.database import supabase  # noqa: E402
from app.core.lecture_seule import lecture_seule  # noqa: E402
from app.modules.dsn_export.domain.cotisation_mapping import (  # noqa: E402
    COTI_ID_EXONERATION_JEI,
    COTI_ID_EXONERES_JEI,
    REGLES,
    _exoneration_jei_totale,
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
    blocs_a_la_source,
    lignes_corrigeables,
)
from app.modules.payroll.engine.corrections_manuelles import CorrectionDeLigne, CorrectionInvalide  # noqa: E402
from app.modules.payslips.domain.anomalies_bulletin import anomalies_du_bulletin  # noqa: E402
from app.modules.payslips.domain.coherence import (  # noqa: E402
    MESSAGE_CORRECTION_EN_ATTENTE,
    raisons_de_ne_pas_valider,
)
from app.shared.reprise_paie import raison_de_blocage_avant_bascule  # noqa: E402
from theoreme_mutants import Mutant, revue_contre_les_erreurs  # noqa: E402
from theoreme_preuves import (  # noqa: E402
    attendus_apres_un_gain,
    bilan,
    compta_garde_les_patronales,
    constats_independants,
    cumuls_du_mois_suivant_a_verifier,
    salaries_a_jouer,
)

#: Mutant en cours (`theoreme_mutants`) : le test doit voir ce qu'il abîme.
_MUTANT: Mutant | None = None
_MOIS_JOUE: tuple[int, int] | None = None
_EFFETS: set[str] = set()
#: En mode mutants, un salarié se recalcule une seule fois par saisie : on rejoue les mutants sur la copie.
_CACHE: dict[str, dict] = {}
_CACHE_ACTIF = False


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


def _effet_si(avant: object, apres: object) -> None:
    """Le mutant en cours a changé quelque chose : un constat doit rougir."""
    if _MUTANT is not None and json.dumps(avant, sort_keys=True, default=str) != json.dumps(apres, sort_keys=True, default=str):
        _EFFETS.add(_MUTANT.nom)


def _lignes(payslip_data: dict) -> list[dict]:
    return [
        ligne
        for rubrique in payslip_data.get("cotisations_officielles") or []
        for ligne in rubrique.get("lignes") or []
    ]


def _dsn(payslip_data: dict):
    """Les blocs 78 et 81 du bulletin, tels que le mapping DSN les construit."""
    if _MUTANT is not None and _MUTANT.donnees_dsn is not None:
        mutee = _MUTANT.donnees_dsn(payslip_data)
        _effet_si(_lignes(payslip_data), _lignes(mutee))
        payslip_data = mutee
    return build_bases_and_cotisations(
        _lignes(payslip_data),
        brut=float(payslip_data.get("salaire_brut") or 0),
        period_start="2026-01-01",
        period_end="2026-01-31",
    )


def _montants_dsn(payslip_data: dict) -> dict[str, float]:
    _, cotisations, _ = _dsn(payslip_data)
    sortie: dict[str, float] = {}
    for cotisation in cotisations:
        sortie[cotisation.code] = round(sortie.get(cotisation.code, 0.0) + float(cotisation.montant_patronal or 0), 2)
    return sortie


def _bases_dsn(payslip_data: dict, saisies: tuple = ()) -> dict[str, float]:
    bases, _, _ = _dsn(payslip_data)
    sortie = {base.code: round(float(base.montant or 0.0), 2) for base in bases}
    if _MUTANT is not None and _MUTANT.bases_dsn is not None:
        mutees = _MUTANT.bases_dsn(sortie, {"saisies": list(saisies)})
        _effet_si(sortie, mutees)
        return mutees
    return sortie


def _avertissements_dsn(payslip_data: dict) -> list[str]:
    return _dsn(payslip_data)[2]


def _jei_totale(payslip_data: dict) -> bool:
    return _exoneration_jei_totale(_lignes(payslip_data), [])


def _jei_partielle_signalee(payslip_data: dict) -> bool:
    """La DSN repasse aux cotisations pleines : elle le dit, ou il n'y a plus aucune exonération."""
    plus_d_exoneration = not any(float(l.get("montant_patronal") or 0.0) for l in _lignes(payslip_data) if l.get("coti_id") == COTI_ID_EXONERATION_JEI)
    return plus_d_exoneration or any("Exonération JEI partielle" in message for message in _avertissements_dsn(payslip_data))


def _dsn_a_bouge(
    avant: dict[str, float],
    apres: dict[str, float],
    ligne: dict,
    salarial: float,
    patronal: float,
    exoneres_jei: frozenset | set = frozenset(),
) -> bool:
    """La somme des codes DSN bouge du montant de la régularisation.

    Agirc-Arrco déclare le total sur le code 131 et redéclare la part patronale
    sur 142 ou 146. Les deux bougent, donc la somme bouge du total plus cette part.
    Une cotisation que la DSN individuelle ne traduit pas (l'exonération apprenti)
    ne doit pas non plus apparaître via sa régularisation ; de même une part
    patronale couverte par une exonération JEI totale (code 014, montant nul).
    """
    ecart = round(sum(apres.values()) - sum(avant.values()), 2)
    if not _traduire(ligne, 0.0, 0.0, 0.0) or ligne.get("coti_id") in exoneres_jei:
        return abs(ecart) <= 0.02
    attendu = round(salarial + patronal, 2)
    regle = REGLES.get(str(ligne.get("coti_id") or ""))
    if regle is not None and regle.code_patronal:
        attendu = round(attendu + patronal, 2)
    return abs(ecart - attendu) <= 0.02


def _indemnites_suivies(payslip_data: dict, sauf_famille: str = "") -> float:
    """Primes que le moteur recalcule à partir du brut : précarité, IFM, congés de CDD.

    `sauf_famille` : la famille qu'on vient de corriger elle-même, dont le
    mouvement est déjà compté par la correction.
    """
    total = 0.0
    for ligne in payslip_data.get("calcul_du_brut") or []:
        if not isinstance(ligne, dict):
            continue
        libelle = str(ligne.get("libelle") or "").lower()
        if sauf_famille not in ("brut:precarite", "brut:ifm") and ("précarité" in libelle or "precarite" in libelle or "fin de mission" in libelle):
            total += float(ligne.get("gain") or 0)
    for ligne in payslip_data.get("details_conges") or []:
        if not isinstance(ligne, dict):
            continue
        libelle = str(ligne.get("libelle") or "").lower()
        if sauf_famille != "brut:iccp" and ("indemnité compensatrice" in libelle or "indemnite compensatrice" in libelle):
            total += float(ligne.get("gain") or 0)
    return round(total, 2)


def _ligne_od(payslip_data: dict, employee: dict) -> dict:
    ligne = ligne_od_du_bulletin(
        payslip_id="theoreme",
        employee=employee,
        payslip_data=payslip_data,
        saisies_du_salarie=[],
        compte_de_saisie=lambda _type: "421000",
    )
    if _MUTANT is not None and _MUTANT.ligne_od is not None:
        mutee = _MUTANT.ligne_od(ligne)
        _effet_si(ligne, mutee)
        return mutee
    return ligne


def _residu(payslip_data: dict, employee: dict) -> float:
    return residu_du_bulletin(_ligne_od(payslip_data, employee))


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


def _motif_du_refus(exc: HTTPException) -> str:
    """La cause d'un bulletin refusé, sans reprendre le message (il peut nommer le salarié)."""
    if "plus présent" in str(exc.detail):
        return "sorti avant le mois"
    return f"autre refus ({exc.status_code})"


def _generer_moteur(employee_id: str, year: int, month: int, cumuls: dict | None, saisies_en_plus: tuple = ()):
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


def _depuis_le_cache(employee_id: str, year: int, month: int, cumuls: dict | None, saisies_en_plus: tuple) -> dict:
    cle = json.dumps([employee_id, year, month, cumuls, list(saisies_en_plus)], sort_keys=True, default=str)
    if cle not in _CACHE:
        _CACHE[cle] = _generer_moteur(employee_id, year, month, cumuls, saisies_en_plus)
    return copy.deepcopy(_CACHE[cle])


def _generer(employee_id: str, year: int, month: int, cumuls: dict | None, saisies_en_plus: tuple = ()):
    """Le calcul, éventuellement abîmé par le mutant en cours (jamais la base)."""
    if not _CACHE_ACTIF and _MUTANT is None:
        return _generer_moteur(employee_id, year, month, cumuls, saisies_en_plus)
    res = _depuis_le_cache(employee_id, year, month, cumuls, saisies_en_plus)
    if _MUTANT is None or _MUTANT.bulletin is None:
        return res
    avant = copy.deepcopy(res)
    _MUTANT.bulletin(
        res,
        {
            "saisies": list(saisies_en_plus),
            "bulletin_sans_correction": _depuis_le_cache(employee_id, year, month, cumuls, ()),
            "mois_suivant": _MOIS_JOUE is not None and (year, month) != _MOIS_JOUE,
        },
    )
    _effet_si(avant, res)
    return res


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
        rapport.append({"salarie": employee_id, "ok": True, "cas": "bulletin de départ refusé", "saute": True, "cause": _motif_du_refus(exc)})
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
        if _jei_totale(data0) and not _jei_totale(data1):
            # La régularisation dépasse l'exonération : la DSN repasse aux cotisations pleines et doit le dire.
            constats["dsn"] = _jei_partielle_signalee(data1)
        else:
            exoneres = COTI_ID_EXONERES_JEI if _jei_totale(data1) else frozenset()
            constats["dsn"] = _dsn_a_bouge(_montants_dsn(data0), _montants_dsn(data1), ligne, salarial, patronal, exoneres)
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
    jei = _jei_totale(data0) and _jei_totale(data1)
    for code in set(avant) | set(apres):
        l0, l1 = avant.get(code) or {}, apres.get(code) or {}
        # La ligne d'avant dit si la DSN la traduit : à zéro, la ligne corrigée n'y paraît plus.
        ligne = l0 or l1
        salarial = _ecart(l0.get("montant_salarial"), l1.get("montant_salarial"))
        patronal = _ecart(l0.get("montant_patronal"), l1.get("montant_patronal"))
        if not (salarial or patronal) or not _traduire(ligne, 0.0, 0.0, 0.0):
            continue
        if jei and ligne.get("coti_id") in COTI_ID_EXONERES_JEI:
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


#: Une fois par famille et par société : une valeur nulle, une grande (franchit un plafond), une négative.
_VARIANTES_JOUEES: set[str] = set()


def _variantes_de_valeur(ligne: LigneCorrigeable) -> list[tuple[str, CorrectionDeLigne]]:
    commun = dict(ligne=ligne.code, libelle=ligne.libelle, motif="Test du théorème")
    if ligne.mode == MODE_TAUX:
        return [("zero", CorrectionDeLigne(**commun, taux=0.0)), ("grande", CorrectionDeLigne(**commun, taux=43.0))]
    if ligne.bloc == BLOC_BRUT:
        if ligne.mode == MODE_BASE_OU_TAUX:
            return [
                ("zero", CorrectionDeLigne(**commun, base=0.0)),
                ("grande", CorrectionDeLigne(**commun, base=round(float(ligne.base or 0.0) + 300.0, 2))),
            ]
        variantes = [
            ("zero", CorrectionDeLigne(**commun, montant=0.0)),
            ("grande", CorrectionDeLigne(**commun, montant=round(float(ligne.montant or 0.0) + 6000.0, 2))),
        ]
        if famille_du_code(ligne.code) != "brut:salaire_base":
            # Sur la ligne principale, le brut deviendrait négatif : le moteur le ramène à zéro et la revue (B02) bloque.
            variantes.append(("negative", CorrectionDeLigne(**commun, montant=-50.0)))
        return variantes
    if famille_du_code(ligne.code) == "cotisation:reduction_generale":
        return []
    if ligne.mode == MODE_BASE_OU_TAUX:
        return [
            ("zero", CorrectionDeLigne(**commun, base=0.0)),
            ("grande", CorrectionDeLigne(**commun, base=round(float(ligne.base or 0.0) + 6000.0, 2))),
        ]
    champ = "montant_patronal" if ligne.montant_patronal else "montant_salarial"
    return [
        ("zero", CorrectionDeLigne(**commun, **{champ: 0.0})),
        ("negative", CorrectionDeLigne(**commun, **{champ: round(-abs(float(getattr(ligne, champ) or 0.0)) - 5.0, 2)})),
    ]


def _delta_heures(ligne: LigneCorrigeable, correction: CorrectionDeLigne) -> float:
    if ligne.mode == MODE_BASE_OU_TAUX and correction.base is not None:
        return round(float(correction.base) - float(ligne.base or 0.0), 2)
    return 0.0


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


def _mouvement_du_gain(ligne: LigneCorrigeable, attendu: dict[str, float]) -> float:
    """Ce que la correction fait bouger au brut : le montant voulu moins le montant d'avant, en signe de brut."""
    apres = float(attendu["montant"])
    avant = float(ligne.montant or 0.0)
    return round(-(apres - avant) if ligne.retenue else apres - avant, 2)


def _assiette_csg_suit(bases0: dict[str, float], bases1: dict[str, float], ligne: LigneCorrigeable, correction: CorrectionDeLigne) -> bool | None:
    """Corriger la CSG ne double pas l'assiette en DSN : l'assiette 04 bouge au plus de la base corrigée."""
    if "04" not in bases0 or "04" not in bases1 or correction.base is None:
        return None
    return abs(_ecart(bases0["04"], bases1["04"])) <= abs(float(correction.base) - float(ligne.base or 0.0)) + 0.02


def _solde_conges(data: dict) -> object:
    return (data.get("pied_de_page") or {}).get("solde_conges")


def _cout_employeur(data: dict) -> float:
    return float((data.get("pied_de_page") or {}).get("cout_total_employeur") or 0.0)


def _alertes_de_revue(data: dict) -> set[tuple[str, str]]:
    """Les alertes de la revue, sans celle qui dit justement qu'une ligne a été corrigée (B07)."""
    return {(a.rule_id, str(a.field)) for a in anomalies_du_bulletin(data) if a.rule_id != "B07"}


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
    base: dict,
    res: dict,
    ligne: LigneCorrigeable,
    apres: LigneCorrigeable | None,
    cumuls: dict | None = None,
    delta_heures: float = 1.0,
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
    if _cumul(base, "brut_annee_civile") or _cumul(res, "brut_annee_civile"):
        constats["cumul_brut_annee"] = (
            abs(mouvement("brut_annee_civile") - _ecart(data0.get("salaire_brut"), data1.get("salaire_brut"))) < 0.011
        )
    famille = famille_du_code(ligne.code)
    if famille == "cotisation:reduction_generale" and apres is not None:
        constats["cumul_reduction"] = abs(
            mouvement("reduction_generale_patronale") - _ecart(ligne.montant_patronal, apres.montant_patronal)
        ) < 0.011
    if ligne.mode == MODE_BASE_OU_TAUX and famille in HEURES_SUIVIES and "forfait" not in ligne.libelle.lower():
        for cle in HEURES_SUIVIES[famille]:
            if _ecart(_cumul({"cumuls": cumuls or {}}, cle), _cumul(base, cle)) > 0.005:
                if delta_heures <= -float(ligne.base or 0.0) + 1e-6 and abs(mouvement(cle)) < 0.011:
                    # Défaut connu : base corrigée à zéro, le cumul d'heures n'en sort pas
                    # (`resultat_brut["heures_base_remunerees"] or heures du contrat`).
                    # Voir test_corriger_la_base_a_zero_retire_les_heures_du_smic.
                    constats[f"defaut_connu_cumul_{cle}_base_a_zero"] = True
                    continue
                constats[f"cumul_{cle}"] = abs(mouvement(cle) - delta_heures) < 0.011
            else:
                # Mois sans heure rémunérée (arrêt non maintenu ou absence sur
                # tout le mois) : le moteur borne les heures du mois à zéro, et
                # une heure de base en plus peut rester sous la borne.
                constats[f"cumul_{cle}_borne_a_zero"] = -0.011 < mouvement(cle) < delta_heures + 0.011
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
    return all(
        abs((_cumul(suivant, cle) - valeur) - _cumul(res, cle)) < 0.011
        for cle, valeur in cumuls_du_mois_suivant_a_verifier(suivant["payslip_data"]).items()
    )


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
    if enregistre is None:
        return  # Pas de bulletin enregistré ce mois-ci : rien à comparer.
    stockes, calcules = _doublons(enregistre), _doublons(data0)
    if not stockes and not calcules:
        return
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
        rapport.append({"salarie": employee_id, "ok": True, "cas": "bulletin de départ refusé", "saute": True, "cause": _motif_du_refus(exc)})
        return
    data0 = base["payslip_data"]
    lignes0 = lignes_corrigeables(data0)
    for ligne in lignes0:
        if ligne.code is None:
            _noter(rapport, employee_id, False, cas="type de ligne non couvert", libelle=ligne.libelle)
    _doublons_du_bulletin_enregistre(rapport, employee_id, enregistre, data0)
    periode = {"employee_id": employee_id, "company_id": company_id, "year": year, "month": month}
    dsn0, residu0, totaux0, cotisations0 = _montants_dsn(data0), _residu(data0, employee), _totaux(data0), _lignes_par_code(data0)
    bases0 = _bases_dsn(data0)
    alertes0 = _alertes_de_revue(data0)
    familles: set[str] = set()
    mois_suivant_verifie = False
    blocs = blocs_a_la_source(data0)
    rapport.append({"salarie": employee_id, "ok": True, "cas": "blocs à la source", "blocs": [b["libelle"] for b in blocs], "information": True})

    def _jouer_la_correction(ligne: LigneCorrigeable, correction: CorrectionDeLigne, variante: str | None = None) -> None:
        nonlocal mois_suivant_verifie
        doublon = "#" in str(ligne.code)
        code_note = {"code": ligne.code, "doublon": doublon, **({"variante": variante} if variante else {})}
        saisie = {**correction.saisie_du_mois(periode), "id": "theoreme-ligne"}
        try:
            res = _generer(employee_id, year, month, cumuls, (saisie,))
        except HTTPException as exc:
            # Refus du recalcul : une correction extrême n'est pas toujours calculable (règle 9).
            _noter(rapport, employee_id, variante is not None and exc.status_code in (400, 422), **code_note, refus=str(exc.detail)[:300])
            return
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
            "residu_nul": abs(_residu(data1, employee)) < 0.015,
            "compta_patronales": compta_garde_les_patronales(_ligne_od(data1, employee)),
            "rien_en_attente": not data1.get("corrections_en_attente"),
            **_cumuls_suivent(
            base,
            res,
            ligne,
            apres,
            cumuls,
            delta_heures=_delta_heures(ligne, correction),
        ),
            **(constats_independants(data0, data1, bloc=ligne.bloc, famille=famille_du_code(ligne.code), res0=base, res1=res) if variante is None else {}),
            "compteurs_inchanges": _solde_conges(data0) == _solde_conges(data1),
            "cout_employeur_suit": abs(
                _ecart(_cout_employeur(data0), _cout_employeur(data1)) - (_ecart(totaux0["brut"], totaux1["brut"]) + _ecart(totaux0["patronal"], totaux1["patronal"]))
            ) < 0.021,
            "revue_sans_alerte": not (_alertes_de_revue(data1) - alertes0),
        }
        if doublon:
            # La numérotation du calcul et celle du bulletin concordent : la
            # correction de « code#n » se pose sur la ligne que le bulletin lit
            # sous ce code, et sur elle seule.
            constats["doublon_a_sa_place"] = [l.code for l in lignes1 if l.correction] == [ligne.code]
        if ligne.bloc == BLOC_COTISATIONS and ligne.code in cotisations0 and apres is not None:
            if _jei_totale(data0) and not _jei_totale(data1):
                # La correction dépasse l'exonération : DSN aux cotisations pleines, et elle doit le dire.
                constats["dsn"] = _jei_partielle_signalee(data1)
            else:
                constats["dsn"] = _dsn_suit_les_lignes(dsn0, _montants_dsn(data1), data0, data1)
            if "csg" in str(ligne.code):
                constats["dsn_assiettes"] = _assiette_csg_suit(bases0, _bases_dsn(data1, (saisie,)), ligne, correction)
        if ligne.bloc == BLOC_BRUT:
            if variante is None:
                # Les variantes (zéro, grande, négative) franchissent plafonds et planchers :
                # elles vérifient la pose, les copies, les cumuls et le résidu, pas ces valeurs.
                constats.update(
                    attendus_apres_un_gain(
                        data0,
                        data1,
                        _mouvement_du_gain(ligne, attendu),
                        famille=famille_du_code(ligne.code),
                        delta_indemnites=_ecart(
                            _indemnites_suivies(data0, famille_du_code(ligne.code)),
                            _indemnites_suivies(data1, famille_du_code(ligne.code)),
                        ),
                    )
                )
            bases1 = _bases_dsn(data1, (saisie,))
            if "03" in bases0 and "03" in bases1 and float(data1.get("salaire_brut") or 0.0) > 0:
                constats["dsn_assiettes"] = abs(
                    _ecart(bases0["03"], bases1["03"]) - _ecart(data0.get("salaire_brut"), data1.get("salaire_brut"))
                ) < 0.011
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
        _noter(rapport, employee_id, not echec, **code_note, echecs=echec, **constats)

    for ligne in lignes0:
        if not ligne.code or not ligne.mode:
            continue
        doublon = "#" in ligne.code
        famille = famille_du_code(ligne.code)
        if famille in familles and not doublon:
            continue
        familles.add(famille)
        try:
            correction = _correction_pour(ligne)
        except CorrectionInvalide as exc:
            _noter(rapport, employee_id, False, code=ligne.code, correction_impossible=str(exc))
            continue
        _jouer_la_correction(ligne, correction)
        # En mode mutants (cache actif) : pas de variantes de valeur, seules les corrections principales se rejouent.
        if not _CACHE_ACTIF and famille not in _VARIANTES_JOUEES and not doublon:
            _VARIANTES_JOUEES.add(famille)
            for variante, autre in _variantes_de_valeur(ligne):
                _jouer_la_correction(ligne, autre, variante)
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


def _constats_rouges(rapport: list[dict]) -> set[str]:
    rouges: set[str] = set()
    for cas in rapport:
        if cas.get("ok"):
            continue
        rouges.update(cas.get("echecs") or [])
        rouges.update(cle for cle, valeur in cas.items() if valeur is False and cle not in ("ok", "doublon", "saute"))
        if not cas.get("echecs"):
            rouges.add(str(cas.get("cas") or cas.get("coti_id") or cas.get("code") or "échec"))
    return rouges


def jouer_mutants(
    company_id: str, employee_id: str, year: int, month: int, mutants: tuple[Mutant, ...], *, avec_regularisations: bool = True
) -> dict:
    """Rejoue un salarié sous chaque erreur injectée : chaque injection doit faire rougir au moins un constat.

    Le salarié se calcule une fois par saisie (cache) ; les mutants n'agissent que
    sur la copie rendue au test. Un mutant sans effet (salarié sans la ligne visée)
    est compté à part, avec le constat qu'il attendait.
    """
    global _MUTANT, _MOIS_JOUE, _CACHE_ACTIF
    _MUTANT, _MOIS_JOUE, _CACHE_ACTIF = None, (year, month), True
    _CACHE.clear()
    try:
        with lecture_seule():
            propre: list[dict] = []
            if avec_regularisations:
                _un_salarie(company_id, employee_id, year, month, propre)
            _corrections_directes(company_id, employee_id, year, month, propre)
            reference = _constats_rouges(propre)
            base = _depuis_le_cache(employee_id, year, month, _cumuls_precedents(employee_id, year, month), ())
            revue = revue_contre_les_erreurs(base["payslip_data"], anomalies_du_bulletin)
            resultats: dict[str, dict] = {}
            for mutant in mutants:
                _MUTANT = mutant
                _EFFETS.clear()
                rapport: list[dict] = []
                try:
                    if avec_regularisations:
                        _un_salarie(company_id, employee_id, year, month, rapport)
                    _corrections_directes(company_id, employee_id, year, month, rapport)
                except Exception as exc:  # noqa: BLE001 — un mutant qui casse le calcul se voit aussi
                    rapport.append({"ok": False, "cas": f"exception {type(exc).__name__}", "salarie": employee_id})
                finally:
                    _MUTANT = None
                rouges = _constats_rouges(rapport) - reference
                resultats[mutant.nom] = {
                    "quoi": mutant.quoi,
                    "sans_effet_si": mutant.sans_effet_si,
                    "effet": mutant.nom in _EFFETS,
                    "rouges": sorted(rouges),
                    "attendus_vus": sorted(rouges & mutant.constats),
                    "cas": len(rapport),
                    "verdict": "vu" if rouges else ("sans effet" if mutant.nom not in _EFFETS else "NON VU"),
                }
    finally:
        _MUTANT, _MOIS_JOUE, _CACHE_ACTIF = None, None, False
        _CACHE.clear()
    return {
        "salarie": employee_id[:8],
        "cas_de_reference": len(propre),
        "rouges_sans_mutant": sorted(reference),
        "mutants": resultats,
        "revue": revue,
    }


def main(societe: str, year: int, month: int, sortie: str, partie: str = "tout", tranche: tuple[int, int] = (0, 1)) -> int:
    if partie not in ("tout", "regularisations", "directes"):
        raise SystemExit("partie : tout, regularisations ou directes")
    company = supabase.table("companies").select("id").eq("company_name", societe).single().execute().data
    # Un mois repris de l'ancien logiciel ne se corrige pas à l'écran : le jouer
    # ne prouverait rien sur ce que Gaëlle peut faire (R-178).
    refus = raison_de_blocage_avant_bascule(company["id"], year, month)
    if refus:
        print(f"MOIS NON CORRIGEABLE : {refus}", flush=True)
        return 2
    employes = supabase.table("employees").select("*").eq("company_id", company["id"]).execute().data
    enregistres = {
        str(ligne["employee_id"]): ligne.get("payslip_data")
        for ligne in supabase.table("payslips")
        .select("employee_id, payslip_data")
        .match({"company_id": company["id"], "year": year, "month": month})
        .execute()
        .data
    }
    rapport: list[dict] = []
    numero, tranches = tranche
    jouer = [e for rang, e in enumerate(sorted(salaries_a_jouer(employes, year, month), key=lambda e: str(e["id"]))) if rang % tranches == numero]
    for employe in jouer:
        employee_id = employe["id"]
        print(f"salarie {employee_id[:8]}", flush=True)
        try:
            with lecture_seule():
                if partie in ("tout", "regularisations"):
                    _un_salarie(company["id"], employee_id, year, month, rapport)
                if partie in ("tout", "directes"):
                    _corrections_directes(
                        company["id"], employee_id, year, month, rapport, enregistres.get(str(employee_id))
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
    with open(sortie, "w", encoding="utf-8") as fichier:
        json.dump(rapport, fichier, ensure_ascii=False, indent=1)
    resultat = bilan(rapport)
    print(resultat.phrase, flush=True)
    return resultat.code


if __name__ == "__main__":
    arguments = sys.argv[5:6] if len(sys.argv) > 5 else []
    tranche = tuple(int(x) for x in sys.argv[6].split("/")) if len(sys.argv) > 6 else (0, 1)
    sys.exit(main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], *(arguments or ["tout"]), tranche))
