"""Tests DSN spécifiques aux alternants (codes dispositif, validations)."""

from __future__ import annotations

from app.modules.payroll.exports.dsn import code_dispositif_politique_publique


class TestCodeDispositifPolitiquePublique:
    def _config(self):
        return {
            "codes_dispositif_politique_publique": {
                "Apprentissage": "64",
                "Contrat de professionnalisation": "61",
            }
        }

    def test_apprentissage(self):
        assert (
            code_dispositif_politique_publique(self._config(), "Apprentissage")
            == "64"
        )

    def test_professionnalisation(self):
        assert (
            code_dispositif_politique_publique(
                self._config(), "Contrat de professionnalisation"
            )
            == "61"
        )

    def test_cdi_aucun_dispositif(self):
        assert code_dispositif_politique_publique(self._config(), "CDI") is None

    def test_type_absent(self):
        assert code_dispositif_politique_publique(self._config(), None) is None

    def test_config_vide(self):
        assert code_dispositif_politique_publique({}, "Apprentissage") is None
