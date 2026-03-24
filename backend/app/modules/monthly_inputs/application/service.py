"""
Service applicatif monthly_inputs.

Toute la logique métier des anciens routeurs est centralisée ici :
- commands.py : création (batch, single), suppression (par id, par employé).
- queries.py : listes par période / employé + période, catalogue de primes (parsing config_data).
- dto.py : résultats des cas d'usage (CreateBatchResultDto, CreateSingleResultDto, ListMonthlyInputsResultDto).

Ce module est réservé à une orchestration partagée future (ex. règles de validation métier,
coordination multi-étapes). Pour l’instant les cas d’usage sont uniquement dans commands et queries.
"""
