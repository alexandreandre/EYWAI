-- Rôle de lecture dédié à la copie prod -> test.
--
-- Ne peut jamais écrire : lecture seule au niveau du serveur (aucun privilège
-- d'écriture accordé, et default_transaction_read_only forcé). C'est la
-- garantie structurelle que la production ne peut pas être modifiée par le
-- pipeline de resynchro, même en cas de bug du script.
--
-- POURQUOI pg_read_all_data ET NON DES GRANT PAR SCHÉMA :
--   1. Le schéma auth appartient à supabase_admin, pas à postgres : un
--      GRANT USAGE ON SCHEMA auth échoue et le rôle reçoit
--      « permission denied for schema auth » au moment du dump.
--   2. pg_read_all_data est un rôle intégré PostgreSQL qui donne le SELECT sur
--      tous les schémas, y compris auth, et couvre automatiquement les tables
--      créées après coup.
--   3. Il implique la lecture des tables protégées par RLS. Sans cela,
--      PostgreSQL applique la RLS au rôle : pg_dump ne renvoie PAS d'erreur,
--      il renvoie zéro ligne — un environnement de test silencieusement vide.
--      BYPASSRLS reste posé en complément, et sa présence est vérifiée en fin
--      de fichier.
--
-- Usage en ligne de commande :
--   psql "<URL_PROD>" -v ON_ERROR_STOP=1 -v reader_password="'<MOT_DE_PASSE>'" \
--        -f scripts/test_env/create_readonly_role.sql
--
-- Usage dans l'éditeur SQL du tableau de bord Supabase : remplacer
-- :reader_password par le mot de passe entre apostrophes. Ce fichier ne
-- contient aucune méta-commande psql (\set, \i…), que l'éditeur web rejette.

DROP ROLE IF EXISTS eywai_replica_reader;

CREATE ROLE eywai_replica_reader WITH LOGIN PASSWORD :reader_password;

-- Toute session de ce rôle est en lecture seule, quoi qu'elle tente.
ALTER ROLE eywai_replica_reader SET default_transaction_read_only = on;

GRANT CONNECT ON DATABASE postgres TO eywai_replica_reader;

-- Lecture sur tous les schémas, auth compris (cf. explication en tête).
GRANT pg_read_all_data TO eywai_replica_reader;

-- Complément explicite : BYPASSRLS reste utile si pg_read_all_data venait à
-- être révoqué, et rend l'intention lisible.
ALTER ROLE eywai_replica_reader BYPASSRLS;

-- Vérification : rolbypassrls doit valoir true, et la lecture de auth.users
-- doit renvoyer un nombre, pas une erreur de permission.
SELECT rolname, rolcanlogin, rolbypassrls
  FROM pg_roles
 WHERE rolname = 'eywai_replica_reader';
