# Autonomie du module contract_parser

## Étape A — Analyse des dépendances

### Imports dans le module (tous fichiers)

| Fichier | Import | Cible | Legacy ? |
|---------|--------|-------|----------|
| api/router.py | app.core.security.get_current_user | app/core/* | Non |
| api/router.py | app.modules.users.schemas.responses.User | app/modules/users/* | Non |
| api/router.py | app.modules.contract_parser.* | interne | — |
| application/commands.py | app.modules.contract_parser.* | interne | — |
| application/service.py | app.modules.contract_parser.infrastructure.* | interne | — |
| infrastructure/providers.py | app.modules.contract_parser.domain.* | interne | — |
| Autres | stdlib / pydantic / fastapi / openai / PIL / pdfplumber / PyPDF2 / pdf2image / pytesseract | libs externes | — |

### Dépendances legacy (hors app/*)

- **Aucune.** Aucun import vers api/*, schemas/*, services/*, core/* (racine), backend_calculs/*.

### Dépendances sous app/* (autorisées)

1. **app.core.security** — `get_current_user`  
   - Usage : dépendance FastAPI pour protéger les 3 routes.  
   - Type : sécurité transverse (auth).  
   - Cible correcte : app/core/* (déjà le cas).

2. **app.modules.users.schemas.responses** — `User`  
   - Usage : type du paramètre `current_user` (Depends(get_current_user)).  
   - Type : contrat inter-module (auth retourne User).  
   - Cible correcte : app/modules/users/* (contrat métier inter-module).

### Wrappers de compatibilité

- Aucun. Le module n’utilise pas de wrapper vers le legacy.

---

## Étape B — Modifications appliquées

- Aucune modification structurelle nécessaire : le module ne contenait déjà aucun import legacy.
- Ajout de la documentation des dépendances externes dans api/router.py (docstring).
- Création du présent fichier AUTONOMY.md pour traçabilité.

---

## Étape C — Vérification d’autonomie

1. **Aucun fichier dans app/modules/contract_parser n’importe** : api/*, schemas/*, services/*, core/* (legacy), backend_calculs/*, ni aucun chemin hors app/*.
2. **Imports restants** : app/core/* (security), app.modules.contract_parser.* (interne), app.modules.users.* (User), bibliothèques externes.
3. **Comportement** : aucun changement fonctionnel ni de contrat HTTP.

---

## Verdict

**Module autonome.**

Le module est structurellement autonome et indépendant du legacy. Les seules dépendances hors contract_parser sont app.core.security (auth) et app.modules.users (type User), toutes deux dans app/* et conformes à l’architecture cible.
