#!/usr/bin/env python3
"""Graba una app web real (Plataforma N4) pareciendo un humano usándola.

Corre dentro del display X11 que levanta entorno.sh (Wayland: Chrome ignora
DISPLAY y hay que forzar --ozone-platform=x11 + limpiar WAYLAND_DISPLAY, igual
que entorno.sh chrome). Playwright se conecta al Chrome YA LANZADO por CDP
(connect_over_cdp), nunca al navegador empaquetado de Playwright.

uso:
    grabar_web.py login <perfil> <url>   # el humano loguea a mano, una vez

API para scripts de toma (ver references/grabacion.md):
    from grabar_web import Toma
    t = Toma("docente-n4", "https://tutor.active-ia.com/...")
    t.grabar_iniciar("v01-comisiones")
    t.click("Mis comisiones")
    t.marca("abrio comisiones")
    t.grabar_detener()
    t.cerrar()
"""
import json
import math
import os
import random
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import rec  # noqa: E402
from plataforma import SISTEMA  # noqa: E402

PERFILES_DIR = Path(os.path.expanduser("~/.config/tutorial-video/perfiles"))

VELOCIDAD_PX_S = 900.0
PASO_S = 1 / 60
DURACION_MIN = 0.15


def _formatear_marca(t: float, nombre: str) -> dict:
    """{t, nombre} en segundos desde el inicio de la grabación, redondeado a ms."""
    return {"t": round(t, 3), "nombre": nombre}


def _escribir_marca(destino: Path, marca: dict) -> None:
    """Agrega `marca` como una línea JSON a `destino` (raw/<nombre>.marcas.json)."""
    with open(destino, "a", encoding="utf-8") as f:
        f.write(json.dumps(marca, ensure_ascii=False) + "\n")


def _script_init(entradas: list[str]) -> str:
    """JS para context.add_init_script: sobrevive a cada navegación (a diferencia de
    page.add_init_script, que sólo corre una vez).

    - Neutraliza alert/confirm/print/prompt ANTES de que el navegador pueda abrir el
      diálogo nativo: un alert()/confirm() real congela el renderizado y la
      grabación sigue filmando el cartel (CLAUDE.md §4.10, pasó en N4 v02). confirm
      devuelve true, alert/print no hacen nada, prompt sacа la próxima respuesta de
      una cola (la Plataforma usa window.prompt para el input() de Pyodide).
    - Cada diálogo interceptado se loguea en window.__tomaDialogs, para que el
      script que grava pueda leerlo (o para depurar una toma que salió rara).
    - Dibuja un cursor DOM (flecha SVG, position:fixed, z-index altísimo,
      pointer-events:none para no interceptar clicks) con un método
      window.__tomaCursor.mover(x,y) y .click() (ripple) que usa Toma para que el
      puntero se vea en el video: los clicks de CDP no mueven el cursor del SO.
    """
    cola_json = json.dumps(list(entradas), ensure_ascii=False)
    return f"""
(() => {{
  window.__tomaDialogs = window.__tomaDialogs || [];
  window.__tomaPromptQueue = {cola_json};
  window.alert = (msg) => {{ window.__tomaDialogs.push({{tipo: 'alert', msg: String(msg)}}); }};
  window.confirm = (msg) => {{ window.__tomaDialogs.push({{tipo: 'confirm', msg: String(msg)}}); return true; }};
  window.print = () => {{ window.__tomaDialogs.push({{tipo: 'print', msg: ''}}); }};
  window.prompt = (msg, def_) => {{
    const hay = window.__tomaPromptQueue.length > 0;
    const val = hay ? window.__tomaPromptQueue.shift() : null;
    window.__tomaDialogs.push({{tipo: 'prompt', msg: String(msg), val}});
    return val;
  }};

  const cursor = document.createElement('div');
  cursor.id = '__toma-cursor';
  cursor.style.cssText = 'position:fixed;top:0;left:0;width:22px;height:22px;'
    + 'z-index:2147483647;pointer-events:none;transform:translate(-2px,-2px);'
    + 'transition:none;';
  cursor.innerHTML = '<svg width="22" height="22" viewBox="0 0 22 22">'
    + '<path d="M2 1 L2 18 L7 14 L10 20 L13 19 L10 13 L17 13 Z" '
    + 'fill="#ffffff" stroke="#111111" stroke-width="1.2"/></svg>';
  const ripple = document.createElement('div');
  ripple.id = '__toma-ripple';
  ripple.style.cssText = 'position:fixed;top:0;left:0;width:28px;height:28px;'
    + 'margin:-14px 0 0 -14px;border-radius:50%;border:2px solid #ffffff;'
    + 'z-index:2147483646;pointer-events:none;opacity:0;';
  const montar = () => {{
    if (document.body) {{ document.body.appendChild(cursor); document.body.appendChild(ripple); }}
  }};
  if (document.body) montar(); else document.addEventListener('DOMContentLoaded', montar);

  window.__tomaCursor = {{
    mover(x, y) {{ cursor.style.transform = `translate(${{x - 2}}px, ${{y - 2}}px)`; }},
    click(x, y) {{
      ripple.style.left = x + 'px'; ripple.style.top = y + 'px';
      ripple.style.transition = 'none'; ripple.style.opacity = '0.9';
      ripple.style.transform = 'scale(0.4)';
      requestAnimationFrame(() => {{
        ripple.style.transition = 'opacity 200ms ease-out, transform 200ms ease-out';
        ripple.style.opacity = '0'; ripple.style.transform = 'scale(1.6)';
      }});
    }},
  }};
}})();
"""


