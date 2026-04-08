# Demarrage rapide (debut de session)

Ce guide te sert de routine quand tu commences a travailler sur le projet.

## Etape 1 - Terminal backend

Depuis la racine du projet :

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
```

Resultat attendu :
- `Uvicorn running on http://127.0.0.1:8000`
- `Waiting for application startup.`

## Etape 2 - Terminal frontend

Depuis la racine du projet :

```bash
cd frontend
npm run dev
```

Resultat attendu :
- `Local: http://localhost:8080/`

## Etape 3 - Terminal git (branche de developpement)

Depuis la racine du projet :

```bash
git branch
```

Verification :
- Tu dois etre sur ta branche de travail (par exemple `dev-jose`).
- Si besoin, bascule dessus avec :

```bash
git checkout dev-jose
```

## Routine conseillee (optionnel)

Dans le terminal git, tu peux lancer rapidement :

```bash
git status
```

Pour verifier les fichiers modifies avant de commencer.
