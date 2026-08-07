-- Type d'absence JTC. Migration séparée du paramétrage : PostgreSQL interdit
-- d'utiliser une valeur d'enum dans la transaction qui l'ajoute, et une
-- migration ultérieure qui référencerait 'jtc' échouerait si les deux étaient
-- appliquées ensemble.

ALTER TYPE public.absence_type ADD VALUE IF NOT EXISTS 'jtc';
