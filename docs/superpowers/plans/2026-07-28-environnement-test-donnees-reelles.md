# Environnement de test avec données réelles — plan d'implémentation

> **Pour les agents :** SOUS-COMPÉTENCE REQUISE — utiliser
> `superpowers:subagent-driven-development` (recommandé) ou
> `superpowers:executing-plans` pour dérouler ce plan tâche par tâche. Les
> étapes utilisent des cases à cocher (`- [ ]`).

**Objectif :** disposer d'un second environnement en ligne (Cloud Run + projet
Supabase dédiés) contenant une copie des données de production, resynchronisable
à la demande, sans qu'aucune écriture ne puisse jamais remonter vers la
production.

**Architecture :** deux services Cloud Run supplémentaires pointant vers un
second projet Supabase. Un workflow GitHub Actions copie prod → test
(unidirectionnel). Les sorties vers le monde réel — e-mail, signature
électronique, dépôt DSN — sont neutralisées par des garde-fous applicatifs
pilotés par `APP_ENV` et `EMAIL_FORCE_REDIRECT_TO`.

**Stack :** FastAPI / Python 3.12, React + Vite, Supabase (**PostgreSQL 17.6**
en production), Google Cloud Run, GitHub Actions, `pg_dump` **17+** (un client
plus ancien refuse de dumper un serveur plus récent).

**Coordonnées de production :** projet Supabase `slleauhyjnmiawosvlcg`,
organisation `vvxnsapnmdkpxyxxyvro`, région `eu-west-3`.

**Spec :** `docs/superpowers/specs/2026-07-28-environnement-test-donnees-reelles-design.md`

## Contraintes globales

- **Ne jamais modifier `PAYSLIP_EMAIL_REDIRECT`.** C'est un filet de sécurité de
  production actif pendant la collecte des 148 adresses e-mail manquantes. Le
  nouveau mécanisme s'y ajoute, ne le remplace pas.
- **Ne jamais fabriquer d'adresse e-mail**, y compris dans la base de test
  (règle projet, branche `fix/emails-reels-suppression-placeholders`).
- Aucun comportement de production ne doit changer. Chaque garde-fou est inactif
  quand `APP_ENV` vaut `prod` (valeur par défaut), et un test le vérifie.
- Commande de test backend (depuis `backend/`) :
  `SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key .venv/bin/python -m pytest <chemin> -v`
- Commits fréquents, un par tâche minimum. Messages en français, préfixe
  conventionnel (`feat:`, `fix:`, `test:`, `chore:`, `ci:`, `docs:`).

## Structure des fichiers

| Fichier | Responsabilité |
|---|---|
| `backend/app/core/settings.py` | Modifié : `APP_ENV`, `EMAIL_FORCE_REDIRECT_TO`, helpers d'environnement et parsing des origines CORS |
| `backend/app/main.py` | Modifié : garde de démarrage, origines CORS extensibles |
| `backend/app/shared/infrastructure/email/smtp_sender.py` | Modifié : redirection centralisée aux deux points d'envoi |
| `backend/app/services/yousign_service.py` | Modifié : refus en environnement de test |
| `backend/app/modules/net_entreprises/infrastructure/api_connector.py` | Modifié : refus en environnement de test |
| `backend/app/modules/test_env/` | Créé : endpoint de déclenchement et d'état de la resynchro |
| `scripts/test_env/refresh_from_prod.sh` | Créé : orchestration dump → restauration |
| `scripts/test_env/copy_storage.py` | Créé : copie des objets Storage |
| `scripts/test_env/neutralize_test_db.sql` | Créé : neutralisation post-copie |
| `.github/workflows/refresh-test-from-prod.yml` | Créé : workflow de resynchro |
| `.github/workflows/deploy.yml` | Modifié : `staging` devient l'environnement de test, double build frontend |
| `frontend/src/components/TestEnvBanner.tsx` | Créé : bandeau et bouton de resynchro |

## Découpage

- **Lot 1 — Tâches 1 à 5.** Garde-fous applicatifs. Aucune dépendance
  d'infrastructure, livrable immédiatement.
- **Lot 2 — Tâches 6 à 9.** Projet Supabase de test et resynchro.
  **Bloqué** tant que le jeton Supabase n'est pas disponible (§10 de la spec).
- **Lot 3 — Tâches 10 et 11.** Services Cloud Run et intégration CI.
- **Lot 4 — Tâches 12 et 13.** Interface.

---

## Lot 1 — Garde-fous applicatifs

### Tâche 1 : variables d'environnement et helpers

**Fichiers :**
- Modifier : `backend/app/core/settings.py`
- Créer : `backend/tests/unit/core/test_environment_settings.py`

**Interfaces produites :**
- `APP_ENV: str` — `"prod"` par défaut
- `EMAIL_FORCE_REDIRECT_TO: str | None` — `None` par défaut
- `is_test_environment() -> bool`
- `check_environment_consistency() -> None` — lève `RuntimeError`
- `parse_extra_origins(raw: str | None) -> list[str]`

Les helpers lisent les variables **globales du module** à chaque appel, jamais
une copie capturée : c'est ce qui les rend surchargeable par
`monkeypatch.setattr(settings, ...)` dans les tests, comme le fait déjà
`tests/unit/notifications/test_employee_document_alerts.py`.

- [ ] **Étape 1 : écrire les tests qui échouent**

Créer `backend/tests/unit/core/test_environment_settings.py` :

```python
"""Environnement d'exécution : APP_ENV, redirection e-mail, origines CORS."""

import pytest

from app.core import settings


def test_app_env_defaut_est_prod():
    assert settings.APP_ENV == "prod"
    assert settings.is_test_environment() is False


def test_is_test_environment_vrai_quand_app_env_test(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    assert settings.is_test_environment() is True


def test_check_environment_consistency_ok_en_prod(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "prod")
    monkeypatch.setattr(settings, "EMAIL_FORCE_REDIRECT_TO", None)
    settings.check_environment_consistency()  # ne lève pas


def test_check_environment_consistency_refuse_test_sans_redirection(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "EMAIL_FORCE_REDIRECT_TO", None)
    with pytest.raises(RuntimeError, match="EMAIL_FORCE_REDIRECT_TO"):
        settings.check_environment_consistency()


def test_check_environment_consistency_ok_test_avec_redirection(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "EMAIL_FORCE_REDIRECT_TO", "test@eywai.fr")
    settings.check_environment_consistency()  # ne lève pas


@pytest.mark.parametrize(
    "raw,attendu",
    [
        (None, []),
        ("", []),
        ("   ", []),
        ("https://a.run.app", ["https://a.run.app"]),
        ("https://a.run.app,https://b.run.app", ["https://a.run.app", "https://b.run.app"]),
        (" https://a.run.app , , https://b.run.app ", ["https://a.run.app", "https://b.run.app"]),
    ],
)
def test_parse_extra_origins(raw, attendu):
    assert settings.parse_extra_origins(raw) == attendu
```

- [ ] **Étape 2 : lancer les tests pour vérifier qu'ils échouent**

```bash
cd backend && SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key \
  .venv/bin/python -m pytest tests/unit/core/test_environment_settings.py -v
```

Attendu : `AttributeError: module 'app.core.settings' has no attribute 'APP_ENV'`.

- [ ] **Étape 3 : implémenter**

Dans `backend/app/core/settings.py`, après le bloc `PAYSLIP_EMAIL_REDIRECT`
(ligne 70) :

