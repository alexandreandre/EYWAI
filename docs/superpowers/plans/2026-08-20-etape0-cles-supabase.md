# Étape 0 — Clés Supabase à l'endroit + UPDATE participation ciblé

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre tout le code Supabase « role-aware » (déployable avant ET
après remise à l'endroit des clés inversées), cibler l'UPDATE de
traçabilité participation par ids, puis basculer les secrets (test → prod).

**Architecture:** Constat confirmé : `SUPABASE_KEY` porte un JWT
`role=service_role` et `SUPABASE_SERVICE_KEY` un `role=anon` (inversion des
noms, partout : `backend/.env`, Cloud Run test et prod).
`get_supabase_admin_env()` (backend/app/core/settings.py:137-162) est déjà
role-aware ; le client **par défaut** (backend/app/core/database.py:39-44)
et trois autres points choisissent encore une variable **par son nom**. On
rend ces points role-aware d'abord (comportement identique dans les deux
états), la bascule des valeurs vient en dernier. Défaillance à éviter :
sous RLS, une mauvaise clé donne des **200 avec listes vides**, pas des
erreurs.

**Tech Stack:** Python/FastAPI, Supabase (supabase-py), pytest, GitHub
Actions (deploy.yml), Cloud Run.

## Global Constraints

- Lancer les tests avec `cwd=backend`, via `venv/bin/python -m pytest` ;
  exporter des `SUPABASE_URL/KEY` factices si le test n'en pose pas
  (`backend/.env` pointe sur la PROD — aucun test ne doit toucher une vraie base).
- Jamais de valeur de clé/secret dans le code, les tests, les logs ou les
  messages de commit — uniquement des JWT factices forgés dans les tests.
- Commits par chemins explicites (sessions concurrentes possibles), sur la
  branche `dev-etape0-cles-supabase` créée depuis `main` à jour.
- Ne PAS échanger les valeurs des variables (`.env`, secrets, Cloud Run)
  pendant les tâches 1-6 : c'est la tâche 7, et uniquement dans son ordre.

---

### Task 1: Sélection anon explicite dans settings

**Files:**
- Modify: `backend/app/core/settings.py` (après `get_supabase_admin_env`, ligne 162)
- Test: `backend/tests/unit/core/test_supabase_env_selection.py` (nouveau)

**Interfaces:**
- Consumes: `_jwt_role(jwt) -> str | None` (settings.py:122), variables module `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_URL`.
- Produces: `get_supabase_anon_env() -> tuple[str, str]` — retourne (url, clé dont le rôle JWT est `anon`), repli sur SUPABASE_KEY si aucun rôle décodable.

- [ ] **Step 1: Écrire le test qui échoue**

```python
"""Tests de la sélection role-aware des clés Supabase (clés forgées, aucun vrai secret)."""
import base64
import json

import pytest

from app.core import settings


def _fake_jwt(role: str) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(
        json.dumps({"role": role}).encode()
    ).rstrip(b"=").decode()
    return f"{header}.{payload}.sig"


ANON = _fake_jwt("anon")
SERVICE = _fake_jwt("service_role")


def test_anon_env_prefere_la_cle_anon_meme_inversee(monkeypatch):
    # État actuel de prod : SUPABASE_KEY = service_role, SUPABASE_SERVICE_KEY = anon
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_KEY", SERVICE)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_KEY", ANON)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None)
    url, key = settings.get_supabase_anon_env()
    assert key == ANON


def test_anon_env_apres_bascule(monkeypatch):
    # État cible : SUPABASE_KEY = anon, SUPABASE_SERVICE_KEY = service_role
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_KEY", ANON)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_KEY", SERVICE)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None)
    url, key = settings.get_supabase_anon_env()
    assert key == ANON


def test_anon_env_repli_si_roles_indecodables(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_KEY", "pas-un-jwt")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_KEY", None)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None)
    url, key = settings.get_supabase_anon_env()
    assert key == "pas-un-jwt"


def test_admin_env_prefere_service_role_dans_les_deux_etats(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://x.supabase.co")
    for cfg in [(SERVICE, ANON), (ANON, SERVICE)]:
        monkeypatch.setattr(settings, "SUPABASE_KEY", cfg[0])
        monkeypatch.setattr(settings, "SUPABASE_SERVICE_KEY", cfg[1])
        monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None)
        url, key = settings.get_supabase_admin_env()
        assert key == SERVICE
```

