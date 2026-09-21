#!/usr/bin/env python3
"""Tipea en la app de OpenCode (Electron) vía Chrome DevTools Protocol.

xdotool NO sirve con Electron: Chromium filtra los eventos sintéticos de XTEST.
CDP entra por dentro de la app, así que no depende del foco de ninguna ventana.

Requiere lanzar la app con --remote-debugging-port=9222

uso: ty-cdp.py 'texto' [--enter] [--limpiar] [--delay MS] [--puerto N]
"""
import json
import sys
import time
import urllib.request

from websocket import create_connection


def pagina_ws(puerto: int) -> str:
    data = json.load(urllib.request.urlopen(f"http://127.0.0.1:{puerto}/json", timeout=10))
    for t in data:
        if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
            return t["webSocketDebuggerUrl"]
    raise RuntimeError("no encontré la página de la app; ¿está con --remote-debugging-port?")


class Cdp:
    def __init__(self, url: str):
        self.ws = create_connection(url, timeout=20)
        self.n = 0

    def cmd(self, metodo: str, **params) -> dict:
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": metodo, "params": params}))
        while True:
            r = json.loads(self.ws.recv())
            if r.get("id") == self.n:
                return r

    def tecla(self, key: str, code: str, vk: int) -> None:
        for t in ("keyDown", "keyUp"):
            self.cmd("Input.dispatchKeyEvent", type=t, key=key, code=code,
                     windowsVirtualKeyCode=vk, nativeVirtualKeyCode=vk)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    texto = args[0] if args else ""
    enter = "--enter" in sys.argv
    limpiar = "--limpiar" in sys.argv
    delay = 35
    puerto = 9222
    for i, a in enumerate(sys.argv):
        if a == "--delay": delay = int(sys.argv[i + 1])
        if a == "--puerto": puerto = int(sys.argv[i + 1])

    c = Cdp(pagina_ws(puerto))
    c.cmd("Runtime.enable")

    # el input del prompt: lo enfocamos desde adentro, sin depender de la ventana
    c.cmd("Runtime.evaluate", expression="""
        (() => {
          const cands = [...document.querySelectorAll('textarea, [contenteditable="true"], input[type="text"]')]
            .filter(e => e.offsetParent !== null);
          const el = cands[cands.length - 1];
          if (el) { el.focus(); return el.tagName + ':' + (el.className || '').slice(0, 40); }
          return 'NO-ENCONTRADO';
        })()
    """)

    if limpiar:
        for _ in range(400):
            c.tecla("Backspace", "Backspace", 8)

    for ch in texto:
        c.cmd("Input.insertText", text=ch)
        time.sleep(delay / 1000)

    if enter:
        time.sleep(0.5)
        c.tecla("Enter", "Enter", 13)
    print(f"  tipeado ({len(texto)} chars){' + enter' if enter else ''}")


if __name__ == "__main__":
    main()
