"""Le vocabulaire des types d'absence du code doit exister dans la base.

Pourquoi ce test existe : le 07/09/2026, `payslip_generator` filtrait les
demandes validées sur `type in ('conge_paye', 'recuperation_modulation')`.
`recuperation_modulation` figure dans le `Literal` Python, dans les schémas
d'API et dans l'écran de demande d'absence — mais aucune migration ne l'a
jamais ajouté à l'enum PostgreSQL `absence_type`. Postgres refusait la valeur
(22P02), la requête entière échouait, et les congés disparaissaient des
bulletins. Trois semaines, aucune alerte, 6 600 tests unitaires au vert : ils
travaillaient tous sur des dictionnaires en mémoire, jamais contre la base.

Une divergence entre le vocabulaire du code et celui de la base ne se voit
qu'ici. Ce test la rend visible avant qu'elle n'atteigne une paie.
"""

from typing import get_args

import pytest

from app.core.database import supabase
from app.modules.absences.domain.enums import AbsenceType

pytestmark = pytest.mark.integration


def _valeur_refusee_par_l_enum(exc: Exception) -> bool:
    message = str(exc)
    return "22P02" in message or "invalid input value for enum" in message


class TestVocabulaireDesTypesDAbsence:
    def test_chaque_type_du_code_est_accepte_par_la_base(self):
        """Chaque valeur d'`AbsenceType` doit pouvoir servir de filtre sur
        `absence_requests.type`. Une seule valeur inconnue fait échouer TOUTE
        requête qui l'emploie — y compris celles du moteur de paie."""
        refuses: list[str] = []
        for type_absence in get_args(AbsenceType):
            try:
                (
                    supabase.table("absence_requests")
                    .select("id")
                    .eq("type", type_absence)
                    .limit(1)
                    .execute()
                )
            except Exception as exc:  # noqa: BLE001 — on trie juste après
                if _valeur_refusee_par_l_enum(exc):
                    refuses.append(type_absence)
                else:
                    raise

        assert not refuses, (
            "Types déclarés par le code mais absents de l'enum PostgreSQL "
            f"`absence_type` : {sorted(refuses)}. Ajouter une migration "
            "`ALTER TYPE absence_type ADD VALUE IF NOT EXISTS ...`, ou retirer "
            "ces types du code — mais ne pas laisser les deux diverger."
        )

    def test_les_types_projetes_en_conges_sont_utilisables_en_paie(self):
        """Garde resserrée sur le chemin qui a cassé : les types que la
        validation d'absence projette sous `conges_payes` sont exactement ceux
        que le moteur relit pour décider si un congé atteint le bulletin."""
        from app.modules.payroll.documents.payslip_generator import (
            _TYPES_DEMANDE_PROJETES_EN_CONGES_PAYES,
        )

        assert _TYPES_DEMANDE_PROJETES_EN_CONGES_PAYES, (
            "Aucun type projeté en congés payés : le moteur n'étiquetterait "
            "plus aucun congé."
        )
        assert _TYPES_DEMANDE_PROJETES_EN_CONGES_PAYES <= set(get_args(AbsenceType))
