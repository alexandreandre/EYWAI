-- Colorplast : affectation de la formule « GAN Famille 2026 (EMU3+SMU2) »
-- à GIRERD, ESPINOSA et GAUTHERON (retour service paie 07/09/2026). La
-- formule S'AJOUTE à l'Isolé que chacun conserve (empilement Quadra :
-- Isolé 29,24/29,23 + Famille 98,13/0 = 156,60 €).
--
-- L'id de la formule diffère entre prod et test (gen_random_uuid à
-- l'insertion) : ciblage par LIBELLÉ dans la société. Idempotente : le
-- garde @> ne ré-ajoute jamais un id déjà présent.
UPDATE employees
SET specificites_paie = jsonb_set(
  specificites_paie,
  '{mutuelle,mutuelle_type_ids}',
  COALESCE(specificites_paie->'mutuelle'->'mutuelle_type_ids', '[]'::jsonb)
    || (
      SELECT to_jsonb(ARRAY[m.id::text])
      FROM company_mutuelle_types m
      WHERE m.company_id = 'dbe2b9f5-44dd-41bc-a625-36ed33d160f7'
        AND m.libelle = 'GAN Famille 2026 (EMU3+SMU2)'
        AND m.is_active
    )
)
WHERE id IN (
  'bceb467d-d0ac-454a-9084-4b20d3cd0e9e',  -- GIRERD
  '53c92e83-4a1a-4214-b30d-577cd1ab9d2d',  -- ESPINOSA
  '1c4cc8b6-5f55-4d71-bba5-5acb8fa3efd2'   -- GAUTHERON
)
  AND NOT COALESCE(specificites_paie->'mutuelle'->'mutuelle_type_ids', '[]'::jsonb)
      @> (
        SELECT to_jsonb(ARRAY[m.id::text])
        FROM company_mutuelle_types m
        WHERE m.company_id = 'dbe2b9f5-44dd-41bc-a625-36ed33d160f7'
          AND m.libelle = 'GAN Famille 2026 (EMU3+SMU2)'
          AND m.is_active
      );
