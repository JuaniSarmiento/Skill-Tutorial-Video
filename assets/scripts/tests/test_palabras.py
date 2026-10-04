"""Tiempos por palabra y resolución de cues (palabras.py).

Una "cue" dice CUÁNDO entra un elemento de una escena: en la palabra que lo
nombra. Se escribe como la frase ("base de datos"), como la forma larga del
plan ("cuando dice 'base de datos'") o directamente en segundos (1.5). Se
resuelve contra la transcripción por palabra que da faster-whisper.
"""
import json
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


def test_las_cues_no_tienen_que_venir_en_el_orden_en_que_se_dicen():
    # un diagrama lista nodos y despues flechas, pero la voz los intercala
    assert palabras.resolver_cues(TRANSCRIPCION, ["base de datos", "interés"]) == [1.80, 0.12]


def test_la_misma_frase_repetida_toma_la_aparicion_siguiente_aunque_haya_otras_en_medio():
    assert palabras.resolver_cues(TRANSCRIPCION, ["base", "crecer", "base"]) == [1.80, 1.30, 3.00]


# --- tolerancia a lo que Whisper oye mal --------------------------------------
# Casos reales del ejemplo de interés compuesto, transcripto con el modelo base.

def _oido(texto, paso=0.5):
    return [_p(w, i * paso, i * paso + 0.4) for i, w in enumerate(texto.split())]


def test_una_letra_mal_oida_no_impide_encontrar_la_cue():
    voz = _oido("Para llevarte, empezar tembrano pesan las que poner mucho")
    assert palabras.resolver_cue(voz, "empezar temprano") == 1.0


def test_dos_palabras_que_whisper_pego_en_una_se_encuentran():
    voz = _oido("tu capital rinde un interés, es interés esuma y el capital nuevo")
    assert palabras.resolver_cue(voz, "se suma") == 3.5   # "esuma", palabra 7


def test_un_numero_dicho_en_palabras_matchea_el_que_whisper_escribio_en_digitos():
    voz = _oido("A las 2 décadas, 6 .700 y a las 3 décadas, más")
    assert palabras.resolver_cue(voz, "dos décadas") == 1.0
    assert palabras.resolver_cue(voz, "tres décadas") == 4.5   # "3", palabra 9


def test_si_la_frase_aparece_exacta_gana_aunque_antes_haya_una_parecida():
    voz = _oido("la casa grande y la cosa chica")
    assert palabras.resolver_cue(voz, "la cosa") == 2.0


def test_una_palabra_corta_parecida_no_alcanza():
    # "hoy" y "voy" se parecen en 2 de 3 letras: eso no es la misma palabra
    with pytest.raises(ValueError):
        palabras.resolver_cue(_oido("mañana voy al banco"), "hoy")


# --- falsos positivos: una cue que no se dijo tiene que fallar ---------------
# La lista de QA (02/10): todas se ataban a otra palabra parecida sin avisar.

@pytest.mark.parametrize("dicho, cue", [
    ("Esto pasa sin aviso", "sí"),
    ("Ellos nos avisaron", "no"),
    ("Pasaron muchos años", "año"),
    ("Tenés 100 pesos", "diez"),
    ("Tenés 1000 pesos", "cien"),
    ("Un auto blanco", "banco"),
    ("Compró la casa", "la tasa"),
    ("Fue el solo de guitarra", "el sol"),
    ("Los capitales extranjeros", "capital"),
    ("Un paño viejo", "pan"),
    ("El ano pasado", "año"),
])
def test_una_cue_que_no_se_dijo_falla_aunque_haya_una_palabra_parecida(dicho, cue):
    with pytest.raises(ValueError, match="no se dice"):
        palabras.resolver_cue(_oido(dicho), cue)


@pytest.mark.parametrize("dicho, cue, t", [
    ("Pasó un año entero", "año", 1.0),
    ("Hay mas plata", "más", 0.5),
    ("Tenés 10 pesos", "diez", 0.5),
    ("El 1 de enero llega una carta", "una carta", 2.5),
])
def test_la_palabra_dicha_de_verdad_se_sigue_encontrando(dicho, cue, t):
    assert palabras.resolver_cue(_oido(dicho), cue) == t


