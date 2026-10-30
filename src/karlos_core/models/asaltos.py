"""Dónde empieza y dónde acaba cada asalto, en fotogramas.

Johan, 7 de octubre de 2026: «son algunos rounds, hay que determinar cuándo
inicia el round y cuándo finaliza, dejarlo fijo, y que no se borre a cada
rato».

Las dos ideas que lo gobiernan:

- **Es un hecho del vídeo, no de la pasada.** El asalto empieza y acaba en
  los mismos fotogramas para quien anota al primer competidor y para quien
  anota al segundo. Por eso se guarda con la sesión y no se borra al cambiar
  de atleta, que es lo que pasaba antes con el inicio y el fin del combate.
- **Las marca el evaluador.** El programa no adivina dónde empieza un asalto:
  dice dónde está el vídeo y apunta lo que le marcan (decisión 0001).

Un deporte de un solo asalto —el karate— no necesita nada de esto y sigue con
su inicio y su fin de combate de siempre.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Asaltos:
    """Las marcas de los asaltos de un combate."""

    total: int = 1
    inicios: list[Optional[int]] = field(default_factory=list)
    finales: list[Optional[int]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.total = max(1, int(self.total))
        self.inicios = (list(self.inicios) + [None] * self.total)[:self.total]
        self.finales = (list(self.finales) + [None] * self.total)[:self.total]

    # ── Consulta ────────────────────────────────────────────────────
    def inicio(self, n: int) -> Optional[int]:
        """El fotograma en que empieza el asalto n (1 = el primero)."""
        return self.inicios[n - 1] if 1 <= n <= self.total else None

    def fin(self, n: int) -> Optional[int]:
        return self.finales[n - 1] if 1 <= n <= self.total else None

    def completo(self, n: int) -> bool:
        return self.inicio(n) is not None and self.fin(n) is not None

    @property
    def inicio_del_combate(self) -> Optional[int]:
        """Donde empieza el primer asalto marcado."""
        marcados = [f for f in self.inicios if f is not None]
        return min(marcados) if marcados else None

    @property
    def fin_del_combate(self) -> Optional[int]:
        """Donde acaba el último asalto marcado."""
        marcados = [f for f in self.finales if f is not None]
        return max(marcados) if marcados else None

    def de_fotograma(self, frame: int) -> int:
        """En qué asalto cae ese fotograma; 0 si no cae en ninguno.

        Con el asalto empezado y todavía sin cerrar, cuenta desde su inicio:
        mientras se anota el asalto 2, lo que se anota es del 2.
        """
        frame = int(frame)
        for n in range(1, self.total + 1):
            ini, fin = self.inicio(n), self.fin(n)
            if ini is None:
                continue
            if frame >= ini and (fin is None or frame <= fin):
                return n
        return 0

    @property
    def en_curso(self) -> int:
        """El asalto que se está marcando: el primero sin cerrar, o el
        siguiente sin empezar. Si están todos cerrados, el último."""
        for n in range(1, self.total + 1):
            if self.inicio(n) is None or self.fin(n) is None:
                return n
        return self.total

    @property
    def marcados(self) -> int:
        """Cuántos asaltos tienen inicio y fin."""
        return sum(1 for n in range(1, self.total + 1) if self.completo(n))

    # ── Marcar ──────────────────────────────────────────────────────
    def marcar_inicio(self, n: int, frame: int) -> None:
        """Volver a marcarlo es corregirlo: se queda el último."""
        if 1 <= n <= self.total:
            self.inicios[n - 1] = int(frame)

    def marcar_fin(self, n: int, frame: int) -> None:
        if 1 <= n <= self.total:
            self.finales[n - 1] = int(frame)

    def borrar(self, n: int) -> None:
        if 1 <= n <= self.total:
            self.inicios[n - 1] = self.finales[n - 1] = None

    # ── Guardar y reponer ───────────────────────────────────────────
    def a_lista(self) -> list[dict[str, Any]]:
        """Para la sesión guardada: una fila por asalto."""
        return [{"asalto": n, "inicio": self.inicio(n), "fin": self.fin(n)}
                for n in range(1, self.total + 1)]

    @classmethod
    def de_lista(cls, filas: Any, total: int) -> "Asaltos":
        """Lo guardado, de vuelta. Lo que no se entienda se ignora: una
        sesión vieja no tiene asaltos y empieza sin marcas."""
        asaltos = cls(total=total)
        for fila in (filas or []):
            try:
                n = int(fila["asalto"])
            except (TypeError, KeyError, ValueError):
                continue
            if fila.get("inicio") is not None:
                asaltos.marcar_inicio(n, fila["inicio"])
            if fila.get("fin") is not None:
                asaltos.marcar_fin(n, fila["fin"])
        return asaltos

    def resumen(self, fps: float = 30.0) -> str:
        """Lo marcado, en una línea, para la barra de estado."""
        def reloj(frame: Optional[int]) -> str:
            if frame is None:
                return "—"
            s = int(frame / max(fps, 1.0))
            return f"{s // 60:d}:{s % 60:02d}"

        return " · ".join(f"A{n} {reloj(self.inicio(n))}–{reloj(self.fin(n))}"
                          for n in range(1, self.total + 1))
