-- Rôle de lecture dédié à la copie prod -> test.
--
-- Ne peut jamais écrire : privilèges SELECT uniquement, et sessions forcées en
-- lecture seule au niveau du serveur. C'est la garantie structurelle que la
-- production ne peut pas être modifiée par le pipeline de resynchro, même en
-- cas de bug du script.
--
-- ATTENTION — piège RLS : PostgreSQL applique la RLS aux rôles non
-- privilégiés. Un pg_dump exécuté par un rôle disposant seulement de SELECT
-- sur des tables protégées ne renvoie PAS d'erreur, il renvoie zéro ligne.
-- L'attribut BYPASSRLS est donc indispensable, et sa présence doit être
-- vérifiée après création (voir la vérification en fin de fichier).
--
-- Usage :
--   psql "<URL_PROD>" -v reader_password="'<MOT_DE_PASSE>'" \
--        -f scripts/test_env/create_readonly_role.sql

\set ON_ERROR_STOP on

DROP ROLE IF EXISTS eywai_replica_reader;

CREATE ROLE eywai_replica_reader WITH LOGIN PASSWORD :reader_password;

-- Toute session de ce rôle est en lecture seule, quoi qu'elle tente.
ALTER ROLE eywai_replica_reader SET default_transaction_read_only = on;

GRANT CONNECT ON DATABASE postgres TO eywai_replica_reader;

GRANT USAGE ON SCHEMA public  TO eywai_replica_reader;
GRANT USAGE ON SCHEMA auth    TO eywai_replica_reader;
GRANT USAGE ON SCHEMA storage TO eywai_replica_reader;

GRANT SELECT ON ALL TABLES IN SCHEMA public  TO eywai_replica_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA auth    TO eywai_replica_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA storage TO eywai_replica_reader;

GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO eywai_replica_reader;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO eywai_replica_reader;

-- Sans BYPASSRLS, le dump serait silencieusement vide sur les tables à RLS.
-- Peut échouer si Supabase réserve cet attribut au superutilisateur : dans ce
-- cas, la vérification ci-dessous le signalera et il faudra replier sur la
-- connexion postgres pour le seul pg_dump (voir la spec, §12.3).
ALTER ROLE eywai_replica_reader BYPASSRLS;

-- Vérification : doit afficher rolbypassrls = true.
SELECT rolname, rolcanlogin, rolbypassrls
  FROM pg_roles
 WHERE rolname = 'eywai_replica_reader';
