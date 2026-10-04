"""Transiciones entre tramos (S6 del Hito 2, docs/explicador/HITO2.md)."""
import sys
from pathlib import Path

import encoder

TIPOS = ("corte", "fundido", "barrido")


class TransicionError(ValueError):
    """Tipo de transición desconocido o valor de "transicion" con una forma inválida."""


def normalizar(valor):
    """Valor crudo de la clave "transicion" (arriba del guion o en un segmento) ->
    dict{"tipo", "duracion"?} | None.

    None/False (ausente o apagada): None, hereda el default de arriba o cae en "corte".
    Un string es taquigrafía de {"tipo": string}.
    """
    if valor is None or valor is False:
        return None
    if isinstance(valor, str):
        return {"tipo": valor}
    if isinstance(valor, dict):
        return dict(valor)
    raise TransicionError(f"'transicion' tiene que ser un objeto, texto o false, no {valor!r}")


def validar_tipo(tipo: str) -> None:
    """R-6.7: tipo desconocido, nombrando los válidos."""
    if tipo not in TIPOS:
        raise TransicionError(f"tipo de transición desconocido {tipo!r} (válidos: {', '.join(TIPOS)})")


def resolver(seg: dict, default: dict | None) -> dict:
    """Transición EN LA ENTRADA de `seg`: lo que declara el propio segmento, o el
    default de arriba, o "corte" si no hay ninguno de los dos (formato del guion,
    HITO2.md: "arriba, default para todos los cambios; en segmento, transición de
    entrada")."""
    propia = normalizar(seg.get("transicion"))
    resuelta = propia if propia is not None else (default or {"tipo": "corte"})
    validar_tipo(resuelta["tipo"])
    return resuelta


def duracion_de(transicion: dict, brand: dict) -> float:
    """R-6.4: la que pide el guion, o si no `brand.movimiento.entrada` (la misma
    noción de "cuánto tarda en entrar algo" que usan las escenas, `base.js`)."""
    pedida = transicion.get("duracion")
    if pedida is not None:
        return float(pedida)
    return float(brand.get("movimiento", {}).get("entrada", 0.7))


def duracion_efectiva(duracion: float, slot_saliente: float, slot_entrante: float, i: int) -> float:
    """R-6.6: si el slot más corto de los dos lados no entra 3 veces en `duracion`,
    se acorta a slot/3, avisando (nunca se acorta en silencio)."""
    minimo = min(slot_saliente, slot_entrante)
    if minimo < 3 * duracion:
        nueva = minimo / 3
        print(f"AVISO: la transición de entrada del segmento {i:02d} pide {duracion:.2f}s pero "
              f"el slot más corto de los dos lados da {minimo:.2f}s; se acorta a {nueva:.2f}s",
              file=sys.stderr)
        return nueva
    return duracion


def validar(g: dict) -> None:
    """R-6.7: aborta (TransicionError) ANTES de generar nada si algún tipo de
    transición del guion (el default de arriba o el de cualquier segmento) es
    desconocido."""
    default = normalizar(g.get("transicion"))
    if default is not None:
        validar_tipo(default["tipo"])
    for seg in g["segmentos"]:
        propia = normalizar(seg.get("transicion"))
        if propia is not None:
            validar_tipo(propia["tipo"])


def avisar_si_tapa_cue(i: int, spec_entrante: dict | None, mitad: float) -> None:
    """R-6.5: si la primera cue de la escena ENTRANTE cae dentro de la ventana de
    la transición (sus primeros `mitad` segundos), avisa (no aborta: la escena
    sigue siendo válida, sólo que su primer elemento nace tapado)."""
    if spec_entrante is None:
        return
    import escena  # lazy: sólo entra acá cuando el lado entrante es una escena
    cues = escena._con_cue(spec_entrante, [])
    if not cues:
        return
    primera = min(e["t"] for e in cues)
    if primera < mitad:
        print(f"AVISO: la transición de entrada del segmento {i:02d} dura {mitad * 2:.2f}s "
              f"y la primera cue de la escena entra en t={primera:.2f}s, dentro de la transición",
              file=sys.stderr)


