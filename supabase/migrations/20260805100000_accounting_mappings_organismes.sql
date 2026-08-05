-- Interfaçage comptable (#26) : ventilation des cotisations par organisme.
--
-- Une cotisation demande deux comptes : la charge patronale (classe 6) et la
-- dette envers l'organisme (classe 4). La table n'en portait qu'un, si bien que
-- toutes les charges atterrissaient sur 645000 et toutes les dettes sur 431000.

alter table public.accounting_mappings
  add column if not exists coti_id text,
  add column if not exists compte_charge text,
  add column if not exists compte_tiers text,
  add column if not exists organisme text;

comment on column public.accounting_mappings.coti_id is
  'Identifiant stable de la cotisation dans le bulletin (structure_cotisations). Clé de rattachement — ne jamais se fier au libellé, qui varie par société.';
comment on column public.accounting_mappings.compte_charge is
  'Compte de classe 6 débité pour la part patronale.';
comment on column public.accounting_mappings.compte_tiers is
  'Compte de classe 4 crédité (dette organisme ou salarié).';
comment on column public.accounting_mappings.organisme is
  'Clé d''organisme : URSSAF, RETRAITE, RETRAITE_SUP, MUTUELLE, PREVOYANCE.';

-- Unicité du couple (société, rubrique). company_id NULL = défaut plateforme.
create unique index if not exists accounting_mappings_company_rubrique_uidx
  on public.accounting_mappings (company_id, rubrique_code)
  where company_id is not null;

create unique index if not exists accounting_mappings_global_rubrique_uidx
  on public.accounting_mappings (rubrique_code)
  where company_id is null;

-- Correction : le net à payer est une rémunération due (421), pas un acompte
-- (425). Le cabinet utilise bien 42100000.
update public.accounting_mappings
   set compte_comptable = '421000',
       updated_at = now()
 where company_id is null
   and rubrique_code = 'net_a_payer'
   and compte_comptable = '425000';

-- Défauts plateforme par organisme et éléments hors cotisations.
--
-- `insert … where not exists` plutôt que `on conflict do nothing` : la table
-- porte des contraintes deferrable, que ON CONFLICT refuse comme arbitre.
insert into public.accounting_mappings
  (company_id, rubrique_code, rubrique_libelle, compte_comptable,
   compte_charge, compte_tiers, organisme, sens, type_rubrique, journal, is_active)
select null::uuid, v.rubrique_code, v.rubrique_libelle, v.compte_comptable,
       v.compte_charge, v.compte_tiers, v.organisme, v.sens, v.type_rubrique, 'OD', true
  from (values
    ('organisme_urssaf',       'URSSAF',                  '645100', '645100', '431000', 'URSSAF',       'debit',  'charge_patronale'),
    ('organisme_retraite',     'Retraite complémentaire', '645300', '645300', '437200', 'RETRAITE',     'debit',  'charge_patronale'),
    ('organisme_retraite_sup', 'Retraite supplémentaire', '645301', '645301', '437800', 'RETRAITE_SUP', 'debit',  'charge_patronale'),
    ('organisme_mutuelle',     'Mutuelle',                '645242', '645242', '437020', 'MUTUELLE',     'debit',  'charge_patronale'),
    ('organisme_prevoyance',   'Prévoyance',              '645241', '645241', '437400', 'PREVOYANCE',   'debit',  'charge_patronale'),
    ('prime_soumise',          'Primes soumises',         '641100', '641100', null,     null,           'debit',  'salaire'),
    ('indemnite_transport',    'Indemnité de transport',  '648000', '648000', null,     null,           'debit',  'autre'),
    ('note_de_frais',          'Notes de frais',          '428625', null,     '428625', null,           'credit', 'dette_salarie')
  ) as v(rubrique_code, rubrique_libelle, compte_comptable, compte_charge,
         compte_tiers, organisme, sens, type_rubrique)
 where not exists (
   select 1 from public.accounting_mappings m
    where m.company_id is null and m.rubrique_code = v.rubrique_code
 );

-- Alignement des lignes existantes sur les nouvelles colonnes.
update public.accounting_mappings
   set compte_charge = case when sens = 'debit'  then compte_comptable else compte_charge end,
       compte_tiers  = case when sens = 'credit' then compte_comptable else compte_tiers  end
 where compte_charge is null and compte_tiers is null;
