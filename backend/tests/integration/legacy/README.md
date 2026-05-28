# Tests legacy (racine `backend/tests/test_*.py`)

Ces fichiers restent à la racine `tests/` pour compatibilité CI historique.

**Migration progressive** : déplacer vers `tests/integration/legacy/` et marquer `@pytest.mark.integration`.

Nouveaux tests : préférer `tests/integration/<module>/`.
