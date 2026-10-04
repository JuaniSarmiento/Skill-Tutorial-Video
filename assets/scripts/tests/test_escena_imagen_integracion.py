"""Escena "imagen" (HITO2.md S4) contra un Chrome de verdad: que se DIBUJE, no que
aparezca de golpe (R-4.2), y que recolorear al brand sólo mueva el dibujo en foco (R-4.4).

El "recuadro del dibujo" se mide como el viewBox del propio SVG (200x200, igual en los
tres dibujos de ejemplo): se serializa el <svg> ya con sus atributos de la animación
(dasharray/dashoffset/fill-opacity, fijados por t) a una imagen y se cuenta en un canvas
cuántos píxeles no son el fondo. Así no hace falta decodificar PNG en Python ni agregar
Pillow como dependencia: todo el conteo pasa dentro del propio Chrome ya abierto.
"""
import pytest

pytest.importorskip("playwright")
import escena  # noqa: E402

pytestmark = pytest.mark.integracion

DIBUJOS = escena.ESCENAS / "dibujos"

LEER_PIXELES = """async ({ selector, fondo, modo }) => {
  const el = document.querySelector(selector);
  const svg = el.querySelector('svg');
  const vb = svg.viewBox.baseVal;
  const w = Math.round(vb.width) || 200, h = Math.round(vb.height) || 200;
  // el color y la opacidad están en el DIV contenedor (currentColor, opacity del fade
  // de entrada), no en el <svg> en sí: serializar sólo el <svg> los pierde. Se clona y
  // se fijan explícitos ANTES de serializar, así la imagen aislada queda igual que la
  // que se ve en pantalla.
  const estilo = getComputedStyle(el);
  const clon = svg.cloneNode(true);
  clon.style.color = estilo.color;
  clon.style.opacity = estilo.opacity;
  const xml = new XMLSerializer().serializeToString(clon);
  const blob = new Blob([xml], { type: 'image/svg+xml' });
  const url = URL.createObjectURL(blob);
  const img = new Image();
  await new Promise((res, rej) => {
    img.onload = res;
    img.onerror = () => rej(new Error('no cargó el SVG serializado'));
    img.src = url;
  });
  const canvas = document.createElement('canvas');
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(img, 0, 0, w, h);
  const data = ctx.getImageData(0, 0, w, h).data;
  URL.revokeObjectURL(url);
  if (modo === 'hash') {
    // para R-4.4: un conteo de "es fondo o no" no distingue color, dos colores
    // distintos pueden dar el mismo conteo. El hash de los bytes sí los distingue.
    const buf = await crypto.subtle.digest('SHA-256', data.buffer);
    return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
  }
  const [fr, fg, fb] = fondo;
  let cont = 0;
  for (let i = 0; i < data.length; i += 4) {
    if (data[i + 3] === 0) continue;
    if (Math.abs(data[i] - fr) > 12 || Math.abs(data[i + 1] - fg) > 12 || Math.abs(data[i + 2] - fb) > 12)
      cont++;
  }
  return cont;
}"""


def _fondo_rgb(brand):
    hexcolor = brand["colores"]["fondo"].lstrip("#")
    return [int(hexcolor[i:i + 2], 16) for i in (0, 2, 4)]


def _pixeles(page, caja, fondo):
    return page.evaluate(LEER_PIXELES, {"selector": f"[data-caja='{caja}']", "fondo": fondo, "modo": "contar"})


def _hash_pixeles(page, caja):
    return page.evaluate(LEER_PIXELES, {"selector": f"[data-caja='{caja}']", "fondo": [0, 0, 0], "modo": "hash"})


UN_DIBUJO = {
    "titulo": {"texto": "Una idea"},
    "dibujos": [{"id": "lampara", "svg": str(DIBUJOS / "lampara.svg"), "cue": 1.0}],
    "duracion": 3.0,
}


@pytest.fixture(scope="module")
def chrome():
    with escena.navegador() as b:
        yield b


