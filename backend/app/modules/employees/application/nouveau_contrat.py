"""« Nouveau contrat » d'un salarié parti : aperçu pour le dialogue, puis enregistrement.

Trois écritures, dans cet ordre, pour que rien ne reste à moitié fait :
1. la fiche bascule sur le nouveau contrat, sous condition qu'elle n'ait pas
   changé depuis la lecture (un double clic ou un autre onglet ne passe pas) ;
2. le contrat précédent est rangé dans les contrats passés ; si cela échoue, la
   fiche revient à son état d'avant ;
3. le salaire passe par l'historique daté (comme l'onglet Augmentations) ; si
   cela échoue, le contrat reste enregistré et la réponse dit où saisir le salaire.

Un nouveau contrat qui commence le mois où le précédent finit : ce mois a deux
bulletins [D3]. Juste après le rangement, son bulletin et ses variables passent
au contrat rangé (`ranger_mois_partage`) ; si ce marquage échoue, le contrat
rangé est retiré et la fiche revient à son état d'avant.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core.database import supabase
from app.core.logging import get_logger
from app.modules.employees.application.commands import apply_salary_update
from app.modules.employees.application.contract_periods import (
    ContractPeriodIn,
    add_contract_period,
)
from app.modules.employees.application.queries import get_employee_by_id
from app.modules.employees.domain.nouveau_contrat import (
    TYPES_DE_CONTRAT,
    Demande,
    contrat_precedent,
    date_anciennete,
    ecritures,
    fiche_rangee,
    meme_mois,
    message_de_succes,
    premier_jour_possible,
    raison_du_refus,
    raison_indisponible,
    valeur_salaire,
)
from app.shared.reprise_paie import lire_bascule

logger = get_logger(__name__)

COLONNES_FICHE = (
    "id, company_id, employment_status, hire_date, date_debut_execution, "
    "date_conclusion_contrat, contract_type, contract_end_date, seniority_reference_date, "
    "duree_hebdomadaire, is_temps_partiel, job_title, salaire_de_base, current_exit_id, "
    "specificites_paie, classification_conventionnelle"
)


class NouveauContratRefuse(ValueError):
    """La demande ne peut pas être enregistrée (→ 400). Rien n'est écrit."""


class FicheModifiee(RuntimeError):
    """La fiche a changé depuis la lecture (→ 409). Rien n'est écrit."""


class NonEnregistre(RuntimeError):
    """Une écriture a échoué (→ 500) ; le message dit l'état laissé."""


class NouveauContratIn(BaseModel):
    date_debut: date
    contract_type: str = Field(min_length=1, max_length=40)
    date_fin: date | None = None
    duree_hebdomadaire: float
    salaire_mensuel: float
    job_title: str | None = Field(default=None, max_length=200)
    reprendre_anciennete: bool = False

    @field_validator("contract_type")
    @classmethod
    def _type_nettoye(cls, valeur: str) -> str:
        return valeur.strip()


