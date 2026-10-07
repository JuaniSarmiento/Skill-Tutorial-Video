"""Transiciones entre tramos (S6 del Hito 2, docs/explicador/HITO2.md).

Hallazgo 2 de HITO2.md: una superposición tipo xfade desincroniza la voz (el video se
arma con `concat -c copy` y la voz suma slots). Las transiciones de este módulo pasan
DENTRO de cada slot (mitad en la cola del tramo saliente, mitad en la cabeza del
entrante), así G1 (cuadros) y G2 (el .srt y el arranque de la voz) no se tocan.

Decisión de Juani (Q4): hay transición sólo si al menos uno de los dos lados es una
escena; pantalla->pantalla queda en corte seco sin importar lo que diga el guion.
"""
import pytest

import transiciones


# --- normalizar(): la clave "transicion" cruda (arriba o en un segmento) -----------

def test_normalizar_none_da_none():
    assert transiciones.normalizar(None) is None


def test_normalizar_false_da_none():
    assert transiciones.normalizar(False) is None


def test_normalizar_un_string_es_taquigrafia_de_tipo():
    assert transiciones.normalizar("barrido") == {"tipo": "barrido"}


def test_normalizar_un_objeto_se_devuelve_tal_cual():
    assert transiciones.normalizar({"tipo": "fundido", "duracion": 0.4}) == {"tipo": "fundido", "duracion": 0.4}


def test_normalizar_un_numero_no_es_valido():
    with pytest.raises(transiciones.TransicionError):
        transiciones.normalizar(3.5)


# --- validar_tipo() / resolver(): R-6.7 (tipo desconocido) y herencia del default ---

def test_validar_tipo_con_un_tipo_valido_no_rompe():
    for tipo in ("corte", "fundido", "barrido", "whip"):
        transiciones.validar_tipo(tipo)


def test_validar_tipo_desconocido_nombra_los_validos():
    with pytest.raises(transiciones.TransicionError) as e:
        transiciones.validar_tipo("transicon")
    assert "transicon" in str(e.value)
    assert "corte" in str(e.value) and "fundido" in str(e.value) and "barrido" in str(e.value)


def test_validar_tipo_desconocido_nombra_whip_entre_los_validos_r67():
    with pytest.raises(transiciones.TransicionError) as e:
        transiciones.validar_tipo("transicon")
    assert "whip" in str(e.value)


def test_resolver_sin_nada_en_ningun_lado_da_corte():
    assert transiciones.resolver({"texto": "x"}, None) == {"tipo": "corte"}


def test_resolver_hereda_el_default_de_arriba_si_el_segmento_no_declara_nada():
    default = {"tipo": "barrido", "duracion": 0.4}
    assert transiciones.resolver({"texto": "x"}, default) == default


def test_resolver_el_segmento_pisa_al_default_de_arriba():
    default = {"tipo": "barrido"}
    seg = {"texto": "x", "transicion": "corte"}
    assert transiciones.resolver(seg, default) == {"tipo": "corte"}


def test_resolver_con_tipo_desconocido_en_el_segmento_avisa():
    with pytest.raises(transiciones.TransicionError):
        transiciones.resolver({"texto": "x", "transicion": "transicon"}, None)


# --- duracion_de() / duracion_efectiva(): R-6.4 (default del brand) y R-6.6 (slot corto) --

BRAND = {"colores": {"fondo": "#111318", "acento": "#F2B544"}, "movimiento": {"entrada": 0.7}}


def test_duracion_de_usa_la_pedida_por_el_guion_si_esta():
    assert transiciones.duracion_de({"tipo": "barrido", "duracion": 0.4}, BRAND) == 0.4


def test_duracion_de_sin_pedido_cae_al_movimiento_entrada_del_brand():
    assert transiciones.duracion_de({"tipo": "barrido"}, BRAND) == 0.7


def test_duracion_efectiva_con_slots_grandes_no_cambia_nada():
    assert transiciones.duracion_efectiva(0.5, slot_saliente=6.0, slot_entrante=6.0, i=3) == 0.5


def test_duracion_efectiva_con_un_slot_corto_se_acorta_a_slot_sobre_3_y_avisa(capsys):
    # slot más corto = 1.2s -> 1.2/3 = 0.4s, menor que la pedida (0.5s)
    d = transiciones.duracion_efectiva(0.5, slot_saliente=6.0, slot_entrante=1.2, i=2)

    assert d == pytest.approx(0.4)
    aviso = capsys.readouterr().err
    assert "02" in aviso and "0.40" in aviso