def test_antes_de_su_cue_el_recuadro_del_dibujo_es_fondo_puro(chrome):
    brand = escena.cargar_brand(None)
    spec = escena.resolver_dibujos(UN_DIBUJO)
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla("imagen"), spec, brand) as (page, _):
        escena._cuadro(page, 0.3)   # antes de cue=1.0
        assert _pixeles(page, "dibujo lampara", _fondo_rgb(brand)) == 0


def test_en_t_mas_movimiento_entrada_el_dibujo_esta_al_maximo_y_se_mantiene(chrome):
    brand = escena.cargar_brand(None)
    entrada = brand["movimiento"]["entrada"]
    spec = escena.resolver_dibujos(UN_DIBUJO)
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla("imagen"), spec, brand) as (page, _):
        escena._cuadro(page, 1.0 + entrada)
        maximo = _pixeles(page, "dibujo lampara", _fondo_rgb(brand))
        escena._cuadro(page, 2.9)   # bien después: tiene que seguir en el máximo, no bajar
        despues = _pixeles(page, "dibujo lampara", _fondo_rgb(brand))
    assert maximo > 0
    assert despues == maximo


def test_a_mitad_de_camino_esta_estrictamente_entre_fondo_y_maximo(chrome):
    brand = escena.cargar_brand(None)
    entrada = brand["movimiento"]["entrada"]
    spec = escena.resolver_dibujos(UN_DIBUJO)
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla("imagen"), spec, brand) as (page, _):
        escena._cuadro(page, 1.0 + entrada * 0.5)
        medio = _pixeles(page, "dibujo lampara", _fondo_rgb(brand))
        escena._cuadro(page, 1.0 + entrada)
        maximo = _pixeles(page, "dibujo lampara", _fondo_rgb(brand))
    assert 0 < medio < maximo


def test_los_pixeles_no_bajan_de_un_cuadro_muestreado_al_siguiente(chrome):
    brand = escena.cargar_brand(None)
    entrada = brand["movimiento"]["entrada"]
    spec = escena.resolver_dibujos(UN_DIBUJO)
    tiempos = [1.0 + f * entrada for f in (0.0, 0.15, 0.35, 0.55, 0.75, 1.0, 1.3)]
    conteos = []
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla("imagen"), spec, brand) as (page, _):
        for t in tiempos:
            escena._cuadro(page, t)
            conteos.append(_pixeles(page, "dibujo lampara", _fondo_rgb(brand)))
    for antes, despues in zip(conteos, conteos[1:]):
        assert despues >= antes, conteos


DOS_DIBUJOS = {
    "titulo": {"texto": "Dos ideas"},
    "dibujos": [{"id": "lampara", "svg": str(DIBUJOS / "lampara.svg"), "cue": 0.3},
                {"id": "semilla", "svg": str(DIBUJOS / "semilla.svg"), "cue": 1.6}],
    "duracion": 3.5,
}


def _render_en(chrome, acento, t):
    brand = {**escena.cargar_brand(None), "colores": {**escena.cargar_brand(None)["colores"], "acento": acento}}
    spec = escena.resolver_dibujos(DOS_DIBUJOS)
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla("imagen"), spec, brand) as (page, _):
        escena._cuadro(page, t)
        foco = _hash_pixeles(page, "dibujo semilla")
        no_foco = _hash_pixeles(page, "dibujo lampara")
    return foco, no_foco


def test_cambiar_el_acento_cambia_el_dibujo_en_foco_y_deja_el_resto_igual(chrome):
    # t después de que entraron los dos: "semilla" (la última) es el foco, "lampara" no.
    t = 1.6 + escena.cargar_brand(None)["movimiento"]["entrada"]
    foco_a, no_foco_a = _render_en(chrome, "#F2B544", t)
    foco_b, no_foco_b = _render_en(chrome, "#2255FF", t)
    assert foco_a != foco_b, "el dibujo en foco tiene que cambiar con el acento"
    assert no_foco_a == no_foco_b, "el dibujo que no está en foco no puede cambiar"


# --- B4(c): SVG sin viewBox (QA 03/10/2026) ------------------------------------