```python
# --- Environnement d'exécution -------------------------------------------------
# "prod" (défaut) ou "test". Pilote les garde-fous de l'environnement de test :
# redirection e-mail, blocage signature électronique et dépôt DSN.
APP_ENV = (os.getenv("APP_ENV", "prod").strip().lower() or "prod")

# Redirection forcée de TOUS les e-mails sortants, quel que soit leur type.
# Distincte de PAYSLIP_EMAIL_REDIRECT, qui ne couvre que les bulletins et reste
# un filet de production pendant la collecte des adresses manquantes.
EMAIL_FORCE_REDIRECT_TO = os.getenv("EMAIL_FORCE_REDIRECT_TO", "").strip() or None


def is_test_environment() -> bool:
    """True si le service tourne dans l'environnement de test."""
    return APP_ENV == "test"


def check_environment_consistency() -> None:
    """
    Refuse de démarrer un environnement de test sans redirection e-mail.

    Sans cette garde, une variable oubliée suffirait à faire partir de vrais
    e-mails vers de vrais salariés depuis un environnement contenant les
    données réelles. Ici, soit la redirection est active, soit le service ne
    démarre pas.
    """
    if is_test_environment() and not EMAIL_FORCE_REDIRECT_TO:
        raise RuntimeError(
            "APP_ENV=test sans EMAIL_FORCE_REDIRECT_TO : refus de démarrer. "
            "Configurez l'adresse de redirection des e-mails de test."
        )


def parse_extra_origins(raw: str | None) -> list[str]:
    """Découpe une liste d'origines CORS séparées par des virgules."""
    if not raw:
        return []
    return [o.strip() for o in raw.split(",") if o.strip()]


# Origines CORS supplémentaires (frontend de test, etc.). Vide en production.
ALLOWED_ORIGINS_EXTRA = parse_extra_origins(os.getenv("ALLOWED_ORIGINS_EXTRA"))
```

- [ ] **Étape 4 : lancer les tests pour vérifier qu'ils passent**

Même commande qu'à l'étape 2. Attendu : `11 passed`.

- [ ] **Étape 5 : commit**

```bash
git add backend/app/core/settings.py backend/tests/unit/core/test_environment_settings.py
git commit -m "feat(backend): APP_ENV et redirection e-mail forcée pour l'environnement de test"
```

---

### Tâche 2 : refus de démarrage sans redirection

**Fichiers :**
- Modifier : `backend/app/main.py` (après la création de `app`, avant les middlewares)
- Test : couvert par la tâche 1 (`check_environment_consistency`)

**Interfaces consommées :** `settings.check_environment_consistency()`

- [ ] **Étape 1 : brancher la garde au démarrage**

Dans `backend/app/main.py`, juste après le bloc de création de `app` (après la
ligne 62) :

```python
from app.core.settings import check_environment_consistency

# Refuse de démarrer un environnement de test sans redirection e-mail
# (cf. docs/superpowers/specs/2026-07-28-environnement-test-donnees-reelles-design.md §7.3).
check_environment_consistency()
```

- [ ] **Étape 2 : vérifier que la production démarre toujours**

```bash
cd backend && SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key \
  .venv/bin/python -c "import app.main; print('import OK')"
```

Attendu : `import OK` (APP_ENV absent ⇒ `prod` ⇒ aucune levée).

- [ ] **Étape 3 : vérifier que le test sans redirection refuse de démarrer**

```bash
cd backend && APP_ENV=test SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key \
  .venv/bin/python -c "import app.main" 2>&1 | tail -3
```

Attendu : `RuntimeError: APP_ENV=test sans EMAIL_FORCE_REDIRECT_TO : refus de démarrer.`

- [ ] **Étape 4 : vérifier que le test avec redirection démarre**

```bash
cd backend && APP_ENV=test EMAIL_FORCE_REDIRECT_TO=test@eywai.fr \
  SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key \
  .venv/bin/python -c "import app.main; print('import OK')"
```

Attendu : `import OK`.

- [ ] **Étape 5 : commit**

```bash
git add backend/app/main.py
git commit -m "feat(backend): refuser le démarrage d'un environnement de test sans redirection e-mail"
```

---

### Tâche 3 : redirection e-mail centralisée

**Fichiers :**
- Modifier : `backend/app/shared/infrastructure/email/smtp_sender.py`
- Créer : `backend/tests/unit/shared/email/test_smtp_redirect.py`

**Interfaces consommées :** `settings.EMAIL_FORCE_REDIRECT_TO`

**Interfaces produites :**
- `SmtpMailSender._apply_forced_redirect(recipients: list[str], subject: str) -> tuple[list[str], str]`

Le module a exactement deux points d'envoi — `send_email_with_attachments`
(ligne 111) et `send_multipart_email` (ligne 152) — et deux affectations de
`msg["To"]` (lignes 87 et 138). Tous les autres envois, y compris
`send_password_reset_email`, passent par ces deux méthodes. Couvrir ces deux
points couvre donc l'intégralité du courrier sortant.

- [ ] **Étape 1 : écrire les tests qui échouent**

Créer `backend/tests/unit/shared/email/test_smtp_redirect.py` :

```python
"""Redirection forcée de tous les e-mails sortants en environnement de test."""

from unittest.mock import MagicMock, patch

import pytest

from app.core import settings
from app.modules.platform_settings.domain.value_objects import ResolvedEmailConfig
from app.shared.infrastructure.email import smtp_sender as mod


@pytest.fixture
def config_smtp():
    return ResolvedEmailConfig(
        smtp_host="smtp.test",
        smtp_port=587,
        smtp_user="u",
        smtp_password="p",
        smtp_security="starttls",
        from_email="no-reply@eywai.fr",
        from_name="EYWAI",
        reply_to=None,
        frontend_url="https://app.eywai.fr",
    )


@pytest.fixture
def sender(config_smtp):
    s = mod.SmtpMailSender()
    with patch.object(s, "_load_config", return_value=config_smtp):
        yield s


def _serveur_mock():
    serveur = MagicMock()
    serveur.__enter__ = MagicMock(return_value=serveur)
    serveur.__exit__ = MagicMock(return_value=False)
    return serveur


def test_sans_redirection_le_destinataire_est_conserve(sender, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_FORCE_REDIRECT_TO", None)
    serveur = _serveur_mock()
    with patch.object(sender, "_connect", return_value=serveur):
        ok, err = sender.send_multipart_email(
            "salarie@exemple.fr", "Sujet", "texte", "<p>html</p>"
        )
    assert (ok, err) == (True, None)
    msg = serveur.send_message.call_args[0][0]
    assert msg["To"] == "salarie@exemple.fr"
    assert msg["Subject"] == "Sujet"


def test_redirection_remplace_le_destinataire_et_prefixe_le_sujet(sender, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_FORCE_REDIRECT_TO", "bac-a-sable@eywai.fr")
    serveur = _serveur_mock()
    with patch.object(sender, "_connect", return_value=serveur):
        sender.send_multipart_email("salarie@exemple.fr", "Sujet", "texte", "<p>html</p>")
    msg = serveur.send_message.call_args[0][0]
    assert msg["To"] == "bac-a-sable@eywai.fr"
    assert msg["Subject"] == "[dest. salarie@exemple.fr] Sujet"


def test_redirection_couvre_les_envois_avec_pieces_jointes(sender, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_FORCE_REDIRECT_TO", "bac-a-sable@eywai.fr")
    serveur = _serveur_mock()
    with patch.object(sender, "_connect", return_value=serveur):
        sender.send_email_with_attachments(
            ["a@exemple.fr", "b@exemple.fr"],
            "Bulletin",
            "texte",
            "<p>html</p>",
            [("b.pdf", b"%PDF", "application/pdf")],
        )
    msg = serveur.send_message.call_args[0][0]
    assert msg["To"] == "bac-a-sable@eywai.fr"
    assert msg["Subject"] == "[dest. a@exemple.fr, b@exemple.fr] Bulletin"


def test_redirection_ne_depend_pas_de_l_origine_de_la_config(sender, monkeypatch):
    """La config SMTP vient de la base : la redirection s'applique quand même."""
    monkeypatch.setattr(settings, "EMAIL_FORCE_REDIRECT_TO", "bac-a-sable@eywai.fr")
    serveur = _serveur_mock()
    with patch.object(sender, "_connect", return_value=serveur):
        sender.send_multipart_email("salarie@exemple.fr", "Sujet", "t", "<p>h</p>")
    assert serveur.send_message.call_args[0][0]["To"] == "bac-a-sable@eywai.fr"
```

- [ ] **Étape 2 : lancer les tests pour vérifier qu'ils échouent**

```bash
cd backend && SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key \
  .venv/bin/python -m pytest tests/unit/shared/email/test_smtp_redirect.py -v
```

Attendu : les trois tests de redirection échouent (`assert 'salarie@exemple.fr' == 'bac-a-sable@eywai.fr'`).

Si `ResolvedEmailConfig` n'accepte pas ces champs, lire
`backend/app/modules/platform_settings/domain/value_objects.py` et ajuster la
fixture aux champs réels — sans changer les assertions.

