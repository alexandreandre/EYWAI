"""Reprise Colorplast : importe littéralement les bulletins de janvier à juin 2026.

Les mois payés dans Quadra ne se reconstruisent pas, ils se copient. L'interface
affiche le PDF stocké à côté des cumuls, donc la copie la plus fidèle possible
consiste à découper les PDF de Gaëlle par salarié et à les servir tels quels :
ses libellés, ses codes, sa mise en page. Rien n'est réinterprété par notre
moteur, et Gaëlle reconnaît ses propres documents.

Les données de bulletin (`payslips.payslip_data`) restent celles de notre rejeu,
à quatre exceptions copiées du PDF pour que les listes, les cumuls et les
compteurs affichés ne contredisent pas le document servi : `salaire_brut`,
`net_a_payer`, le bloc `cumuls` et les soldes de congés du pied de page — ces
derniers sont posés à la génération et un mois importé ne se régénère plus, donc
sans cette copie la case resterait vide ou porterait un recalcul depuis nos
absences. Les autres sections ne sont plus affichées mais restent lues en aval
(base du dixième des congés, contingent d'heures sup, provision comptable,
attestations) : elles sont marquées comme non reprises dans `payslip_data`.

Chaque bulletin importé porte `origine = 'importe'`. Le verrou de génération, lui,
vient de la bascule de la société (cf. app/shared/reprise_paie.py).

Usage :
    python -m scripts.reprise_colorplast_import_litteral            # simulation
    python -m scripts.reprise_colorplast_import_litteral --apply    # écrit
"""

from __future__ import annotations

import calendar
import io
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyPDF2 import PdfReader, PdfWriter  # noqa: E402

from app.core.database import get_supabase_admin_client, supabase  # noqa: E402
from app.modules.absences.domain.rules import (  # noqa: E402
    get_cp_previous_reference_period,
    get_cp_reference_period,
)
from scripts.backtest.colorplast_lignes_quadra import (  # noqa: E402
    lire_bulletins,
    pdf_du_mois,
)

COMPANY_ID = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"
ANNEE = 2026
MOIS_REPRIS = (1, 2, 3, 4, 5, 6)
SEAU = "payslips"
#: La période de congés ouvre le 1er juin chez Colorplast (company_leave_settings).
DEBUT_PERIODE_CP = 6

#: Ce que l'on copie du PDF dans `payslip_data`, à la place de notre rejeu.
SECTIONS_COPIEES_DU_PDF = ("salaire_brut", "net_a_payer", "cumuls", "solde_conges")

#: Sections de `payslip_data` qui restent issues de notre rejeu, pas du PDF.
SECTIONS_NON_REPRISES = (
    "calcul_du_brut",
    "cotisations_officielles",
    "structure_cotisations",
    "details_absences",
    "details_conges",
    "details_maintien",
    "synthese_net",
)


def _cle(nom: str) -> str:
    return nom.upper().replace(" ", "").replace("-", "")


def _fiches(admin) -> dict[str, dict]:
    lignes = (
        admin.table("employees")
        .select("id, last_name, first_name, employee_folder_name")
        .eq("company_id", COMPANY_ID)
        .execute()
        .data
    )
    return {_cle(str(e["last_name"])): e for e in lignes}


def _fiche_du_matricule(fiches: dict[str, dict], matricule: str) -> dict | None:
    """Apparie un matricule Quadra à une fiche, en tolérant la troncature.

    Quadra tronque le matricule à dix caractères : DA SILVA CARDOSO y figure en
    « DASILVACAR ». Le préfixe suffit donc, mais seulement s'il ne désigne qu'une
    seule fiche — en cas d'ambiguïté on préfère ne rien importer.
    """
    if matricule in fiches:
        return fiches[matricule]
    candidats = [f for cle, f in fiches.items() if cle.startswith(matricule)]
    return candidats[0] if len(candidats) == 1 else None


def _pages_du_salarie(pdf: Path, pages: list[int]) -> bytes:
    """Un PDF ne contenant que les pages de ce salarié, dans l'ordre du bulletin."""
    lecteur = PdfReader(str(pdf))
    ecrivain = PdfWriter()
    for numero in pages:
        ecrivain.add_page(lecteur.pages[numero - 1])
    tampon = io.BytesIO()
    ecrivain.write(tampon)
    return tampon.getvalue()


def _cumuls_affiches(bulletin) -> dict:
    """Le bloc de cumuls tel que Quadra l'imprime, pour l'afficher sans le recalculer."""
    return {
        "brut_total": bulletin.droite.get("cumul_bruts"),
        "net_imposable": bulletin.net.get("net_imposable_cumul"),
        "impot_preleve_a_la_source": bulletin.net.get("pas_cumul"),
        "heures_remunerees": bulletin.droite.get("cumul_heures"),
        "heures_supplementaires_remunerees": bulletin.droite.get("cumul_hs"),
        "montant_net_hs_exonerees_cumul": bulletin.net.get("net_hs_exo_cumul"),
    }


def _brut_du_mois(bulletin) -> float:
    for lg in bulletin.lignes:
        if lg.libelle.strip().upper() == "SALAIRE BRUT" and lg.gain is not None:
            return round(lg.gain, 2)
    return 0.0