def _un_dibujo(chrome, tmp_path, svg_contenido):
    svg = tmp_path / "dibujo.svg"
    svg.write_text(svg_contenido)
    brand = escena.cargar_brand(None)
    spec = escena.resolver_dibujos(
        {"titulo": {"texto": "x"}, "duracion": 1.0, "dibujos": [{"id": "a", "svg": str(svg), "cue": 0.1}]})
    return brand, spec


def test_svg_sin_viewbox_pero_con_contenido_medible_se_calcula_del_bbox(chrome, tmp_path):
    brand, spec = _un_dibujo(chrome, tmp_path, '<svg><rect x="40" y="40" width="20" height="20" fill="currentColor"/></svg>')
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla("imagen"), spec, brand) as (page, d):
        escena._cuadro(page, d - 0.05)
        ancho, alto = page.evaluate(
            "() => { const s = document.querySelector('[data-caja^=\"dibujo\"] svg').viewBox.baseVal;"
            " return [s.width, s.height]; }")
    assert ancho > 0 and alto > 0


def test_svg_sin_viewbox_y_sin_contenido_medible_falla_nombrando_el_dibujo(chrome, tmp_path):
    brand, spec = _un_dibujo(chrome, tmp_path, "<svg></svg>")
    with pytest.raises(escena.ContratoError, match="viewBox"):
        with escena.pagina_de_escena(chrome, escena.ruta_plantilla("imagen"), spec, brand) as (page, d):
            escena._cuadro(page, d - 0.05)


# --- B4(a): formas fuera de la convención (sólo relleno, <text>) se revelan ----
# progresivo, no de golpe (QA 03/10/2026)

def _dibujo_con_cue(tmp_path, svg_contenido, cue=1.0, duracion=3.0):
    svg = tmp_path / "forma.svg"
    svg.write_text(svg_contenido)
    brand = escena.cargar_brand(None)
    spec = escena.resolver_dibujos({"titulo": {"texto": "Una idea"}, "duracion": duracion,
                                    "dibujos": [{"id": "a", "svg": str(svg), "cue": cue}]})
    return brand, spec


def test_una_forma_solo_con_relleno_se_revela_progresivo_no_de_golpe(chrome, tmp_path):
    brand, spec = _dibujo_con_cue(
        tmp_path, '<svg viewBox="0 0 200 200"><circle cx="100" cy="100" r="80" fill="currentColor"/></svg>')
    entrada = brand["movimiento"]["entrada"]
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla("imagen"), spec, brand) as (page, _):
        escena._cuadro(page, 1.0 + entrada * 0.15)
        temprano = _pixeles(page, "dibujo a", _fondo_rgb(brand))
        escena._cuadro(page, 1.0 + entrada)
        maximo = _pixeles(page, "dibujo a", _fondo_rgb(brand))
    assert 0 < temprano < maximo * 0.7, (temprano, maximo)


# N2 (QA 04/10/2026, repro circulo.svg): el revelado con resorte (overshoot ~4%) de las
# formas "otros" viola R-4.2: los píxeles no-fondo bajan varios cuadros, con el máximo bien
# antes de t0+entrada. El revelado tiene que ser monótono (nunca bajar), con el máximo
# recién en t0+entrada, igual que el trazo.

def test_una_forma_solo_con_relleno_nunca_baja_de_un_cuadro_al_siguiente(chrome, tmp_path):
    brand, spec = _dibujo_con_cue(
        tmp_path, '<svg viewBox="0 0 200 200"><circle cx="100" cy="100" r="80" fill="currentColor"/></svg>')
    entrada = brand["movimiento"]["entrada"]
    tiempos = [1.0 + f * entrada for f in (0.0, 0.15, 0.35, 0.55, 0.75, 1.0, 1.3)]
    conteos = []
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla("imagen"), spec, brand) as (page, _):
        for t in tiempos:
            escena._cuadro(page, t)
            conteos.append(_pixeles(page, "dibujo a", _fondo_rgb(brand)))
    for antes, despues in zip(conteos, conteos[1:]):
        assert despues >= antes, conteos
    assert conteos[-2] == conteos[-1], "el máximo tiene que caer en t0+entrada y mantenerse, no antes"


