"""Lo que el programa mide, ya no lo que hace cumplir.

Hasta el 24-09-2026 aqui vivian las reglas mecanicas que salieron del
arbitraje de ID30: no anotar dentro de una parada, juntar una tanda de
fintas en una fila, exigir un ataque del rival delante de una esquiva,
fundir dos filas de la misma parada, rechazar las fintas mas cortas de
ocho fotogramas. Se retiraron todas.

La razon la dio Johan y es de metodo: cada entrada tiene que ser una
linea, y agrupar o descartar en el momento de anotar fija por adelantado
un criterio que despues no se puede revisar sin volver a ver los
combates. Con el dato crudo entero, el criterio se cambia en el
tratamiento de datos tantas veces como haga falta.

Quedan los numeros de la calibracion, que sirven para leer los datos.
"""

from __future__ import annotations

# Numeros de la calibracion ID30. NINGUNO se hace cumplir: estan aqui
# porque el manual los cita y porque sirven para leer los datos.
#
#   TANDA_S            ventana con que se miraban las tandas de fintas
#   FINTA_MIN_REFERENCIA  las fintas que solo uno marcaba duraban 0,27 s
#                      de mediana (8 fotogramas a 29,97) y las que solo
#                      marcaba el otro, 0,67 s
#   ESQUIVA_JANELA_S   con cuanta antelacion se miraba el ataque del rival
TANDA_S = 1.5
FINTA_MIN_REFERENCIA = 8
ESQUIVA_JANELA_S = 1.0

# Lo que el arbitro senala con el combate detenido.
CATEGORIAS_EN_PAUSA = ("PENALTY", "REFEREE STOP")