# --- error en palabra corta, sólo con un ancla exacta -------------------------
# Transcripción REAL del ejemplo (Fish + Whisper base, QA2 02/10), segmentos 3 y 4.
# Regla: si la cue tiene OTRA palabra de 4+ letras que coincide exacto (el ancla),
# se tolera 1 error en una palabra corta y hasta 2 en una larga. "la"/"el" no anclan.

SEG3 = ("Hablamos números. Hoy ponés mil pesos al 10 % anual. Pasada una década, "
        "tenés 2 .600. A las 2 décadas, 6 .700 y a las 3 décadas, más de 17 .000.")
SEG4 = ("Para llevarte, empezar tembrano pesan las que poner mucho porque el que "
        "multiplica es el tiempo.")


def _resuelve(voz, cue):
    try:
        return palabras.resolver_cue(voz, cue)
    except ValueError:
        return None


@pytest.mark.parametrize("dicho, cue, t", [
    (SEG4, "más que poner", 2.5),       # "las que poner": ancla "poner"
    (SEG3, "Hagamos números", 0.0),     # "Hablamos" (2 errores, larga): ancla "números"
    (SEG3, "17000", 14.5),              # Whisper escribió "17 .000"
    (SEG3, "17.000", 14.5),
    (SEG3, "más de 17000", 13.5),
    (SEG3, "2600", 7.0),                # "2 .600"
    ("Ahora son las cara", "más cara", 1.0),   # ancla de justo 4 letras
])
def test_un_error_se_tolera_si_otra_palabra_de_la_cue_coincide_exacto(dicho, cue, t):
    assert _resuelve(_oido(dicho), cue) == t


@pytest.mark.parametrize("dicho, cue", [
    (SEG4, "pesa más"),                  # "pesan las": dos errores y ningún ancla (costo declarado)
    ("Ahora son las que", "más que"),    # "que" tiene 3 letras: no ancla
    ("compró lacasa", "la tasa"),        # pegadas: "la" no ancla a "casa"
    ("fue elsolo", "el sol"),
    (SEG3, "Hacemos números"),           # contra "Hablamos": 3 errores, ni con ancla
    ("Tenés 2 .700", "2600"),            # un número con un dígito distinto es otro número
])
def test_sin_ancla_exacta_o_con_demasiados_errores_la_cue_falla(dicho, cue):
    with pytest.raises(ValueError, match="no se dice"):
        palabras.resolver_cue(_oido(dicho), cue)


@pytest.mark.parametrize("dicho, cue", [
    ("compró unas casas", "unas tasas"),   # QA3: "unas" tiene 4 letras y anclaba
    ("hace unos mesas", "unos meses"),
    ("vi aquella casa", "aquella tasa"),
])
def test_un_articulo_o_demostrativo_no_ancla_aunque_sea_largo(dicho, cue):
    with pytest.raises(ValueError, match="no se dice"):
        palabras.resolver_cue(_oido(dicho), cue)


@pytest.mark.parametrize("dicho, cue, t", [
    ("compró unas tasas", "unas tasas", 0.5),   # dicha exacta, se sigue encontrando
    ("compró unas casas altas", "unas tasas altas", 0.5),   # el ancla es "altas", no "unas"
])
def test_un_articulo_largo_no_ancla_pero_otra_palabra_si(dicho, cue, t):
    assert _resuelve(_oido(dicho), cue) == t


