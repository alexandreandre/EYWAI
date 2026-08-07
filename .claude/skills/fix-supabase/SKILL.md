---
name: fix-supabase
description: >-
  Use when the Supabase MCP is broken, disconnected, Pending approval, Needs
  authentication, Failed to connect, missing tools (list_tables, execute_sql,
  apply_migration), or when the user types /fix-supabase. Repairs Claude Code
  MCP so the session can keep working on the same EYWAI projects as before.
---

# Fix Supabase (`/fix-supabase`)

## Objectif

Remettre le MCP Supabase **en état de marche dans la session courante**, branché
sur les mêmes projets qu’avant, sans abandonner le travail en cours.

| Serveur | Projet | Rôle |
|---------|--------|------|
| `supabase-eywai-prod` | `slleauhyjnmiawosvlcg` | Instance métier EYWAI (dev = prod) |
| `supabase-eywai-test` | `tlvkjwleahkmuzcegrde` | Environnement de test |

Auth : Personal Access Token `SUPABASE_ACCESS_TOKEN` (jamais l’afficher).

## Règle absolue

1. **Exécuter le script** — ne pas « réparer à la main » avant.
2. **Vérifier avec un outil MCP** après le script.
3. **Ne redémarrer la session que en dernier recours** (après `/mcp`).

## Étape 1 — Lancer le script

Depuis la racine du dépôt :

```bash
bash .claude/skills/fix-supabase/fix-supabase.sh
```

Le script :
- réécrit `.mcp.json` canonique (prod + test, features complètes) ;
- vérifie le token (sans l’imprimer) via l’API Management ;
- persiste le token dans `.claude/settings.local.json` **et** `~/.claude/settings.json`
  (sinon VS Code / Claude lancés depuis le Dock → `Unauthorized`) ;
- enregistre prod + test en **scope local** (`claude mcp add -s local`) — bypass
  du gate `Pending approval` sur `.mcp.json` ;
- réécrit `enabledMcpjsonServers` dans `~/.claude.json` **après** chaque appel
  `claude` (sinon `claude mcp list` les efface et le prochain boot revient en Pending) ;
- health-check `claude mcp list`.

Si exit ≠ 0 : lire le message, corriger (token manquant / invalide), relancer
**une fois**. Ne pas inventer un autre setup HTTP/OAuth. Ne jamais coller
`claude mcp get` (affiche le PAT).

## Étape 2 — Recharger les outils dans *cette* session

Si `claude mcp list` dit Connected mais les tools MCP sont absents du tour :

1. Demander à l’utilisateur de taper **`/mcp`** et de réactiver / rafraîchir
   `supabase-eywai-prod` (et test si besoin).
2. **Ne pas** proposer de nouvelle session tant que `/mcp` n’a pas été tenté.
3. Seulement si `/mcp` échoue encore : demander un restart Claude Code
   (l’état disque est déjà réparé — au reboot ça doit reconnecter).

## Étape 3 — Smoke-test MCP (obligatoire)

Appeler un outil du serveur **prod** :

- `list_tables` (schéma `public`), **ou**
- `execute_sql` avec `select 1 as ok;`

Puis, si pertinent, un appel équivalent sur `supabase-eywai-test`.

**Succès** = réponse JSON/SQL normale, pas d’erreur auth / connection.

## Étape 4 — Rapport court

```markdown
## /fix-supabase

- Script : OK / FAIL (exit N)
- supabase-eywai-prod (`slleauhyjnmiawosvlcg`) : Connected + smoke OK / …
- supabase-eywai-test (`tlvkjwleahkmuzcegrde`) : …
- Action utilisateur : aucune / taper /mcp / redémarrer Claude
- Suite : on peut continuer le travail DB
```

Ensuite **reprendre la tâche en cours** avec le MCP.

## Interdits

| Excuse | Réalité |
|--------|---------|
| « Je répare à la main sans le script » | Le script est la procédure. Lancer le `.sh`. |
| « Il faut une nouvelle session » | D’abord script → `/mcp` → smoke. Restart = dernier recours. |
| « Je bascule sur l’URL HTTP Cursor » | Claude Code = `.mcp.json` + PAT npx. Ne pas mélanger. |
| « J’affiche le token pour debug » | Jamais. Longueur / HTTP code seulement. |
| « Pending approval, je ne peux rien faire » | Le script écrit `enabledMcpjsonServers`. Relancer le `.sh`. |

## Symptômes → action

| Symptôme | Action |
|----------|--------|
| `Pending approval` | Étape 1 (script) |
| `Needs authentication` / token HTTP ≠ 200 | Étape 1 ; si fail → PAT dashboard → `settings.local.json` |
| `Failed to connect` | Étape 1 (escalade local) |
| Tools absents alors que Connected | Étape 2 (`/mcp`) |
| Auth OK mais tools morts | Étape 2 puis restart |
