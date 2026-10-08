"""Generación de la trayectoria curva del cursor (bezier, ease-in-out, jitter
determinístico por seed) que usa Toma.click() para mover el puntero dibujado.
Capa pura: sin Playwright, sin Chrome real (ver test_grabar_web_integracion.py).
"""
import grabar_web


def test_la_trayectoria_arranca_exactamente_en_el_origen_y_termina_en_el_destino():
    puntos = grabar_web.trayectoria((0, 0), (500, 300), seed=1)

    assert puntos[0] == {"t": 0.0, "x": 0, "y": 0}
    assert puntos[-1]["x"] == 500
    assert puntos[-1]["y"] == 300


def test_el_tiempo_es_estrictamente_creciente():
    puntos = grabar_web.trayectoria((0, 0), (800, 10), seed=2)

    tiempos = [p["t"] for p in puntos]
    assert tiempos == sorted(tiempos)
    assert len(set(tiempos)) == len(tiempos)


def test_la_duracion_crece_con_la_distancia():
    corta = grabar_web.trayectoria((0, 0), (100, 0), seed=3)
    larga = grabar_web.trayectoria((0, 0), (1200, 0), seed=3)

    assert larga[-1]["t"] > corta[-1]["t"]


def test_con_la_misma_seed_la_trayectoria_es_identica():
    a = grabar_web.trayectoria((10, 10), (600, 400), seed=42)
    b = grabar_web.trayectoria((10, 10), (600, 400), seed=42)

    assert a == b


def test_con_otra_seed_cambia_la_forma_intermedia_de_la_curva():
    a = grabar_web.trayectoria((10, 10), (600, 400), seed=1)
    b = grabar_web.trayectoria((10, 10), (600, 400), seed=2)

    medio_a = a[len(a) // 2]
    medio_b = b[len(b) // 2]
    assert (medio_a["x"], medio_a["y"]) != (medio_b["x"], medio_b["y"])
