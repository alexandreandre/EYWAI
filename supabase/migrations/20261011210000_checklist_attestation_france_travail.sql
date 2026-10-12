-- [H14] La tâche de checklist des départs déjà créés s'appelait « Attestation
-- Pôle Emploi » ; l'écran, les documents et la DSN disent « France Travail »
-- (l'opérateur a changé de nom le 01/01/2024). Le code crée désormais la tâche
-- sous le bon nom ; cette migration renomme celles qui existent. Libellé
-- seulement : ni l'état « faite », ni la date, ni le code de la tâche ne
-- changent.
UPDATE public.exit_checklist_items
   SET item_label = 'Attestation France Travail'
 WHERE item_code = 'unemployment_certificate'
   AND item_label = 'Attestation Pôle Emploi';
