"""Conformité de notre DSN face à celle réellement déposée par le cabinet.

Les entrées vivent hors dépôt (`data/_dsn_conformance/`, gitignoré) parce
qu'elles contiennent l'état civil et la paie de salariés réels. Sans elles les
tests se marquent `skipped` : la CI reste verte, l'exécution locale reste
complète. Pour les produire :

    python scripts/dsn_conformance_snapshot.py

Le chantier avance bloc par bloc. `BLOCS_LIVRES` liste ce qui est censé être
conforme aujourd'hui ; tout le reste est neutralisé. Un lot se clôt en ajoutant
ses blocs ici et en gardant les tests verts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from app.modules.dsn_export.application.builder import build_parsed_dsn_from_payroll
from app.modules.dsn_export.domain.conformance import EcartAttendu, comparer
from app.modules.dsn_export.domain.settings import depuis_dict
from app.modules.dsn_export.domain.writer import encode_dsn_bytes

FIXTURES = Path(__file__).resolve().parents[4] / "data" / "_dsn_conformance"

# Blocs dont la conformité est acquise. À étendre lot par lot.
BLOCS_LIVRES: List[str] = [
    "S10.G00.00",
    "S10.G00.01",
    "S20.G00.05",
    "S20.G00.07",
    "S21.G00.06",
    "S21.G00.11",
    "S21.G00.30",
    "S21.G00.40",
    "S90.G00.90",
]

# Rubriques vues dans les fichiers du cabinet dont la sémantique n'est pas
# établie de notre côté : on préfère ne pas les émettre plutôt que leur inventer
# une valeur. À trancher avec le cahier technique P26V01.
RUBRIQUES_A_DOCUMENTER: List[str] = [
    "S21.G00.30.013",
    "S21.G00.30.017",
    "S21.G00.30.025",
    "S21.G00.30.029",
    # .003 « Code statut catégoriel Retraite Complémentaire obligatoire » et .010
    # « Date de fin prévisionnelle du contrat » : leur sens est désormais établi
    # (note DGFiP, 07/08/2026), mais nous ne les produisons toujours pas. Ce ne
    # sont donc plus des rubriques à documenter — ce sont deux lacunes connues de
    # notre export. Le terme du CDD est en base depuis la correction de la
    # rubrique à l'import : il reste à le porter jusqu'au fichier produit.
    "S21.G00.40.003",
    "S21.G00.40.010",
    "S21.G00.40.021",
    "S21.G00.40.072",
]

# Les salariés sortis restent déclarés par le cabinet le mois de leur solde de
# tout compte ; nous ne les produisons pas encore (bloc S21.G00.62, lot 6).
# 32 individus concernés sur les cinq sociétés mesurées.
SORTANTS_TRAITES = False

# Tout ce qui n'est pas encore livré, neutralisé pour ne pas masquer les
# régressions sur ce qui l'est.
BLOCS_A_VENIR: List[str] = [
    "S10.G00.02",
    "S21.G00.15",
    "S21.G00.20",
    "S21.G00.22",
    "S21.G00.23",
    "S21.G00.31",
    "S21.G00.41",
    "S21.G00.44",
    "S21.G00.50",
    "S21.G00.51",
    "S21.G00.52",
    "S21.G00.53",
    "S21.G00.54",
    # Composant de versement : ventilation des paiements aux organismes par
    # population, trimestrielle — n'apparaît que sur les mois de fin de
    # trimestre (vu en juin, 2026T02). DSN-VAL n'en exige rien.
    "S21.G00.55",
    "S21.G00.58",
    "S21.G00.60",
    "S21.G00.62",
    "S21.G00.65",
    # Temps partiel thérapeutique : vu chez MBC en juin (un salarié).
    "S21.G00.66",
    "S21.G00.70",
    "S21.G00.71",
    "S21.G00.78",
    "S21.G00.79",
    "S21.G00.81",
    "S21.G00.85",
    "S21.G00.86",
]

ECARTS_ATTENDUS: List[EcartAttendu] = [
    EcartAttendu(
        rubrique="S10.G00.00.001",
        motif="nom du logiciel émetteur : EYWAI, pas Cegid",
        depuis="2026-08-03",
    ),
    EcartAttendu(
        rubrique="S10.G00.00.002",
        motif="éditeur du logiciel émetteur : EYWAI, pas Cegid",
        depuis="2026-08-03",
    ),
    EcartAttendu(
        rubrique="S10.G00.00.003",
        motif="version de notre logiciel, sans rapport avec celle du cabinet",
        depuis="2026-08-03",
    ),
    EcartAttendu(
        rubrique="S10.G00.00.008",
        motif="numéro d'ordre de l'envoi, propre à l'émetteur",
        depuis="2026-08-03",
    ),
    EcartAttendu(
        rubrique="S20.G00.05.007",
        motif="date de constitution du fichier : celle du jour où on le produit",
        depuis="2026-08-03",
    ),
    EcartAttendu(
        rubrique="S21.G00.06.004",
        motif="libellé d'adresse issu de notre fiche société, forme libre",
        depuis="2026-08-03",
    ),
    EcartAttendu(
        rubrique="S21.G00.11.003",
        motif="libellé d'adresse issu de notre fiche société, forme libre",
        depuis="2026-08-03",
    ),
    EcartAttendu(
        rubrique="S21.G00.30.002",
        motif="nom de famille en majuscules ; le cabinet écrit « De CARVALHO »",
        depuis="2026-08-03",
    ),
    # Écarts de données entre notre fiche et celle du cabinet, relevés le
    # 2026-08-03 sur Mont Blanc Composite. À arbitrer avec Elsa : tant que le
    # sujet n'est pas tranché, ils restent affichés à chaque rapport.
    EcartAttendu(
        rubrique="S21.G00.30.007",
        motif="typographie du lieu de naissance (3 salariés MBC)",
        depuis="2026-08-03",
    ),
    EcartAttendu(
        rubrique="S21.G00.30.008",
        motif="typographie de l'adresse du salarié",
        depuis="2026-08-03",
    ),
    EcartAttendu(
        rubrique="S21.G00.40.001",
        motif=(
            "date de début de contrat divergente pour 1 salarié MBC "
            "(02/05/2022 chez nous, 05/01/2026 au cabinet) : à arbitrer"
        ),
        depuis="2026-08-03",
    ),
    EcartAttendu(
        rubrique="S21.G00.40.006",
        motif=(
            "libellé d'emploi divergent pour 3 salariés MBC : notre fiche de "
            "poste et celle du cabinet ne disent pas la même chose"
        ),
        depuis="2026-08-03",
    ),
    EcartAttendu(
        rubrique="S21.G00.40.041",
        motif="niveau conventionnel divergent pour 2 salariés MBC : à arbitrer",
        depuis="2026-08-03",
    ),
    EcartAttendu(
        rubrique="S21.G00.40.004",
        motif=(
            "PCS d'un salarié MBC dégradé par le cabinet en juin : '625h' en "
            "mai (comme notre fiche), '9999' en juin — notre valeur est la bonne"
        ),
        depuis="2026-08-11",
    ),
    EcartAttendu(
        rubrique="S21.G00.30.016",
        motif="complément d'adresse du salarié, typographie de notre fiche",
        depuis="2026-08-03",
    ),
    EcartAttendu(
        rubrique="S21.G00.30.010",
        motif="typographie de la commune du salarié, issue de notre fiche",
        depuis="2026-08-03",
    ),
    EcartAttendu(
        rubrique="S21.G00.40.019",
        motif=(
            "rattachement multi-établissement non modélisé : 19 contrats Cartol "
            "dépendent du SIRET 798 171 096 00034 et non de celui de la société"
        ),
        depuis="2026-08-03",
    ),
    EcartAttendu(
        rubrique="S21.G00.40.013",
        motif="quotité arrondie au centième d'heure près sur quelques contrats",
        depuis="2026-08-03",
    ),
    EcartAttendu(
        rubrique="S21.G00.30.005",
        motif=(
            "sexe déduit du NIR : le cabinet déclare 8 salariés avec un sexe "
            "que leur propre NIR contredit"
        ),
        depuis="2026-08-03",
    ),
]


def instantanes() -> List[Tuple[str, str, Path]]:
    if not FIXTURES.exists():
        return []
    trouves = []
    for input_json in sorted(FIXTURES.glob("*/*/input.json")):
        repertoire = input_json.parent
        if (repertoire / "reference.dsn").exists():
            trouves.append((repertoire.parent.name, repertoire.name, repertoire))
    return trouves


INSTANTANES = instantanes()

besoin_de_fixtures = pytest.mark.skipif(
    not INSTANTANES,
    reason="instantanés absents : lancer scripts/dsn_conformance_snapshot.py",
)


def generer(donnees: Dict[str, Any]) -> bytes:
    fichier, _avertissements = build_parsed_dsn_from_payroll(
        donnees["company"],
        donnees["employees_data"],
        donnees["periode"],
        file_name=f"dsn_mensuelle_{donnees['periode'].replace('-', '_')}.dsn",
        settings=depuis_dict(donnees.get("dsn_settings")),
    )
    return encode_dsn_bytes(fichier)


@besoin_de_fixtures
@pytest.mark.parametrize(
    "societe,periode,repertoire",
    INSTANTANES,
    ids=[f"{s}-{p}" for s, p, _ in INSTANTANES],
)
def test_blocs_livres_sont_conformes(societe: str, periode: str, repertoire: Path):
    donnees = json.loads((repertoire / "input.json").read_text())
    rapport = comparer(
        generer(donnees),
        (repertoire / "reference.dsn").read_bytes(),
        ecarts_attendus=ECARTS_ATTENDUS,
        rubriques_hors_perimetre=BLOCS_A_VENIR + RUBRIQUES_A_DOCUMENTER,
        comparer_les_individus=SORTANTS_TRAITES,
    )
    assert rapport.conforme, f"{societe} {periode} :\n{rapport.texte()}"


# Écart résiduel des blocs cotisation, mesuré le 09/08/2026 sur les cinq
# instantanés de mai (157 salariés dont le brut est identique à celui du
# cabinet ; 68 autres écartés parce que leur brut diverge, ce qui relève du
# moteur de paie et non de la traduction DSN).
#
# Ces plafonds ne valident rien : ils empêchent que la situation empire pendant
# que les causes résiduelles se traitent une à une. Chaque baisse obtenue doit
# être répercutée ici, sinon le garde-fou se relâche.
#
# Ce qui reste, par cause :
#   - 100 lignes absentes : forfait social jamais calculé par le moteur (67),
#     CPF-CDD (13), CSG d'épargne salariale déclarée à part par le cabinet pour
#     10 salariés, exonérations d'apprentis (8).
#   - 617 montants divergents : dominés par la réduction générale, dont le
#     total lui-même diffère du cabinet pour 150 salariés sur 156. La
#     ventilation 018/106 est juste, c'est le montant calculé qui ne l'est pas.
#     Le +1 du 10/08 est un transfert, pas un recul : une cotisation 059 que le
#     moteur ne calcule pas encore (retraite supplémentaire) était une ligne
#     absente ; elle est désormais déclarée à 0,00 pour porter l'identifiant
#     d'affiliation qu'exige le validateur (CCH-13), et compte donc comme
#     montant divergent (99 absentes + 617 = l'ancien 100 + 616).
#
# 11/08 : le périmètre passe de cinq instantanés (mai) à dix (mai + juin) —
# juin, validé DSN-VAL à zéro comme mai, ajoute son propre résiduel moteur,
# mêmes causes (forfait social, CPF-CDD, réduction générale, apprentis).
# Mesuré le 11/08 : 174 absentes, 17 en trop, 1031 divergents, 23 taux.
# Les plafonds suivent la mesure ; à mai constant, la part de juin est
# 75 / 10 / 414 / 5 — toute baisse obtenue doit être répercutée ici.
PLAFOND_LIGNES_MANQUANTES = 174
PLAFOND_LIGNES_EN_TROP = 17
PLAFOND_MONTANTS_DIVERGENTS = 1031
PLAFOND_TAUX_DIVERGENTS = 23


@besoin_de_fixtures
def test_les_blocs_cotisation_ne_regressent_pas():
    """Garde-fou chiffré sur les blocs 78 et 81, encore hors périmètre livré.

    Le comparateur général perd l'appariement code/montant : il voit deux
    listes séparées. Ici chaque ligne est recomposée en `(base, code)` avant
    d'être confrontée, seule façon de voir qu'un montant a changé de code.
    """
    from scripts.dsn_cotisations_ecart import (  # import tardif : dépend de data/
        Compte,
        bruts,
        comparer_individu,
        lignes_cotisation,
        traiter,
    )

    compte = Compte()
    for _societe, _periode, repertoire in INSTANTANES:
        notre, reference, _ = traiter(repertoire)
        nos_lignes, leurs_lignes = lignes_cotisation(notre), lignes_cotisation(reference)
        nos_bruts, leurs_bruts = bruts(notre), bruts(reference)
        for nir in set(nos_lignes) & set(leurs_lignes):
            if abs(nos_bruts.get(nir, 0) - leurs_bruts.get(nir, 0)) > 0.01:
                continue  # écart de paie, pas de traduction
            compte.individus_compares += 1
            comparer_individu(nos_lignes[nir], leurs_lignes[nir], compte)

    assert compte.individus_compares > 0, "aucun salarié comparable"
    mesures = (
        ("lignes absentes", sum(compte.codes_manquants.values()), PLAFOND_LIGNES_MANQUANTES),
        ("lignes en trop", sum(compte.codes_en_trop.values()), PLAFOND_LIGNES_EN_TROP),
        ("montants divergents", sum(compte.montants.values()), PLAFOND_MONTANTS_DIVERGENTS),
        ("taux divergents", sum(compte.taux.values()), PLAFOND_TAUX_DIVERGENTS),
    )
    regressions = [f"{nom} : {mesure} > {plafond}" for nom, mesure, plafond in mesures if mesure > plafond]
    assert not regressions, (
        "la conformité des cotisations a reculé :\n  " + "\n  ".join(regressions)
    )


@besoin_de_fixtures
def test_aucun_bloc_oublie_entre_livres_et_a_venir():
    """Tout bloc vu dans une référence est soit livré, soit explicitement à venir."""
    connus = set(BLOCS_LIVRES) | set(BLOCS_A_VENIR)
    for _societe, _periode, repertoire in INSTANTANES:
        contenu = (repertoire / "reference.dsn").read_bytes().decode("latin-1")
        for ligne in contenu.splitlines():
            if "," not in ligne:
                continue
            rubrique = ligne.split(",", 1)[0].strip()
            if rubrique.count(".") == 3:
                bloc = rubrique.rsplit(".", 1)[0]
                assert bloc in connus, f"bloc {bloc} ni livré ni planifié"