# --- color_de(): R-6.3, el color sale del brand ------------------------------------

def test_color_de_barrido_usa_el_acento_del_brand():
    assert transiciones.color_de("barrido", BRAND) == "0xF2B544"


def test_color_de_fundido_usa_el_fondo_del_brand():
    assert transiciones.color_de("fundido", BRAND) == "0x111318"


def test_color_de_cambiar_el_acento_del_brand_cambia_el_color_de_barrido():
    otro = {"colores": {"fondo": "#000000", "acento": "#00FF00"}, "movimiento": {"entrada": 0.7}}
    assert transiciones.color_de("barrido", otro) == "0x00FF00"


# --- anchos_barrido() / comandos_barrido(): la ventana del barrido, sin ffmpeg ----
#
# `drawbox` no reevalúa `w`/`x` por cuadro con `t` en ffmpeg 6.1.1 (medido: una
# expresión con `t` queda congelada en el valor que dio al armar el filtro, NaN
# en ese momento), así que el barrido se maneja cuadro a cuadro con `sendcmd`.
#
# Mejora de calidad (QA): un solo barrido CRUZADO, no una cortina que entra y se
# repliega. `anchos_barrido` devuelve (t, x, w): en la mitad SALIENTE el borde de
# ataque crece con x=0 fijo (como antes); en la ENTRANTE el borde de SALIDA sigue
# hacia la derecha (x crece, w se achica) en vez de retraerse hacia la izquierda.
# Las dos mitades comparten una única curva ease-in-out (sin salto de velocidad
# en el corte) en vez de dos ease-out independientes.

def test_anchos_barrido_saliente_arranca_casi_en_0_y_termina_en_el_ancho_completo():
    anchos = transiciones.anchos_barrido("saliente", t0=1.0, mitad=0.2, ancho=320, fps=30)

    # el primer punto queda anclado a la grilla real de cuadros (contado para
    # atrás desde el último cuadro real, no para adelante desde t0), así que
    # puede caer hasta 1 cuadro antes de t0 -nunca más lejos- (ver docstring de
    # anchos_barrido: evita que un comando quede desalineado y "se pierda").
    assert abs(anchos[0][0] - 1.0) <= 1 / 30 + 1e-6
    assert anchos[0][1:] == (0, 1)           # x=0, w≈0: nunca 0 exacto (drawbox w=0 = "completo")
    assert anchos[-1][1:] == (0, 320)        # x=0, w=ancho: 100% de cobertura en el corte
    assert all(x == 0 for _, x, _ in anchos)  # saliente: el borde de ataque, x siempre fijo en 0
    assert all(a[2] <= b[2] for a, b in zip(anchos, anchos[1:]))  # w monótono creciente


def test_anchos_barrido_entrante_arranca_completo_y_termina_casi_en_0():
    anchos = transiciones.anchos_barrido("entrante", t0=0.0, mitad=0.2, ancho=320, fps=30)

    assert anchos[0][1:] == (0, 320)         # x=0, w=ancho: arranca cubriendo del todo
    assert anchos[-1][1] == 319               # x≈ancho: el borde de salida llegó al final
    assert anchos[-1][2] == 1
    assert all(a[1] <= b[1] for a, b in zip(anchos, anchos[1:]))  # entrante: x (borde de salida) monótono CRECIENTE...
    assert all(a[2] >= b[2] for a, b in zip(anchos, anchos[1:]))  # ...y w monótono decreciente (nunca se repliega)


def test_anchos_barrido_tiene_un_punto_por_cuadro_de_la_ventana():
    # 0.2s a 30fps = 6 cuadros -> 7 puntos (incluye los dos extremos)
    anchos = transiciones.anchos_barrido("saliente", t0=0.0, mitad=0.2, ancho=320, fps=30)
    assert len(anchos) == 7


def test_anchos_barrido_redondea_hacia_arriba_desde_0_5_para_no_acortar_r64():
    # mitad=0.35s a 30fps = 10.5 cuadros exactos: round() banker's da 10 (se acorta),
    # el redondeo correcto para R-6.4 (±1 cuadro) es 11.
    anchos = transiciones.anchos_barrido("saliente", t0=0.0, mitad=0.35, ancho=320, fps=30)
    assert len(anchos) == 12  # n=11 -> 12 puntos


