"""Tiempos por palabra y resolución de cues (palabras.py).

Una "cue" dice CUÁNDO entra un elemento de una escena: en la palabra que lo
nombra. Se escribe como la frase ("base de datos"), como la forma larga del
plan ("cuando dice 'base de datos'") o directamente en segundos (1.5). Se
resuelve contra la transcripción por palabra que da faster-whisper.
"""
from types import SimpleNamespace

import pytest

import palabras


def _p(texto, inicio, fin):
    return {"palabra": texto, "inicio": inicio, "fin": fin}


# "El interés compuesto hace crecer la base de datos, y la base crece."
TRANSCRIPCION = [
    _p("El", 0.00, 0.12), _p("interés", 0.12, 0.55), _p("compuesto", 0.55, 1.10),
    _p("hace", 1.10, 1.30), _p("crecer", 1.30, 1.70), _p("la", 1.70, 1.80),
    _p("base", 1.80, 2.10), _p("de", 2.10, 2.20), _p("datos,", 2.20, 2.70),
    _p("y", 2.80, 2.90), _p("la", 2.90, 3.00), _p("base", 3.00, 3.30),
    _p("crece.", 3.30, 3.80),
]


def test_una_frase_resuelve_al_inicio_de_su_primera_palabra():
    assert palabras.resolver_cue(TRANSCRIPCION, "base de datos") == 1.80


def test_la_comparacion_ignora_mayusculas_tildes_y_puntuacion():
    # "Interes" sin tilde y con mayúscula; "datos" sin la coma que trae whisper
    assert palabras.resolver_cue(TRANSCRIPCION, "Interes compuesto") == 0.12
    assert palabras.resolver_cue(TRANSCRIPCION, "de datos") == 2.10


def test_la_forma_larga_cuando_dice_se_resuelve_igual():
    assert palabras.resolver_cue(TRANSCRIPCION, "cuando dice 'crecer'") == 1.30


def test_un_numero_es_un_tiempo_en_segundos_y_pasa_tal_cual():
    assert palabras.resolver_cue(TRANSCRIPCION, 2.5) == 2.5


def test_desde_salta_la_primera_aparicion():
    # "base" aparece dos veces: desde 2.0 encuentra la segunda
    assert palabras.resolver_cue(TRANSCRIPCION, "base", desde=2.0) == 3.00


def test_una_cue_que_no_se_dice_falla_nombrando_la_cue():
    with pytest.raises(ValueError, match="hipoteca"):
        palabras.resolver_cue(TRANSCRIPCION, "hipoteca")


def test_una_frase_partida_no_matchea_palabras_sueltas():
    # "datos crece" no es contiguo en la transcripción
    with pytest.raises(ValueError):
        palabras.resolver_cue(TRANSCRIPCION, "datos crece")


def test_las_cues_en_secuencia_buscan_despues_de_la_anterior():
    # dos elementos nombrados "base": el segundo toma la segunda aparición
    assert palabras.resolver_cues(TRANSCRIPCION, ["la base", "la base"]) == [1.70, 2.90]


def test_las_cues_numericas_no_mueven_el_cursor_de_busqueda():
    assert palabras.resolver_cues(TRANSCRIPCION, [0.0, "base", 0.5, "base"]) == [0.0, 1.80, 0.5, 3.00]


class _ModeloFalso:
    """Imita WhisperModel.transcribe(word_timestamps=True)."""

    def __init__(self, segmentos):
        self.segmentos = segmentos
        self.kwargs = None

    def transcribe(self, audio, **kwargs):
        self.kwargs = kwargs
        return iter(self.segmentos), SimpleNamespace(language="es")


def _w(word, start, end):
    return SimpleNamespace(word=word, start=start, end=end)


def test_transcribir_aplana_las_palabras_de_todos_los_segmentos():
    modelo = _ModeloFalso([
        SimpleNamespace(words=[_w(" Hola", 0.0, 0.4), _w(" mundo.", 0.4, 0.9)]),
        SimpleNamespace(words=[_w(" Chau", 1.5, 1.9)]),
    ])

    salida = palabras.transcribir("voz.wav", modelo=modelo)

    assert salida == [_p("Hola", 0.0, 0.4), _p("mundo.", 0.4, 0.9), _p("Chau", 1.5, 1.9)]
    assert modelo.kwargs["word_timestamps"] is True
    assert modelo.kwargs["language"] == "es"


def test_transcribir_redondea_los_tiempos_a_milisegundos():
    modelo = _ModeloFalso([SimpleNamespace(words=[_w(" uno", 0.123456, 0.987654)])])

    assert palabras.transcribir("voz.wav", modelo=modelo) == [_p("uno", 0.123, 0.988)]


@pytest.mark.parametrize("cue", ["", "  ", "cuando dice '...'"])
def test_una_cue_sin_palabras_es_un_error_y_no_el_segundo_cero(cue):
    with pytest.raises(ValueError, match="vacía"):
        palabras.resolver_cue(TRANSCRIPCION, cue)
