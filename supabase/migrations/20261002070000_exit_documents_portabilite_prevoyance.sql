-- L'attestation de portabilité prévoyance doit pouvoir s'enregistrer.
-- La création d'un départ la génère avec celle de la mutuelle, mais la
-- contrainte ne connaissait que la mutuelle : le PDF partait au stockage sans
-- ligne en base. Aucun type existant n'est retiré. Idempotente.

ALTER TABLE public.exit_documents
    DROP CONSTRAINT IF EXISTS exit_documents_document_type_check;

ALTER TABLE public.exit_documents
    ADD CONSTRAINT exit_documents_document_type_check CHECK (
        document_type IN (
            'lettre_demission',
            'convention_rupture_signee',
            'lettre_licenciement',
            'accuse_reception',
            'convocation_entretien',
            'justificatif_autre',
            'certificat_travail',
            'attestation_pole_emploi',
            'solde_tout_compte',
            'recu_solde_compte',
            'attestation_portabilite_mutuelle',
            'attestation_portabilite_prevoyance'
        )
    );
