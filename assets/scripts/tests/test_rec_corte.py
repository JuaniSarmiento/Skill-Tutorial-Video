"""Estrategia de corte prolijo de la grabación (rec.py stop()).

taskkill /F equivale a un SIGKILL y corrompe el .mkv a mitad de escribir un
cluster ("invalid as first byte of an EBML number", verificado en la
práctica). El corte tiene que ser CTRL_BREAK_EVENT (Linux: SIGINT) y
esperar a que el proceso termine solo; taskkill /F queda como último
recurso SOLO si no respondió al corte prolijo.

Estos tests no dependen de Windows real: `matar` y `vivo` son funciones
inyectadas, así que se puede probar la lógica de reintento/espera sin
ctypes ni procesos de verdad.
"""
import rec


def test_el_proceso_termina_solo_con_el_corte_prolijo():
    llamadas_matar = []
    estados = iter([True, True, False])  # vivo, vivo, muerto

    def matar(pid):
        llamadas_matar.append(pid)

    def vivo(pid):
        return next(estados)

    ok = rec._corte_prolijo(1234, matar, vivo, intentos=5, espera=0)

    assert ok is True
    assert llamadas_matar == [1234]  # se llama UNA sola vez, no en loop


def test_el_proceso_que_no_responde_agota_los_intentos():
    def matar(pid):
        pass

    def vivo(pid):
        return True  # nunca muere

    ok = rec._corte_prolijo(1234, matar, vivo, intentos=3, espera=0)

    assert ok is False
