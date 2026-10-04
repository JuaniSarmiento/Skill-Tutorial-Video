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
    for tipo in ("corte", "fundido", "barrido"):
        transiciones.validar_tipo(tipo)


def test_validar_tipo_desconocido_nombra_los_validos():
    with pytest.raises(transiciones.TransicionError) as e:
        transiciones.validar_tipo("transicon")
    assert "transicon" in str(e.value)
    assert "corte" in str(e.value) and "fundido" in str(e.value) and "barrido" in str(e.value)


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

def test_anchos_barrido_saliente_arranca_casi_en_0_y_termina_en_el_ancho_completo():
    anchos = transiciones.anchos_barrido("saliente", t0=1.0, mitad=0.2, ancho=320, fps=30)

    assert anchos[0] == (1.0, 1)          # nunca 0 exacto: drawbox trata w=0 como "completo"
    assert anchos[-1][1] == 320
    assert all(a[1] <= b[1] for a, b in zip(anchos, anchos[1:]))  # monótono creciente


def test_anchos_barrido_entrante_arranca_completo_y_termina_casi_en_0():
    anchos = transiciones.anchos_barrido("entrante", t0=0.0, mitad=0.2, ancho=320, fps=30)

    assert anchos[0] == (0.0, 320)
    assert anchos[-1][1] == 1
    assert all(a[1] >= b[1] for a, b in zip(anchos, anchos[1:]))  # monótono decreciente


def test_anchos_barrido_tiene_un_punto_por_cuadro_de_la_ventana():
    # 0.2s a 30fps = 6 cuadros -> 7 puntos (incluye los dos extremos)
    anchos = transiciones.anchos_barrido("saliente", t0=0.0, mitad=0.2, ancho=320, fps=30)
    assert len(anchos) == 7


def test_comandos_barrido_un_comando_w_por_cuadro():
    anchos = [(0.0, 1), (0.033333, 10), (0.066667, 320)]
    texto = transiciones.comandos_barrido(anchos, filtro="t6")

    assert texto.count("drawbox@t6 w") == 3
    assert "0.000000 drawbox@t6 w '1';" in texto
    assert "0.066667 drawbox@t6 w '320';" in texto


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
    assert "transicon" in str(e.value)


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
