"""Las salidas del karate: el CSV del combate, la exportación y los informes.

Son los módulos de siempre, entregados por el contrato (``Salidas``,
decisión 0004) para que el núcleo no los importe; desde la fase F4 viven en
este paquete. Se cargan al pedirlos, como antes.
"""
from __future__ import annotations

from typing import Any


class SalidasKarate:
    def csv_del_combate(self) -> Any:
        from karlos_karate import csv_combate
        return csv_combate

    def exportador(self) -> Any:
        from karlos_karate.export_manager import ExportManager
        return ExportManager()

    def vista_informe(self, colors: Any, sport_meta: dict, parent: Any = None) -> Any:
        from karlos_karate.match_report import MatchReportView
        return MatchReportView(colors=colors, sport_meta=sport_meta, parent=parent)

    def informe_pdf(self, **datos: Any) -> str:
        from karlos_karate.pdf_report_generator import generate_professional_report
        return generate_professional_report(**datos)

    def informe_entrenador(self) -> Any:
        from karlos_karate.relatorio_treinador import RelatorioTreinador
        return RelatorioTreinador()

    def probar(self) -> tuple[bool, str]:
        """Que el informe PDF entra en el ejecutable (reportlab dentro)."""
        from karlos_karate import pdf_report_generator  # noqa: F401
        return True, "reportlab dentro"


SALIDAS = SalidasKarate()
