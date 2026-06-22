"""Tests unitaires — dédoublonnage import CP."""

from app.modules.admin_import.application.cp_import import _dedupe_pages
from app.modules.admin_import.application.cp_payslip_parser import ParsedPayslipPage


def _page(
    *,
    siret: str = "49861035100013",
    matricule: str = "BOUFRIDA",
    year: int = 2026,
    month: int = 5,
    n1: float = 0.0,
    n: float = 11.96,
    source: str = "a.pdf",
    page: int = 1,
) -> ParsedPayslipPage:
    return ParsedPayslipPage(
        source_file=source,
        page_index=page,
        parse_format="cegid_clarifie",
        siret=siret,
        matricule=matricule,
        year=year,
        month=month,
        cp_n1_solde=n1,
        cp_n_solde=n,
    )


class TestDedupePages:
    def test_identical_pages_collapsed(self):
        pages = [_page(page=1), _page(page=2, source="b.pdf")]
        deduped, removed, conflicts = _dedupe_pages(pages)
        assert len(deduped) == 1
        assert removed == 1
        assert conflicts == []

    def test_conflicting_soldes_reported(self):
        pages = [_page(n1=0.0), _page(n1=5.0, page=2)]
        deduped, removed, conflicts = _dedupe_pages(pages)
        assert len(deduped) == 1
        assert removed == 1
        assert len(conflicts) == 1