- [ ] **Step 2: Vérifier l'échec**

Run: `cd backend && venv/bin/python -m pytest tests/unit/core/test_supabase_env_selection.py -v`
Expected: FAIL — `AttributeError: module 'app.core.settings' has no attribute 'get_supabase_anon_env'` (les tests admin passent déjà).

- [ ] **Step 3: Implémenter dans settings.py** (après la ligne 162)

```python
def get_supabase_anon_env() -> tuple[str, str]:
    """
    Retourne (url, key) pour un client Supabase anonyme (auth publique :
    sign_in, refresh). Préfère la JWT dont le rôle est ``anon`` parmi
    SUPABASE_KEY, SUPABASE_SERVICE_KEY, SUPABASE_SERVICE_ROLE_KEY — les
    noms de variables ont été historiquement inversés, seul le claim fait foi.
    """
    if not SUPABASE_URL:
        raise RuntimeError("Variable d'environnement SUPABASE_URL manquante.")
    candidates = [
        k for k in (SUPABASE_KEY, SUPABASE_SERVICE_KEY, SUPABASE_SERVICE_ROLE_KEY) if k
    ]
    for key in candidates:
        if _jwt_role(key) == "anon":
            return SUPABASE_URL, key
    if not SUPABASE_KEY:
        raise RuntimeError("Variable d'environnement SUPABASE_KEY manquante.")
    return SUPABASE_URL, SUPABASE_KEY
```

- [ ] **Step 4: Vérifier le vert**

Run: `cd backend && venv/bin/python -m pytest tests/unit/core/test_supabase_env_selection.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/settings.py backend/tests/unit/core/test_supabase_env_selection.py
git commit -m "feat(core): sélection anon role-aware des clés Supabase"
```

---

### Task 2: Client par défaut role-aware

**Files:**
- Modify: `backend/app/core/database.py:38-44`
- Test: `backend/tests/unit/core/test_supabase_env_selection.py` (ajout)

**Interfaces:**
- Consumes: `get_supabase_admin_env()` (Task 1 en garantit le comportement dans les deux états).
- Produces: le client module `supabase` (importé partout comme client par défaut) est construit sur la clé **service_role quelle que soit la variable qui la porte** — comportement inchangé aujourd'hui, inchangé après bascule.

- [ ] **Step 1: Test qui échoue** (ajouter au fichier de Task 1)

```python
def test_database_default_client_choisit_service_role(monkeypatch):
    """Le client par défaut du backend doit être service_role dans les deux états."""
    import importlib

    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", ANON)          # état cible (post-bascule)
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", SERVICE)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    captured = {}

    def fake_create_client(url, key, options=None):
        captured["key"] = key

        class _Fake:  # objet client minimal
            pass

        return _Fake()

    import app.core.settings as settings_mod
    importlib.reload(settings_mod)
    import app.core.database as database_mod
    monkeypatch.setattr("supabase.create_client", fake_create_client)
    importlib.reload(database_mod)
    assert captured["key"] == SERVICE
```

- [ ] **Step 2: Vérifier l'échec**

Run: `cd backend && venv/bin/python -m pytest tests/unit/core/test_supabase_env_selection.py::test_database_default_client_choisit_service_role -v`
Expected: FAIL — `captured["key"] == ANON` (le module lit `require_supabase_env()` = SUPABASE_KEY aveuglément).
Note : si le reload pose problème (imports en cascade), isoler le test dans un sous-processus `python -c` ; l'assertion reste la même.