- [ ] **Étape 3 : implémenter**

Dans `smtp_sender.py`, ajouter l'import du module de configuration en tête :

```python
from app.core import settings
```

Puis ajouter la méthode dans `SmtpMailSender`, avant `send_email_with_attachments` :

```python
    def _apply_forced_redirect(
        self,
        recipients: Sequence[str],
        subject: str,
    ) -> Tuple[list[str], str]:
        """
        En environnement de test, force tous les destinataires vers l'adresse
        de redirection et reporte les destinataires prévus dans le sujet.

        Lecture dynamique de settings.EMAIL_FORCE_REDIRECT_TO : la valeur est
        résolue à chaque envoi, jamais capturée à l'import.
        """
        forced = settings.EMAIL_FORCE_REDIRECT_TO
        if not forced:
            return list(recipients), subject
        intended = ", ".join(recipients) or "?"
        logger.info("Email redirigé vers %s (dest. prévus %s)", forced, intended)
        return [forced], f"[dest. {intended}] {subject}"
```

Dans `send_email_with_attachments`, remplacer les lignes 72-74 par :

```python
        recipients = [e.strip() for e in to_emails if e and e.strip()]
        if not recipients:
            return True, None
        recipients, subject = self._apply_forced_redirect(recipients, subject)
```

Dans `send_multipart_email`, insérer juste après `config = self._load_config()`
(ligne 133) :

```python
        recipients, subject = self._apply_forced_redirect([to_email], subject)
        to_email = recipients[0]
```

- [ ] **Étape 4 : lancer les tests pour vérifier qu'ils passent**

Même commande qu'à l'étape 2. Attendu : `4 passed`.

- [ ] **Étape 5 : vérifier la non-régression du filet bulletins existant**

```bash
cd backend && SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key \
  .venv/bin/python -m pytest tests/unit/notifications/test_employee_document_alerts.py -v
```

Attendu : `6 passed`. `PAYSLIP_EMAIL_REDIRECT` reste intact.

- [ ] **Étape 6 : commit**

```bash
git add backend/app/shared/infrastructure/email/smtp_sender.py \
        backend/tests/unit/shared/email/test_smtp_redirect.py
git commit -m "feat(backend): rediriger tous les e-mails sortants en environnement de test"
```

---

### Tâche 4 : origines CORS extensibles

**Fichiers :**
- Modifier : `backend/app/main.py:64-71`
- Test : `backend/tests/unit/core/test_environment_settings.py` (complété)

**Interfaces consommées :** `settings.ALLOWED_ORIGINS_EXTRA`

Sans cette tâche, le frontend de test verrait tous ses appels API rejetés par le
navigateur : son origine Cloud Run n'est dans aucune liste.

- [ ] **Étape 1 : écrire le test qui échoue**

Ajouter à `backend/tests/unit/core/test_environment_settings.py` :

```python
def test_origines_extra_ajoutees_sans_toucher_aux_origines_de_prod(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS_EXTRA", "https://sirh-frontend-test.run.app")
    import importlib

    from app.core import settings as settings_mod

    importlib.reload(settings_mod)
    try:
        assert settings_mod.ALLOWED_ORIGINS_EXTRA == [
            "https://sirh-frontend-test.run.app"
        ]
    finally:
        monkeypatch.delenv("ALLOWED_ORIGINS_EXTRA", raising=False)
        importlib.reload(settings_mod)


def test_origines_extra_vides_par_defaut():
    from app.core import settings as settings_mod

    assert settings_mod.ALLOWED_ORIGINS_EXTRA == []
```

- [ ] **Étape 2 : lancer les tests**

```bash
cd backend && SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key \
  .venv/bin/python -m pytest tests/unit/core/test_environment_settings.py -v
```

Attendu : `13 passed` (`ALLOWED_ORIGINS_EXTRA` existe déjà depuis la tâche 1).

- [ ] **Étape 3 : brancher dans main.py**

Remplacer les lignes 64-71 de `backend/app/main.py` par :

```python
from app.core.settings import ALLOWED_ORIGINS_EXTRA

ALLOWED_ORIGINS = [
    "http://localhost:8080",
    "http://localhost:5173",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:5173",
    "https://sirh-frontend-app-505040845625.europe-west1.run.app",
    "https://sirh-frontend-505040845625.europe-west1.run.app",
    # Origines supplémentaires (frontend de test) — vide en production.
    *ALLOWED_ORIGINS_EXTRA,
]
```

- [ ] **Étape 4 : vérifier que la production est inchangée**

```bash
cd backend && SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key \
  .venv/bin/python -c "import app.main; print(app.main.ALLOWED_ORIGINS)"
```

Attendu : exactement les 6 origines d'origine, aucune de plus.

```bash
cd backend && ALLOWED_ORIGINS_EXTRA=https://x.run.app \
  SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key \
  .venv/bin/python -c "import app.main; print(app.main.ALLOWED_ORIGINS[-1])"
```

Attendu : `https://x.run.app`.

- [ ] **Étape 5 : commit**

```bash
git add backend/app/main.py backend/tests/unit/core/test_environment_settings.py
git commit -m "feat(backend): permettre d'ajouter des origines CORS par variable d'environnement"
```

---

### Tâche 5 : blocage de la signature électronique et du dépôt DSN

**Fichiers :**
- Modifier : `backend/app/services/yousign_service.py:61`
- Modifier : `backend/app/modules/net_entreprises/infrastructure/api_connector.py:50`
- Créer : `backend/tests/unit/core/test_test_env_guards.py`

**Interfaces consommées :** `settings.is_test_environment()`

Note : `NetEntreprisesApiConnector.submit_dsn` lève déjà
`NetEntreprisesNotConfigured` et `NET_ENTREPRISES_ENABLED` vaut `False` par
défaut — aucun dépôt réel n'est possible aujourd'hui. La garde est une précaution
pour le jour où l'API sera branchée. **Yousign, en revanche, appelle une API
réelle** : c'est le risque concret que cette tâche supprime.

- [ ] **Étape 1 : écrire les tests qui échouent**

Créer `backend/tests/unit/core/test_test_env_guards.py` :

```python
"""Blocage des sorties vers le monde réel en environnement de test."""

import pytest

from app.core import settings


def test_yousign_refuse_en_environnement_de_test(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    from app.services.yousign_service import YousignService

    with pytest.raises(RuntimeError, match="environnement de test"):
        YousignService().create_signature_request(
            document_content=b"%PDF",
            document_name="doc.pdf",
            signer_email="salarie@exemple.fr",
            signer_first_name="Jean",
            signer_last_name="Dupont",
        )


def test_yousign_ne_bloque_pas_en_production(monkeypatch):
    """En prod, l'absence de clé API reste la seule cause de refus."""
    monkeypatch.setattr(settings, "APP_ENV", "prod")
    monkeypatch.delenv("YOUSIGN_API_KEY", raising=False)
    from app.services.yousign_service import YousignService

    with pytest.raises(Exception) as exc:
        YousignService().create_signature_request(
            document_content=b"%PDF",
            document_name="doc.pdf",
            signer_email="salarie@exemple.fr",
            signer_first_name="Jean",
            signer_last_name="Dupont",
        )
    assert "environnement de test" not in str(exc.value)


def test_depot_dsn_refuse_en_environnement_de_test(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    from app.modules.net_entreprises.infrastructure.api_connector import (
        NetEntreprisesApiConnector,
    )

    with pytest.raises(Exception, match="environnement de test"):
        NetEntreprisesApiConnector().submit_dsn({}, b"<xml/>", {})
```

- [ ] **Étape 2 : lancer les tests pour vérifier qu'ils échouent**

```bash
cd backend && SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key \
  .venv/bin/python -m pytest tests/unit/core/test_test_env_guards.py -v
```

Attendu : échec sur l'absence du message « environnement de test ».

- [ ] **Étape 3 : implémenter la garde Yousign**

Dans `backend/app/services/yousign_service.py`, ajouter en tête :

```python
from app.core import settings
```

Puis en première instruction de `create_signature_request` (après la docstring) :

```python
        if settings.is_test_environment():
            raise RuntimeError(
                "Signature électronique désactivée en environnement de test : "
                "aucune demande n'est envoyée à un signataire réel."
            )
```

