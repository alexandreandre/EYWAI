"""L'attestation de portabilité prévoyance doit pouvoir s'enregistrer.

La création d'un départ génère les attestations de portabilité mutuelle et
prévoyance ; la contrainte `exit_documents_document_type_check` ne connaissait
que la mutuelle : le PDF prévoyance partait au stockage sans ligne en base
(02/10/2026, deux fins de CDD). La migration élargit la contrainte sans retirer
aucun type existant.
"""

from __future__ import annotations

from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "supabase" / "migrations"

_TYPES_EXISTANTS = (
    "lettre_demission",
    "convention_rupture_signee",
    "lettre_licenciement",
    "accuse_reception",
    "convocation_entretien",
    "justificatif_autre",
    "certificat_travail",
    "attestation_pole_emploi",
    "solde_tout_compte",
    "recu_solde_compte",
    "attestation_portabilite_mutuelle",
)


def _migration_text() -> str:
    candidates = sorted(_MIGRATIONS_DIR.glob("*_exit_documents_portabilite_prevoyance.sql"))
    assert len(candidates) == 1, f"Migration attendue une fois : {candidates}"
    return candidates[0].read_text(encoding="utf-8")


def test_la_contrainte_accepte_la_portabilite_prevoyance():
    sql = _migration_text()
    assert "DROP CONSTRAINT IF EXISTS exit_documents_document_type_check" in sql
    assert "ADD CONSTRAINT exit_documents_document_type_check" in sql
    assert "'attestation_portabilite_prevoyance'" in sql


def test_aucun_type_existant_n_est_retire():
    sql = _migration_text()
    for type_document in _TYPES_EXISTANTS:
        assert f"'{type_document}'" in sql, type_document
