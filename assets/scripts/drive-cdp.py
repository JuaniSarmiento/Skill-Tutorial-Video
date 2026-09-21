#!/usr/bin/env python3
"""Vigila la app de OpenCode por CDP: aprueba permisos seguros y FRENA ante los riesgosos.

Equivalente de drive.sh para la app Electron. A diferencia de aquel, lee el texto COMPLETO
del diálogo (no truncado), así el filtro no puede fallar abierto por un comando que quedó
más allá del corte.

uso: drive-cdp.py [max_segundos=900]
"""
import json
import re
import sys
import time
import urllib.request

from websocket import create_connection

RIESGOSO = re.compile(
    r"rm\s+-[rf]|rm\s+--recursive|\bsudo\b|git\s+push|git\s+reset|git\s+-C\s+\S+\s+push|"
    r"curl[^|]*\|\s*(ba)?sh|chmod\s+(-R\s+)?777|mkfs|dd\s+if=|>\s*/dev/|"
    r"find\b[^\n]*-delete|\bmv\b[^\n]*(\.ssh|\.config|\.claude)|>>?\s*~?/?\.(bashrc|zshrc|profile)",
    re.I)


def conectar(puerto: int = 9222):
    data = json.load(urllib.request.urlopen(f"http://127.0.0.1:{puerto}/json", timeout=10))
    url = next(t["webSocketDebuggerUrl"] for t in data if t.get("type") == "page")
    return create_connection(url, timeout=25)


def evaluar(ws, n: int, expr: str):
    ws.send(json.dumps({"id": n, "method": "Runtime.evaluate",
                        "params": {"expression": expr, "returnByValue": True}}))
    while True:
        r = json.loads(ws.recv())
        if r.get("id") == n:
            return r.get("result", {}).get("result", {}).get("value")


LEER_DIALOGO = """
 (() => {
   const els = [...document.querySelectorAll('*')].filter(e =>
     e.offsetParent && /Permiso requerido|Permission required/i.test(e.innerText || '') );
   if (!els.length) return null;
   const caja = els[els.length - 1];
   return (caja.innerText || '').slice(0, 4000);
 })()
"""

APROBAR = """
 (() => {
   const b = [...document.querySelectorAll('button,[role="button"]')]
     .reverse().find(e => e.offsetParent && /^permitir siempre$/i.test((e.innerText||'').trim()));
   if (!b) return 'SIN-BOTON';
   b.click(); return 'APROBADO';
 })()
"""


def main() -> None:
    maximo = int(sys.argv[1]) if len(sys.argv) > 1 else 900
    ws = conectar()
    n = 0
    fin = time.time() + maximo
    aprobados = 0
    while time.time() < fin:
        n += 1
        texto = evaluar(ws, n, LEER_DIALOGO)
        if texto:
            if RIESGOSO.search(texto):
                print("PERMISO RIESGOSO, freno:")
                print("  " + texto.replace("\n", "\n  ")[:600])
                return
            n += 1
            r = evaluar(ws, n, APROBAR)
            if r == "APROBADO":
                aprobados += 1
                primera = next((l for l in texto.splitlines() if l.strip()
                                and "Permiso" not in l), "")[:70]
                print(f"  aprobado #{aprobados}: {primera}")
                time.sleep(4)
                continue
        time.sleep(5)
    print(f"TIMEOUT tras {maximo}s ({aprobados} permisos aprobados)")


if __name__ == "__main__":
    main()