def test_r64_cuenta_de_cuadros_con_acento_coincide_con_la_duracion_pedida():
    # Repro del hallazgo NOTE 1 de QA: 0.6s daba 16 cuadros, 0.7s daba 18.
    for duracion, esperado in [(0.6, 18), (0.7, 21)]:
        fps, ancho = 30, 1920
        mitad = duracion / 2
        saliente = transiciones.anchos_barrido("saliente", t0=0.0, mitad=mitad, ancho=ancho, fps=fps)
        entrante = transiciones.anchos_barrido("entrante", t0=0.0, mitad=mitad, ancho=ancho, fps=fps)
        con_acento = sum(1 for _, _, w in saliente + entrante if w / ancho > 0.01)
        assert abs(con_acento - esperado) <= 1, (duracion, con_acento, esperado)


def test_comandos_barrido_un_comando_x_y_un_comando_w_por_cuadro():
    anchos = [(0.0, 0, 1), (0.033333, 0, 10), (0.066667, 0, 320)]
    texto = transiciones.comandos_barrido(anchos, filtro="t6")

    assert texto.count("drawbox@t6 w") == 3
    assert texto.count("drawbox@t6 x") == 3
    assert "0.000000 drawbox@t6 x '0';" in texto
    assert "0.000000 drawbox@t6 w '1';" in texto
    assert "0.066667 drawbox@t6 w '320';" in texto


def test_barrido_es_un_solo_cruce_con_una_curva_sin_salto_de_velocidad_en_el_corte():
    mitad, fps, ancho = 0.3, 30, 320
    saliente = transiciones.anchos_barrido("saliente", t0=0.0, mitad=mitad, ancho=ancho, fps=fps)
    entrante = transiciones.anchos_barrido("entrante", t0=0.0, mitad=mitad, ancho=ancho, fps=fps)

    # Una sola línea de tiempo (0..2×ancho): en saliente el borde relevante es x+w
    # (borde de ataque); en entrante, trasladado, es ancho+x (borde de salida que
    # sigue de largo). Es el MISMO barrido visto en sus dos mitades.
    borde = [x + w for _, x, w in saliente] + [ancho + x for _, x, w in entrante]

    # Cruza de punta a punta: monótono en TODA la transición, nunca se repliega.
    assert all(a <= b for a, b in zip(borde, borde[1:]))

    # El cuadro del corte (último del saliente) está al 100% de cobertura.
    assert saliente[-1][1:] == (0, ancho)

    # Sin salto de velocidad en el corte mayor que el máximo del resto: comparo el
    # salto de la velocidad (2da diferencia) exactamente en la costura contra el
    # máximo de esa misma magnitud en el resto de la curva.
    velocidad = [b - a for a, b in zip(borde, borde[1:])]
    saltos = [abs(b - a) for a, b in zip(velocidad, velocidad[1:])]
    idx_costura = len(saliente) - 2  # costura entre el último punto de saliente y el primero de entrante
    salto_costura = saltos[idx_costura]
    resto = saltos[:idx_costura] + saltos[idx_costura + 1:]
    assert salto_costura <= max(resto) + 1  # +1: margen de redondeo a entero (px)


# --- anchos_whip() / comandos_whip(): H7 (HITO3.md) -- "whip" con velocidades --
# pareadas: el tramo saliente acelera desplazándose (desenfoque creciente) y el
# entrante llega frenando (desenfoque decreciente), con la MISMA curva sweep de
# anchos_barrido (continuidad de la derivada en el corte, p=0.5).

def test_anchos_whip_saliente_arranca_quieto_y_nitido_y_termina_desplazado_y_maximo_de_desenfoque():
    cuadros = transiciones.anchos_whip("saliente", t0=0.0, mitad=0.3, ancho=320, fps=30)
    assert cuadros[0][1:] == (0, 0.0)          # x=0 (imagen completa), sigma=0 (nítido): reposo
    assert cuadros[-1][1] == 320                # x=ancho: la imagen ya salió del todo en el corte
    assert cuadros[-1][2] == pytest.approx(20.0, abs=0.01)  # sigma máxima justo en el corte


def test_anchos_whip_entrante_arranca_con_el_mismo_desenfoque_maximo_que_el_corte_y_termina_nitido():
    cuadros = transiciones.anchos_whip("entrante", t0=0.0, mitad=0.3, ancho=320, fps=30)
    assert cuadros[0][1:] == (0, pytest.approx(20.0, abs=0.01))   # continuidad: mismo sigma que el final del saliente
    assert cuadros[-1][1:] == (320, 0.0)        # imagen asentada, nítida


