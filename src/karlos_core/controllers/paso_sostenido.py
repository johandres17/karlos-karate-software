"""Repeticion de teclas conducida por el programa, no por el sistema.

Mantener [L] pulsada deberia barrer el video de continuo, un fotograma
tras otro. Con la repeticion del sistema operativo no lo hace: macOS y
Windows esperan entre 250 y 500 ms antes de empezar a repetir, y luego
repiten al ritmo que tenga configurado esa maquina, entre 10 y 30 veces
por segundo. Asi que al mantener la tecla se sentia un fotograma, un
silencio largo, y despues un avance a tirones que ademas iba distinto en
cada ordenador. Anotando karate eso es justo lo que no puede pasar: el
frame exacto de inicio y fin de cada accion es el dato del estudio, y
los dos evaluadores tienen que moverse igual.

Aqui la repeticion la lleva un temporizador propio: la pulsacion da un
fotograma al instante, y si la tecla sigue abajo pasado un margen corto,
el temporizador sigue dando fotogramas a ritmo fijo hasta que se suelta.
Mismo comportamiento en las dos maquinas.

No hay aceleracion a proposito. Un barrido que se acelera solo deja de
ser contable, y lo que hace falta es ir fotograma a fotograma; para
cubrir distancia estan Shift y la rueda.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QTimer

# Margen antes de empezar a repetir. Corto para que mantener la tecla
# responda enseguida, y largo para que un toque suelto de un solo
# fotograma, que es como se afina un limite.
ESPERA_MS = 180

# Ritmo del barrido de un fotograma. Medido en 1080p: 1,24 ms hacia
# adelante y 2,12 hacia atras, asi que en el tick de 16 ms cabe entre
# ocho y trece veces. Sesenta por segundo deja el video avanzando al
# doble del tiempo real, que es un barrido comodo.
INTERVALO_MS = 16

# Los saltos de diez con Shift cuestan mucho mas: 12,9 ms adelante y
# 28,3 atras, porque cada uno paga una busqueda. A 16 ms el temporizador
# pedira mas trabajo del que cabe y la ventana se atasca, asi que van a
# su propio ritmo. Siguen cubriendo 220 fotogramas por segundo.
INTERVALO_SALTO_MS = 45


class PasoSostenido(QObject):
    """Un fotograma al pulsar, y un barrido parejo mientras no se suelte."""

    def __init__(self, paso: Callable[[int], None], parent=None) -> None:
        super().__init__(parent)
        self._paso = paso
        self._delta = 0
        self._arranque = QTimer(self)
        self._arranque.setSingleShot(True)
        self._arranque.timeout.connect(self._empezar_barrido)
        self._barrido = QTimer(self)
        self._barrido.timeout.connect(self._repetir)

    def pulsar(self, delta: int) -> None:
        """Un fotograma ya, y prepara el barrido por si la tecla sigue abajo.

        Una pulsacion que llega con la tecla YA abajo se ignora. Es la
        repeticion del sistema, que en Windows se cuela pese al
        `setAutoRepeat(False)` del atajo. Atenderla tenia dos efectos, y
        los dos malos: daba un fotograma al ritmo irregular del sistema,
        y reiniciaba la espera, de modo que el barrido propio no llegaba
        a arrancar nunca. El resultado era el avance a tirones de antes,
        pero solo en Windows: en macOS el atajo no repite y no se
        notaba. Aqui se ignora, y el ritmo lo marca siempre el
        temporizador propio.
        """
        if delta == self._delta and (self._arranque.isActive()
                                     or self._barrido.isActive()):
            return
        self._delta = delta
        self._paso(delta)
        self._barrido.stop()
        self._arranque.start(ESPERA_MS)

    def soltar(self) -> None:
        """La tecla subio, o la ventana perdio el foco: se para todo."""
        self._arranque.stop()
        self._barrido.stop()
        self._delta = 0

    @property
    def barriendo(self) -> bool:
        return self._barrido.isActive()

    def _empezar_barrido(self) -> None:
        if self._delta:
            self._barrido.start(INTERVALO_MS if abs(self._delta) <= 1
                                else INTERVALO_SALTO_MS)

    def _repetir(self) -> None:
        if self._delta:
            self._paso(self._delta)
        else:
            self._barrido.stop()
