# Module payroll

Sous-monolithe paie : moteur de calcul, génération documents, exports.

## Structure

| Dossier | Rôle |
|---------|------|
| `engine/` | Moteur de calcul paie (contexte, lignes, cotisations) |
| `documents/` | Génération bulletins (classique, forfait jour) |
| `application/` | Commandes (`*_commands.py`), pas de façade unique obligatoire |
| `domain/` | Règles métier pures |
| `exports/` | Exports fichiers |

## Règles transverses

- `is_forfait_jour` : `app.shared.domain.employment_rules` (ne pas dupliquer).
- Forfait jour analyse : `app.shared.infrastructure.forfait_jour`.

## Notes

`application/service.py` peut rester minimal ; préférer les commandes dédiées par cas d'usage.
