"""Recette SQL sur PostgreSQL jetable, Unix local uniquement, sans DSN externe.

Lance ses propres binaires initdb/postgres/psql depuis le même dossier, applique
la migration du dépôt et arrête uniquement son processus enfant en finally.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

EMPLOYEE = "00000000-0000-0000-0000-000000000001"
COMPANY = "00000000-0000-0000-0000-000000000011"
OTHER_COMPANY = "00000000-0000-0000-0000-000000000012"
TOKEN_A = "00000000-0000-0000-0000-000000000021"
TOKEN_B = "00000000-0000-0000-0000-000000000022"


def quote(value: str | None) -> str:
    return "null" if value is None else "'" + value.replace("'", "''") + "'"


def main() -> None:
    binary = shutil.which("postgres")
    if not binary:
        raise SystemExit("PostgreSQL local requis (postgres, initdb et psql).")
    bindir = Path(binary).parent
    migrations = Path(__file__).resolve().parents[2] / "supabase/migrations"
    migration = migrations / "20261112234500_calendar_edit_revision.sql"
    results: list[str] = []
    with tempfile.TemporaryDirectory(prefix="eywai-elsa-calendar-pg-", dir="/private/tmp") as directory:
        root = Path(directory)
        data, socket = root / "data", root / "socket"
        socket.mkdir()
        subprocess.run([str(bindir / "initdb"), "-D", str(data), "-A", "trust", "-U", "postgres", "--no-locale"], check=True, capture_output=True)
        with (root / "postgres.log").open("w") as log:
            server = subprocess.Popen([str(bindir / "postgres"), "-D", str(data), "-k", str(socket), "-h", "", "-p", "55439", "-F"], stdout=log, stderr=log)
            args = [str(bindir / "psql"), "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-v", "VERBOSITY=verbose", "-h", str(socket), "-p", "55439", "-U", "postgres", "-d", "postgres"]

            def sql(statement: str, *, token: str | None = None, role: str = "service_role", error: str | None = None) -> str:
                headers = json.dumps({"x-eywai-calendar-token": token} if token else {})
                prefix = f"set role {role}; set request.headers = {quote(headers)};" if role else ""
                completed = subprocess.run(args, input=prefix + statement, text=True, capture_output=True, timeout=15, check=False)
                if error:
                    assert completed.returncode != 0 and error in completed.stderr, completed.stderr
                else:
                    assert completed.returncode == 0, completed.stderr
                return completed.stdout.strip()

            def snapshot(month: int = 11, *, token: str | None = None, company: str = COMPANY):
                value = sql(f"select public.read_calendar_snapshot('{EMPLOYEE}', '{company}', 2026, {month});", token=token)
                return json.loads(value) if value else None

            def begin(revision: str | None, token: str = TOKEN_A, month: int = 11, company: str = COMPANY) -> str:
                return sql(f"select public.begin_calendar_edit('{EMPLOYEE}', '{company}', 2026, {month}, {quote(revision)}::uuid, '{token}', 60);")

            def end(token: str = TOKEN_A, month: int = 11):
                sql(f"select public.end_calendar_edit('{EMPLOYEE}', 2026, {month}, '{token}');")

            def renew(token: str = TOKEN_A, month: int = 11) -> str:
                return sql(f"select public.renew_calendar_edit('{EMPLOYEE}', 2026, {month}, '{token}', 60);")

            update = f"update public.employee_schedules set planned_calendar = '{{\"calendrier_prevu\":[{{\"jour\":6,\"type\":\"repos\",\"heures_prevues\":0}}]}}' where employee_id = '{EMPLOYEE}' and year = 2026 and month = 11;"
            try:
                for _ in range(100):
                    ready = subprocess.run(args, input="select 1;", text=True, capture_output=True, check=False)
                    if ready.returncode == 0:
                        break
                    if server.poll() is not None:
                        raise AssertionError((root / "postgres.log").read_text())
                    time.sleep(0.05)
                else:
                    raise AssertionError("PostgreSQL local non prêt")
                sql(f"""
                    create role service_role nologin bypassrls;
                    create role anon nologin;
                    create role authenticated nologin;
                    create table public.employees (id uuid primary key, company_id uuid not null);
                    create table public.employee_schedules (
                      employee_id uuid not null references public.employees(id), company_id uuid not null,
                      year integer not null, month integer not null, planned_calendar jsonb, actual_hours jsonb,
                      payroll_events jsonb, cumuls jsonb, primary key(employee_id, year, month)
                    );
                    grant usage on schema public to service_role;
                    grant select, insert, update, delete on public.employees, public.employee_schedules to service_role;
                    insert into public.employees values ('{EMPLOYEE}', '{COMPANY}');
                    insert into public.employee_schedules values ('{EMPLOYEE}', '{COMPANY}', 2026, 11,
                      '{{"calendrier_prevu":[{{"jour":6,"type":"travail","heures_prevues":7}}]}}',
                      '{{"calendrier_reel":[{{"jour":6,"type":"travail","heures_faites":7}}]}}',
                      '{{"heures":3}}', '{{"historique":20}}');
                """, role="")
                sql(migration.read_text(), role="")
                original = snapshot()
                assert original["revision"] and original["busy"] is False
                assert snapshot(12)["revision"] is None
                results.append("Révision du mois existant et état nul du mois neuf")
                sql(migration.read_text(), role="")
                assert snapshot() == original
                results.append("Migration réappliquée sans changement des entrées ni de la révision")

                assert begin(original["revision"]) == "acquired"
                assert snapshot()["busy"] is True and snapshot(token=TOKEN_A)["busy"] is False
                before = snapshot(token=TOKEN_A)
                sql(update, error="PT409")
                sql(update, token=TOKEN_B, error="PT409")
                sql(f"delete from public.employee_schedules where employee_id='{EMPLOYEE}' and month=11;", error="PT409")
                assert snapshot(token=TOKEN_A) == before
                results.append("Réservation : lectures possibles, écritures et suppression étrangères refusées")
                sql(update, token=TOKEN_A)
                changed = snapshot(token=TOKEN_A)
                assert changed["revision"] != original["revision"]
                assert changed["actual_hours"] == original["actual_hours"]
                assert sql(f"select cumuls::text from employee_schedules where employee_id='{EMPLOYEE}' and month=11;", token=TOKEN_A) == '{"historique": 20}'
                results.append("Écriture du propriétaire : nouvelle révision, réel et historique conservés")
                sql(f"update public.employee_schedules set payroll_events='{{\"heures\":4}}', cumuls='{{\"historique\":21}}' where employee_id='{EMPLOYEE}' and month=11;", token=TOKEN_A)
                assert snapshot(token=TOKEN_A)["revision"] == changed["revision"]
                sql(update, token=TOKEN_A)
                assert snapshot(token=TOKEN_A)["revision"] == changed["revision"]
                results.append("Révision stable pour un recalcul dérivé ou des entrées identiques")
                end(TOKEN_B)
                assert renew() == "t"
                end()
                assert begin(original["revision"]) == "conflict"
                assert sql("select count(*) from public.calendar_edit_locks;") == "0"
                assert snapshot()["revision"] == changed["revision"]
                results.append("Ancienne lecture refusée sans réservation ni écriture ; rendu étranger sans effet")

                barrier = Barrier(2)
                def simultaneous(token: str):
                    barrier.wait()
                    return begin(changed["revision"], token)
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [pool.submit(simultaneous, token) for token in (TOKEN_A, TOKEN_B)]
                    outcomes = [future.result() for future in futures]
                assert sorted(outcomes) == ["acquired", "busy"], outcomes
                owner = (TOKEN_A, TOKEN_B)[outcomes.index("acquired")]
                end(owner)
                results.append("Deux connexions concurrentes : une seule réservation acceptée")

                # Un auteur externe tient la transaction ouverte après son
                # UPDATE. La prise attend, puis doit relire la NOUVELLE révision.
                writer = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                writer.stdin.write(f"set role service_role; begin; update employee_schedules set actual_hours='{{\"calendrier_reel\":[]}}' where employee_id='{EMPLOYEE}' and month=11; select 'writer-entered'; select pg_sleep(0.5); commit;\n")
                writer.stdin.close()
                assert writer.stdout.readline().strip() == "writer-entered"
                assert writer.poll() is None
                assert begin(changed["revision"]) == "conflict"
                assert writer.wait(timeout=5) == 0, writer.stderr.read()
                after_external = snapshot()
                assert after_external["revision"] != changed["revision"]
                results.append("Écriture externe déjà engagée : attente puis conflit sur la nouvelle révision")

                assert begin(None, month=12) == "acquired"
                insert = f"insert into employee_schedules (employee_id,company_id,year,month,planned_calendar) values ('{EMPLOYEE}','{COMPANY}',2026,12,'{{\"calendrier_prevu\":[]}}');"
                sql(insert, error="PT409")
                sql(insert, token=TOKEN_A)
                assert snapshot(12, token=TOKEN_A)["revision"]
                end(month=12)
                assert begin(None, month=12) == "conflict"
                results.append("Création du mois neuf réservée ; seconde création fondée sur null refusée")

                assert begin(after_external["revision"]) == "acquired"
                sql("update public.calendar_edit_locks set locked_until=clock_timestamp()-interval '1 second';", role="")
                assert renew() == "f"
                sql(update, token=TOKEN_A, error="PT409")
                assert begin(after_external["revision"], TOKEN_B) == "acquired"
                end(TOKEN_A)
                sql(update, token=TOKEN_A, error="PT409")
                assert renew(TOKEN_B) == "t"
                end(TOKEN_B)
                results.append("Expiration : ancien jeton bloqué, reprise possible et nouveau propriétaire préservé")

                assert snapshot(company=OTHER_COMPANY) is None
                assert begin(after_external["revision"], company=OTHER_COMPANY) == "not_found"
                for role in ["anon", "authenticated"]:
                    sql(f"select public.read_calendar_snapshot('{EMPLOYEE}','{COMPANY}',2026,11);", role=role, error="42501")
                    assert sql(f"select has_table_privilege('{role}','public.calendar_edit_locks','select');", role="") == "f"
                assert sql("select relrowsecurity from pg_class where oid='public.calendar_edit_locks'::regclass;", role="") == "t"
                results.append("Fonctions et jetons réservés au serveur ; société étrangère non lisible")

                # UPDATE déjà verrouillé contre UPSERT : le trigger n'attend
                # pas un verrou advisory en tenant la ligne dans l'ordre inverse.
                assert begin(snapshot()["revision"]) == "acquired"
                owner_headers = quote(json.dumps({"x-eywai-calendar-token": TOKEN_A}))
                upsert_writer = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                upsert_writer.stdin.write(f"set role service_role; set request.headers={owner_headers}; begin; select pg_advisory_xact_lock(public.calendar_edit_key('{EMPLOYEE}',2026,11)); select 'owner-entered'; select pg_sleep(0.4); insert into employee_schedules(employee_id,company_id,year,month,planned_calendar) values('{EMPLOYEE}','{COMPANY}',2026,11,'{{}}') on conflict(employee_id,year,month) do update set planned_calendar=excluded.planned_calendar; commit;\n")
                upsert_writer.stdin.close()
                # pg_advisory_xact_lock rend une ligne vide avant le marqueur.
                assert upsert_writer.stdout.readline().strip() == ""
                assert upsert_writer.stdout.readline().strip() == "owner-entered"
                assert upsert_writer.poll() is None
                sql(update, error="PT409")
                assert upsert_writer.wait(timeout=5) == 0, upsert_writer.stderr.read()
                sql(f"update employee_schedules set month=10 where employee_id='{EMPLOYEE}' and month=11;", error="PT409")
                end()
                results.append("UPDATE/UPSERT en ordre inverse : refus immédiat, sans interblocage ; déplacement réservé refusé")

                before_move = snapshot(12)["revision"]
                sql(f"update employee_schedules set month=10 where employee_id='{EMPLOYEE}' and month=12;")
                assert snapshot(10)["revision"] != before_move
                sql(f"update employee_schedules set month=12 where employee_id='{EMPLOYEE}' and month=10;")
                assert snapshot(12)["revision"] != before_move
                results.append("Déplacement libre conservé, avec nouvelle révision et contrôle des deux clés")

                revision_before_delete = snapshot()["revision"]
                sql(f"delete from employee_schedules where employee_id='{EMPLOYEE}' and month=11;")
                sql(insert.replace("2026,12,", "2026,11,"))
                assert snapshot()["revision"] != revision_before_delete
                assert begin(revision_before_delete) == "conflict"
                results.append("Suppression/recréation : une ancienne révision ne redevient pas valable")

                # La saisie utilise aussi le verrou existant des générations,
                # avant sa réservation de calendrier. Vérifier ses vraies RPC.
                sql((migrations / "20260926140000_verrou_generation_bulletin.sql").read_text(), role="")
                take = f"select public.prendre_verrou_generation_bulletin('{EMPLOYEE}',2026,11,'{{token}}',60);"
                give = f"select public.rendre_verrou_generation_bulletin('{EMPLOYEE}',2026,11,'{{token}}');"
                assert sql(take.format(token=TOKEN_A)) == "t"
                assert sql(take.format(token=TOKEN_B)) == "f"
                sql(give.format(token=TOKEN_B))
                assert sql(take.format(token=TOKEN_B)) == "f"
                sql(give.format(token=TOKEN_A))
                assert sql(take.format(token=TOKEN_B)) == "t"
                sql(give.format(token=TOKEN_B))
                results.append("Verrou de bulletin existant : prise concurrente refusée et seul le propriétaire libère")
                print(json.dumps({"results": results, "count": len(results), "postgres": sql("select version();", role=""), "host": "Unix local isolé", "hosted_database_used": False}, ensure_ascii=False, indent=2))
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)


if __name__ == "__main__":
    main()
