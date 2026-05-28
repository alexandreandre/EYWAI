## Résumé

<!-- Quoi et pourquoi -->

## Checklist architecture

- [ ] Couches backend respectées (pas d'import DB dans routers hors allowlist documentée)
- [ ] Pas de `HTTPException` ajouté en couche `application/`
- [ ] Résolution employé via `app.shared.employee_resolution` si applicable
- [ ] Front : pas d'import `@/pages/` depuis `components/` ou `hooks/`
- [ ] `npm run test` et `npm run build` (frontend) / `pytest tests/unit` (backend) passent
- [ ] Routes / OpenAPI inchangées ou changelog explicite

## Tests

<!-- Scénarios manuels ou automatisés -->
