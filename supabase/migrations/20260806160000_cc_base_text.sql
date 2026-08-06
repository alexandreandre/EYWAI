-- Texte de base intégral des conventions collectives, pour l'assistant RH.
--
-- `full_text` est un corpus construit pour le moteur de paie (avenants salaires
-- départementaux, annexes paie, extrait rémunération du texte de base) : il ne
-- contient ni période d'essai, ni préavis, ni congés. L'assistant RH a besoin du
-- texte de base complet, que la synchronisation KALI rapatrie déjà avant de le
-- réduire à son extrait rémunération.
--
-- On ajoute donc une colonne dédiée plutôt que de modifier `full_text`, dont la
-- paie dépend. Les deux colonnes sont alimentées par la même synchronisation.

alter table public.collective_agreement_texts
  add column if not exists base_text text,
  add column if not exists base_text_char_count integer not null default 0,
  add column if not exists base_text_updated_at timestamptz;

comment on column public.collective_agreement_texts.base_text is
  'Texte de base intégral de la convention (KALI, section « Texte de base »), '
  'destiné à l''assistant RH. Distinct de full_text, corpus paie.';
comment on column public.collective_agreement_texts.base_text_char_count is
  'Nombre de caractères de base_text (0 si absent).';
comment on column public.collective_agreement_texts.base_text_updated_at is
  'Date du dernier rapatriement de base_text depuis KALI.';
