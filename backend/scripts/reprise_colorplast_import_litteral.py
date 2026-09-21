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
SECTIONS_COPIEES_DU_PDF = (
    "salaire_brut",
    "net_a_payer",
    "cumuls",
    "solde_conges",
    "calcul_du_brut",
    "synthese_net",
    "cotisations (rassises sur le brut du PDF)",
)

#: Sections de `payslip_data` qui restent issues de notre rejeu, pas du PDF.
SECTIONS_NON_REPRISES = (
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


def _cumuls_affiches(bulletin, annee: int, mois: int) -> dict:
    """Le bloc de cumuls tel que Quadra l'imprime, dans la forme du moteur.

    Forme imbriquée `{"cumuls": {...}, "periode": {...}}` : c'est celle que la
    vue du bulletin et tout l'aval lisent. Écrit à plat (jusqu'au 21/09/2026),
    le bloc existait mais personne ne le voyait, et la colonne de droite des
    bulletins repris restait vide.
    """
    return {
        "cumuls": {
            "brut_total": bulletin.droite.get("cumul_bruts"),
            "net_imposable": bulletin.net.get("net_imposable_cumul"),
            "impot_preleve_a_la_source": bulletin.net.get("pas_cumul"),
            "heures_remunerees": bulletin.droite.get("cumul_heures"),
            "heures_supplementaires_remunerees": bulletin.droite.get("cumul_hs"),
            "montant_net_hs_exonerees_cumul": bulletin.net.get("net_hs_exo_cumul"),
        },
        "periode": {"annee_en_cours": annee, "dernier_mois_calcule": mois},
        "reprise": {
            "source": "bulletin PDF Quadra",
            "fait_foi": True,
            "logiciel_precedent": "Quadra",
        },
    }


#: Libellés Quadra rendus dans notre vocabulaire : l'aval reconnaît les heures
#: sup par leur libellé (contingent, repos compensateur, comparaison N/N-1).
_LIBELLES_GAIN = {
    "SALAIRE DE BASE": "Salaire de base",
    "H. SUPP MAJORÉES À 25 %": "Heures suppl. structurelles majorées à 25%",
    "SOUS TOTAL SALAIRE DE BASE": "SOUS-TOTAL SALAIRE CONTRACTUEL",
    "HEURES SUPPLÉMENTAIRES 25": "Heures suppl. majorées à 25%",
    "HEURES SUPPLÉMENTAIRES 50": "Heures suppl. majorées à 50%",
}
#: Mêmes libellés en retenue : une « H. supp majorées à 25 % » qui retire du
#: salaire est la réduction des heures structurelles des jours d'absence.
_LIBELLES_PERTE = {
    "H. SUPP MAJORÉES À 25 %": "Réduction HS structurelles (jours d'absence)",
}


def _normaliser(libelle: str) -> str:
    return " ".join(str(libelle or "").split()).upper()


def _lignes_du_brut(bulletin) -> list[dict]:
    """Les lignes de la zone brut du PDF, dans la forme de `calcul_du_brut`.

    S'arrête à « SALAIRE BRUT » : tout ce qui suit est cotisation ou net. Un
    gain devient un gain, une retenue (colonne salariale dans cette zone)
    devient une perte.
    """
    lignes: list[dict] = []
    for lg in bulletin.lignes:
        libelle_norme = _normaliser(lg.libelle)
        if libelle_norme == "SALAIRE BRUT":
            break
        if lg.section:  # une cotisation d'une page suivante
            continue
        if lg.gain is None and lg.montant_sal is None:
            continue  # ligne de mention (entrée, sortie, solde de tout compte)
        if libelle_norme.startswith("CONGÉS PAYÉS :") or libelle_norme.startswith("CONGES PAYES :"):
            # Entête du bloc « CP N-1 / CP N » : Quadra réimprime le même
            # montant en ligne de paie « ARBITRAGE DES CONGES PAYES ».
            continue
        if lg.gain is not None:
            libelle = _LIBELLES_GAIN.get(libelle_norme, str(lg.libelle).strip())
            lignes.append(
                {
                    "libelle": libelle,
                    "quantite": lg.base,
                    "taux": lg.taux,
                    "gain": round(float(lg.gain), 2),
                    "perte": None,
                    **({"is_sous_total": True} if "SOUS-TOTAL" in libelle.upper() else {}),
                }
            )
            continue
        lignes.append(
            {
                "libelle": _LIBELLES_PERTE.get(libelle_norme, str(lg.libelle).strip()),
                "quantite": lg.base,
                "taux": lg.taux,
                "gain": None,
                "perte": round(float(lg.montant_sal), 2),
            }
        )
    return lignes


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


def _base_dominante(groupes: list) -> float:
    """La base sur laquelle les cotisations sont assises : la plus fréquente.

    C'est le brut qui a servi au calcul. On la lit dans les cotisations plutôt
    que dans `salaire_brut` : rejouer l'import ne doit pas dépendre de ce que
    le passage précédent a déjà écrit.
    """
    compte: dict[float, int] = {}
    for groupe in groupes:
        for ligne in (groupe or {}).get("lignes") or []:
            base = ligne.get("base") if isinstance(ligne, dict) else None
            if isinstance(base, (int, float)) and base > 0:
                arrondie = round(float(base), 2)
                compte[arrondie] = compte.get(arrondie, 0) + 1
    if not compte:
        return 0.0
    return max(compte.items(), key=lambda kv: (kv[1], kv[0]))[0]


def _asseoir_les_cotisations(groupes: list | None, nouveau_brut: float) -> list:
    """Rassoit les cotisations du rejeu sur le brut du PDF.

    Nos taux et notre structure sont justes ; seule la base était celle du
    rejeu. Remettre la base et recalculer redonne les montants de Quadra, y
    compris là où il regroupe plusieurs de nos lignes en une seule (tranche 1
    et CEG imprimées ensemble). Une ligne dont la base n'est pas le brut
    (mutuelle au forfait) n'est pas touchée : elle ne suit pas le salaire.
    """
    if not isinstance(groupes, list) or nouveau_brut <= 0:
        return groupes if isinstance(groupes, list) else []
    ancien_brut = _base_dominante(groupes)
    if ancien_brut <= 0 or abs(nouveau_brut - ancien_brut) < 0.005:
        return groupes

    sortie = []
    for groupe in groupes:
        if not isinstance(groupe, dict):
            sortie.append(groupe)
            continue
        neuf = dict(groupe)
        lignes = []
        for ligne in groupe.get("lignes") or []:
            if not isinstance(ligne, dict) or abs(
                float(ligne.get("base") or 0.0) - ancien_brut
            ) > 0.005:
                lignes.append(ligne)
                continue
            assise = dict(ligne)
            assise["base"] = nouveau_brut
            for taux, montant in (
                ("taux_patronal", "montant_patronal"),
                ("taux_salarial", "montant_salarial"),
            ):
                if assise.get(taux) is not None:
                    assise[montant] = round(nouveau_brut * float(assise[taux]), 2)
            lignes.append(assise)
        neuf["lignes"] = lignes
        for champ, cle in (
            ("total_patronal", "montant_patronal"),
            ("total_salarial", "montant_salarial"),
        ):
            if champ in groupe:
                neuf[champ] = round(
                    float(groupe.get(champ) or 0.0)
                    + _ecart_des_montants(groupe.get("lignes") or [], lignes, cle),
                    2,
                )
        sortie.append(neuf)
    return sortie


def _rasseoir_ligne(ligne: dict, ancien_brut: float, nouveau_brut: float) -> dict:
    """Une ligne assise sur le brut du rejeu : base et montants refaits.

    Seules les lignes dont le montant est bien « base × taux » sont refaites.
    Une ligne dont le montant sort d'une formule (réduction générale) ou d'un
    autre calcul garde ses valeurs : la recalculer au taux affiché donnerait
    un montant faux (Bugny juin : 584,81 au lieu de 552,97).
    """
    if not isinstance(ligne, dict) or abs(float(ligne.get("base") or 0.0) - ancien_brut) > 0.005:
        return ligne
    assise = dict(ligne)
    refaite = False
    for taux, montant in (
        ("taux_patronal", "montant_patronal"),
        ("taux_salarial", "montant_salarial"),
    ):
        valeur, courant = assise.get(taux), assise.get(montant)
        if valeur is None or courant is None:
            continue
        if abs(float(courant) - ancien_brut * float(valeur)) > 0.011:
            return ligne  # pas un produit : formule, plafond, barème
        assise[montant] = round(nouveau_brut * float(valeur), 2)
        refaite = True
    if not refaite:
        return ligne
    assise["base"] = nouveau_brut
    return assise


def _ecart_des_montants(avant: list, apres: list, cle: str) -> float:
    """Ce que le rassoiement a ajouté ou retiré, pour ajuster un total sans
    présumer de la convention de signe de ce total."""
    somme = 0.0
    for ancienne, neuve in zip(avant, apres):
        if isinstance(ancienne, dict) and isinstance(neuve, dict):
            somme += float(neuve.get(cle) or 0.0) - float(ancienne.get(cle) or 0.0)
    return round(somme, 2)


def _asseoir_la_structure(structure: dict | None, nouveau_brut: float) -> dict:
    """Rassoit les blocs imprimés (`structure_cotisations`) sur le brut du PDF.

    Même règle que les cotisations : seules les lignes assises sur le brut du
    rejeu sont refaites ; une base propre (CSG, allègements calculés sur les
    heures sup) n'est pas touchée. Les totaux suivent les lignes.
    """
    if not isinstance(structure, dict) or nouveau_brut <= 0:
        return structure if isinstance(structure, dict) else {}
    lignes_plates = list(structure.get("bloc_principales") or [])
    lignes_plates += list(structure.get("bloc_allegements") or [])
    lignes_plates += list(structure.get("bloc_csg_non_deductible") or [])
    lignes_plates += list((structure.get("bloc_autres_contributions") or {}).get("lignes") or [])
    ancien_brut = _base_dominante([{"lignes": lignes_plates}])
    if ancien_brut <= 0 or abs(nouveau_brut - ancien_brut) < 0.005:
        return structure

    neuve = dict(structure)
    for bloc in ("bloc_principales", "bloc_allegements", "bloc_csg_non_deductible"):
        if isinstance(structure.get(bloc), list):
            neuve[bloc] = [
                _rasseoir_ligne(x, ancien_brut, nouveau_brut) for x in structure[bloc]
            ]
    autres = structure.get("bloc_autres_contributions")
    if isinstance(autres, dict):
        lignes = [
            _rasseoir_ligne(x, ancien_brut, nouveau_brut) for x in (autres.get("lignes") or [])
        ]
        neuf = dict(autres)
        neuf["lignes"] = lignes
        if "total" in autres:
            neuf["total"] = round(
                float(autres.get("total") or 0.0)
                + _ecart_des_montants(autres.get("lignes") or [], lignes, "montant_patronal"),
                2,
            )
        neuve["bloc_autres_contributions"] = neuf

    for champ, cle in (
        ("total_patronal", "montant_patronal"),
        ("total_salarial", "montant_salarial"),
    ):
        if champ not in structure:
            continue
        delta = 0.0
        for bloc in ("bloc_principales", "bloc_allegements", "bloc_csg_non_deductible"):
            delta += _ecart_des_montants(
                structure.get(bloc) or [], neuve.get(bloc) or [], cle
            )
        delta += _ecart_des_montants(
            (structure.get("bloc_autres_contributions") or {}).get("lignes") or [],
            (neuve.get("bloc_autres_contributions") or {}).get("lignes") or [],
            cle,
        )
        neuve[champ] = round(float(structure.get(champ) or 0.0) + delta, 2)
    return neuve


#: Cotisations dont le montant ne se déduit pas du brut : elles se copient du
#: PDF, une à une. Libellé Quadra (début, normalisé) → notre `coti_id`, et le
#: champ de montant concerné.
_COTISATIONS_DU_PDF = (
    ("CSG DÉDUCTIBLE À L'IR", "csg_deductible", "montant_salarial"),
    ("CSG/CRDS NON DÉDUCTIBLE À L'IR", "csg_non_deductible", "montant_salarial"),
    ("EXO., ECRET. ET ALLEG. COTIS", "reduction_generale", "montant_patronal"),
    ("REDUCTION SALARIALE HS/HC", "reduction_hs_salariale", "montant_salarial"),
    ("REDUCT HEURES SUPPL.", "deduction_hs_patronale", "montant_patronal"),
)


def _lignes_de_cotisation_du_pdf(bulletin) -> dict[str, dict]:
    """Les cotisations du PDF à copier, par `coti_id`, dans l'ordre du document.

    Quadra imprime deux fois « CSG/CRDS non déductible à l'IR » (la part
    normale et celle des heures sup) : les montants sont rendus dans l'ordre,
    pour être appariés à nos deux lignes dans le même ordre.
    """
    trouvees: dict[str, dict] = {}
    for lg in bulletin.lignes:
        libelle = _normaliser(lg.libelle)
        if libelle == "SALAIRE BRUT":
            continue
        for debut, coti_id, champ in _COTISATIONS_DU_PDF:
            if not libelle.startswith(debut):
                continue
            montant = lg.montant_sal if champ == "montant_salarial" else lg.montant_pat
            if montant is None:
                continue
            entree = trouvees.setdefault(coti_id, {"champ": champ, "bases": [], "montants": []})
            entree["bases"].append(lg.base)
            entree["montants"].append(abs(float(montant)))
            break
    return trouvees


def _copier_une_cotisation(ligne: dict, lues: dict, rang: int) -> dict:
    """Écrit la base et le montant du PDF dans une ligne, sans changer son signe."""
    if rang >= len(lues["montants"]):
        return ligne
    champ = lues["champ"]
    courant = float(ligne.get(champ) or 0.0)
    signe = -1.0 if courant < 0 else 1.0
    copie = dict(ligne)
    copie[champ] = round(signe * lues["montants"][rang], 2)
    base = lues["bases"][rang]
    if base is not None:
        copie["base"] = round(float(base), 2)
    return copie


def _copier_les_cotisations_du_pdf(structure: dict | None, bulletin) -> dict:
    """Copie dans les blocs imprimés les cotisations que le brut ne donne pas.

    CSG, réduction générale, allègements sur heures sup : leur montant sort
    d'une base propre ou d'une formule. Le PDF les imprime, on les prend.
    """
    if not isinstance(structure, dict):
        return structure if isinstance(structure, dict) else {}
    lues = _lignes_de_cotisation_du_pdf(bulletin)
    if not lues:
        return structure

    neuve = dict(structure)
    rangs: dict[str, int] = {}
    for bloc in ("bloc_principales", "bloc_allegements", "bloc_csg_non_deductible"):
        if not isinstance(structure.get(bloc), list):
            continue
        lignes = []
        for ligne in structure[bloc]:
            coti_id = (ligne or {}).get("coti_id")
            if coti_id in lues:
                rang = rangs.get(coti_id, 0)
                rangs[coti_id] = rang + 1
                lignes.append(_copier_une_cotisation(ligne, lues[coti_id], rang))
            else:
                lignes.append(ligne)
        neuve[bloc] = lignes

    for champ, cle in (
        ("total_patronal", "montant_patronal"),
        ("total_salarial", "montant_salarial"),
    ):
        if champ not in structure:
            continue
        delta = 0.0
        for bloc in ("bloc_principales", "bloc_allegements", "bloc_csg_non_deductible"):
            delta += _ecart_des_montants(
                structure.get(bloc) or [], neuve.get(bloc) or [], cle
            )
        neuve[champ] = round(float(structure.get(champ) or 0.0) + delta, 2)
    return neuve


def _pied_de_page_du_pdf(existant: dict, bulletin) -> dict:
    """L'allègement du mois et le total versé employeur, imprimés par Quadra.

    Ce sont des agrégats : les recomposer depuis nos lignes ne redonne pas son
    périmètre. La colonne de droite du PDF les donne, on les prend.
    """
    pied = dict(existant or {})
    droite = getattr(bulletin, "droite", None) or {}
    if droite.get("allegement_mois") is not None:
        pied["total_allegements_patronaux"] = round(abs(float(droite["allegement_mois"])), 2)
    if droite.get("verse_employeur") is not None:
        pied["cout_total_employeur"] = round(float(droite["verse_employeur"]), 2)
    return pied


def _synthese_du_pdf(existantes: dict, bulletin) -> dict:
    """Les nets imprimés par Quadra, copiés dans la synthèse du bulletin."""
    synthese = dict(existantes.get("synthese_net") or {})
    net = getattr(bulletin, "net", None) or {}
    correspondances = (
        ("net_imposable", "net_imposable"),
        ("montant_net_social", "mns"),
        ("net_social_avant_impot", "mns"),
        ("montant_net_hs_exonerees", "net_hs_exo"),
    )
    for chez_nous, chez_quadra in correspondances:
        if net.get(chez_quadra) is not None:
            synthese[chez_nous] = float(net[chez_quadra])
    if net.get("pas_montant") is not None:
        synthese["impot_prelevement_a_la_source"] = {
            "base": net.get("pas_base"),
            "taux": net.get("pas_taux"),
            "montant": net.get("pas_montant"),
        }
    return synthese


def _donnees_reprises(existantes: dict | None, bulletin, annee: int, mois: int) -> dict:
    """Le `payslip_data` du bulletin importé : notre rejeu, sauf ce qui vient du PDF."""
    donnees = dict(existantes or {})
    donnees["salaire_brut"] = _brut_du_mois(bulletin)
    donnees["cotisations_officielles"] = _asseoir_les_cotisations(
        donnees.get("cotisations_officielles"), donnees["salaire_brut"]
    )
    donnees["structure_cotisations"] = _copier_les_cotisations_du_pdf(
        _asseoir_la_structure(donnees.get("structure_cotisations"), donnees["salaire_brut"]),
        bulletin,
    )
    donnees["synthese_net"] = _synthese_du_pdf(donnees, bulletin)
    donnees["net_a_payer"] = float(bulletin.net.get("net_a_payer") or 0.0)
    donnees["cumuls"] = _cumuls_affiches(bulletin, annee, mois)
    donnees["calcul_du_brut"] = _lignes_du_brut(bulletin)
    # Les absences et congés du PDF sont dans les lignes ci-dessus : garder en
    # plus celles du rejeu les compterait deux fois.
    donnees["details_absences"] = []
    donnees["details_conges"] = []
    pied_de_page = _pied_de_page_du_pdf(donnees.get("pied_de_page") or {}, bulletin)
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
