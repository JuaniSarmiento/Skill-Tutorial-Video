"""H6 (HITO3.md): "marcar" en la escena `presentacion` resalta una palabra con un
subrayado, un círculo o un resaltado dibujados a mano (stroke-dasharray en función
de t, la misma técnica de `imagen.html`), en su propio cue."""
import pytest

pytest.importorskip("playwright")
import escena  # noqa: E402

pytestmark = pytest.mark.integracion

SPEC = {
    "tipo": "presentacion",
    "titulo": {"texto": "Programación dinámica", "cue": 0},
    "puntos": [{"texto": "Guardamos cada resultado en memoización", "cue": 0.5},
               {"texto": "Evitamos recalcular lo mismo", "cue": 1.5}],
    "marcar": [{"texto": "memoización", "como": "subrayado", "cue": 2.2}],
    "duracion": 5.0,
}


@pytest.fixture(scope="module")
def chrome():
    with escena.navegador() as b:
        yield b


def _abrir(chrome, spec=SPEC):
    return escena.pagina_de_escena(chrome, escena.ruta_plantilla("presentacion"), spec, escena.cargar_brand(None))


def _medir(page, t, selector=".marca"):
    escena._cuadro(page, t)
    return page.evaluate("""sel => {
        const p = document.querySelector(sel);
        if (!p) return null;
        return {op: +getComputedStyle(p).opacity, dashoffset: getComputedStyle(p).strokeDashoffset,
                largo: p.getTotalLength ? p.getTotalLength() : null};
    }""", selector)


def test_antes_de_su_cue_la_marca_no_se_ve(chrome):
    with _abrir(chrome) as (page, _):
        m = _medir(page, 1.0)
    assert m is not None
    assert m["op"] == 0


def test_despues_de_su_cue_se_dibuja_completa(chrome):
    with _abrir(chrome) as (page, _):
        m = _medir(page, 4.0)
    assert m["op"] == 1
    assert float(m["dashoffset"].replace("px", "")) == pytest.approx(0, abs=0.5)


def test_a_mitad_del_dibujo_el_trazo_esta_a_mitad_de_camino(chrome):
    with _abrir(chrome) as (page, _):
        m = _medir(page, 2.35)
    off = float(m["dashoffset"].replace("px", ""))
    assert 0 < off < m["largo"]


# --- triangulación: "circulo" dibuja otra forma (cerrada) y otro "como" cambia la clase

def test_circulo_dibuja_un_trazo_cerrado(chrome):
    spec = {**SPEC, "marcar": [{"texto": "memoización", "como": "circulo", "cue": 2.2}]}
    with _abrir(chrome, spec) as (page, _):
        escena._cuadro(page, 3.0)
        d = page.evaluate("document.querySelector('.marca').getAttribute('d')")
    assert d.strip().endswith("Z")


def test_como_invalido_falla_claro(chrome):
    spec = {**SPEC, "marcar": [{"texto": "memoización", "como": "tachado", "cue": 2.2}]}
    with pytest.raises(escena.ContratoError, match="como"):
        with _abrir(chrome, spec):
            pass


# --- arreglo H6: el círculo pisaba la letra anterior (margen fijo de +20px, sin
# medir el hueco real con la palabra vecina). Repro: "trabajo" pegado a "mismo",
# igual que el caso real que señaló Juani ("trabajo" tocaba la "o" de "mismo").

SPEC_PALABRAS_PEGADAS = {
    "tipo": "presentacion",
    "titulo": {"texto": "Programación dinámica", "cue": 0},
    "puntos": [{"texto": "Evitamos recalcular lo mismo trabajo", "cue": 0.5}],
    "marcar": [{"texto": "trabajo", "como": "circulo", "cue": 1.0}],
    "duracion": 5.0,
}


def _bbox_del_circulo(page):
    return page.evaluate("""() => {
        const p = document.querySelector('.marca');
        const b = p.getBBox();
        return {left: b.x, right: b.x + b.width, top: b.y, bottom: b.y + b.height};
    }""")


def _bbox_de_palabra(page, texto):
    """Mide la caja real de `texto` (medición de test, no reusa producción) con
    un Range sobre el nodo de texto que la contiene, igual criterio de "palabra
    completa" que `envolverPalabra` de la plantilla."""
    return page.evaluate("""texto => {
        const buscar = texto.toLowerCase();
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        let nodo;
        while ((nodo = walker.nextNode())) {
            const low = nodo.textContent.toLowerCase();
            const i = low.indexOf(buscar);
            if (i === -1) continue;
            const antes = i === 0 || /\\s/.test(low[i - 1]);
            const despues = i + buscar.length >= low.length || /\\s/.test(low[i + buscar.length]);
            if (!antes || !despues) continue;
            const r = document.createRange();
            r.setStart(nodo, i);
            r.setEnd(nodo, i + buscar.length);
            const rect = r.getBoundingClientRect();
            return {left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom};
        }
        return null;
    }""", texto)


def test_circulo_no_pisa_la_palabra_anterior(chrome):
    with _abrir(chrome, SPEC_PALABRAS_PEGADAS) as (page, _):
        escena._cuadro(page, 3.0)
        circulo = _bbox_del_circulo(page)
        vecina = _bbox_de_palabra(page, "mismo")
    assert vecina is not None
    assert circulo["left"] > vecina["right"], (
        f"el círculo (left={circulo['left']:.1f}) pisa a 'mismo' (right={vecina['right']:.1f})")


def test_circulo_encierra_su_propia_palabra_con_margen_positivo(chrome):
    # triangulación: no basta con "no tocar la vecina" a costa de encoger el
    # círculo hasta pegarlo a la palabra marcada (un margen 0 también "no
    # pisa" nada, pero no es un círculo que encierra).
    with _abrir(chrome, SPEC_PALABRAS_PEGADAS) as (page, _):
        escena._cuadro(page, 3.0)
        circulo = _bbox_del_circulo(page)
        propia = _bbox_de_palabra(page, "trabajo")
    assert propia is not None
    assert circulo["left"] < propia["left"] - 1
    assert circulo["right"] > propia["right"] + 1