- [ ] **Étape 4 : implémenter la garde net-entreprises**

Dans `backend/app/modules/net_entreprises/infrastructure/api_connector.py`,
ajouter en tête :

```python
from app.core import settings
```

Puis en première instruction de `submit_dsn`, avant le `raise` existant :

```python
        if settings.is_test_environment():
            raise NetEntreprisesNotConfigured(
                "Dépôt DSN désactivé en environnement de test : "
                "aucune déclaration n'est transmise."
            )
```

- [ ] **Étape 5 : lancer les tests pour vérifier qu'ils passent**

Même commande qu'à l'étape 2. Attendu : `3 passed`.

- [ ] **Étape 6 : lancer toute la suite unitaire (non-régression)**

```bash
cd backend && SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key \
  .venv/bin/python -m pytest tests/unit -q 2>&1 | tail -5
```

Attendu : aucun échec nouveau par rapport à la référence relevée avant le lot 1.
Relever ce nombre de référence **avant** de commencer la tâche 1.

- [ ] **Étape 7 : commit**

```bash
git add backend/app/services/yousign_service.py \
        backend/app/modules/net_entreprises/infrastructure/api_connector.py \
        backend/tests/unit/core/test_test_env_guards.py
git commit -m "feat(backend): bloquer signature électronique et dépôt DSN en environnement de test"
```

---

## Lot 2 — Projet Supabase de test et resynchro

> **Prérequis bloquant :** jeton d'accès Supabase (`supabase login` ou
> `SUPABASE_ACCESS_TOKEN`). Les tâches 6 à 9 ne peuvent pas démarrer sans lui.

### Tâche 6 : création du projet Supabase de test

**Fichiers :** aucun fichier de code. Résultat consigné dans les secrets GitHub.

- [ ] **Étape 1 : authentifier la CLI**

```bash
supabase login          # ou : export SUPABASE_ACCESS_TOKEN=sbp_xxx
supabase orgs list
supabase projects list
```

Relever : identifiant d'organisation, région du projet de production, et sa
référence (`project ref`).

- [ ] **Étape 2 : créer le projet**

```bash
supabase projects create eywai-test \
  --org-id "<ORG_ID>" \
  --region "<REGION_IDENTIQUE_A_LA_PROD>" \
  --db-password "<MOT_DE_PASSE_FORT_GENERE>"
```

Conserver le mot de passe : il n'est plus affiché ensuite.

- [ ] **Étape 3 : relever les identifiants du projet de test**

```bash
supabase projects list          # référence du projet de test
supabase projects api-keys --project-ref "<TEST_REF>"
```

- [ ] **Étape 4 : enregistrer les secrets GitHub**

```bash
gh secret set SUPABASE_TEST_URL        --body "https://<TEST_REF>.supabase.co"
gh secret set SUPABASE_TEST_KEY        --body "<anon key du projet de test>"
gh secret set SUPABASE_TEST_SERVICE_KEY --body "<service_role key du projet de test>"
gh secret set SUPABASE_TEST_DB_URL     --body "postgresql://postgres:<PWD>@db.<TEST_REF>.supabase.co:5432/postgres"
gh variable set SUPABASE_PROD_REF      --body "<PROD_REF>"
gh variable set SUPABASE_TEST_REF      --body "<TEST_REF>"
```

- [ ] **Étape 5 : vérifier la connexion à la base de test**

```bash
psql "<SUPABASE_TEST_DB_URL>" -c "select current_database(), current_user;"
```

Attendu : une ligne `postgres | postgres`.

---

### Tâche 7 : accès en lecture à la production

**Fichiers :** `scripts/test_env/create_readonly_role.sql` (créé)

**Piège central de ce plan.** PostgreSQL applique la RLS aux rôles non
privilégiés. Un `pg_dump` exécuté par un rôle disposant seulement de `SELECT` sur
des tables protégées par RLS **ne renvoie pas d'erreur : il renvoie zéro ligne**.
La migration `20260722120000_security_rls_advisor_fixes.sql` ayant activé la RLS
sur plusieurs tables, une resynchro naïve produirait un environnement de test
silencieusement vide. L'étape 3 vérifie ce point avant toute utilisation.

- [ ] **Étape 1 : écrire le script de création du rôle**

Créer `scripts/test_env/create_readonly_role.sql` :

```sql
-- Rôle de lecture dédié à la copie prod → test.
-- Ne peut jamais écrire : privilèges SELECT uniquement + sessions en lecture seule.
CREATE ROLE eywai_replica_reader WITH LOGIN PASSWORD :'reader_password';

ALTER ROLE eywai_replica_reader SET default_transaction_read_only = on;

GRANT CONNECT ON DATABASE postgres TO eywai_replica_reader;
GRANT USAGE ON SCHEMA public, auth, storage TO eywai_replica_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public, auth, storage TO eywai_replica_reader;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO eywai_replica_reader;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO eywai_replica_reader;
```

- [ ] **Étape 2 : créer le rôle en production**

```bash
psql "<SUPABASE_DB_URL_PROD>" \
  -v reader_password="'<MOT_DE_PASSE_LECTEUR>'" \
  -f scripts/test_env/create_readonly_role.sql
```

- [ ] **Étape 3 : vérifier que la RLS ne tronque pas la lecture**

Comparer les décomptes vus par le rôle lecteur et par `postgres` sur une table
protégée par RLS :

```bash
psql "<SUPABASE_DB_URL_PROD>" -tAc "select count(*) from public.employees;"
psql "postgresql://eywai_replica_reader:<PWD>@db.<PROD_REF>.supabase.co:5432/postgres" \
  -tAc "select count(*) from public.employees;"
```

- **Si les deux nombres sont identiques** : le rôle lecteur convient, continuer.
- **S'ils diffèrent (typiquement `0` côté lecteur)** : la RLS tronque la lecture.
  Tenter alors :

```bash
psql "<SUPABASE_DB_URL_PROD>" -c "ALTER ROLE eywai_replica_reader BYPASSRLS;"
```

  puis relancer la comparaison. Si Supabase refuse l'attribut `BYPASSRLS`
  (PostgreSQL 15 le réserve au superutilisateur), **replier sur l'option B** :
  utiliser le secret `SUPABASE_DB_URL` de production déjà présent dans le dépôt
  pour le seul `pg_dump`. La garantie de non-écriture repose alors sur trois
  points, à consigner dans la spec : `pg_dump` ouvre explicitement une
  transaction `READ ONLY`, le workflow n'exécute **jamais** `psql` contre la
  production, et le contrôle de décompte de la tâche 9 détecte toute copie
  partielle.

- [ ] **Étape 4 : enregistrer le secret retenu**

```bash
gh secret set SUPABASE_PROD_READ_URL --body "<URL de connexion retenue à l'étape 3>"
```

- [ ] **Étape 5 : commit**

```bash
git add scripts/test_env/create_readonly_role.sql
git commit -m "chore(test-env): rôle PostgreSQL de lecture pour la copie prod vers test"
```

---

### Tâche 8 : script de resynchro

**Fichiers :**
- Créer : `scripts/test_env/refresh_from_prod.sh`
- Créer : `scripts/test_env/neutralize_test_db.sql`
- Créer : `scripts/test_env/copy_storage.py`
- Créer : `backend/tests/unit/core/test_refresh_guard.py`

**Interfaces produites :** script exécutable prenant
`SUPABASE_PROD_READ_URL`, `SUPABASE_TEST_DB_URL`, `SUPABASE_PROD_REF`,
`SUPABASE_TEST_REF` en variables d'environnement.

- [ ] **Étape 1 : écrire le test du garde de destination**

Créer `backend/tests/unit/core/test_refresh_guard.py` :

