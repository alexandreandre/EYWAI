# Demarrage rapide (debut de session)

Ce guide te sert de routine quand tu commences a travailler sur le projet.

## Etape 1 - Terminal git (branche de developpement)

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

## Etape 2 - Mettre a jour ta branche dev avec main (sans toucher main)

Version terminal (enchainement unique) :

```bash
git fetch origin && git merge origin/main && git status --short --branch
```

Version prompt (unique, a donner a Cursor) :

`mets a jour ma branche dev-jose avec main sans toucher main, puis confirme le status final`

## Etape 3 - Terminal backend

Depuis la racine du projet :

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
```

Resultat attendu :
- `Uvicorn running on http://127.0.0.1:8000`
- `Waiting for application startup.`

## Etape 4 - Terminal frontend

Depuis la racine du projet :

```bash
cd frontend
npm run dev
```

Resultat attendu :
- `Local: http://localhost:8080/`

## Routine conseillee (optionnel)

Dans le terminal git, tu peux lancer rapidement :

```bash
git status
```

Pour verifier les fichiers modifies avant de commencer.

Phrase utile pour deleguer commit + push a Cursor :
`je veux commit et push les changements que j'ai fait sur ma branche dev-jose`
