"""La subida automática a IPPON sobre rival derribado ya no existe.

Hasta el 24-09-2026, `derribo_vigente` (Art. 6: la técnica que llega
sobre un rival derribado vale tres puntos, venga de donde venga)
comprobaba si el barrido de este atleta seguía vigente dentro de
COMBINACION_S (1,5 s) para subir la puntuación sola. Era una regla de
tiempo que miraba las filas de al lado, y se retiró con las otras seis:
el programa registra la técnica y el nivel, y de ahí sale la puntuación
de tabla (Jodan de pierna sigue dando IPPON, eso es una consulta
técnica-más-nivel, no una regla de tiempo). Si la técnica llegó sobre un
rival derribado, eso queda en el registro del barrido anterior
(`contact: Down`), y subir la puntuación es una decisión del
tratamiento de datos, no del momento de anotar.
"""

from __future__ import annotations

from karlos_karate import csv_combate


def test_ya_no_existe_ninguna_pieza_de_la_regla():
    for retirada in ("derribo_vigente", "corta_la_tanda", "COMBINACION_S"):
        assert not hasattr(csv_combate, retirada), retirada
