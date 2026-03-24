# app/modules/payroll/documents/simulated_payslip_generator.py
# Migré depuis services/simulated_payslip_generator.py. Comportement identique.
# Templates : app.core.paths.payroll_engine_templates().

"""
Service de génération HTML/PDF pour les bulletins simulés.
Utilise le même template que les bulletins réels pour assurer la cohérence visuelle.
"""

import io
from pathlib import Path
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from app.core.paths import payroll_engine_templates


class DictToObject:
    """Convertit récursivement un dictionnaire en objet avec accès par attribut"""
    def __init__(self, data):
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    setattr(self, key, DictToObject(value))
                elif isinstance(value, list):
                    setattr(self, key, [DictToObject(item) if isinstance(item, dict) else item for item in value])
                else:
                    setattr(self, key, value)
        else:
            self._value = data

    def __getitem__(self, key):
        return getattr(self, key, None)

    def __iter__(self):
        return iter(self.__dict__.items())

    def get(self, key, default=None):
        return getattr(self, key, default)


class SimulatedPayslipGenerator:
    """Générateur de bulletins de paie simulés au format HTML/PDF"""

    def __init__(self, template_dir: str | Path | None = None):
        """
        Initialise le générateur avec le répertoire des templates.

        Args:
            template_dir: Chemin vers le dossier contenant template_bulletin.html.
                         Par défaut: app.core.paths.payroll_engine_templates().
        """
        if template_dir is None:
            template_dir = payroll_engine_templates()
        self.template_dir = Path(template_dir)

        if not self.template_dir.exists():
            raise FileNotFoundError(f"Le répertoire de templates {self.template_dir} n'existe pas")

        self.env = Environment(loader=FileSystemLoader(str(self.template_dir)))

    def prepare_simulation_data_for_template(self, simulation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prépare les données de simulation pour le template Jinja2.
        Transforme le format de simulation vers le format attendu par template_bulletin.html.
        """
        if 'en_tete' not in simulation_data:
            simulation_data['en_tete'] = {
                'periode': f"{simulation_data.get('month', '??')}/{simulation_data.get('year', '????')}",
                'entreprise': {'raison_sociale': 'Simulation'},
                'salarie': {'nom_complet': 'Simulation', 'statut': 'Simulation'},
            }

        simulation_data['en_tete']['is_simulation'] = True
        simulation_data['en_tete']['watermark_text'] = 'SIMULATION'

        if 'calcul_du_brut' not in simulation_data:
            simulation_data['calcul_du_brut'] = []

        if 'structure_cotisations' not in simulation_data:
            simulation_data['structure_cotisations'] = {
                'bloc_principales': [],
                'total_salarial': 0,
                'total_patronal': 0
            }

        if 'synthese_net' not in simulation_data and 'resultat_final' not in simulation_data:
            simulation_data['synthese_net'] = {
                'net_social_avant_impot': simulation_data.get('net_imposable', 0),
                'net_imposable': simulation_data.get('net_imposable', 0),
                'impot_prelevement_a_la_source': {'montant': 0, 'taux': 0}
            }

        return simulation_data

    def generate_html(self, simulation_data: Dict[str, Any]) -> str:
        """Génère le HTML du bulletin simulé."""
        template_data = self.prepare_simulation_data_for_template(simulation_data)
        template_data_objects = DictToObject(template_data)
        template = self.env.get_template('template_bulletin.html')
        html_content = template.render(template_data_objects.__dict__)
        return html_content

    def generate_pdf(self, simulation_data: Dict[str, Any]) -> bytes:
        """Génère le PDF du bulletin simulé."""
        html_content = self.generate_html(simulation_data)
        base_url = str(self.template_dir)
        pdf_bytes = HTML(string=html_content, base_url=base_url).write_pdf()
        return pdf_bytes

    def generate_pdf_to_file(
        self,
        simulation_data: Dict[str, Any],
        output_path: Path
    ) -> Path:
        """Génère le PDF et l'écrit dans un fichier."""
        pdf_bytes = self.generate_pdf(simulation_data)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(pdf_bytes)
        return output_path

    def generate_pdf_stream(self, simulation_data: Dict[str, Any]) -> io.BytesIO:
        """Génère le PDF et le retourne comme stream."""
        pdf_bytes = self.generate_pdf(simulation_data)
        stream = io.BytesIO(pdf_bytes)
        stream.seek(0)
        return stream


def generate_simulated_payslip_pdf(
    simulation_data: Dict[str, Any],
    output_format: str = 'bytes'
) -> bytes | io.BytesIO | str:
    """
    Fonction utilitaire pour générer rapidement un bulletin simulé.

    Args:
        simulation_data: Données de simulation au format bulletin
        output_format: Format de sortie ('bytes', 'stream', ou 'html')

    Returns:
        bytes | BytesIO | str: Contenu du bulletin selon le format demandé
    """
    generator = SimulatedPayslipGenerator()

    if output_format == 'html':
        return generator.generate_html(simulation_data)
    elif output_format == 'stream':
        return generator.generate_pdf_stream(simulation_data)
    else:
        return generator.generate_pdf(simulation_data)