def _jj_mm_aaaa(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _mm_aaaa(d: date) -> str:
    return d.strftime("%m/%Y")


def _euros(montant: float) -> str:
    return f"{montant:,.2f}".replace(",", " ").replace(".", ",")


def _lire(employee_id: str, company_id: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    fiches = (
        supabase.table("employees")
        .select(COLONNES_FICHE)
        .eq("id", employee_id)
        .eq("company_id", company_id)
        .limit(1)
        .execute()
        .data
    )
    if not fiches:
        raise NouveauContratRefuse("Salarié introuvable dans cette société.")
    departs = (
        supabase.table("employee_exits")
        .select("id, last_working_day, status")
        .eq("employee_id", employee_id)
        .eq("company_id", company_id)
        .neq("status", "annulee")
        .order("last_working_day", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return dict(fiches[0]), (dict(departs[0]) if departs else None)


def _bulletin_existe(employee_id: str, annee: int, mois: int) -> bool:
    lignes = (
        supabase.table("payslips")
        .select("id")
        .eq("employee_id", employee_id)
        .eq("year", annee)
        .eq("month", mois)
        .limit(1)
        .execute()
        .data
    )
    return bool(lignes)


def _effets_par_mois(employee_id: str, annee: int, mois: int) -> bool:
    """Le bulletin du mois a appliqué du CET ou crédité de la modulation : ces
    effets se défont par (salarié, mois), pas par bulletin."""
    cet = (
        supabase.table("employee_cet_movements")
        .select("id")
        .eq("employee_id", employee_id)
        .eq("year", annee)
        .eq("month", mois)
        .eq("status", "applied_payroll")
        .limit(1)
        .execute()
        .data
    )
    if cet:
        return True
    modulation = (
        supabase.table("employee_modulation_movements")
        .select("id")
        .eq("employee_id", employee_id)
        .eq("year", annee)
        .eq("month", mois)
        .eq("movement_type", "credit_hs")
        .eq("source", "payroll_auto")
        .limit(1)
        .execute()
        .data
    )
    return bool(modulation)


def _rendre_la_fiche(employee_id: str, company_id: str, fiche: dict, nouvelle_fiche: dict) -> bool:
    """Remet la fiche dans son état d'avant ; False si la remise a échoué."""
    avant = {cle: fiche.get(cle) for cle in nouvelle_fiche}
    try:
        return bool(
            supabase.table("employees")
            .update(avant)
            .eq("id", employee_id)
            .eq("company_id", company_id)
            .execute()
            .data
        )
    except Exception:  # noqa: BLE001 — sans retour, le message dit l'état laissé
        return False


def apercu(employee_id: str, company_id: str) -> dict[str, Any]:
    """Ce que le dialogue affiche : possible ou pourquoi pas, contrat précédent, champs préremplis."""
    fiche, depart = _lire(employee_id, company_id)
    precedent = contrat_precedent(fiche, depart)
    raison = raison_indisponible(fiche, precedent)
    type_actuel = str(fiche.get("contract_type") or "").strip()
    try:
        duree = float(fiche.get("duree_hebdomadaire") or 0) or None
    except (TypeError, ValueError):
        duree = None
    anciennete = fiche.get("seniority_reference_date") or (
        precedent.debut.isoformat() if precedent else None
    )
    return {
        "possible": raison is None,
        "raison": raison,
        "contrat_precedent": (
            {
                "contract_type": precedent.contract_type,
                "date_debut": precedent.debut.isoformat(),
                "date_fin": precedent.fin.isoformat(),
            }
            if precedent
            else None
        ),
        "premier_jour_possible": premier_jour_possible(precedent).isoformat() if precedent else None,
        "date_anciennete": str(anciennete)[:10] if anciennete else None,
        "prerempli": {
            "contract_type": type_actuel if type_actuel in TYPES_DE_CONTRAT else "CDD",
            "duree_hebdomadaire": duree,
            "salaire_mensuel": valeur_salaire(fiche.get("salaire_de_base")),
            "job_title": fiche.get("job_title"),
        },
        "types": list(TYPES_DE_CONTRAT),
    }


def creer(
    employee_id: str, company_id: str, corps: NouveauContratIn, user_id: str
) -> dict[str, Any]:
    """Enregistre le nouveau contrat ; lève NouveauContratRefuse, FicheModifiee ou NonEnregistre."""
    fiche, depart = _lire(employee_id, company_id)
    precedent = contrat_precedent(fiche, depart)
    demande = Demande(
        date_debut=corps.date_debut,
        contract_type=corps.contract_type,
        date_fin=corps.date_fin,
        duree_hebdomadaire=float(corps.duree_hebdomadaire),
        salaire_mensuel=float(corps.salaire_mensuel),
        job_title=corps.job_title,
        reprendre_anciennete=corps.reprendre_anciennete,
    )
    bascule = lire_bascule(company_id)
    raison = raison_du_refus(
        fiche,
        precedent,
        demande,
        bulletin_du_dernier_mois=(
            _bulletin_existe(employee_id, precedent.fin.year, precedent.fin.month)
            if precedent
            else False
        ),
        rang_de_bascule=bascule.rang if bascule else None,
        effets_par_mois=(
            precedent is not None
            and meme_mois(precedent, demande)
            and _effets_par_mois(employee_id, precedent.fin.year, precedent.fin.month)
        ),
    )
    if raison:
        raise NouveauContratRefuse(raison)
    assert precedent is not None
    periode, nouvelle_fiche, salaire = ecritures(fiche, precedent, demande)

    # 1. La fiche bascule, seulement si elle est encore celle qu'on a lue.
    basculee = (
        supabase.table("employees")
        .update(nouvelle_fiche)
        .eq("id", employee_id)
        .eq("company_id", company_id)
        .eq("employment_status", fiche.get("employment_status"))
        .eq("hire_date", fiche.get("hire_date"))
        .execute()
        .data
    )
    if not basculee:
        raise FicheModifiee(
            "La fiche a changé pendant la saisie (un autre onglet, un double clic ?). "
            "Rechargez la page : rien n'a été enregistré."
        )

    # 2. Le contrat précédent est rangé ; sinon la fiche revient en arrière.
    try:
        ligne = add_contract_period(
            employee_id,
            company_id,
            ContractPeriodIn(
                contract_type=periode["contract_type"],
                date_debut=periode["date_debut"],
                date_fin=periode["date_fin"],
            ),
            fiche=fiche_rangee(fiche, nouvelle_fiche),
        )
    except Exception as exc:  # l'état laissé est dit dans le message
        logger.exception("Nouveau contrat : rangement du contrat précédent impossible")
        if _rendre_la_fiche(employee_id, company_id, fiche, nouvelle_fiche):
            raise NonEnregistre(
                "Le nouveau contrat n'a pas été enregistré : rien n'a changé sur la fiche. "
                "Réessayez dans un instant."
            ) from exc
        raise NonEnregistre(
            "La fiche porte le nouveau contrat, mais le contrat précédent n'a pas été rangé : "
            f"ajoutez-le dans les contrats passés : {precedent.contract_type} du "
            f"{_jj_mm_aaaa(precedent.debut)} au {_jj_mm_aaaa(precedent.fin)}."
        ) from exc

    # 2 bis. Mois partagé : son bulletin et ses variables vont au contrat rangé.
    # Sinon le premier bulletin du nouveau contrat remplacerait le sien [D3].
    if meme_mois(precedent, demande):
        try:
            supabase.rpc(
                "ranger_mois_partage",
                {
                    "p_period": ligne["id"],
                    "p_employee": employee_id,
                    "p_year": precedent.fin.year,
                    "p_month": precedent.fin.month,
                },
            ).execute()
        except Exception as exc:  # l'état laissé est dit dans le message
            logger.exception("Nouveau contrat : mois partagé non rangé")
            try:
                supabase.table("employee_contract_periods").delete().eq("id", ligne["id"]).execute()
                retire = True
            except Exception:  # noqa: BLE001 — le message dit l'état laissé
                retire = False
            if retire and _rendre_la_fiche(employee_id, company_id, fiche, nouvelle_fiche):
                raise NonEnregistre(
                    "Le nouveau contrat n'a pas été enregistré : rien n'a changé sur la fiche. "
                    "Réessayez dans un instant."
                ) from exc
            raise NonEnregistre(
                f"Le nouveau contrat est enregistré, mais le bulletin de {_mm_aaaa(precedent.fin)} "
                "n'est pas rangé avec le contrat précédent. Ne générez pas le bulletin du "
                "nouveau contrat pour ce mois : contactez le support."
            ) from exc

    # 3. Le salaire, daté du début du nouveau contrat.
    avertissements: list[str] = []
    if salaire:
        try:
            apply_salary_update(
                employee_id,
                company_id,
                salaire["ancien_salaire"],
                salaire["nouveau_salaire"],
                salaire["motif"],
                salaire["effective_date"],
                user_id,
            )
        except Exception:  # le contrat est enregistré, la réponse le dit
            logger.exception("Nouveau contrat : historique de salaire non écrit")
            avertissements.append(
                "Le salaire n'a pas été mis à jour : saisissez "
                f"{_euros(demande.salaire_mensuel)} € dans l'onglet Augmentations, date "
                f"d'effet le {_jj_mm_aaaa(demande.date_debut)}."
            )

    return {
        "message": message_de_succes(precedent, demande),
        "avertissements": avertissements,
        "contrat_precedent": ligne,
        "date_anciennete": date_anciennete(fiche, precedent, demande).isoformat(),
        "employee": get_employee_by_id(employee_id, company_id),
    }