def _cmd_chrome(perfil: str, url: str, puerto: int = 9333, escala: float = 1.5) -> list[str]:
    """argv de Chrome grabable: perfil persistente en PERFILES_DIR/<perfil>, modo
    --app (sin pestañas/barra/favoritos, CLAUDE.md §4.2), ventana 1920x1080 en el
    origen, --force-device-scale-factor (default 1.5, para que el texto mida
    >=24px en el cuadro final) y --remote-debugging-port para connect_over_cdp.
    No baja Chrome: usa el instalado (como entorno.sh chrome).
    """
    perfil_dir = PERFILES_DIR / perfil
    return [
        "google-chrome",
        f"--user-data-dir={perfil_dir}",
        f"--app={url}",
        "--window-position=0,0",
        "--window-size=1920,1080",
        f"--force-device-scale-factor={escala}",
        f"--remote-debugging-port={puerto}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=Translate,TranslateUI",
        "--disable-infobars",
        "--hide-crash-restore-bubble",
        # openbox (entorno.sh) dibuja una barra de título sobre cualquier
        # ventana normal: --kiosk la saca sin mostrar el cartel transitorio
        # "mantené Esc para salir de pantalla completa" que sí muestra
        # --start-fullscreen (verificado a mano, ver references/grabacion.md).
        "--kiosk",
        "--hide-scrollbars",
    ]


def _lanzar_chrome(perfil: str, url: str, puerto: int = 9333, escala: float = 1.5,
                   display: str | None = None) -> subprocess.Popen:
    """Lanza el Chrome instalado (nunca el de Playwright) con el perfil persistente
    de `perfil`, grabable por CDP. Bajo Wayland, Chrome ignora DISPLAY y abre en
    Ozone/Wayland en vez de en el Xephyr que graba `entorno.sh start`: hay que
    forzar --ozone-platform=x11 Y limpiar WAYLAND_DISPLAY (las dos cosas, ver
    references/grabacion.md y entorno.sh chrome).
    """
    (PERFILES_DIR / perfil).mkdir(parents=True, exist_ok=True)
    argv = _cmd_chrome(perfil, url, puerto, escala) + ["--ozone-platform=x11", "--disable-gpu"]
    env = dict(os.environ)
    env.pop("WAYLAND_DISPLAY", None)
    env.pop("XDG_SESSION_TYPE", None)
    env["DISPLAY"] = display or os.environ.get("DISPLAY", ":0")
    return subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def login(perfil: str, url: str, puerto: int = 9334, display: str | None = None) -> None:
    """Abre `url` en el perfil persistente de `perfil`, visible, para que el humano
    loguee A MANO. No toca ningún formulario, no tipea ni lee ninguna contraseña.
    Vuelve cuando el humano cierra la ventana (nunca se mata el proceso)."""
    proc = _lanzar_chrome(perfil, url, puerto=puerto, display=display)
    proc.wait()


class DialogoNativoError(RuntimeError):
    """Se detectó un diálogo nativo pese al override, o una acción falló: la toma
    se corta en vez de seguir grabando una página congelada (ver CLAUDE.md §4.10)."""


