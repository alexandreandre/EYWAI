-- Saisie du mois « sur le net » : acompte, net négatif reporté, trop-perçu, avance.
--
-- Jusqu'ici, le moteur reconnaissait ces saisies à leur libellé (« Report NAP
-- négatif », « Acompte »…) : un autre libellé, et le montant partait sur le brut
-- comme une prime, cotisations comprises. La gestionnaire choisit désormais
-- « Retenue sur le net » ou « Versement sur le net » ; la saisie porte ce choix.
-- Montant négatif : retenue ; positif : versement. Hors assiette sociale et
-- fiscale, hors montant net social : seul le net à payer bouge.

alter table public.monthly_inputs
  add column if not exists sur_le_net boolean not null default false;

comment on column public.monthly_inputs.sur_le_net is
  'Vrai : la saisie ne touche que le net à payer (retenue si négative, versement si positive), ni le brut, ni les cotisations, ni le net imposable, ni le montant net social.';