def test_anchos_whip_tiene_un_punto_por_cuadro_de_la_ventana_r64():
    # 0.2s a 30fps = 6 cuadros -> 7 puntos (igual criterio que anchos_barrido)
    cuadros = transiciones.anchos_whip("saliente", t0=0.0, mitad=0.2, ancho=320, fps=30)
    assert len(cuadros) == 7


def test_anchos_whip_x_es_monotono_en_las_dos_mitades():
    # el desplazamiento nunca retrocede dentro de cada mitad (misma curva que barrido)
    saliente = transiciones.anchos_whip("saliente", t0=0.0, mitad=0.3, ancho=320, fps=30)
    entrante = transiciones.anchos_whip("entrante", t0=0.0, mitad=0.3, ancho=320, fps=30)
    assert all(a[1] <= b[1] for a, b in zip(saliente, saliente[1:]))
    assert all(a[1] <= b[1] for a, b in zip(entrante, entrante[1:]))


def test_whip_es_un_solo_cruce_con_una_curva_sin_salto_de_velocidad_en_el_corte():
    # Mismo chequeo que test_barrido_es_un_solo_cruce_...: el desplazamiento por
    # cuadro (x) en las dos mitades es la MISMA curva vista desde cada lado, así
    # que el salto de velocidad justo en la costura no es mayor que el máximo del
    # resto de la curva.
    mitad, fps, ancho = 0.3, 30, 320
    saliente = transiciones.anchos_whip("saliente", t0=0.0, mitad=mitad, ancho=ancho, fps=fps)
    entrante = transiciones.anchos_whip("entrante", t0=0.0, mitad=mitad, ancho=ancho, fps=fps)

    # línea de tiempo única: saliente ve 0->ancho, entrante (trasladado) ve ancho->2ancho
    desplazamiento = [x for _, x, _ in saliente] + [ancho + x for _, x, _ in entrante]
    assert all(a <= b for a, b in zip(desplazamiento, desplazamiento[1:]))  # monótono de punta a punta

    velocidad = [b - a for a, b in zip(desplazamiento, desplazamiento[1:])]
    saltos = [abs(b - a) for a, b in zip(velocidad, velocidad[1:])]
    idx_costura = len(saliente) - 2  # costura entre el último punto de saliente y el primero de entrante
    salto_costura = saltos[idx_costura]
    resto = saltos[:idx_costura] + saltos[idx_costura + 1:]
    assert salto_costura <= max(resto) + 1  # +1: margen de redondeo a entero (px)


def test_comandos_whip_un_comando_x_de_crop_y_un_comando_sigma_de_desenfoque_por_cuadro():
    cuadros = [(0.0, 0, 0.0), (0.033333, 50, 10.5), (0.066667, 320, 20.0)]
    texto = transiciones.comandos_whip(cuadros)

    assert texto.count("crop@wc x") == 3
    assert texto.count("gblur@wb sigma") == 3
    assert "0.000000 crop@wc x '0';" in texto
    assert "0.066667 crop@wc x '320';" in texto
    assert "0.066667 gblur@wb sigma '20.0';" in texto


def test_vf_fundido_saliente_usa_fade_out_con_el_color():
    vf = transiciones.vf_fundido("saliente", t0=5.5, mitad=0.25, color="0x111318")
    assert vf == "fade=t=out:st=5.500000:d=0.250000:color=0x111318"


def test_vf_fundido_entrante_usa_fade_in():
    vf = transiciones.vf_fundido("entrante", t0=0.0, mitad=0.25, color="0x111318")
    assert vf == "fade=t=in:st=0.000000:d=0.250000:color=0x111318"


# --- aplicar(): reencodea un seg/NN.mp4 con el filtro ya armado, in-place ----------

def _clip(tmp_path, nombre: str, dur: float = 1.0, w: int = 320, h: int = 240) -> "__import__('pathlib').Path":
    import subprocess
    from pathlib import Path
    out = Path(tmp_path) / nombre
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"testsrc=s={w}x{h}:r=30:d={dur}",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(out)], check=True)
    return out


def _cuadros(mp4) -> list[str]:
    """[codec_name, width, height, pix_fmt, r_frame_rate, nb_read_packets]."""
    import subprocess
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-count_packets",
                          "-show_entries", "stream=codec_name,width,height,pix_fmt,r_frame_rate,nb_read_packets",
                          "-of", "csv=p=0", str(mp4)], capture_output=True, text=True, check=True).stdout.strip()
    return out.split(",")