def _ease_in_out(s: float) -> float:
    """smoothstep: 0 en s=0, 1 en s=1, derivada 0 en los dos bordes (arranca y frena)."""
    return s * s * (3 - 2 * s)


def _bezier_cubica(p0, p1, p2, p3, u: float) -> tuple[float, float]:
    mu = 1 - u
    x = mu**3 * p0[0] + 3 * mu**2 * u * p1[0] + 3 * mu * u**2 * p2[0] + u**3 * p3[0]
    y = mu**3 * p0[1] + 3 * mu**2 * u * p1[1] + 3 * mu * u**2 * p2[1] + u**3 * p3[1]
    return x, y


def trayectoria(origen: tuple[float, float], destino: tuple[float, float],
                seed: int = 0, velocidad_px_s: float = VELOCIDAD_PX_S,
                paso_s: float = PASO_S) -> list[dict]:
    """Puntos {t, x, y} desde origen a destino, en segundos desde el inicio del
    movimiento (t[0] == 0.0, estrictamente creciente).

    Curva de Bezier cúbica con los puntos de control arqueados perpendicular a la
    recta origen->destino, con jitter chico determinístico por `seed` (misma seed
    = misma curva, para que un test o una toma se pueda repetir igual). El timing
    usa ease-in-out (smoothstep) sobre el parámetro de la curva, así el cursor
    arranca y frena en vez de viajar a velocidad constante. La duración crece con
    la distancia (distancia / velocidad_px_s, con un piso para movimientos cortos).
    Los extremos quedan EXACTOS (nunca movidos por el jitter): el click necesita
    caer justo en el centro del elemento, no cerca.
    """
    x0, y0 = origen
    x3, y3 = destino
    dx, dy = x3 - x0, y3 - y0
    dist = math.hypot(dx, dy)
    duracion = max(DURACION_MIN, dist / velocidad_px_s)

    rng = random.Random(seed)
    base = dist or 1.0
    arco = min(base * 0.25, 120.0)
    nx, ny = (-dy / base, dx / base) if dist else (0.0, 0.0)
    j1 = rng.uniform(-1, 1) * arco * 0.3
    j2 = rng.uniform(-1, 1) * arco * 0.3
    p1 = (x0 + dx * 0.33 + nx * (arco + j1), y0 + dy * 0.33 + ny * (arco + j1))
    p2 = (x0 + dx * 0.66 + nx * (-arco + j2), y0 + dy * 0.66 + ny * (-arco + j2))

    n_pasos = max(1, round(duracion / paso_s))
    puntos = []
    for i in range(n_pasos + 1):
        s = i / n_pasos
        u = _ease_in_out(s)
        x, y = _bezier_cubica((x0, y0), p1, p2, (x3, y3), u)
        puntos.append({"t": round(s * duracion, 4), "x": x, "y": y})
    puntos[0] = {"t": 0.0, "x": x0, "y": y0}
    puntos[-1] = {"t": round(duracion, 4), "x": x3, "y": y3}
    return puntos


def _esperar_cdp(puerto: int, intentos: int = 40, pausa_s: float = 0.25) -> None:
    """Espera (acotado: a lo sumo intentos*pausa_s) a que el endpoint CDP de Chrome
    responda. Acotado a propósito: nunca un loop que pueda colgarse para siempre."""
    import urllib.request
    for _ in range(intentos):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{puerto}/json/version", timeout=1)
            return
        except Exception:
            time.sleep(pausa_s)
    raise DialogoNativoError(f"Chrome no respondió en el puerto CDP {puerto} tras "
                             f"{intentos * pausa_s:.0f}s (¿perfil bloqueado por otro Chrome?)")


