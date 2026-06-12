"""Tests registre fournisseurs comptables."""

from app.modules.accounting_integration.domain.providers import (
    PROVIDER_REGISTRY,
    get_provider_definition,
    list_provider_definitions,
    mode_from_provider_key,
    provider_key_from_mode,
)


class TestProviderRegistry:
    def test_manual_provider_exists(self):
        manual = get_provider_definition("manual")
        assert manual is not None
        assert manual.connector_class == "manual"

    def test_cegid_quadra_metadata(self):
        cegid = PROVIDER_REGISTRY["cegid_quadra"]
        assert cegid.logo_key == "cegid"
        assert cegid.mode == "api_quadra"
        assert "api" in cegid.capabilities

    def test_list_definitions_includes_stubs(self):
        keys = {d.key for d in list_provider_definitions()}
        assert "sage" in keys
        assert "pennylane" in keys

    def test_mode_mapping_roundtrip(self):
        assert provider_key_from_mode("api_quadra") == "cegid_quadra"
        assert mode_from_provider_key("cegid_quadra") == "api_quadra"