@pytest.mark.parametrize("dicho, cue, t", [
    ("más de 17 .000", "diecisiete mil", 1.0),
    ("tenés 2 .600", "dos mil seiscientos", 0.5),
    ("tiene 35 años", "treinta y cinco", 0.5),
    ("ponés 1000 pesos", "mil pesos", 0.5),
    ("pasaron veintiún años", "21 años", 0.5),
    ("más de diecisiete mil", "17000", 1.0),        # al revés: Whisper lo escribió en letras
    ("más de 17 mil", "diecisiete mil", 1.0),        # Whisper mezcla: dígitos + "mil" (S8)
    ("llegás a 4 mil dólares", "cuatro mil dólares", 1.0),
    ("son 2 mil seiscientos", "2600", 0.5),          # y la cola en letras sigue sumando
])
def test_un_numero_compuesto_en_palabras_es_el_mismo_que_en_digitos(dicho, cue, t):
    assert _resuelve(_oido(dicho), cue) == t


@pytest.mark.parametrize("dicho, cue", [
    ("tenés 2 .700", "dos mil seiscientos"),
    ("tiene 36 años", "treinta y cinco"),
    ("ponés 100 pesos", "mil pesos"),
    ("más de 17 mil", "diecisiete"),        # "17 mil" es 17000, no 17
])
def test_un_numero_en_palabras_distinto_del_oido_falla(dicho, cue):
    with pytest.raises(ValueError, match="no se dice"):
        palabras.resolver_cue(_oido(dicho), cue)


# --- miles: sólo se une el patrón de miles, no dos números vecinos -----------
# Whisper escribe los miles con punto ("17.000", y partido "17 .000"). Dos números
# separados por coma y espacio son dos números (QA3, 02/10).

@pytest.mark.parametrize("dicho, cue, t", [
    ("cuesta 100, 200 y después 100 más", "100", 0.5),   # unía "100200" y tomaba el segundo 100
    ("cuesta 100, 200 y después 100 más", "200", 1.0),
    ("en 2024, 500 personas", "500", 1.0),
    ("subió 3 100 veces", "3", 0.5),                     # sin punto, tampoco se unen
    ("son 1 .000 .000 de pesos", "1000000", 0.5),         # el patrón real se sigue uniendo
    ("más de 17.000", "17000", 1.0),
])
def test_solo_se_unen_los_miles_escritos_con_punto(dicho, cue, t):
    assert _resuelve(_oido(dicho), cue) == t


@pytest.mark.parametrize("dicho, cue", [
    ("cuesta 2500 pesos", "2,500"),     # en es-AR "2,500" es dos coma cinco
    ("cuesta 2,500 pesos", "2500"),
])
def test_una_coma_entre_digitos_es_decimal_y_no_separa_miles(dicho, cue):
    with pytest.raises(ValueError, match="no se dice"):
        palabras.resolver_cue(_oido(dicho), cue)


def test_una_frase_repetida_mas_veces_de_las_que_se_dice_falla():
    with pytest.raises(ValueError, match="no se dice"):
        palabras.resolver_cues(_oido("la base crece"), ["la base", "la base"])


# --- palabras.py por línea de comandos ---------------------------------------

def _cli(monkeypatch, capsys, *args):
    import runpy
    import sys
    modelo = _ModeloFalso([SimpleNamespace(words=[_w(" Hola", 0.0, 0.4), _w(" mundo.", 0.4, 0.9)])])
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=lambda *a, **k: modelo))
    monkeypatch.setattr(sys, "argv", ["palabras.py", *args])
    runpy.run_path(palabras.__file__, run_name="__main__")
    return capsys.readouterr().out


def test_el_cli_escribe_el_json_de_palabras_en_la_salida(tmp_path, monkeypatch, capsys):
    salida = tmp_path / "p.json"
    _cli(monkeypatch, capsys, "voz.wav", str(salida))
    assert salida.exists(), "no escribió la salida"
    assert json.loads(salida.read_text()) == [_p("Hola", 0.0, 0.4), _p("mundo.", 0.4, 0.9)]


def test_el_cli_sin_salida_imprime_el_json(monkeypatch, capsys):
    out = _cli(monkeypatch, capsys, "voz.wav")
    assert out.strip(), "no imprimió nada"
    assert json.loads(out) == [_p("Hola", 0.0, 0.4), _p("mundo.", 0.4, 0.9)]