class Toma:
    """API de scripts de toma: navega, clickea, tipea y grava una app web real
    pareciendo un humano. Se conecta por CDP al Chrome que ella misma lanza
    (nunca al navegador de Playwright): ver _lanzar_chrome.
    """

    def __init__(self, perfil: str, url: str, salida: str | None = None,
                escala: float = 1.5, seed: int = 0, puerto: int = 9333,
                display: str | None = None, entradas: list[str] | None = None):
        from playwright.sync_api import sync_playwright

        self.perfil = perfil
        self._display = display or os.environ.get("DISPLAY", ":0")
        self._proc = _lanzar_chrome(perfil, url, puerto=puerto, escala=escala, display=display)
        _esperar_cdp(puerto)
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.connect_over_cdp(f"http://127.0.0.1:{puerto}")
        self._context = self._browser.contexts[0]
        self._dialogos_vistos: list[dict] = []
        self._context.on("page", lambda p: p.on("dialog", self._on_dialogo_nativo))
        self._context.add_init_script(_script_init(list(entradas or [])))
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        self._page.on("dialog", self._on_dialogo_nativo)
        # add_init_script sólo corre en navegaciones FUTURAS: Chrome ya cargó la
        # página (vía --app) antes de que Playwright se conecte por CDP, así que
        # hace falta un reload para que el init script corra sobre ESTA página.
        self._page.reload()
        self._rng = random.Random(seed)
        self._cursor_pos = (960.0, 540.0)
        self._t0: float | None = None
        self._grab_nombre: str | None = None
        self._marcas_path: Path | None = None

    # -------------------------------------------------------------- dialogos

    def _on_dialogo_nativo(self, dialog) -> None:
        """Red de seguridad: con el init script, esto NUNCA debería dispararse (alert/
        confirm/prompt/print ya están pisados antes de que el navegador abra el
        diálogo real). Si se dispara igual, se acepta para no colgar el proceso y se
        guarda para que _verificar_sin_dialogo() corte la toma (CLAUDE.md §4.10)."""
        self._dialogos_vistos.append({"tipo": dialog.type, "mensaje": dialog.message})
        try:
            dialog.accept()
        except Exception:
            pass

    def _verificar_sin_dialogo(self) -> None:
        if self._dialogos_vistos:
            raise DialogoNativoError(
                f"diálogo nativo detectado pese al override: {self._dialogos_vistos!r}. "
                "La toma se corta: nunca se sigue grabando una página congelada.")

    # -------------------------------------------------------------- resolver objetivo

    def _resolver(self, objetivo):
        """objetivo: un Locator ya armado, (role, name), un selector CSS (#id, .clase,
        [attr]) o texto visible. NUNCA coordenadas fijas: un modal que crece corre
        todo lo de abajo y una coordenada fija cae en otro elemento."""
        if hasattr(objetivo, "click") and hasattr(objetivo, "bounding_box"):
            return objetivo
        if isinstance(objetivo, tuple):
            role, name = objetivo
            return self._page.get_by_role(role, name=name)
        texto = str(objetivo)
        if texto.startswith(("#", ".", "[")) or texto.startswith(("css=", "xpath=")):
            return self._page.locator(texto)
        return self._page.get_by_text(texto, exact=False).first

    # -------------------------------------------------------------- cursor

    def _mover_cursor_hacia(self, destino: tuple[float, float]) -> None:
        seed = self._rng.randint(0, 2**31)
        puntos = trayectoria(self._cursor_pos, destino, seed=seed)
        anterior_t = 0.0
        for p in puntos:
            self._page.evaluate("([x, y]) => window.__tomaCursor.mover(x, y)", [p["x"], p["y"]])
            time.sleep(max(0.0, p["t"] - anterior_t))
            anterior_t = p["t"]
        self._cursor_pos = destino

    # -------------------------------------------------------------- API de toma

    def ir(self, url: str) -> None:
        self._verificar_sin_dialogo()
        self._page.goto(url)
        self._verificar_sin_dialogo()

    def click(self, objetivo) -> None:
        """Anima el cursor dibujado hasta el centro de `objetivo` y clickea.

        El click REAL va por Locator.click() (nunca page.mouse.click con una
        coordenada capturada antes): Playwright vuelve a resolver el elemento y
        espera a que esté "estable" (que no se siga moviendo) recién al momento de
        clickear. Si se usara la coordenada vieja, un modal que corre todo lo de
        abajo entre el cálculo del centro (para animar el cursor) y el click
        real desalinea el click (pasó de verdad en una toma anterior).
        """
        self._verificar_sin_dialogo()
        locator = self._resolver(objetivo)
        locator.scroll_into_view_if_needed()
        caja = locator.bounding_box()
        if caja is None:
            raise DialogoNativoError(f"click: no encontré el elemento {objetivo!r} visible")
        centro = (caja["x"] + caja["width"] / 2, caja["y"] + caja["height"] / 2)
        self._mover_cursor_hacia(centro)
        time.sleep(0.15)
        self._verificar_sin_dialogo()
        locator.click()
        caja_final = locator.bounding_box() or caja
        centro_final = (caja_final["x"] + caja_final["width"] / 2,
                        caja_final["y"] + caja_final["height"] / 2)
        self._cursor_pos = centro_final
        self._page.evaluate("([x, y]) => window.__tomaCursor.mover(x, y)", list(centro_final))
        self._page.evaluate("([x, y]) => window.__tomaCursor.click(x, y)", list(centro_final))
        self._verificar_sin_dialogo()

    def escribir(self, objetivo, texto: str) -> None:
        """Tipea con ritmo humano (delay por caracter, seedeado). Si el objetivo es
        (o contiene) un editor CodeMirror-like, clickea DIRECTO su .cm-line (no el
        wrapper): clickear el contenedor grande puede dejar el caret fuera de la
        línea, y después se verifica leyendo ese mismo .cm-line."""
        self._verificar_sin_dialogo()
        locator = self._resolver(objetivo)
        cm = locator.locator(".cm-line")
        objetivo_real = cm.last if cm.count() > 0 else locator
        objetivo_real.click()
        rng = random.Random(self._rng.randint(0, 2**31))
        for ch in texto:
            self._page.keyboard.type(ch)
            time.sleep(rng.uniform(0.03, 0.09))
        self._verificar_sin_dialogo()
        cm = locator.locator(".cm-line")
        if cm.count() > 0 and texto not in cm.inner_text():
            raise DialogoNativoError(
                f"escribir: el editor no recibió el texto esperado (vio {cm.inner_text()!r})")

    def scroll(self, objetivo=None, y: int = 600, pasos: int = 12, pausa_s: float = 0.02) -> None:
        if objetivo is not None:
            self._resolver(objetivo).scroll_into_view_if_needed()
            return
        actual = self._page.evaluate("() => window.scrollY")
        for i in range(1, pasos + 1):
            frac = _ease_in_out(i / pasos)
            self._page.evaluate("(yy) => window.scrollTo(0, yy)", actual + y * frac)
            time.sleep(pausa_s)

    def pausa(self, s: float) -> None:
        time.sleep(s)

    def entradas(self, lista: list[str]) -> None:
        """Encola respuestas para los próximos window.prompt() (input() de Pyodide)."""
        self._page.evaluate("(xs) => { window.__tomaPromptQueue.push(...xs); }", list(lista))

    def esperar(self, objetivo, timeout: float = 10000) -> None:
        self._resolver(objetivo).wait_for(timeout=timeout)

    def marca(self, nombre: str) -> None:
        if self._t0 is None or self._marcas_path is None:
            raise RuntimeError("marca(): no hay grabación iniciada (llamá grabar_iniciar primero)")
        t = time.monotonic() - self._t0
        _escribir_marca(self._marcas_path, _formatear_marca(t, nombre))

    # -------------------------------------------------------------- grabación

    def grabar_iniciar(self, nombre: str) -> None:
        """rec.py arma el comando de x11grab leyendo os.environ["DISPLAY"] al momento
        de llamar a start(): si el proceso del script de toma tiene otro DISPLAY (el
        real del host bajo Wayland, no el de Xephyr), rec.py graba la pantalla
        EQUIVOCADA y el .mkv sale negro sin avisar (mismo gotcha de Wayland que
        references/grabacion.md). Por eso se pisa con el DISPLAY de ESTA Toma,
        restaurando el valor anterior después de arrancar la captura."""
        self._grab_nombre = nombre
        anterior = os.environ.get("DISPLAY")
        os.environ["DISPLAY"] = self._display
        try:
            rec.start(nombre)
        finally:
            if anterior is None:
                os.environ.pop("DISPLAY", None)
            else:
                os.environ["DISPLAY"] = anterior
        self._t0 = time.monotonic()
        self._marcas_path = rec.RAIZ / f"{nombre}.marcas.json"

    def grabar_detener(self) -> None:
        if self._grab_nombre:
            rec.stop(self._grab_nombre)
        self._t0 = None

    def cerrar(self) -> None:
        try:
            self._browser.close()
        except Exception:
            pass
        try:
            self._pw.stop()
        except Exception:
            pass
        try:
            self._proc.terminate()
            self._proc.wait(timeout=5)
        except Exception:
            pass


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "login":
        login(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