def _pixel(mp4, t: float):
    """Color (r,g,b) del pixel (0,0) en el segundo `t` (para medir el acento, R-6.1).

    Sin crop: yuv420p exige ancho/alto pares (submuestreo de croma), y crop=1:1
    rompe con "Invalid ... size for width '0'". Se decodifica el cuadro entero a
    rgb24 y se lee el primer pixel de los bytes crudos (orden por fila).
    """
    import subprocess
    out = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(t), "-i", str(mp4), "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return tuple(out[:3])


def test_aplicar_no_cambia_la_cantidad_de_cuadros_ni_el_codec(tmp_path):
    clip = _clip(tmp_path, "00.mp4", dur=1.0)
    antes = _cuadros(clip)

    transiciones.aplicar(clip, transiciones.vf_fundido("entrante", 0.0, 0.25, "0x111318"))

    despues = _cuadros(clip)
    assert despues[-1] == antes[-1] == "30"  # G1: mismo número de cuadros
    assert despues[:4] == ["h264", "320", "240", "yuv420p"]  # G4


def _cerca(rgb, esperado, tol=4):
    return all(abs(a - b) <= tol for a, b in zip(rgb, esperado))


def test_aplicar_barrido_no_cambia_la_cantidad_de_cuadros_ni_el_codec(tmp_path):
    clip = _clip(tmp_path, "00.mp4", dur=1.0)
    antes = _cuadros(clip)

    transiciones.aplicar_barrido(clip, "entrante", t0=0.0, mitad=0.25, color="0xF2B544",
                                 ancho=320, fps=30)

    despues = _cuadros(clip)
    assert despues[-1] == antes[-1] == "30"  # G1: mismo número de cuadros
    assert despues[:4] == ["h264", "320", "240", "yuv420p"]  # G4


def test_aplicar_barrido_entrante_cubre_casi_del_todo_en_t_cero_y_se_despeja_despues(tmp_path):
    clip = _clip(tmp_path, "00.mp4", dur=1.0)
    transiciones.aplicar_barrido(clip, "entrante", t0=0.0, mitad=0.25, color="0xF2B544",
                                 ancho=320, fps=30)

    # (242, 181, 68) = F2B544 en RGB (±4 por la ida y vuelta yuv420p<->rgb24 de libx264):
    # en t=0 el barrido cubre casi toda la pantalla.
    assert _cerca(_pixel(clip, 0.0), (242, 181, 68))
    # bien pasada la transición (t=0.6 > mitad), el barrido ya se fue del todo
    assert not _cerca(_pixel(clip, 0.6), (242, 181, 68))


def test_aplicar_barrido_saliente_empieza_despejado_y_termina_cubierto(tmp_path):
    clip = _clip(tmp_path, "00.mp4", dur=1.0)
    # t0 = 0.75 (slot=1.0, mitad=0.25): arranca despejado y cubre del todo al final
    transiciones.aplicar_barrido(clip, "saliente", t0=0.75, mitad=0.25, color="0xF2B544",
                                 ancho=320, fps=30)

    assert not _cerca(_pixel(clip, 0.1), (242, 181, 68))
    assert _cerca(_pixel(clip, 0.966), (242, 181, 68))


# --- aplicar_whip(): H7 (HITO3.md) -- whip pan con velocidades pareadas -----------

def test_aplicar_whip_no_cambia_la_cantidad_de_cuadros_ni_el_codec(tmp_path):
    clip = _clip(tmp_path, "00.mp4", dur=1.0)
    antes = _cuadros(clip)

    transiciones.aplicar_whip(clip, "entrante", t0=0.0, mitad=0.25, color="0x111318",
                               ancho=320, fps=30)

    despues = _cuadros(clip)
    assert despues[-1] == antes[-1] == "30"  # G1: mismo número de cuadros
    assert despues[:4] == ["h264", "320", "240", "yuv420p"]  # G4


def test_aplicar_whip_saliente_en_el_corte_la_pantalla_quedo_del_color_de_fondo(tmp_path):
    # pad=2*ancho:h:0:0:color=fondo pone la imagen (rojo) a la izquierda y el
    # fondo a la derecha; en el corte (último cuadro real) el recorte ya se fue
    # del todo sobre el fondo: no debería quedar nada de rojo en pantalla.
    clip = _clip_color(tmp_path, "00.mp4", "red", dur=1.0, w=320, h=240)
    transiciones.aplicar_whip(clip, "saliente", t0=0.75, mitad=0.25, color="0x111318",
                               ancho=320, fps=30)

    ultimo_frame_t = (round(1.0 * 30) - 1) / 30
    assert _cerca(_pixel(clip, ultimo_frame_t), (0x11, 0x13, 0x18), tol=10)