```python
"""Le script de resynchro doit refuser d'écrire vers la production."""

import subprocess
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[4] / "scripts" / "test_env" / "refresh_from_prod.sh"
)


def _lancer(env_extra):
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "SUPABASE_PROD_READ_URL": "postgresql://r@db.prodref.supabase.co:5432/postgres",
        "SUPABASE_TEST_DB_URL": "postgresql://postgres@db.testref.supabase.co:5432/postgres",
        "SUPABASE_PROD_REF": "prodref",
        "SUPABASE_TEST_REF": "testref",
        **env_extra,
    }
    return subprocess.run(
        ["bash", str(SCRIPT), "--dry-run"], env=env, capture_output=True, text=True
    )


def test_refuse_si_la_cible_est_la_production():
    r = _lancer({"SUPABASE_TEST_REF": "prodref"})
    assert r.returncode != 0
    assert "production" in (r.stderr + r.stdout).lower()


def test_refuse_si_l_url_cible_contient_la_reference_de_production():
    r = _lancer(
        {"SUPABASE_TEST_DB_URL": "postgresql://postgres@db.prodref.supabase.co:5432/postgres"}
    )
    assert r.returncode != 0
    assert "production" in (r.stderr + r.stdout).lower()


def test_accepte_une_cible_de_test():
    r = _lancer({})
    assert r.returncode == 0
```

- [ ] **Étape 2 : lancer le test pour vérifier qu'il échoue**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/core/test_refresh_guard.py -v
```

Attendu : échec, le script n'existe pas.

- [ ] **Étape 3 : écrire le script**

Créer `scripts/test_env/refresh_from_prod.sh` :

```bash
#!/usr/bin/env bash
# Resynchronise l'environnement de test depuis la production.
#
# Sens unique : lit la production, écrit le test. N'exécute jamais d'écriture
# contre la production.
#
# Variables requises :
#   SUPABASE_PROD_READ_URL  connexion de lecture à la production
#   SUPABASE_TEST_DB_URL    connexion à la base de test (écriture)
#   SUPABASE_PROD_REF       référence du projet de production
#   SUPABASE_TEST_REF       référence du projet de test
#
# Option --dry-run : vérifie les gardes puis s'arrête sans rien copier.

set -euo pipefail

: "${SUPABASE_PROD_READ_URL:?SUPABASE_PROD_READ_URL manquant}"
: "${SUPABASE_TEST_DB_URL:?SUPABASE_TEST_DB_URL manquant}"
: "${SUPABASE_PROD_REF:?SUPABASE_PROD_REF manquant}"
: "${SUPABASE_TEST_REF:?SUPABASE_TEST_REF manquant}"

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

# --- Garde de destination -----------------------------------------------------
if [ "$SUPABASE_TEST_REF" = "$SUPABASE_PROD_REF" ]; then
  echo "ERREUR : la cible est la production ($SUPABASE_PROD_REF). Abandon." >&2
  exit 1
fi
if [[ "$SUPABASE_TEST_DB_URL" == *"$SUPABASE_PROD_REF"* ]]; then
  echo "ERREUR : l'URL cible désigne la production ($SUPABASE_PROD_REF). Abandon." >&2
  exit 1
fi

echo "Gardes OK : $SUPABASE_PROD_REF (lecture) -> $SUPABASE_TEST_REF (écriture)"
[ "$DRY_RUN" -eq 1 ] && exit 0

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

# --- 1. Dump de la production -------------------------------------------------
# public : schéma ET données. Restaurer un dump complet dans une base vidée
# supprime les problèmes d'ordre des clés étrangères et la dérive de schéma.
echo "Dump du schéma public..."
pg_dump "$SUPABASE_PROD_READ_URL" \
  --schema=public --no-owner --no-privileges \
  --file "$WORKDIR/public.sql"

# auth : données seules. Le schéma auth est géré par Supabase et existe déjà
# dans un projet neuf ; le recréer casserait l'authentification. Les sessions et
# jetons de rafraîchissement sont exclus : propres au projet source, invalides
# ailleurs.
echo "Dump des comptes de connexion..."
pg_dump "$SUPABASE_PROD_READ_URL" \
  --schema=auth --data-only --no-owner --no-privileges \
  --exclude-table=auth.sessions \
  --exclude-table=auth.refresh_tokens \
  --exclude-table=auth.mfa_amr_claims \
  --exclude-table=auth.flow_state \
  --file "$WORKDIR/auth.sql"

# --- 2. Décomptes de référence (contrôle anti-copie partielle) ----------------
psql "$SUPABASE_PROD_READ_URL" -tAc \
  "select count(*) from public.employees;" > "$WORKDIR/prod_employees.count"

# --- 3. Restauration dans le test --------------------------------------------
echo "Purge de la base de test..."
psql "$SUPABASE_TEST_DB_URL" -v ON_ERROR_STOP=1 \
  -c "drop schema if exists public cascade; create schema public;"

echo "Restauration du schéma public..."
psql "$SUPABASE_TEST_DB_URL" -v ON_ERROR_STOP=1 -f "$WORKDIR/public.sql"

echo "Restauration des comptes de connexion..."
psql "$SUPABASE_TEST_DB_URL" -v ON_ERROR_STOP=1 \
  -c "truncate auth.identities, auth.users cascade;" \
  -f "$WORKDIR/auth.sql"

# --- 4. Neutralisation --------------------------------------------------------
echo "Neutralisation de la base de test..."
psql "$SUPABASE_TEST_DB_URL" -v ON_ERROR_STOP=1 \
  -f "$(dirname "$0")/neutralize_test_db.sql"

# --- 5. Storage ---------------------------------------------------------------
echo "Copie des fichiers Storage..."
python3 "$(dirname "$0")/copy_storage.py"

# --- 6. Contrôle de cohérence -------------------------------------------------
PROD_COUNT="$(cat "$WORKDIR/prod_employees.count")"
TEST_COUNT="$(psql "$SUPABASE_TEST_DB_URL" -tAc "select count(*) from public.employees;")"
if [ "$PROD_COUNT" != "$TEST_COUNT" ]; then
  echo "ERREUR : $PROD_COUNT salariés en production, $TEST_COUNT en test." >&2
  echo "Copie partielle probable (RLS tronquant la lecture, cf. tâche 7)." >&2
  exit 1
fi
echo "Contrôle OK : $TEST_COUNT salariés copiés."

psql "$SUPABASE_TEST_DB_URL" -v ON_ERROR_STOP=1 -c \
  "insert into public.test_env_refresh_log (finished_at, employees_count)
   values (now(), $TEST_COUNT);"

echo "Resynchro terminée."
```

Rendre exécutable :

```bash
chmod +x scripts/test_env/refresh_from_prod.sh
```

- [ ] **Étape 4 : écrire le script de neutralisation**

Créer `scripts/test_env/neutralize_test_db.sql` :

```sql
-- Neutralisation de la base de test après copie.
-- Les adresses e-mail des salariés sont VOLONTAIREMENT conservées : les
-- réécrire reviendrait à fabriquer des adresses (règle projet). La protection
-- vient de EMAIL_FORCE_REDIRECT_TO, sans lequel le backend refuse de démarrer.

-- Journal des resynchros (créé ici car la purge du schéma public l'efface).
CREATE TABLE IF NOT EXISTS public.test_env_refresh_log (
  id bigserial PRIMARY KEY,
  finished_at timestamptz NOT NULL DEFAULT now(),
  employees_count integer
);

-- Configuration SMTP : sans cela, le test hérite des identifiants d'envoi de
-- la production.
UPDATE public.platform_settings
   SET value = NULL
 WHERE key LIKE 'smtp_%' OR key LIKE 'email_%';

-- Files d'envoi et notifications en attente.
TRUNCATE TABLE public.notifications;
```

Avant de figer ce fichier, vérifier les noms réels des tables et colonnes :

```bash
psql "<SUPABASE_TEST_DB_URL>" -c "\d public.platform_settings"
psql "<SUPABASE_TEST_DB_URL>" -c "\dt public.*notification*"
```

Ajuster les `UPDATE` / `TRUNCATE` aux colonnes réellement présentes.

- [ ] **Étape 5 : écrire la copie Storage**

Créer `scripts/test_env/copy_storage.py` :

```python
#!/usr/bin/env python3
"""
Copie les objets Storage de la production vers le projet de test.

Les objets ont deux faces : les fichiers et les lignes storage.objects. Les
lignes arrivent avec le dump ; ce script apporte les fichiers, puis compare les
décomptes pour détecter toute incohérence.

Variables requises :
  SUPABASE_PROD_URL, SUPABASE_PROD_SERVICE_KEY
  SUPABASE_TEST_URL, SUPABASE_TEST_SERVICE_KEY
"""

import os
import sys

import requests

PROD_URL = os.environ["SUPABASE_PROD_URL"].rstrip("/")
PROD_KEY = os.environ["SUPABASE_PROD_SERVICE_KEY"]
TEST_URL = os.environ["SUPABASE_TEST_URL"].rstrip("/")
TEST_KEY = os.environ["SUPABASE_TEST_SERVICE_KEY"]

TIMEOUT = 120


def _headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}", "apikey": key}


