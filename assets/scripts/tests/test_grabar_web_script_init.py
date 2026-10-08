"""El script que Toma inyecta con context.add_init_script (sobrevive a
navegaciones): neutraliza los diálogos nativos (alert/confirm/print/prompt,
que en tomas anteriores congelaban el navegador grabando, CLAUDE.md §4.10) y
dibuja un cursor DOM porque los clicks por CDP no mueven el puntero del SO.

Esta capa prueba el TEXTO JS generado (contrato: qué overrides trae, cómo se
embebe la cola de prompts), sin Chrome real. El comportamiento en vivo (el
prompt devuelve las respuestas en orden, el cursor se mueve, nada bloquea) se
prueba en test_grabar_web_integracion.py contra la página local de fixtures.
"""
import json

import grabar_web


def test_sobreescribe_los_cuatro_dialogos_nativos():
    script = grabar_web._script_init(["uno", "dos"])

    assert "window.alert" in script
    assert "window.confirm" in script
    assert "window.print" in script
    assert "window.prompt" in script


def test_confirm_devuelve_true_y_alert_print_no_hacen_nada():
    script = grabar_web._script_init([])

    bloque_confirm = script.split("window.confirm = ", 1)[1].split("};", 1)[0]
    assert "return true" in bloque_confirm


def test_la_cola_inicial_de_prompt_queda_embebida_como_json_de_las_entradas():
    script = grabar_web._script_init(["mariana perez", "28"])

    assert json.dumps(["mariana perez", "28"], ensure_ascii=False) in script


def test_con_la_cola_vacia_embebe_un_array_vacio():
    script = grabar_web._script_init([])

    assert "[]" in script


def test_dibuja_un_cursor_que_no_intercepta_clicks():
    script = grabar_web._script_init([])

    assert "pointer-events" in script and "none" in script
    assert "ripple" in script.lower()
