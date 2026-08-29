"""services.renderer_stub — the C3.6 stub renderer.

C3.6 is a seam: ReportService talks to a Renderer, and the composition root
decides whether that is this stub or the real WeasyPrint one. The stub exists
so the report path can be built and tested without a PDF dependency
installed, and so wiring tests never depend on the renderer.

C3.6 frozen behaviour for the stub:
  to_html returns a deterministic canned string containing the payload's
          project code and the fixed token 'STUB-REPORT'
  to_pdf  returns minimal valid PDF bytes — a one-page blank document built
          from a byte constant here

Anti-pattern #9: this stub's output must never reach a real answer. Only the
composition root chooses it.
"""

from __future__ import annotations

from typing import Any

#: The token that marks stub output. Tests assert on it; if it appears in a
#: real report, a stub leaked past the composition root.
STUB_TOKEN = "STUB-REPORT"

#: A minimal, valid, single-page PDF. Kept as a byte constant so the stub
#: needs no PDF library at all.
_STUB_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n"
    b"%%EOF\n"
)


class StubRenderer:
    """C3.6 Renderer — canned, deterministic, dependency-free."""

    def to_html(self, payload: Any) -> str:
        """Deterministic canned html: same payload in, same bytes out.

        Carries the project code so a test can tell which project the stub
        was asked about, and STUB_TOKEN so stub output is identifiable
        anywhere it appears.
        """
        code = getattr(getattr(payload, "project", None), "code", "UNKNOWN")
        return (
            "<!doctype html>\n"
            "<html><head><title>"
            f"{STUB_TOKEN} {code}"
            "</title></head>\n"
            f"<body><h1>{STUB_TOKEN}</h1><p>project: {code}</p></body></html>\n"
        )

    def to_pdf(self, html_text: str) -> bytes:
        """Minimal valid one-page PDF. The html is not rendered — the stub
        proves the seam, not the layout."""
        return _STUB_PDF
