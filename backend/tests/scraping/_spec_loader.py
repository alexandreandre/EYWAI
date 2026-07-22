"""Charge le SPEC d'un dossier scraper sous un nom de module unique.

Évite la collision sys.modules["spec"] quand plusieurs test_<x>_spec.py
chargent chacun le spec.py de leur dossier dans le même run pytest.
"""
import importlib.util
import sys
from pathlib import Path

SCRAPING = Path(__file__).resolve().parents[2] / "scraping"
if str(SCRAPING) not in sys.path:
    sys.path.insert(0, str(SCRAPING))


def load_spec(folder_name: str):
    spec_path = SCRAPING / folder_name / "spec.py"
    mod_name = f"_scraper_spec_{folder_name}"
    spec = importlib.util.spec_from_file_location(mod_name, spec_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module.SPEC