def lister_buckets(base: str, key: str) -> list[dict]:
    r = requests.get(f"{base}/storage/v1/bucket", headers=_headers(key), timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def creer_bucket(base: str, key: str, bucket: dict) -> None:
    payload = {
        "id": bucket["id"],
        "name": bucket["name"],
        "public": bucket.get("public", False),
    }
    r = requests.post(
        f"{base}/storage/v1/bucket", headers=_headers(key), json=payload, timeout=TIMEOUT
    )
    if r.status_code not in (200, 201, 409):
        r.raise_for_status()


def lister_objets(base: str, key: str, bucket_id: str) -> list[dict]:
    objets, offset = [], 0
    while True:
        r = requests.post(
            f"{base}/storage/v1/object/list/{bucket_id}",
            headers=_headers(key),
            json={"prefix": "", "limit": 1000, "offset": offset},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        lot = r.json()
        if not lot:
            return objets
        objets.extend(lot)
        offset += len(lot)


def copier_objet(bucket_id: str, chemin: str) -> None:
    src = requests.get(
        f"{PROD_URL}/storage/v1/object/{bucket_id}/{chemin}",
        headers=_headers(PROD_KEY),
        timeout=TIMEOUT,
    )
    src.raise_for_status()
    dst = requests.post(
        f"{TEST_URL}/storage/v1/object/{bucket_id}/{chemin}",
        headers={
            **_headers(TEST_KEY),
            "Content-Type": src.headers.get("Content-Type", "application/octet-stream"),
            "x-upsert": "true",
        },
        data=src.content,
        timeout=TIMEOUT,
    )
    dst.raise_for_status()


def main() -> int:
    total = 0
    ecarts: list[str] = []
    for bucket in lister_buckets(PROD_URL, PROD_KEY):
        creer_bucket(TEST_URL, TEST_KEY, bucket)
        objets = lister_objets(PROD_URL, PROD_KEY, bucket["id"])
        for objet in objets:
            nom = objet.get("name")
            if not nom:
                continue
            copier_objet(bucket["id"], nom)
            total += 1

        # Contrôle de cohérence : fichiers et métadonnées doivent concorder.
        # Un écart signale des liens morts ou des fichiers orphelins côté test.
        copies = lister_objets(TEST_URL, TEST_KEY, bucket["id"])
        if len(copies) != len(objets):
            ecarts.append(f"{bucket['id']} : {len(objets)} en prod, {len(copies)} en test")
        print(f"{bucket['id']} : {len(objets)} objet(s)")

    if ecarts:
        print("ERREUR : décomptes Storage incohérents :", file=sys.stderr)
        for e in ecarts:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"Total copié : {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Étape 6 : lancer les tests du garde**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/core/test_refresh_guard.py -v
```

Attendu : `3 passed`.

- [ ] **Étape 7 : première resynchro réelle, en observation**

```bash
export SUPABASE_PROD_READ_URL="..." SUPABASE_TEST_DB_URL="..." \
       SUPABASE_PROD_REF="..." SUPABASE_TEST_REF="..." \
       SUPABASE_PROD_URL="..." SUPABASE_PROD_SERVICE_KEY="..." \
       SUPABASE_TEST_URL="..." SUPABASE_TEST_SERVICE_KEY="..."
./scripts/test_env/refresh_from_prod.sh
```

Attendu : `Contrôle OK : <N> salariés copiés.` avec `N` égal à l'effectif réel.
Si le script s'arrête sur un écart de décompte, c'est le piège RLS de la
tâche 7 : reprendre l'option B décrite à son étape 3.

- [ ] **Étape 8 : commit**

```bash
git add scripts/test_env/ backend/tests/unit/core/test_refresh_guard.py
git commit -m "feat(test-env): script de resynchro prod vers test avec garde de destination"
```

---

### Tâche 9 : workflow GitHub de resynchro

**Fichiers :** créer `.github/workflows/refresh-test-from-prod.yml`

- [ ] **Étape 1 : écrire le workflow**

```yaml
# Resynchronise l'environnement de test depuis la production.
# Sens unique : lit la prod, écrit le test. Déclenchement manuel ou par
# l'interface de test (repository_dispatch).
name: Refresh test from prod

on:
  workflow_dispatch:
  repository_dispatch:
    types: [refresh-test-env]

concurrency:
  group: refresh-test-env
  cancel-in-progress: false

permissions:
  contents: read

jobs:
  refresh:
    name: Copie prod -> test
    runs-on: ubuntu-latest
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4

      # La prod tourne sous PostgreSQL 17 : un client plus ancien refuse de la
      # dumper. Le dépôt officiel PGDG est nécessaire, les images GitHub
      # n'embarquant pas toujours le client 17.
      - name: Client PostgreSQL 17
        run: |
          sudo apt-get update
          sudo apt-get install -y curl ca-certificates
          sudo install -d /usr/share/postgresql-common/pgdg
          sudo curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
            --fail https://www.postgresql.org/media/keys/ACCC4CF8.asc
          echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] \
            https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
            | sudo tee /etc/apt/sources.list.d/pgdg.list
          sudo apt-get update
          sudo apt-get install -y postgresql-client-17
          pg_dump --version

      - name: Vérifier les secrets requis
        run: |
          missing=""
          [ -z "${{ secrets.SUPABASE_PROD_READ_URL }}" ] && missing="$missing SUPABASE_PROD_READ_URL"
          [ -z "${{ secrets.SUPABASE_TEST_DB_URL }}" ]   && missing="$missing SUPABASE_TEST_DB_URL"
          [ -z "${{ secrets.SUPABASE_TEST_SERVICE_KEY }}" ] && missing="$missing SUPABASE_TEST_SERVICE_KEY"
          if [ -n "$missing" ]; then
            echo "::error::Secrets manquants :$missing"
            exit 1
          fi

      - name: Resynchro
        env:
          SUPABASE_PROD_READ_URL: ${{ secrets.SUPABASE_PROD_READ_URL }}
          SUPABASE_TEST_DB_URL: ${{ secrets.SUPABASE_TEST_DB_URL }}
          SUPABASE_PROD_REF: ${{ vars.SUPABASE_PROD_REF }}
          SUPABASE_TEST_REF: ${{ vars.SUPABASE_TEST_REF }}
          SUPABASE_PROD_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_PROD_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
          SUPABASE_TEST_URL: ${{ secrets.SUPABASE_TEST_URL }}
          SUPABASE_TEST_SERVICE_KEY: ${{ secrets.SUPABASE_TEST_SERVICE_KEY }}
        run: ./scripts/test_env/refresh_from_prod.sh
```

- [ ] **Étape 2 : lancer le workflow**

```bash
gh workflow run "Refresh test from prod"
gh run watch
```

Attendu : succès, avec `Contrôle OK` dans le journal.

- [ ] **Étape 3 : commit**

```bash
git add .github/workflows/refresh-test-from-prod.yml
git commit -m "ci: workflow de resynchro de l'environnement de test"
```

---

## Lot 3 — Services Cloud Run et intégration CI

### Tâche 10 : amorçage des services Cloud Run de test

**Fichiers :** aucun. Résultat consigné dans les variables GitHub.

L'ordre est imposé : `VITE_API_URL` est figé au build du frontend, or l'URL du
backend n'existe qu'une fois son service créé.

- [ ] **Étape 1 : déployer le backend de test avec l'image de production courante**

```bash
IMAGE=$(gcloud run services describe sirh-backend --region europe-west1 \
        --format 'value(spec.template.spec.containers[0].image)')

gcloud run deploy sirh-backend-test \
  --image "$IMAGE" \
  --region europe-west1 \
  --memory 2Gi --timeout 900 --allow-unauthenticated \
  --set-env-vars "APP_ENV=test,EMAIL_FORCE_REDIRECT_TO=<BOITE_DE_TEST>,SUPABASE_URL=<SUPABASE_TEST_URL>,SUPABASE_KEY=<SUPABASE_TEST_KEY>,COPILOT_RH_DATA_ENABLED=true"
```

- [ ] **Étape 2 : relever l'URL du backend de test**

```bash
BACK_TEST=$(gcloud run services describe sirh-backend-test --region europe-west1 \
            --format 'value(status.url)')
echo "$BACK_TEST"
gh variable set VITE_API_URL_TEST --body "$BACK_TEST"
```

- [ ] **Étape 3 : construire et déployer le frontend de test**

```bash
PROJECT=$(gcloud config get-value project)
docker build -t "gcr.io/$PROJECT/sirh-frontend:test-bootstrap" \
  --build-arg VITE_API_URL="$BACK_TEST" \
  --build-arg VITE_APP_ENV=test ./frontend
docker push "gcr.io/$PROJECT/sirh-frontend:test-bootstrap"

gcloud run deploy sirh-frontend-test \
  --image "gcr.io/$PROJECT/sirh-frontend:test-bootstrap" \
  --region europe-west1 --allow-unauthenticated
```

- [ ] **Étape 4 : autoriser l'origine du frontend de test côté backend**

```bash
FRONT_TEST=$(gcloud run services describe sirh-frontend-test --region europe-west1 \
             --format 'value(status.url)')
gh variable set FRONTEND_URL_TEST --body "$FRONT_TEST"

gcloud run services update sirh-backend-test --region europe-west1 \
  --update-env-vars "ALLOWED_ORIGINS_EXTRA=$FRONT_TEST"
```

- [ ] **Étape 5 : vérifier de bout en bout**

```bash
curl -fsS "$BACK_TEST/health"
curl -fsS -o /dev/null -w '%{http_code}\n' "$FRONT_TEST/"
curl -fsS -o /dev/null -w '%{http_code}\n' \
  -H "Origin: $FRONT_TEST" "$BACK_TEST/health"
```

Attendu : `/health` répond, le frontend renvoie `200`, et l'appel avec en-tête
`Origin` du frontend de test n'est pas rejeté. Ouvrir ensuite `$FRONT_TEST` dans
un navigateur et se connecter avec un compte réel — c'est la vérification qui
compte.

---

### Tâche 11 : intégration dans la CI

**Fichiers :** modifier `.github/workflows/deploy.yml`

- [ ] **Étape 1 : construire une seconde image frontend**

Dans le job `build`, après l'étape de build du frontend existante, ajouter :

```yaml
      - uses: docker/build-push-action@v6
        with:
          context: ./frontend
          push: true
          build-args: |
            VITE_API_URL=${{ vars.VITE_API_URL_TEST }}
            VITE_APP_ENV=test
            VITE_APP_BUILD_ID=${{ env.DEPLOY_SHA }}
          tags: gcr.io/${{ vars.GCP_PROJECT_ID }}/sirh-frontend-test:${{ env.DEPLOY_SHA }}
```

Et déclarer la sortie correspondante dans l'étape `id: images` :

```bash
          echo "frontend_test=gcr.io/${P}/sirh-frontend-test:${DEPLOY_SHA}" >> "$GITHUB_OUTPUT"
```

en ajoutant `frontend_test_image: ${{ steps.images.outputs.frontend_test }}` aux
`outputs` du job.

- [ ] **Étape 2 : transformer le job `staging` en déploiement de test**

Renommer le job `staging` en `test-env`, et remplacer ses variables
d'environnement Supabase par celles du test :

```yaml
          env_vars: |-
            APP_ENV=test
            EMAIL_FORCE_REDIRECT_TO=${{ secrets.EMAIL_FORCE_REDIRECT_TO }}
            ALLOWED_ORIGINS_EXTRA=${{ vars.FRONTEND_URL_TEST }}
            SUPABASE_URL=${{ secrets.SUPABASE_TEST_URL }}
            SUPABASE_KEY=${{ secrets.SUPABASE_TEST_KEY }}
            OPENROUTER_API_KEY=${{ secrets.OPENROUTER_API_KEY }}
            COPILOT_RH_DATA_ENABLED=true
```

Les noms de services deviennent `sirh-backend-test` et `sirh-frontend-test`, et
l'image frontend `${{ needs.build.outputs.frontend_test_image }}`.

Le job `production` conserve `needs: [copilot-security-gate, build, test-env]` :
l'environnement de test reste la marche avant la production.

**Point de vigilance :** le job `migrate` applique `supabase db push` sur
`SUPABASE_DB_URL` (production). Ajouter une étape identique visant
`SUPABASE_TEST_DB_URL`, faute de quoi le test dériverait entre deux resynchros.

- [ ] **Étape 3 : ajouter le déploiement d'une branche au choix**

Dans le bloc `on:` du workflow :

```yaml
  workflow_dispatch:
    inputs:
      test_only_ref:
        description: "Branche à déployer uniquement sur l'environnement de test"
        required: false
        type: string
```

et conditionner le job `production` à `github.event.inputs.test_only_ref == ''`.

- [ ] **Étape 4 : vérifier**

```bash
gh workflow run Deploy
gh run watch
```

Attendu : `test-env` puis `production` verts, avec les tests de fumée passants.

- [ ] **Étape 5 : commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: déployer l'environnement de test à la place du faux staging"
```

---

## Lot 4 — Interface

### Tâche 12 : endpoint de resynchro et d'état

**Fichiers :**
- Créer : `backend/app/modules/test_env/api/router.py`
- Créer : `backend/tests/unit/test_env/test_refresh_endpoint.py`
- Modifier : `backend/app/api/router.py` (montage du routeur)

**Interfaces produites :**
- `GET /test-env/status` → `{"is_test": bool, "last_refresh_at": str | None}`
- `POST /test-env/refresh` → `{"triggered": true}` ; `403` hors environnement de test

- [ ] **Étape 1 : écrire les tests qui échouent**

Créer `backend/tests/unit/test_env/test_refresh_endpoint.py` :

```python
"""Endpoint de resynchro : réservé à l'environnement de test et aux admins."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core import settings


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def test_status_indique_prod_par_defaut(client, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "prod")
    r = client.get("/test-env/status")
    assert r.status_code == 200
    assert r.json()["is_test"] is False


def test_refresh_refuse_en_production(client, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "prod")
    r = client.post("/test-env/refresh")
    assert r.status_code == 403


def test_refresh_declenche_le_workflow_en_environnement_de_test(client, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "EMAIL_FORCE_REDIRECT_TO", "test@eywai.fr")
    with patch(
        "app.modules.test_env.api.router.declencher_workflow_resynchro"
    ) as declencher:
        declencher.return_value = True
        r = client.post("/test-env/refresh")
    assert r.status_code == 200
    assert r.json() == {"triggered": True}
    declencher.assert_called_once()
```

- [ ] **Étape 2 : lancer les tests pour vérifier qu'ils échouent**

```bash
cd backend && SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key \
  .venv/bin/python -m pytest tests/unit/test_env/ -v
```

Attendu : `404` sur les routes inexistantes.

- [ ] **Étape 3 : implémenter**

Créer `backend/app/modules/test_env/api/router.py` :

```python
"""Pilotage de la resynchro de l'environnement de test."""

import os

import requests
from fastapi import APIRouter, HTTPException

from app.core import settings
from app.core.database import supabase
from app.core.logging import get_logger

logger = get_logger("test_env.refresh")

router = APIRouter(prefix="/test-env", tags=["test-env"])

GITHUB_REPO = os.getenv("GITHUB_REPO", "alexandreandre/EYWAI")


def declencher_workflow_resynchro() -> bool:
    """Déclenche le workflow GitHub de resynchro via repository_dispatch."""
    token = os.getenv("GITHUB_DISPATCH_TOKEN", "").strip()
    if not token:
        raise HTTPException(
            status_code=500,
            detail="GITHUB_DISPATCH_TOKEN absent : resynchro impossible.",
        )
    r = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPO}/dispatches",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json={"event_type": "refresh-test-env"},
        timeout=30,
    )
    if r.status_code not in (204, 200):
        logger.error("Déclenchement resynchro refusé : %s %s", r.status_code, r.text)
        raise HTTPException(status_code=502, detail="Déclenchement de la resynchro refusé.")
    return True


@router.get("/status")
def statut() -> dict:
    """Indique s'il s'agit de l'environnement de test et la date de dernière resynchro."""
    if not settings.is_test_environment():
        return {"is_test": False, "last_refresh_at": None}
    derniere = None
    try:
        res = (
            supabase.table("test_env_refresh_log")
            .select("finished_at")
            .order("finished_at", desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            derniere = res.data[0]["finished_at"]
    except Exception:
        logger.warning("Journal de resynchro illisible", exc_info=True)
    return {"is_test": True, "last_refresh_at": derniere}


@router.post("/refresh")
def resynchroniser() -> dict:
    """Déclenche une resynchro depuis la production. Environnement de test uniquement."""
    if not settings.is_test_environment():
        raise HTTPException(
            status_code=403,
            detail="La resynchro n'est disponible que dans l'environnement de test.",
        )
    declencher_workflow_resynchro()
    return {"triggered": True}
```

Monter le routeur dans `backend/app/api/router.py`, en suivant le style des
montages existants :

```python
from app.modules.test_env.api.router import router as test_env_router

api_router.include_router(test_env_router)
```

Créer les `__init__.py` nécessaires :

```bash
touch backend/app/modules/test_env/__init__.py \
      backend/app/modules/test_env/api/__init__.py \
      backend/tests/unit/test_env/__init__.py
```

- [ ] **Étape 4 : lancer les tests**

Même commande qu'à l'étape 2. Attendu : `3 passed`.

- [ ] **Étape 5 : créer le jeton GitHub à portée restreinte**

Créer un jeton fin autorisé sur le seul dépôt, permission `Contents: read` et
`Actions: write`, puis :

```bash
gcloud run services update sirh-backend-test --region europe-west1 \
  --update-env-vars "GITHUB_DISPATCH_TOKEN=<JETON>,GITHUB_REPO=<owner/repo>"
```

- [ ] **Étape 6 : commit**

```bash
git add backend/app/modules/test_env backend/tests/unit/test_env backend/app/api/router.py
git commit -m "feat(backend): endpoint de resynchro de l'environnement de test"
```

---

### Tâche 13 : bandeau et bouton de resynchro

**Fichiers :**
- Créer : `frontend/src/components/TestEnvBanner.tsx`
- Modifier : `frontend/src/App.tsx` (montage du bandeau)
- Modifier : `frontend/Dockerfile` (ARG `VITE_APP_ENV`)

**Interfaces consommées :** `GET /test-env/status`, `POST /test-env/refresh`

- [ ] **Étape 1 : exposer `VITE_APP_ENV` au build**

Dans `frontend/Dockerfile`, à côté de `ARG VITE_API_URL` (ligne 11) :

```dockerfile
ARG VITE_APP_ENV=prod
ENV VITE_APP_ENV=${VITE_APP_ENV}
```

- [ ] **Étape 2 : écrire le composant**

Créer `frontend/src/components/TestEnvBanner.tsx` :

```tsx
import { useEffect, useState } from 'react';
import { apiClient } from '@/api/apiConfig';

type Statut = { is_test: boolean; last_refresh_at: string | null };

/**
 * Bandeau permanent de l'environnement de test.
 * Le rendu dépend de VITE_APP_ENV, figé au build : le composant ne peut pas
 * apparaître dans le bundle de production.
 */
export function TestEnvBanner() {
  const estTest = import.meta.env.VITE_APP_ENV === 'test';
  const [statut, setStatut] = useState<Statut | null>(null);
  const [enCours, setEnCours] = useState(false);

  useEffect(() => {
    if (!estTest) return;
    apiClient
      .get<Statut>('/test-env/status')
      .then((r) => setStatut(r.data))
      .catch(() => setStatut(null));
  }, [estTest]);

  if (!estTest) return null;

  const resynchroniser = async () => {
    const ok = window.confirm(
      "Resynchroniser depuis la production ?\n\n" +
        "Toutes les manipulations faites dans l'environnement de test seront " +
        'définitivement perdues et remplacées par les données de production.',
    );
    if (!ok) return;
    setEnCours(true);
    try {
      await apiClient.post('/test-env/refresh');
      window.alert(
        'Resynchro lancée. Elle prend quelques minutes ; rechargez la page ensuite.',
      );
    } catch {
      window.alert('Échec du déclenchement de la resynchro.');
    } finally {
      setEnCours(false);
    }
  };

  const derniere = statut?.last_refresh_at
    ? new Date(statut.last_refresh_at).toLocaleString('fr-FR')
    : 'jamais';

  return (
    <div
      role="status"
      style={{
        background: '#b45309',
        color: '#fff',
        padding: '6px 12px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        fontSize: 14,
        fontWeight: 600,
      }}
    >
      <span>ENVIRONNEMENT DE TEST — les données sont une copie de la production</span>
      <span style={{ fontWeight: 400, opacity: 0.9 }}>
        dernière resynchro : {derniere}
      </span>
      <button
        type="button"
        onClick={resynchroniser}
        disabled={enCours}
        style={{ marginLeft: 'auto', padding: '4px 10px', cursor: 'pointer' }}
      >
        {enCours ? 'Resynchro en cours…' : 'Resynchroniser depuis la prod'}
      </button>
    </div>
  );
}
```

- [ ] **Étape 3 : monter le bandeau**

Dans `frontend/src/App.tsx`, insérer `<TestEnvBanner />` comme premier enfant du
conteneur racine, au-dessus de la navigation. Adapter l'import au style du
fichier (`@/components/TestEnvBanner`).

- [ ] **Étape 4 : vérifier le build dans les deux modes**

```bash
cd frontend && npm ci
VITE_API_URL=https://x VITE_APP_ENV=prod npm run build && grep -rc "ENVIRONNEMENT DE TEST" dist/assets/*.js | grep -v ':0' || echo "absent du bundle prod : OK"
VITE_API_URL=https://x VITE_APP_ENV=test npm run build && grep -rl "ENVIRONNEMENT DE TEST" dist/assets/*.js && echo "présent dans le bundle test : OK"
```

Attendu : la chaîne est absente du bundle de production et présente dans celui de
test. Si elle apparaît dans les deux, le tronc mort n'a pas été éliminé — vérifier
que la comparaison porte bien sur `import.meta.env.VITE_APP_ENV`, que Vite
remplace littéralement au build.

- [ ] **Étape 5 : vérifier dans le navigateur**

Ouvrir l'URL du frontend de test : le bandeau est visible, la date de dernière
resynchro s'affiche. Ouvrir l'URL de production : aucun bandeau.

- [ ] **Étape 6 : commit**

```bash
git add frontend/src/components/TestEnvBanner.tsx frontend/src/App.tsx frontend/Dockerfile
git commit -m "feat(frontend): bandeau et bouton de resynchro de l'environnement de test"
```

---

## Vérification finale

- [ ] **Les workflows planifiés ne visent que la production.** Vérifier que
      `hr-deadline-reminders-dispatch.yml`, `scheduled-exports-dispatch.yml` et
      `collective-agreements-kali-sync.yml` utilisent bien `secrets.SUPABASE_URL`
      (production) et jamais `SUPABASE_TEST_URL` :

```bash
grep -n "SUPABASE" .github/workflows/hr-deadline-reminders-dispatch.yml \
                   .github/workflows/scheduled-exports-dispatch.yml \
                   .github/workflows/collective-agreements-kali-sync.yml
```

  Attendu : aucune occurrence de `SUPABASE_TEST_`. Sinon, un cron nocturne
  enverrait des rappels depuis l'environnement de test.

- [ ] Suite unitaire backend sans régression par rapport à la référence relevée
      avant la tâche 1.
- [ ] `./scripts/run-local-ci-suite.sh` passe.
- [ ] Le backend de production démarre sans `APP_ENV` (défaut `prod`).
- [ ] Le backend de test refuse de démarrer sans `EMAIL_FORCE_REDIRECT_TO`.
- [ ] Un e-mail envoyé depuis le test arrive dans la boîte de test, sujet préfixé
      du destinataire prévu, et **nulle part ailleurs**.
- [ ] Connexion au frontend de test avec un compte réel : les droits sont ceux de
      la production.
- [ ] Une démission fictive dans le test ne modifie rien en production —
      vérification par décompte avant/après côté production.
- [ ] Une resynchro restaure l'état de la production et efface la démission
      fictive.
