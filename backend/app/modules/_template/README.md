# Template module métier

Copier cette structure pour un nouveau module :

```
<module>/
  api/router.py          # HTTP uniquement
  api/dependencies.py    # optionnel
  application/
    commands.py
    queries.py
    service.py           # optionnel
  domain/
    rules.py
    interfaces.py
  infrastructure/
    repository.py
    queries.py
  schemas/
```

Tests : `tests/unit/<module>/`, `tests/integration/<module>/`.
