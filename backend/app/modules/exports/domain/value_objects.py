# Value objects et constantes du domaine exports (sans dépendance FastAPI ni schemas).
# Ensembles de types d'export pour validation et règles métier.

# Types supportés pour la prévisualisation (comportement identique à l'ancien router).
EXPORT_TYPES_PREVIEW = frozenset({
    "journal_paie",
    "virement_salaires",
    "od_salaires",
    "od_charges_sociales",
    "od_pas",
    "od_globale",
    "export_cabinet_generique",
    "export_cabinet_quadra",
    "export_cabinet_sage",
    "dsn_mensuelle",
})

# Types supportés pour la génération (même liste que preview pour ce module).
EXPORT_TYPES_GENERATE = frozenset({
    "journal_paie",
    "virement_salaires",
    "od_salaires",
    "od_charges_sociales",
    "od_pas",
    "od_globale",
    "export_cabinet_generique",
    "export_cabinet_quadra",
    "export_cabinet_sage",
    "dsn_mensuelle",
})

# Types OD (écritures comptables) — pour branchements conditionnels.
EXPORT_TYPES_OD = frozenset({
    "od_salaires",
    "od_charges_sociales",
    "od_pas",
    "od_globale",
})

# Types cabinet.
EXPORT_TYPES_CABINET = frozenset({
    "export_cabinet_generique",
    "export_cabinet_quadra",
    "export_cabinet_sage",
})