def test_un_text_nunca_baja_de_un_cuadro_al_siguiente(chrome, tmp_path):
    brand, spec = _dibujo_con_cue(
        tmp_path, '<svg viewBox="0 0 200 200"><text x="10" y="150" font-size="140" '
                  'fill="currentColor">OK</text></svg>')
    entrada = brand["movimiento"]["entrada"]
    tiempos = [1.0 + f * entrada for f in (0.0, 0.15, 0.35, 0.55, 0.75, 1.0, 1.3)]
    conteos = []
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla("imagen"), spec, brand) as (page, _):
        for t in tiempos:
            escena._cuadro(page, t)
            conteos.append(_pixeles(page, "dibujo a", _fondo_rgb(brand)))
    for antes, despues in zip(conteos, conteos[1:]):
        assert despues >= antes, conteos


# N2 (QA 04/10/2026): sets típicos (Lucide/Tabler/Font Awesome) ponen stroke/fill en el
# <svg> raíz, heredado por el <path>; getAttribute('stroke') del <path> da null y el
# ícono caía en "otros" (revelado por escala) en vez de dibujarse por trazo.

LUCIDE_ICONO = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
                'stroke-linecap="round" stroke-linejoin="round">'
                '<path d="M4 4 L20 4 L20 20 L4 20 Z"/></svg>')


def test_un_icono_tipo_lucide_se_dibuja_por_trazo_heredado_no_por_escala(chrome, tmp_path):
    brand, spec = _dibujo_con_cue(tmp_path, LUCIDE_ICONO)
    entrada = brand["movimiento"]["entrada"]
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla("imagen"), spec, brand) as (page, _):
        escena._cuadro(page, 1.0 + entrada * 0.5)
        tiene_dasharray = page.evaluate(
            "() => !!document.querySelector('[data-caja=\"dibujo a\"] path').getAttribute('stroke-dasharray')")
    assert tiene_dasharray, ("un <path> dentro de <svg stroke=\"currentColor\" fill=\"none\"> se tiene que "
                             "dibujar por trazo (heredado por CSS), no caer en \"otros\"")


def test_el_relleno_no_entra_hasta_que_el_trazo_esta_casi_completo(chrome):
    # J2 (QA 03/10/2026): ningún test anterior distinguía "el relleno entra después del
    # trazo" de "el relleno entra entero apenas arranca el trazo" (esa mutación sobrevivía).
    brand = escena.cargar_brand(None)
    entrada = brand["movimiento"]["entrada"]
    spec = escena.resolver_dibujos(UN_DIBUJO)
    FILL_OPACITY = ("() => +document.querySelector('[data-caja=\"dibujo lampara\"] .lleno')"
                    ".getAttribute('fill-opacity')")
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla("imagen"), spec, brand) as (page, _):
        escena._cuadro(page, 1.0 + entrada * 0.3)
        temprano = page.evaluate(FILL_OPACITY)
        escena._cuadro(page, 1.0 + entrada)
        final = page.evaluate(FILL_OPACITY)
    assert temprano == 0, "a 30% del tiempo de entrada el relleno todavía no tiene que verse"
    assert final == 1


def test_un_text_tambien_se_revela_progresivo_no_de_golpe(chrome, tmp_path):
    brand, spec = _dibujo_con_cue(
        tmp_path,
        '<svg viewBox="0 0 200 200">'
        '<text x="10" y="150" font-size="140" fill="currentColor">OK</text></svg>')
    entrada = brand["movimiento"]["entrada"]
    with escena.pagina_de_escena(chrome, escena.ruta_plantilla("imagen"), spec, brand) as (page, _):
        escena._cuadro(page, 1.0 + entrada * 0.15)
        temprano = _pixeles(page, "dibujo a", _fondo_rgb(brand))
        escena._cuadro(page, 1.0 + entrada)
        maximo = _pixeles(page, "dibujo a", _fondo_rgb(brand))
    assert 0 < temprano < maximo * 0.7, (temprano, maximo)