def test_aplicar_whip_entrante_arranca_del_color_de_fondo_y_termina_mostrando_la_imagen(tmp_path):
    clip = _clip_color(tmp_path, "00.mp4", "red", dur=1.0, w=320, h=240)
    transiciones.aplicar_whip(clip, "entrante", t0=0.0, mitad=0.25, color="0x111318",
                               ancho=320, fps=30)

    assert _cerca(_pixel(clip, 0.0), (0x11, 0x13, 0x18), tol=10)   # arranca tapado por el fondo
    assert _cerca(_pixel(clip, 0.9), (255, 0, 0), tol=10)          # bien asentada: la imagen (roja)


# --- BLOCKING (QA): la caja de `drawbox` queda montada en todo el archivo con w=1 -
# fuera de la ventana, sólo `sendcmd` cambia `w`. Repro de HITO2.md: fondo GRIS,
# ninguna columna (ni x=0..3) puede tener el acento fuera de la ventana.

def _clip_color(tmp_path, nombre: str, color: str, dur: float = 1.0, w: int = 320, h: int = 240):
    import subprocess
    from pathlib import Path
    out = Path(tmp_path) / nombre
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"color=c={color}:s={w}x{h}:r=30:d={dur}",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(out)], check=True)
    return out


def _fila(mp4, t: float, ancho_px: int = 4, x: int = 0, y: int = 100) -> list[tuple[int, int, int]]:
    """RGB de `ancho_px` columnas consecutivas (fila `y`) en el segundo `t` (repro de
    HITO2.md: `crop=4:2:0:540`, altura 2 por el submuestreo de croma de yuv420p)."""
    import subprocess
    out = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(t), "-i", str(mp4), "-frames:v", "1",
                          "-vf", f"crop={ancho_px}:2:{x}:{y}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return [tuple(out[i * 3:i * 3 + 3]) for i in range(ancho_px)]


def test_aplicar_barrido_saliente_llega_al_100_por_ciento_en_el_cuadro_del_corte(tmp_path):
    # Mejora de calidad (QA): "el saliente llega a 99.5-99.8% porque el comando de
    # t=slot nunca se aplica". slot=1.37 NO es múltiplo de 1/30: el último cuadro
    # real del archivo queda ANTES de t=slot, así que el sendcmd agendado justo en
    # t0+mitad (=slot) cae después del último cuadro y nunca se ejecuta. Se mide
    # cerca del borde derecho (no en x=0, que ya está cubierto con cualquier avance).
    slot, mitad, ancho = 1.37, 0.3, 320
    clip = _clip(tmp_path, "00.mp4", dur=slot, w=ancho, h=240)

    transiciones.aplicar_barrido(clip, "saliente", t0=slot - mitad, mitad=mitad, color="0xF2B544",
                                 ancho=ancho, fps=30)

    ultimo_frame_t = (round(slot * 30) - 1) / 30
    for rgb in _fila(clip, ultimo_frame_t, ancho_px=2, x=ancho - 2, y=100):
        assert _cerca(rgb, (242, 181, 68), tol=10), f"el cuadro del corte no llegó al 100%: {rgb}"


def test_aplicar_barrido_entrante_fuera_de_la_ventana_ninguna_columna_tiene_acento(tmp_path):
    clip = _clip_color(tmp_path, "00.mp4", "gray", dur=1.0)
    gris = _fila(clip, 0.9)[0]  # referencia ANTES de tocar el archivo

    transiciones.aplicar_barrido(clip, "entrante", t0=0.0, mitad=0.25, color="0xF2B544",
                                 ancho=320, fps=30)

    for rgb in _fila(clip, 0.9):  # 0.9 >> mitad=0.25: bien afuera de la ventana
        assert _cerca(rgb, gris, tol=4), f"columna con acento fuera de la ventana: {rgb}"


