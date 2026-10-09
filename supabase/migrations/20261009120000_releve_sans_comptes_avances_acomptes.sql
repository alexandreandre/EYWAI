-- Le relevé mensuel des taux ne cherche plus les « comptes avances et acomptes ».
--
-- Ce ne sont pas des taux officiels mais des sous-comptes comptables de
-- l'entreprise (4251, 4252, 4253), déjà en base dans payroll_config. La source
-- n'a qu'un script IA, qui échoue à chaque relevé (citation non officielle,
-- relevé du 01/10/2026) et rend la page des taux « partielle » tous les mois.
-- Idempotente : la rejouer ne change rien.
update public.scraping_sources
set is_active = false,
    updated_at = now()
where source_key = 'COMPTES_AVANCES_ACOMPTES'
  and is_active;
