"""Lanzador de Karlos Karate (decisión 0006).

Es el punto de entrada de PyInstaller: un fichero fuera de los paquetes, para
que la edición no se cargue dos veces (como __main__ y como módulo).
"""
from karlos_ediciones.karate import arrancar

arrancar()
