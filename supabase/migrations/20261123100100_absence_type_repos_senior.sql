-- Type d'absence « Repos seniors » (plasturgie, accord du 18/04/2025).
-- Migration séparée du réglage, comme pour 'jtc' : PostgreSQL interdit
-- d'utiliser une valeur d'enum dans la transaction qui l'ajoute.
--
-- Comme le JTC, ce type n'écrit jamais le calendrier : le jour reste
-- travaillé et la paie ne retire rien.

ALTER TYPE public.absence_type ADD VALUE IF NOT EXISTS 'repos_senior';