def color_de(tipo: str, brand: dict) -> str:
    """R-6.3: el color sale del brand. Barrido usa el acento (lo que se destaca);
    fundido usa el fondo (una pantalla "en blanco" entre dos tramos, no un flash
    de acento en cada corte)."""
    colores = brand.get("colores", {})
    hexcolor = colores["acento"] if tipo == "barrido" else colores.get("fondo", "#000000")
    return "0x" + hexcolor.lstrip("#").upper()


def ease_out_cubico(p: float) -> float:
    """1-(1-p)^3: la misma curva de `base.js` (función `salida`) para la entrada de
    los elementos de una escena (R-6.4: "comparte forma con las escenas")."""
    p = min(max(p, 0.0), 1.0)
    return 1 - (1 - p) ** 3


def anchos_barrido(fase: str, t0: float, mitad: float, ancho: int = 1920, fps: int = 30) -> list[tuple[float, int]]:
    """[(t_del_cuadro, ancho_del_drawbox_en_px)] para cada cuadro de la ventana de la
    transición: en la mitad SALIENTE la franja del acento crece desde el borde
    izquierdo (0px en t0) hasta cubrir toda la pantalla (en t0+mitad, que coincide
    con el corte); en la mitad ENTRANTE arranca cubriendo del todo (en t=0) y se
    achica hasta desaparecer (en t=mitad).

    DISCRETO y no una expresión ffmpeg con `t`: medido con ffmpeg 6.1.1, `drawbox`
    evalúa `w`/`x` UNA SOLA VEZ (no por cuadro) aunque la expresión use `t` sin
    error -lo probé con `fade`, que sí es dinámico por cuadro, y con `drawbox`, que
    no lo es-, así que una expresión continua queda congelada en el primer valor.
    Por eso `aplicar_barrido` maneja cada cuadro con un comando de `sendcmd` armado
    desde esta lista. Nunca da 0 exacto: `drawbox` trata `w=0` como "ancho
    completo" (no "nada"; medido mandando w='0' por `sendcmd`: cubría toda la
    pantalla igual), así que "sin barrido" es 1px (R-6.1: a 1920 de ancho, bien
    por debajo del 1% que mide R-6.4).
    """
    n = round(mitad * fps)
    salida = []
    for i in range(n + 1):
        if fase == "saliente":
            t = t0 + i / fps
            p = (t - t0) / mitad
        else:
            t = i / fps
            p = t / mitad
        cobertura = ease_out_cubico(p) if fase == "saliente" else 1 - ease_out_cubico(p)
        w = max(1, round(ancho * cobertura))
        salida.append((t, w))
    return salida


def comandos_barrido(anchos: list[tuple[float, int]], filtro: str = "t6") -> str:
    """Script de `sendcmd` (un `w 'ANCHO'` por cuadro) para el filtro `drawbox@filtro`."""
    return "".join(f"{t:.6f} drawbox@{filtro} w '{w}';\n" for t, w in anchos)


def vf_fundido(fase: str, t0: float, mitad: float, color: str) -> str:
    """"fundido" (R-6.3): fundido A UN COLOR del brand (el fondo), no cross-dissolve:
    cada tramo vive en su propio seg/NN.mp4 (concat -c copy, hallazgo 2 de HITO2.md) y
    no tiene acceso a los píxeles del otro lado del corte. Usa el filtro nativo `fade`
    de ffmpeg (determinista, sin decodificar el tramo vecino)."""
    tipo = "out" if fase == "saliente" else "in"
    return f"fade=t={tipo}:st={t0:.6f}:d={mitad:.6f}:color={color}"


def _run(cmd: list[str]) -> None:
    """Corre `cmd` pasando por el vigía anti-cuelgue de `editar.run()` (mismo patrón
    que `musica._run`): import perezoso, nunca al tope del archivo. `editar.py` hace
    `import transiciones`; un `import editar` acá arriba cerraría un ciclo mal
    resuelto según quién se importe primero."""
    import editar
    editar.run(cmd)


def _reencodar(entrada: Path, vf: str, fps: int) -> None:
    """Mismo patrón que `escena.render`: se escribe a un .parcial.mp4 y se renombra
    al final, para que un fallo a mitad no deje un .mp4 corto que parece válido."""
    parcial = entrada.with_name(entrada.stem + ".parcial" + entrada.suffix)
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(entrada),
          "-vf", encoder.vf(vf), "-r", str(fps), *encoder.cv_args(crf=20, preset="veryfast"), str(parcial)])
    parcial.replace(entrada)


