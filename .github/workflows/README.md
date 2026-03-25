# Workflows GitHub Actions

Les définitions YAML sont dans ce dossier. **Guide pas à pas pour débutants** (hooks + GitHub + déploiement) : **[GUIDE_SIMPLE.md](GUIDE_SIMPLE.md)**.

Résumé ultra court :

| Fichier | Rôle |
|---------|------|
| `ci.yml` | Vérifs auto sur chaque PR et push sur `main`. |
| `pull-request.yml` | À chaque PR : zip de contexte ; à la main : commentaire IA sur une PR. |
| `deploy.yml` | Build Docker et déploiement Cloud Run après push sur `main`. |

Déploiement GCP en détail : **[DEPLOIEMENT.md](../../DEPLOIEMENT.md)**.