def _compteurs_affiches(bulletin, annee: int, mois: int) -> dict | None:
    """Le bloc « CP N-1 / CP N » tel que Quadra l'imprime, dans la forme du pied de page.

    Même forme que `get_absence_balances_for_payslip`, pour que le rendu du
    bulletin le lise sans rien savoir de la reprise. Quadra n'imprime rien
    d'autre — « Solde rep.remp. » et « Solde rep.récup. » sont vides sur tous les
    bulletins —, on ne fabrique donc ni RTT ni repos : la question des compteurs
    de repos reste posée à Gaëlle.
    """
    if not bulletin.cp:
        return None
    _, dernier_jour = calendar.monthrange(annee, mois)
    reference = date(annee, mois, dernier_jour)

    def _colonne(indice: int, bornes: tuple[date, date]) -> dict:
        debut, fin = bornes
        return {
            "acquis": bulletin.cp.get("Acquis", (0.0, 0.0))[indice],
            "pris": bulletin.cp.get("Total pris", (0.0, 0.0))[indice],
            "solde": bulletin.cp.get("Solde", (0.0, 0.0))[indice],
            "periode": f"{debut:%d/%m/%Y} – {fin:%d/%m/%Y}",
        }

    return {
        "date_reference": f"{reference:%d/%m/%Y}",
        "conges_payes_periode_precedente": _colonne(
            0, get_cp_previous_reference_period(reference, start_month=DEBUT_PERIODE_CP)
        ),
        "conges_payes": _colonne(
            1, get_cp_reference_period(reference, start_month=DEBUT_PERIODE_CP)
        ),
    }


def _donnees_reprises(existantes: dict | None, bulletin, annee: int, mois: int) -> dict:
    """Le `payslip_data` du bulletin importé : notre rejeu, sauf ce qui vient du PDF."""
    donnees = dict(existantes or {})
    donnees["salaire_brut"] = _brut_du_mois(bulletin)
    donnees["net_a_payer"] = float(bulletin.net.get("net_a_payer") or 0.0)
    donnees["cumuls"] = _cumuls_affiches(bulletin)
    pied_de_page = dict(donnees.get("pied_de_page") or {})
    pied_de_page["solde_conges"] = _compteurs_affiches(bulletin, annee, mois)
    donnees["pied_de_page"] = pied_de_page
    donnees["reprise"] = {
        "logiciel_precedent": "Quadra",
        "document": "PDF d'origine, pages " + ",".join(str(p) for p in bulletin.pages),
        "sections_copiees_du_pdf": list(SECTIONS_COPIEES_DU_PDF),
        "sections_non_reprises": list(SECTIONS_NON_REPRISES),
        "avertissement": (
            "Bulletin repris de Quadra. Le document affiché est l'original ; "
            "les sections de détail ci-dessus viennent de notre recalcul et ne "
            "font pas foi."
        ),
    }
    return donnees


def main(appliquer: bool) -> int:
    admin = get_supabase_admin_client()
    fiches = _fiches(admin)
    total, crees, manquants = 0, 0, []

    for mois in MOIS_REPRIS:
        pdf = pdf_du_mois(ANNEE, mois)
        bulletins = lire_bulletins(ANNEE, mois)
        print(f"\n=== {mois:02d}/{ANNEE} — {pdf.name} — {len(bulletins)} bulletins")
        for nom, bulletin in sorted(bulletins.items()):
            fiche = _fiche_du_matricule(fiches, nom)
            if not fiche:
                manquants.append(f"{nom} {mois:02d}/{ANNEE}")
                print(f"  {nom:12s} !! aucune fiche unique dans la base, ignoré")
                continue
            brut = _brut_du_mois(bulletin)
            net = bulletin.net.get("net_a_payer")
            pages = ",".join(str(p) for p in bulletin.pages)
            existant = (
                admin.table("payslips")
                .select("id, payslip_data, pdf_storage_path")
                .eq("employee_id", fiche["id"])
                .eq("year", ANNEE)
                .eq("month", mois)
                .limit(1)
                .execute()
                .data
            )
            etat = "remplace" if existant else "CRÉE"
            solde_n1, solde_n = bulletin.cp.get("Solde", (0.0, 0.0))
            print(
                f"  {nom:12s} pages {pages:7s} brut {brut:9.2f} net {net or 0:9.2f}"
                f"  CP N-1 {solde_n1:6.2f}  N {solde_n:5.2f}  [{etat}]"
            )
            total += 1
            if not existant:
                crees += 1
            if not appliquer:
                continue

            nom_pdf = f"Bulletin_{fiche['employee_folder_name']}_{mois:02d}-{ANNEE}.pdf"
            chemin = f"{COMPANY_ID}/{fiche['id']}/bulletins/{nom_pdf}"
            supabase.storage.from_(SEAU).upload(
                path=chemin,
                file=_pages_du_salarie(pdf, bulletin.pages),
                file_options={"x-upsert": "true", "content-type": "application/pdf"},
            )
            url = supabase.storage.from_(SEAU).create_signed_url(
                chemin, 3600, options={"download": True}
            )["signedURL"]

            donnees = _donnees_reprises(
                existant[0].get("payslip_data") if existant else None,
                bulletin,
                ANNEE,
                mois,
            )
            charge = {
                "employee_id": fiche["id"],
                "company_id": COMPANY_ID,
                "year": ANNEE,
                "month": mois,
                "name": nom_pdf,
                "payslip_data": donnees,
                "pdf_storage_path": chemin,
                "url": url,
                "origine": "importe",
            }
            admin.table("payslips").upsert(
                charge, on_conflict="company_id,employee_id,year,month"
            ).execute()

    print(f"\n{total} bulletins, dont {crees} à créer.")
    if manquants:
        print("Sans fiche en base : " + ", ".join(manquants))
    if not appliquer:
        print("Simulation. Relancer avec --apply pour importer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--apply" in sys.argv))