def aplicar(entrada, vf: str, fps: int = 30) -> None:
    """Reencodea `entrada` (un seg/NN.mp4 ya armado por `build_segment`) con el
    filtro `vf` ya armado (p.ej. `vf_fundido`), IN PLACE: no cambia duración ni
    cantidad de cuadros (G1/G2), sólo pinta encima en la ventana que `vf` ya
    acota."""
    _reencodar(Path(entrada), vf, fps)


def aplicar_todas(seg_dir, g: dict, tramos: list, brand: dict, ancho: int = 1920, fps: int = 30) -> None:
    """Recorre los cambios de tramo (1..N-1) de `g["segmentos"]` y pinta la
    transición DENTRO de cada `seg/NN.mp4` ya armado por `build_segment` (sin
    mover ningún slot: G1/G2, hallazgo 2 de HITO2.md). `tramos` es la lista
    `(seg, slot, palabras)` que devuelve `editar.preparar()`.

    Q4 (decisión de Juani): sólo hay transición si al menos uno de los dos lados
    es una escena; pantalla->pantalla queda en corte seco sin importar lo que
    diga el guion. El primer segmento no tiene tramo anterior: si declara su
    propia "transicion" se avisa y se ignora."""
    seg_dir = Path(seg_dir)
    segmentos = g["segmentos"]
    default = normalizar(g.get("transicion"))
    if segmentos[0].get("transicion") is not None:
        print("AVISO: el segmento 00 declara 'transicion' pero es el primero del video; "
              "se ignora (no hay tramo anterior)", file=sys.stderr)
    for i in range(1, len(segmentos)):
        saliente, entrante = segmentos[i - 1], segmentos[i]
        transicion = resolver(entrante, default)
        if transicion["tipo"] == "corte":
            continue
        if not (bool(saliente.get("escena")) or bool(entrante.get("escena"))):
            continue  # Q4: pantalla->pantalla, corte seco sin importar el guion
        slot_saliente, slot_entrante = tramos[i - 1][1], tramos[i][1]
        duracion = duracion_efectiva(duracion_de(transicion, brand), slot_saliente, slot_entrante, i)
        mitad = duracion / 2
        color = color_de(transicion["tipo"], brand)
        if entrante.get("escena"):
            import editar
            spec = editar.spec_de_escena(entrante, slot_entrante, tramos[i][2] or [])
            avisar_si_tapa_cue(i, spec, mitad)
        archivo_saliente, archivo_entrante = seg_dir / f"{i - 1:02d}.mp4", seg_dir / f"{i:02d}.mp4"
        if transicion["tipo"] == "barrido":
            aplicar_barrido(archivo_saliente, "saliente", slot_saliente - mitad, mitad, color, ancho=ancho, fps=fps)
            aplicar_barrido(archivo_entrante, "entrante", 0.0, mitad, color, ancho=ancho, fps=fps)
        else:  # fundido
            aplicar(archivo_saliente, vf_fundido("saliente", slot_saliente - mitad, mitad, color), fps=fps)
            aplicar(archivo_entrante, vf_fundido("entrante", 0.0, mitad, color), fps=fps)


def aplicar_barrido(entrada, fase: str, t0: float, mitad: float, color: str,
                     ancho: int = 1920, fps: int = 30) -> None:
    """"barrido" (R-6.1/R-6.3/R-6.4): ver `anchos_barrido`. A diferencia de
    `aplicar` (una expresión de ffmpeg alcanza), necesita escribir un script de
    `sendcmd` temporal al lado de `entrada` (un comando `w` por cuadro de la
    ventana): se borra siempre, incluso si `ffmpeg` falla."""
    entrada = Path(entrada)
    anchos = anchos_barrido(fase, t0, mitad, ancho=ancho, fps=fps)
    cmds = entrada.with_name(entrada.stem + ".sendcmd.txt")
    cmds.write_text(comandos_barrido(anchos))
    try:
        vf = f"sendcmd=f={cmds},drawbox@t6=x=0:y=0:w=1:h=ih:color={color}:thickness=fill"
        _reencodar(entrada, vf, fps)
    finally:
        cmds.unlink(missing_ok=True)
