# HU-03 · «Clase con personaje» en la skill de shorts (motor Remotion)

Pedida por Juani el 16/11/2026, después de la prueba e43 (HU-02 del canal, commit `3151f31`). La skill
tiene que generar sola una clase vertical: un personaje que presenta frente a una pizarra, la boca con
la voz, poses, zooms, diagrama de flujo, código real, música y efectos. El guion elige personaje,
vestuario y fondo; lo que falta lo dibuja el generador de imágenes (Codex) **una vez** y queda en una
biblioteca para reusar. Motor: Remotion (elegido por Juani: «si vamos con remotion»). El constructor
no modifica esta carpeta.

## Interfaz

```
TUT_ROOT=<serie> TUT_REPARTO=<biblioteca> [TUT_GENERADOR=<comando>] \
  uv run ... python assets/scripts/clase.py reparto <guion.json>
  uv run ... python assets/scripts/clase.py props   <guion.json> -o <props.json>
  uv run ... python assets/scripts/clase.py render  <guion.json> -o <video.mp4>
```

- `reparto`: resuelve personaje, vestuario y fondo contra la biblioteca; genera lo que falta.
- `props`: genera la voz y deja los datos resueltos que usa Remotion (para inspeccionar).
- `render`: hace `reparto` y `props` si hace falta, y renderiza el mp4.
- Las rutas relativas del guion (`codigo`) se resuelven contra `TUT_ROOT`.
- `clase.py` declara sus dependencias con metadatos PEP 723 (se corre con `uv run clase.py`).
- `reparto` imprime lo que resolvió (personaje, vestuario y fondo por nombre) y lo que generó.
- `props.json` tiene, como mínimo: `duracion` (s), `voz` (wav de la narración completa),
  `segmentos[i].pose`, `codigo` (`{nombre: texto del archivo}`), `consola` (`{nombre: [líneas]}`),
  `boca` (`[[inicio, fin], ...]` en s, cuándo está abierta), `musica` (ruta) y `sfx` (lista).

### Biblioteca (`TUT_REPARTO`, por defecto `~/.local/share/tutorial-video/reparto/`)

Las imágenes pesan: viven fuera del repo de la skill. `catalogo.json`, con rutas relativas a la biblioteca:

```json
{"personajes": {"profe": {"referencia": "personajes/profe/referencia.png", "descripcion": "...",
    "vestuarios": {"base": {"poses": {"parado": {"cerrada": "personajes/profe/base/parado-cerrada.png",
        "abierta": "personajes/profe/base/parado-abierta.png", "boca": [x, y, w, h], "prompt": "..."}}}}}},
 "fondos": {"aula-pizarra": {"archivo": "fondos/aula-pizarra.png", "prompt": "..."}}}
```

### Generador (`TUT_GENERADOR`, por defecto un envoltorio de `codex exec` con `image_generation`)

`<comando> --prompt <texto> --salida <png> [--referencia <png>]...`: sale con 0 y deja el PNG.
Para la versión con la boca abierta, el prompt dice «boca abierta».

### Guion (`"formato": "clase"`)

```json
{"formato": "clase", "personaje": "profe", "vestuario": "base", "fondo": "aula-pizarra",
 "voz_id": "e09c9a988aac403e8a6317ad188e347d", "velocidad": 1.15,
 "codigo": {"edad": "codigo/edad.py"},
 "segmentos": [{"texto": "...", "pose": "pensar", "camara": "profe|normal|pizarra",
                "escena": {"tipo": "pizarra|diagrama|codigo|terminal", ...}}]}
```

Lo nuevo se pide con descripción: `"vestuario": {"nombre": "invierno", "descripcion": "..."}`,
`"fondo": {"nombre": "laboratorio", "descripcion": "..."}`, `"personaje": {"id": "profa", "descripcion": "..."}`
(primero su referencia, después las poses con esa referencia).

## Criterios

- **C01**: `render` deja un mp4 1080×1920 a 30 fps, de la duración de la voz (± 1 s).
- **C02 (reparto)**: lo existente se reusa sin llamar al generador; un vestuario nuevo se genera con la
  referencia del personaje (dos imágenes por pose usada: cerrada y abierta), queda transparente, con su
  `boca` y su prompt en el catálogo; un fondo nuevo y un personaje nuevo, igual; la segunda corrida no
  genera nada.
- **C03**: el código que se muestra es el archivo real y la terminal es su salida real.
- **C04**: la pose de cada segmento es la del guion; la boca se abre sólo mientras suena la voz.
- **C05**: ritmo: al menos un corte cada 8 s y ningún tramo de más de 2 s sin cambio fuera de los subtítulos.
- **C06**: -16 LUFS ± 1, pico ≤ -1,5 dBTP; música y al menos 3 efectos.
- **C07 (humano)**: Juani mira un video de condicionales con el profe con otra ropa o en otro fondo,
  hecho sólo con el guion, y lo juzga al nivel del e43.

## Negativos

- **N01**: la suite existente de la skill sigue en verde (no cambia ningún default).
- **N02**: si el generador falla o no existe, `reparto` sale con error nombrando lo que falta, sin tocar
  el catálogo ni dejar archivos a medias. Nunca un reemplazo inventado.
- **N03**: no se tocan los cambios sin commitear de `feat/marcas-sobre-pantalla` (el otro árbol de la skill).
- **N04**: un guion que pide una pose que el personaje no tiene y sin descripción para generarla falla con
  un mensaje claro, sin renderizar.

## Cierres

- **K01**: `references/clase.md` (guía del formato, con las lecciones del e43) y su entrada en `SKILL.md`.
- **K02**: Obsidian y `HISTORIAS.md` del proyecto (orquestador).