def test_aplicar_barrido_saliente_fuera_de_la_ventana_ninguna_columna_tiene_acento(tmp_path):
    clip = _clip_color(tmp_path, "00.mp4", "gray", dur=1.0)
    gris = _fila(clip, 0.1)[0]

    transiciones.aplicar_barrido(clip, "saliente", t0=0.75, mitad=0.25, color="0xF2B544",
                                 ancho=320, fps=30)

    for rgb in _fila(clip, 0.1):  # antes de t0=0.75: bien afuera de la ventana
        assert _cerca(rgb, gris, tol=4), f"columna con acento fuera de la ventana: {rgb}"


# --- validar(): chequeo temprano de TODO el guion, antes de generar nada (R-6.7) --

def test_validar_guion_sin_ninguna_transicion_no_rompe():
    transiciones.validar({"segmentos": [{"texto": "a"}, {"texto": "b"}]})


def test_validar_guion_con_tipo_desconocido_arriba_rompe_antes_de_todo():
    with pytest.raises(transiciones.TransicionError):
        transiciones.validar({"transicion": "transicon", "segmentos": [{"texto": "a"}]})


def test_validar_guion_con_tipo_desconocido_en_un_segmento_lo_nombra():
    g = {"segmentos": [{"texto": "a"}, {"texto": "b", "transicion": "transicon"}]}
    with pytest.raises(transiciones.TransicionError) as e:
        transiciones.validar(g)


# --- validar(): NOTES de QA -- "transicion" sin "tipo" y "duracion" inválida -----
# abortan ANTES de armar tramos (no ZeroDivisionError/KeyError a mitad del render),
# nombrando el segmento.

def test_validar_guion_con_transicion_sin_tipo_en_un_segmento_lo_nombra():
    g = {"segmentos": [{"texto": "a"}, {"texto": "b", "transicion": {"duracion": 0.4}}]}
    with pytest.raises(transiciones.TransicionError) as e:
        transiciones.validar(g)
    assert "01" in str(e.value) and "tipo" in str(e.value)


def test_validar_guion_con_transicion_sin_tipo_en_el_default_rompe():
    g = {"transicion": {"duracion": 0.4}, "segmentos": [{"texto": "a"}]}
    with pytest.raises(transiciones.TransicionError) as e:
        transiciones.validar(g)
    assert "tipo" in str(e.value)


@pytest.mark.parametrize("duracion_invalida", [0, -0.5, "rapido"])
def test_validar_guion_con_duracion_invalida_en_un_segmento_lo_nombra(duracion_invalida):
    g = {"segmentos": [{"texto": "a"},
                       {"texto": "b", "transicion": {"tipo": "barrido", "duracion": duracion_invalida}}]}
    with pytest.raises(transiciones.TransicionError) as e:
        transiciones.validar(g)
    assert "01" in str(e.value) and "duracion" in str(e.value)


# --- avisar_si_tapa_cue(): R-6.5, la primera cue de la escena entrante -------------

def test_avisar_si_tapa_cue_sin_spec_no_avisa(capsys):
    transiciones.avisar_si_tapa_cue(2, None, mitad=0.3)
    assert capsys.readouterr().err == ""


def test_avisar_si_tapa_cue_con_la_primera_cue_despues_de_la_transicion_no_avisa(capsys):
    spec = {"duracion": 5.0, "puntos": [{"texto": "x", "cue": "x", "t": 0.5}]}
    transiciones.avisar_si_tapa_cue(2, spec, mitad=0.3)
    assert capsys.readouterr().err == ""


def test_avisar_si_tapa_cue_con_la_primera_cue_dentro_de_la_transicion_avisa(capsys):
    spec = {"duracion": 5.0, "puntos": [{"texto": "x", "cue": "x", "t": 0.1}]}
    transiciones.avisar_si_tapa_cue(2, spec, mitad=0.3)
    aviso = capsys.readouterr().err
    assert "02" in aviso and "0.10" in aviso


# --- aplicar_todas(): orquesta los cambios de tramo de un guion completo ----------

def _seg_dir(tmp_path, n: int, dur: float = 1.0, w: int = 320, h: int = 240):
    """Crea seg_dir/00.mp4..NN.mp4, todos iguales (testsrc), como build_segment ya
    los habría armado."""
    from pathlib import Path
    seg_dir = Path(tmp_path) / "seg"
    seg_dir.mkdir()
    for i in range(n):
        _clip(seg_dir, f"{i:02d}.mp4", dur=dur, w=w, h=h)
    return seg_dir


