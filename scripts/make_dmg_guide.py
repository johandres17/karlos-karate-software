"""Generate the Gatekeeper unlock guide bundled inside the macOS DMG.

Writes two files into the given staging directory:
- "LEEME - Cómo abrir la app.pdf" (bilingual ES/EN guide)
- "LEEME.txt" (plain-text fallback)

Usage: python scripts/make_dmg_guide.py <staging_dir>
"""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
# El nombre y la versión son los de la edición que se empaqueta (decisión
# 0006): Karlos Karate.
sys.path.insert(0, str(ROOT / "src"))
from karlos_ediciones.karate import EDICION  # noqa: E402

NOMBRE = EDICION.nombre
VERSION = EDICION.version

INK = HexColor("#1a1a2e")
ACCENT = HexColor("#c0392b")
MUTED = HexColor("#555566")
CODE_BG = HexColor("#f2f2f7")


def build_pdf(out_path: Path) -> None:
    title = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=20,
                           textColor=INK, spaceAfter=2)
    subtitle = ParagraphStyle("subtitle", fontName="Helvetica", fontSize=11,
                              textColor=MUTED, spaceAfter=10)
    h = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=13,
                       textColor=ACCENT, spaceBefore=12, spaceAfter=4)
    body = ParagraphStyle("body", fontName="Helvetica", fontSize=10.5,
                          textColor=INK, leading=15, spaceAfter=5)
    en = ParagraphStyle("en", parent=body, textColor=MUTED, fontSize=9.5,
                        leading=13)
    code = ParagraphStyle("code", fontName="Courier-Bold", fontSize=10.5,
                          textColor=INK, backColor=CODE_BG, leading=16,
                          borderPadding=6, spaceBefore=4, spaceAfter=6)

    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4, topMargin=18 * mm, bottomMargin=15 * mm,
        leftMargin=20 * mm, rightMargin=20 * mm,
        title=f"{NOMBRE} — Guía de instalación",
        author="Johan Robalino",
    )

    story = [
        Paragraph(f"{NOMBRE.upper()} v{VERSION}", title),
        Paragraph("Guía de instalación para macOS · macOS Install Guide", subtitle),
        HRFlowable(width="100%", thickness=1, color=ACCENT),

        Paragraph("1 · Instalar / Install", h),
        Paragraph(f"Arrastra <b>{NOMBRE}</b> a la carpeta <b>Aplicaciones</b> "
                  "(el acceso directo está en esta misma ventana).", body),
        Paragraph(f"Drag <b>{NOMBRE}</b> into the <b>Applications</b> folder "
                  "(shortcut in this window).", en),

        Paragraph("2 · Primer arranque — macOS mostrará una advertencia", h),
        Paragraph('Al abrir la app por primera vez, macOS dirá que <i>"no puede verificar que '
                  f'{NOMBRE} no contenga malware"</i>. Esto es normal: la app no está '
                  "inscrita en el programa de desarrolladores de pago de Apple. "
                  "<b>No está dañada ni contiene malware.</b> Desbloquéala una sola vez:", body),
        Paragraph(f'On first launch macOS will say it <i>"cannot verify that {NOMBRE} '
                  'does not contain malware"</i>. The app is not damaged — unlock it once:', en),

        Paragraph("Opción A — Ajustes del Sistema (recomendada / recommended)", h),
        Paragraph("1. Haz doble clic en la app; cuando aparezca la advertencia, pulsa <b>OK</b>.<br/>"
                  "2. Abre <b>Ajustes del Sistema → Privacidad y seguridad</b>.<br/>"
                  f"3. Baja hasta el mensaje <i>\"Se bloqueó '{NOMBRE}' para proteger tu Mac\"</i>.<br/>"
                  "4. Pulsa <b>«Abrir de todos modos»</b> y confirma con tu contraseña.", body),
        Paragraph("Double-click the app, press OK on the warning, then go to "
                  "<b>System Settings → Privacy &amp; Security</b>, scroll down and click "
                  "<b>“Open Anyway”</b>.", en),

        Paragraph("Opción B — Terminal (si la Opción A no aparece)", h),
        Paragraph("Abre la app <b>Terminal</b>, pega esta línea y pulsa Enter / "
                  "Open <b>Terminal</b>, paste this line and press Enter:", body),
        Paragraph(f'xattr -cr "/Applications/{NOMBRE}.app"', code),
        Paragraph("Después abre la app normalmente. Solo hace falta una vez. / "
                  "Then open the app normally. Needed only once.", en),

        Paragraph("Requisitos / Requirements", h),
    ]

    req = Table([
        ["Mac", "Apple Silicon (M1, M2, M3, M4…) — no compatible con Mac Intel / not Intel-compatible"],
        ["macOS", "12 Monterey o superior / or later"],
    ], colWidths=[28 * mm, 132 * mm])
    req.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [req, Spacer(1, 8),
              HRFlowable(width="100%", thickness=0.5, color=MUTED),
              Paragraph(f"{NOMBRE} · Elite Combat Intelligence · Johan Robalino", en)]

    doc.build(story)


LEEME_TXT = f"""{NOMBRE.upper()} v{VERSION} — macOS (Apple Silicon)
================================================

1) Arrastra "{NOMBRE}" a la carpeta Aplicaciones.

2) Al abrirla por primera vez, macOS dira que "no puede verificar
   que la app no contenga malware". Es normal (la app no esta
   inscrita en el programa de pago de Apple). NO esta danada.

   Desbloqueala UNA sola vez:

   OPCION A: doble clic en la app > OK en la advertencia >
   Ajustes del Sistema > Privacidad y seguridad > bajar hasta
   "Se bloqueo '{NOMBRE}'..." > pulsar "Abrir de todos modos".

   OPCION B (Terminal): pega esta linea y pulsa Enter:
   xattr -cr "/Applications/{NOMBRE}.app"

Requisitos: Mac con Apple Silicon (M1/M2/M3/M4) y macOS 12 o superior.
No funciona en Mac con procesador Intel.

Ver guia completa: "LEEME - Como abrir la app.pdf" (en esta ventana).
"""


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/make_dmg_guide.py <staging_dir>")
    stage = Path(sys.argv[1])
    stage.mkdir(parents=True, exist_ok=True)
    build_pdf(stage / "LEEME - Cómo abrir la app.pdf")
    (stage / "LEEME.txt").write_text(LEEME_TXT, encoding="utf-8")
    print(f"Guide files written to {stage} (v{VERSION})")


if __name__ == "__main__":
    main()
