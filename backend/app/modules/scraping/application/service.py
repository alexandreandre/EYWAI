"""
Service applicatif du module scraping.

Orchestration partagée : la commande execute_scraper (commands.execute_scraper) centralise
la résolution source_key -> source_data, la validation (source active), la création du job
et le lancement du runner en arrière-plan. Les queries délèguent au repository avec
enrichissement (last_job, success_rate_30d, etc.) dans queries.py.
Aucune logique métier supplémentaire ici pour l'instant.
"""
from __future__ import annotations