def test_aplicar_todas_pantalla_a_pantalla_no_toca_ningun_archivo_q4(tmp_path):
    seg_dir = _seg_dir(tmp_path, 2)
    antes = [(seg_dir / "00.mp4").read_bytes(), (seg_dir / "01.mp4").read_bytes()]
    g = {"transicion": "barrido", "segmentos": [{"texto": "a"}, {"texto": "b"}]}
    tramos = [({"texto": "a"}, 1.0, None), ({"texto": "b"}, 1.0, None)]

    transiciones.aplicar_todas(seg_dir, g, tramos, BRAND, ancho=320, fps=30)

    despues = [(seg_dir / "00.mp4").read_bytes(), (seg_dir / "01.mp4").read_bytes()]
    assert despues == antes  # Q4: pantalla->pantalla, corte seco, ni se tocan los bytes


def test_aplicar_todas_con_un_lado_escena_aplica_el_barrido(tmp_path):
    seg_dir = _seg_dir(tmp_path, 2)
    antes = [(seg_dir / "00.mp4").read_bytes(), (seg_dir / "01.mp4").read_bytes()]
    g = {"transicion": {"tipo": "barrido", "duracion": 0.2},
         "segmentos": [{"texto": "a"}, {"escena": {"tipo": "presentacion"}, "texto": "b"}]}
    tramos = [({"texto": "a"}, 1.0, None), (g["segmentos"][1], 1.0, [])]

    transiciones.aplicar_todas(seg_dir, g, tramos, BRAND, ancho=320, fps=30)

    despues = [(seg_dir / "00.mp4").read_bytes(), (seg_dir / "01.mp4").read_bytes()]
    assert despues != antes  # al menos un lado es escena: Q4 no lo frena


def test_aplicar_todas_con_un_lado_escena_aplica_el_whip(tmp_path):
    seg_dir = _seg_dir(tmp_path, 2)
    antes = [(seg_dir / "00.mp4").read_bytes(), (seg_dir / "01.mp4").read_bytes()]
    g = {"transicion": {"tipo": "whip", "duracion": 0.2},
         "segmentos": [{"texto": "a"}, {"escena": {"tipo": "presentacion"}, "texto": "b"}]}
    tramos = [({"texto": "a"}, 1.0, None), (g["segmentos"][1], 1.0, [])]

    transiciones.aplicar_todas(seg_dir, g, tramos, BRAND, ancho=320, fps=30)

    despues = [(seg_dir / "00.mp4").read_bytes(), (seg_dir / "01.mp4").read_bytes()]
    assert despues != antes  # al menos un lado es escena: Q4 no lo frena


def test_aplicar_todas_con_tipo_corte_explicito_no_toca_nada(tmp_path):
    seg_dir = _seg_dir(tmp_path, 2)
    antes = [(seg_dir / "00.mp4").read_bytes(), (seg_dir / "01.mp4").read_bytes()]
    g = {"segmentos": [{"escena": {"tipo": "presentacion"}, "texto": "a"},
                       {"escena": {"tipo": "presentacion"}, "texto": "b", "transicion": "corte"}]}
    tramos = [(g["segmentos"][0], 1.0, []), (g["segmentos"][1], 1.0, [])]

    transiciones.aplicar_todas(seg_dir, g, tramos, BRAND, ancho=320, fps=30)

    despues = [(seg_dir / "00.mp4").read_bytes(), (seg_dir / "01.mp4").read_bytes()]
    assert despues == antes


def test_aplicar_todas_primer_segmento_con_transicion_avisa_y_no_rompe(tmp_path, capsys):
    seg_dir = _seg_dir(tmp_path, 1)
    g = {"segmentos": [{"texto": "a", "transicion": "barrido"}]}
    tramos = [({"texto": "a", "transicion": "barrido"}, 1.0, None)]

    transiciones.aplicar_todas(seg_dir, g, tramos, BRAND, ancho=320, fps=30)

    aviso = capsys.readouterr().err
    assert "00" in aviso and "primero" in aviso


def test_aplicar_todas_con_slot_corto_avisa_el_acortado_r66(tmp_path, capsys):
    seg_dir = _seg_dir(tmp_path, 2, dur=0.3)
    g = {"transicion": {"tipo": "barrido", "duracion": 0.5},
         "segmentos": [{"texto": "a"}, {"escena": {"tipo": "presentacion"}, "texto": "b"}]}
    tramos = [({"texto": "a"}, 0.3, None), (g["segmentos"][1], 0.3, [])]

    transiciones.aplicar_todas(seg_dir, g, tramos, BRAND, ancho=320, fps=30)

    aviso = capsys.readouterr().err
    assert "01" in aviso and "se acorta" in aviso
