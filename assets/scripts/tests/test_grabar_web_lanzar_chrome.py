"""_lanzar_chrome / login(): arman el entorno para que Chrome abra en Xephyr bajo
Wayland (forzar DISPLAY y limpiar WAYLAND_DISPLAY, igual que entorno.sh chrome:
references/grabacion.md) y lanzan el proceso. No se levanta ningún Chrome real
acá: se inyecta un subprocess.Popen falso (mismo patrón que test_rec_corte.py).

login() no toca ningún formulario: abre el navegador visible con el perfil
persistente y espera a que el humano cierre la ventana (proc.wait()). Nunca
tipea ni lee una contraseña.
"""
import grabar_web


class _ProcesoFalso:
    def __init__(self):
        self.esperado = False

    def wait(self):
        self.esperado = True


def test_lanzar_chrome_limpia_wayland_display_y_fija_display(monkeypatch):
    capturado = {}

    def popen_falso(argv, env=None, **kw):
        capturado["argv"] = argv
        capturado["env"] = env
        return _ProcesoFalso()

    monkeypatch.setattr(grabar_web.subprocess, "Popen", popen_falso)
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setenv("DISPLAY", ":0")

    grabar_web._lanzar_chrome("docente-n4", "https://tutor.example/x", puerto=9333, display=":2")

    assert "WAYLAND_DISPLAY" not in capturado["env"]
    assert capturado["env"]["DISPLAY"] == ":2"
    assert "--ozone-platform=x11" in capturado["argv"]


def test_lanzar_chrome_crea_el_directorio_del_perfil(tmp_path, monkeypatch):
    monkeypatch.setattr(grabar_web, "PERFILES_DIR", tmp_path / "perfiles")
    monkeypatch.setattr(grabar_web.subprocess, "Popen", lambda *a, **kw: _ProcesoFalso())

    grabar_web._lanzar_chrome("docente-n4", "https://tutor.example/x", puerto=9333, display=":2")

    assert (tmp_path / "perfiles" / "docente-n4").is_dir()


def test_login_espera_a_que_el_humano_cierre_la_ventana(monkeypatch):
    proceso = _ProcesoFalso()
    monkeypatch.setattr(grabar_web, "_lanzar_chrome", lambda *a, **kw: proceso)

    grabar_web.login("docente-n4", "https://tutor.example/x")

    assert proceso.esperado is True