- [ ] **Step 3: Implémenter** — remplacer database.py:38-39

```python
# --- Client par défaut (backend de confiance : service_role, sélection par
# claim JWT — les noms de variables ont été historiquement inversés) ---
_default_url, _default_key = get_supabase_admin_env()
```

et l'import ligne 32-35 devient :

```python
from app.core.settings import get_supabase_admin_env
```

(`require_supabase_env` n'est plus utilisé ici ; le docstring de tête (lignes 4-7) est mis à jour : « client par défaut = service_role sélectionné par claim ».)

- [ ] **Step 4: Vérifier le vert + non-régression**

Run: `cd backend && venv/bin/python -m pytest tests/unit/core/ -v`
Expected: tous verts.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/database.py backend/tests/unit/core/test_supabase_env_selection.py
git commit -m "fix(core): client Supabase par défaut sélectionné par claim service_role"
```

---

### Task 3: Auth publique sur clé anon explicite

**Files:**
- Modify: `backend/app/modules/auth/infrastructure/providers.py` (les deux `create_client(SUPABASE_URL, SUPABASE_KEY)` — `sign_in_with_password` et `refresh_session`)
- Test: `backend/tests/unit/auth/test_auth_provider_keys.py` (nouveau)

**Interfaces:**
- Consumes: `get_supabase_anon_env()` (Task 1).
- Produces: `SupabaseAuthProvider` construit ses clients de connexion sur la clé **anon** (jamais service_role) dans les deux états.

- [ ] **Step 1: Test qui échoue**

```python
import base64, json
import pytest


def _fake_jwt(role):
    p = base64.urlsafe_b64encode(json.dumps({"role": role}).encode()).rstrip(b"=").decode()
    return f"h.{p}.s"


def test_sign_in_utilise_la_cle_anon(monkeypatch):
    from app.modules.auth.infrastructure import providers as mod

    monkeypatch.setattr(
        "app.core.settings.SUPABASE_URL", "https://x.supabase.co", raising=False
    )
    monkeypatch.setattr("app.core.settings.SUPABASE_KEY", _fake_jwt("service_role"), raising=False)
    monkeypatch.setattr("app.core.settings.SUPABASE_SERVICE_KEY", _fake_jwt("anon"), raising=False)
    monkeypatch.setattr("app.core.settings.SUPABASE_SERVICE_ROLE_KEY", None, raising=False)

    captured = {}

    def fake_create_client(url, key):
        captured["key"] = key
        raise RuntimeError("stop-ici")  # on n'a besoin que de la clé choisie

    monkeypatch.setattr(mod, "create_client", fake_create_client)
    with pytest.raises(RuntimeError, match="stop-ici"):
        mod.SupabaseAuthProvider().sign_in_with_password("a@b.c", "x")
    assert captured["key"] == _fake_jwt("anon")
```

- [ ] **Step 2: Vérifier l'échec** — Run: `cd backend && venv/bin/python -m pytest tests/unit/auth/test_auth_provider_keys.py -v` — Expected: FAIL (`captured["key"]` = la service_role, ou constantes module figées : adapter le monkeypatch au vrai import du module, voir Step 3).

- [ ] **Step 3: Implémenter** — dans `providers.py`, remplacer les deux constructions :

```python
from app.core.settings import get_supabase_anon_env
```

et dans `sign_in_with_password` et `refresh_session` :

```python
        anon_url, anon_key = get_supabase_anon_env()
        auth_client = create_client(anon_url, anon_key)
```

(supprimer les imports/constantes `SUPABASE_URL, SUPABASE_KEY` devenus inutiles dans ce fichier s'ils ne servent plus ailleurs.)

- [ ] **Step 4: Vérifier le vert** — Run: `cd backend && venv/bin/python -m pytest tests/unit/auth/ -v` — Expected: tous verts.

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/auth/infrastructure/providers.py backend/tests/unit/auth/test_auth_provider_keys.py
git commit -m "fix(auth): sign-in et refresh sur clé anon sélectionnée par claim"
```

---

### Task 4: Scraping role-aware

**Files:**
- Modify: `backend/scraping/VM.py` (fonction `get_supabase`, ~ligne 171)
- Modify: `backend/scraping/scheduler.py:84-88`
- Test: exécution d'un dry-run, pas de test unitaire (scripts autonomes)

**Interfaces:**
- Consumes: `init_supabase_client()` de `backend/scraping/core/supabase_io.py:21` — déjà role-aware (candidats + claim `service_role`).
- Produces: VM.py et scheduler.py obtiennent un client service_role dans les deux états (aujourd'hui ils préfèrent `SUPABASE_SERVICE_KEY` = anon → ils tournent en anon sans le savoir).

- [ ] **Step 1: VM.py** — remplacer le corps de `get_supabase()` :

```python
def get_supabase():
    from scraping.core.supabase_io import init_supabase_client

    return init_supabase_client()
```

- [ ] **Step 2: scheduler.py** — remplacer les lignes 84-88 (sélection url/key + erreur) par :

```python
    from scraping.core.supabase_io import init_supabase_client

    try:
        sb = init_supabase_client()
    except EnvironmentError as exc:
        logger.error("Client Supabase indisponible : %s", exc)
        return
```

(adapter le nom de la variable locale existante — le reste de la fonction utilise le client construit ; conserver le comportement « log + return » en cas d'env manquant.)

- [ ] **Step 3: Vérification statique** — Run: `cd backend && venv/bin/python -c "import scraping.VM, scraping.scheduler"` — Expected: aucun ImportError. Puis `grep -n "SUPABASE_SERVICE_KEY" scraping/VM.py scraping/scheduler.py` — Expected: aucune occurrence restante.

- [ ] **Step 4: Commit**

```bash
git add backend/scraping/VM.py backend/scraping/scheduler.py
git commit -m "fix(scraping): VM et scheduler sur le client role-aware commun"
```

---

### Task 5: secret_store sans repli sur SUPABASE_KEY

**Files:**
- Modify: `backend/app/shared/utils/secret_store.py` (fonction `_fernet_key`)
- Test: `backend/tests/unit/shared/test_secret_store.py` (nouveau ou ajout)

Contexte : 0 secret chiffré en base prod (vérifié 20/08) → aucun re-chiffrement à faire ; c'est LA fenêtre pour couper le repli (sinon la bascule des clés rendrait indéchiffrable tout secret chiffré avec l'ancienne valeur).

**Interfaces:**
- Produces: `_fernet_key()` exige `SECRET_ENCRYPTION_KEY` ; `encrypt_secret`/`decrypt` lèvent `RuntimeError` explicite si absent (plus jamais dérivé d'une clé Supabase).

- [ ] **Step 1: Test qui échoue**

```python
import pytest


def test_fernet_key_exige_secret_encryption_key(monkeypatch):
    from app.shared.utils import secret_store

    monkeypatch.delenv("SECRET_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_ENCRYPTION_KEY"):
        secret_store._fernet_key()


def test_fernet_key_stable_avec_cle_posee(monkeypatch):
    from app.shared.utils import secret_store

    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", "une-phrase-de-test")
    assert secret_store._fernet_key() == secret_store._fernet_key()
```

- [ ] **Step 2: Vérifier l'échec** — Run: `cd backend && venv/bin/python -m pytest tests/unit/shared/test_secret_store.py -v` — Expected: le premier test FAIL (le repli actuel dérive une clé au lieu de lever).

- [ ] **Step 3: Implémenter** — remplacer `_fernet_key` :

```python
def _fernet_key() -> bytes:
    """Dérive une clé Fernet 32 octets depuis SECRET_ENCRYPTION_KEY (obligatoire)."""
    raw = os.getenv("SECRET_ENCRYPTION_KEY")
    if not raw:
        raise RuntimeError(
            "SECRET_ENCRYPTION_KEY manquante : le stockage chiffré de secrets "
            "exige une clé dédiée (plus de repli sur les clés Supabase)."
        )
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)
```

- [ ] **Step 4: Vérifier le vert + chercher les appelants** — Run: `cd backend && venv/bin/python -m pytest tests/unit/shared/ -v` puis `grep -rn "encrypt_secret\|decrypt_secret" app/ --include="*.py" | grep -v secret_store` — vérifier que chaque appelant tolère l'exception (elle doit remonter comme erreur de config, pas être avalée).

- [ ] **Step 5: Commit**

```bash
git add backend/app/shared/utils/secret_store.py backend/tests/unit/shared/test_secret_store.py
git commit -m "fix(secrets): SECRET_ENCRYPTION_KEY obligatoire, plus de repli sur les clés Supabase"
```

---

### Task 6: UPDATE participation ciblé par ids

**Files:**
- Modify: `backend/app/modules/monthly_inputs/application/dto.py:14-17` (ajouter `inserted_ids`)
- Modify: `backend/app/modules/monthly_inputs/application/commands.py:44-58` (propager les ids)
- Modify: `backend/app/modules/participation/application/campaign_service.py:675-685` (cibler l'UPDATE)
- Test: `backend/tests/unit/participation/test_campaign_trace.py` (nouveau)

**Interfaces:**
- Consumes: `monthly_inputs_repository.insert_batch(rows) -> List[Dict]` (retourne déjà les lignes créées avec `id`).
- Produces: `CreateBatchResultDto(inserted_count: int, inserted_ids: list[str])` ; l'UPDATE de traçabilité devient `.in_("id", inserted_ids)` — plus aucun filtre year/month global.

- [ ] **Step 1: DTO** — dans `dto.py` :

```python
@dataclass
class CreateBatchResultDto:
    """Résultat de la création en batch."""

    inserted_count: int
    inserted_ids: list[str] = field(default_factory=list)
```

(ajouter `field` à l'import dataclasses.)

- [ ] **Step 2: commands.py** — fin de `create_monthly_inputs_batch` :

```python
    inserted = monthly_inputs_repository.insert_batch(data_to_insert)
    return CreateBatchResultDto(
        inserted_count=len(inserted),
        inserted_ids=[str(r["id"]) for r in inserted if r.get("id")],
    )
```

- [ ] **Step 3: Test qui échoue** (l'UPDATE doit cibler les ids, jamais year/month)

```python
from unittest.mock import MagicMock, patch


def test_trace_campagne_ciblee_par_ids():
    from app.modules.participation.application import campaign_service as cs

    fake_table = MagicMock()
    fake_supabase = MagicMock()
    fake_supabase.table.return_value = fake_table
    fake_table.update.return_value = fake_table
    fake_table.in_.return_value = fake_table

    with patch.object(cs, "supabase", fake_supabase):
        cs._tag_campaign_inputs("camp-1", ["id-a", "id-b"])

    fake_table.update.assert_called_once_with({"participation_campaign_id": "camp-1"})
    fake_table.in_.assert_called_once_with("id", ["id-a", "id-b"])
    assert not fake_table.eq.called   # plus de filtre year/month
    assert not fake_table.is_.called  # plus de filtre "null" global
```

- [ ] **Step 4: Vérifier l'échec** — Run: `cd backend && venv/bin/python -m pytest tests/unit/participation/test_campaign_trace.py -v` — Expected: FAIL (`_tag_campaign_inputs` n'existe pas).

- [ ] **Step 5: Implémenter dans campaign_service.py** — extraire la trace en fonction et remplacer le bloc lignes 675-685 :

```python
def _tag_campaign_inputs(campaign_id: str, inserted_ids: list[str]) -> None:
    """Trace la campagne sur les seules lignes créées par elle (jamais de filtre global)."""
    if not inserted_ids:
        return
    supabase.table("monthly_inputs").update(
        {"participation_campaign_id": campaign_id}
    ).in_("id", inserted_ids).execute()
```

et au point d'appel :

```python
    if payloads:
        batch_result = create_monthly_inputs_batch(payloads)
        try:
            _tag_campaign_inputs(campaign_id, batch_result.inserted_ids)
        except Exception as exc:
            logger.warning("[participation] campaign_id trace échouée: %s", exc)
```

(passage de `logger.info` à `logger.warning` : un échec de traçabilité doit se voir.)

- [ ] **Step 6: Vérifier le vert + non-régression du module**

Run: `cd backend && venv/bin/python -m pytest tests/unit/participation/ tests/unit/monthly_inputs/ -v` (créer les dossiers de tests si absents) — Expected: verts. Puis suite complète : `venv/bin/python -m pytest tests/unit -q` — Expected: 0 échec.

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/monthly_inputs/application/dto.py backend/app/modules/monthly_inputs/application/commands.py backend/app/modules/participation/application/campaign_service.py backend/tests/unit/participation/test_campaign_trace.py
git commit -m "fix(participation): trace de campagne ciblée par ids créés, plus de filtre global"
```

---

### Task 7: Runbook de bascule (opérations, PAS de code — exécution supervisée)

Pré-requis : Tasks 1-6 mergées sur main, CI verte, déploiement test + prod
effectué avec le code role-aware (comportement identique attendu — vérifier
health, login, un bulletin, page Suivi des taux).

- [ ] **7.1** Créer/vérifier les secrets GitHub (`gh secret list`) : `SUPABASE_SERVICE_ROLE_KEY` (prod, valeur service_role), `SUPABASE_TEST_SERVICE_KEY` (test, valeur service_role) — 5 workflows les référencent déjà. Ne jamais coller une valeur dans le terminal en clair ; utiliser `gh secret set X < fichier` puis supprimer le fichier.
- [ ] **7.2** `deploy.yml` : ajouter `SUPABASE_SERVICE_KEY` aux `env_vars` du job **production** (stratégie merge Cloud Run : sans ça, la valeur anon posée à la main survivrait) ; vérifier le job test ; corriger `deploy-test-env.yml:160` (même secret posé sur les deux variables) et `refresh-test-from-prod.yml:89`. Poser aussi `SECRET_ENCRYPTION_KEY` (nouvelle, générée : `openssl rand -base64 32`) sur test et prod (Task 5 l'exige).
- [ ] **7.3** Remettre les secrets à l'endroit sur GitHub : `SUPABASE_KEY` (prod) = valeur **anon**, `SUPABASE_SERVICE_KEY` (prod) = valeur **service_role** ; idem côté test.
- [ ] **7.4** Déployer **test** ; vérifier : login QA, liste bulletins non vide, `scraping_sources` lisible via l'app, notifications. Un écran vide = mauvaise clé (RLS silencieuse) → rollback immédiat.
- [ ] **7.5** Déployer **prod** ; vérifier : health, openapi, login, un bulletin, Suivi des taux ; contrôler le rôle effectif en décodant le claim des variables Cloud Run (`gcloud run services describe … | …` → décodage local, ne jamais afficher la clé).
- [ ] **7.6** En dernier : échanger les valeurs dans `backend/.env` local (⚠ tout script `--apply` lit ce fichier — ne rien lancer pendant la fenêtre) et dans les `.env` de test locaux éventuels.
- [ ] **7.7** Rollback si besoin : ré-échanger les env vars + `gcloud run services update-traffic` vers la révision précédente. Les changements de code (Tasks 1-6) n'ont jamais besoin de revert : ils sont corrects dans les deux états.
- [ ] **7.8** Clore : mettre à jour la mémoire (clés à l'endroit, date), noter dans `docs/revue-chaine-paie-2026-08.md` que le point C-clés est soldé.
