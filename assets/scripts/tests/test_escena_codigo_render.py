"""H4: la escena `codigo` en la puerta `check` de verificar.py (H2), el render y los CLI.

Aparte de test_escena_codigo.py porque verificar_escena y render abren su propio Chrome (Playwright
sync no se anida con el Chrome de módulo de ese archivo).
"""
import pytest

pytest.importorskip("playwright")
import codigo  # noqa: E402
import escena  # noqa: E402
import verificar  # noqa: E402
from test_escena_codigo import COMPLETO, LLAMADAS, MEMO  # noqa: E402

pytestmark = pytest.mark.integracion


# con título, 8 líneas de código más 4 de terminal no entran a 28 px (falla a propósito):
# el caso con título va sin salida
SIN_SALIDA = [p for p in COMPLETO if p["modo"] != "salida"]


@pytest.mark.parametrize("cabecera, pasos", [({}, COMPLETO),
                                             ({"titulo": {"texto": "Memoización"}, "kicker": "Recursividad"}, SIN_SALIDA)])
def test_la_escena_completa_pasa_la_puerta_de_verificar(tmp_path, cabecera, pasos):
    (tmp_path / "fibonacci_memo.py").write_text(MEMO)
    (tmp_path / "llamadas.py").write_text(LLAMADAS)
    spec = codigo.resolver({"tipo": "codigo", "archivo": "fibonacci_memo.py", "desde": 4, "hasta": 11,
                            "duracion": 9.0, "pasos": pasos, **cabecera}, tmp_path)
    assert verificar.verificar_escena(escena.ruta_plantilla("codigo"), spec) == []


# --- el resaltado de código (derivado del acento, oklch) pasa el contraste en toda
# paleta, incluidas las de fondo claro (H10, HITO3.md) -------------------------------

@pytest.mark.parametrize("paleta", escena.paletas_validas())
def test_la_escena_completa_pasa_la_puerta_de_verificar_en_cada_paleta(tmp_path, paleta):
    (tmp_path / "fibonacci_memo.py").write_text(MEMO)
    (tmp_path / "llamadas.py").write_text(LLAMADAS)
    spec = codigo.resolver({"tipo": "codigo", "archivo": "fibonacci_memo.py", "desde": 4, "hasta": 11,
                            "duracion": 9.0, "pasos": COMPLETO}, tmp_path)
    brand = escena.cargar_brand(None, paleta=paleta)
    hallazgos = verificar.verificar_escena(escena.ruta_plantilla("codigo"), spec, brand)
    assert hallazgos == [], (paleta, verificar.informe(hallazgos))


# --- el motor resuelve el código: render, contacto, verificar.py y editar.py -----------

import json  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

SCRIPTS = Path(__file__).resolve().parents[1]
CORTA = {"tipo": "codigo", "archivo": "fibonacci_memo.py", "desde": 4, "hasta": 6, "duracion": 2.0,
         "pasos": [{"modo": "resaltar", "lineas": "5", "cue": 0.8}]}


@pytest.fixture
def carpeta(tmp_path):
    (tmp_path / "fibonacci_memo.py").write_text(MEMO)
    (tmp_path / "s.json").write_text(json.dumps(CORTA))
    return tmp_path


def test_render_resuelve_el_codigo_contra_el_directorio_del_spec(carpeta):
    mp4 = carpeta / "out.mp4"
    d = escena.render(escena.ruta_plantilla("codigo"), CORTA, mp4, fps=6, ancho=960, base_dir=carpeta)
    assert mp4.exists() and d == pytest.approx(2.0)


def test_el_cli_de_verificar_resuelve_el_codigo(carpeta):
    r = subprocess.run([sys.executable, str(SCRIPTS / "verificar.py"), str(carpeta / "s.json")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "sin hallazgos" in r.stdout


def test_la_hoja_de_contacto_resuelve_el_codigo(carpeta):
    png = carpeta / "hoja.png"
    r = subprocess.run([sys.executable, str(SCRIPTS / "escena.py"), "contacto", str(carpeta / "s.json"), "-o", str(png)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert png.exists()


def test_la_puerta_de_editar_revisar_resuelve_el_codigo(carpeta, monkeypatch):
    import editar
    monkeypatch.setattr(editar, "ROOT", carpeta)
    spec = carpeta / "00.json"
    spec.write_text(json.dumps({**CORTA, "archivo": str(carpeta / "fibonacci_memo.py")}))
    assert editar._desborde_escena(spec) == [] and editar._contraste_escena(spec) == []


# --- los números de línea no se pegan al código ---------------------------------------
# Con `box-sizing: border-box` (base.css) el padding de .num quedaba DENTRO de su ancho:
# con 2 dígitos el número invadía el hueco y se leía "14await" (piloto de Prog IV,
# 12/10/2026). Se mide en Chrome: entre el último dígito y el primer carácter del código
# tiene que quedar el hueco entero.

DOS_DIGITOS = "".join(f"x{i} = {i}\n" for i in range(1, 16))   # 15 líneas, sin sangría


def test_con_numeros_de_dos_digitos_queda_hueco_entre_el_numero_y_el_codigo(tmp_path):
    (tmp_path / "largo.py").write_text(DOS_DIGITOS)
    spec = codigo.resolver({"tipo": "codigo", "archivo": "largo.py", "duracion": 3.0,
                            "pasos": [{"modo": "resaltar", "lineas": "12", "cue": 0.5}]}, tmp_path)
    with escena.navegador() as b:
      with escena.pagina_de_escena(b, escena.ruta_plantilla("codigo"), spec, escena.cargar_brand(None)) as (page, dur):
        page.evaluate(f"window.seek({dur - 0.1})")
        huecos = page.evaluate("""() => [...document.querySelectorAll('.fila')].map(f => {
            const num = f.querySelector('.num'), txt = f.querySelector('.txt');
            const r = document.createRange(); r.selectNodeContents(num);
            const fin = r.getBoundingClientRect().right;
            const r2 = document.createRange(); r2.selectNodeContents(txt);
            return { n: num.textContent.trim(), hueco: r2.getBoundingClientRect().left - fin };
        }).filter(h => h.n)""")
    assert len(huecos) == 15
    pegados = [h for h in huecos if h["hueco"] < 16]
    assert pegados == [], pegados
