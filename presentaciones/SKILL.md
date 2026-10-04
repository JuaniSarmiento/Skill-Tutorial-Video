---
name: presentaciones-tupad
description: >
  Genera presentaciones con el estilo institucional de la cátedra UTN TUPaD (Tecnicatura Universitaria en
  Programación a Distancia): diapositivas .pptx editables y su .pdf, a partir de una especificación YAML con
  diapositivas tipadas (portada, viñetas, tarjetas, numerados, código, código + salida, imagen, tabla, cita,
  síntesis). El código se lee de los .py reales, las salidas se obtienen ejecutándolos y los diagramas de
  recursión (pila de llamadas, árbol) se dibujan desde una traza real. Incluye exportación con LibreOffice y
  revisión diapositiva por diapositiva con hoja de contactos.
  Usala SIEMPRE que pidan armar, rehacer o corregir diapositivas o una presentación para una clase, un video,
  una microteaching o un encuentro de una materia de TUPaD/UTN, aunque no nombren la skill: "armá diapositivas
  para el video de la unidad 5", "hacé una presentación para la clase de listas", "slides estilo UTN",
  "slides estilo TUPaD", "un deck para la microteaching", "pptx para la cátedra", "pasá este guion a
  diapositivas", "necesito las diapos con el código y la salida". NO la uses para revisar apuntes en Word o PDF
  (revision-apuntes-unidad), ni para corregir entregas de alumnos.
---

# Presentaciones TUPaD

Arma presentaciones 16:9 con la identidad visual de la cátedra (azul institucional, tarjetas con barra
lateral, código sobre fondo gris claro, pie con logo UTN y numeración) desde una especificación. El método es
el que se usó para las diapositivas de los videos de la Unidad 10 de Programación I: **nada que se pueda
ejecutar se tipea a mano**, y **nada se da por terminado sin mirar cada diapositiva renderizada**.

Todo lo de abajo usa rutas relativas a la carpeta de esta skill (`<skill>`).

## Antes de empezar

1. Corré `python <skill>/scripts/preflight.py`. Si falta algo obligatorio, mostrale al usuario exactamente qué
   instalar (el script lo dice) y no sigas. Las dependencias de Python van **en un venv**, nunca globales:
   `python3 -m venv .venv && .venv/bin/pip install -r <skill>/scripts/requirements.txt`.
   Por qué las fuentes son obligatorias: sin Inter o DejaVu Sans Mono, LibreOffice las sustituye por otras
   con otras métricas y la diagramación revisada deja de ser la que se ve.
2. Pedí lo que falte para la portada: **materia, unidad, tema y revisor** (y actividad si aplica). Sin esos
   datos `build.py` se niega a generar: una presentación de la cátedra sin revisor no se puede publicar.
3. Juntá el material fuente: guion, apunte, consigna y la carpeta con los `.py`. Si el contenido lo escribe
   la IA, el guion o el apunte mandan; no inventes temas que no estén ahí.

## Flujo

### 1. Escribir la especificación
Un `presentacion.yaml` junto a una carpeta `codigo/` con los programas. Formato completo, con un ejemplo de
cada tipo de diapositiva, en `references/especificacion.md` — **leelo antes de escribir la primera spec**.
Ejemplos que funcionan: `examples/video1-recursividad/` (deck completo de 8 diapositivas) y
`examples/listas-python/` (3 diapositivas).

Esqueleto:
```yaml
nombre: diapositivas
titulo: Listas en Python
pie: "Programación I · Unidad 5: Listas"
revisor: Nombre Apellido
codigo: codigo
diapositivas:
  - tipo: portada
    materia: Programación I
    unidad: "Unidad 5: Listas"
    titulo: Listas en Python
    descripcion: [Qué es una lista y cómo se recorre.]
  - tipo: codigo_salida
    titulo: Crear y recorrer
    codigo: listas.py          # se lee del archivo
    salida: listas.py          # se EJECUTA y se muestra lo que imprime
  - tipo: sintesis
    botones: [append(), len(), for]
    texto: [Próximo video: slicing.]
```

Criterios de contenido (detalle en `references/estilo.md`):
- **Una idea por diapositiva.** Si una tarjeta pasa de tres oraciones, partila o pasá a otra diapositiva.
- Material escrito de la cátedra: **tercera persona o impersonal** ("se recorre", "la función devuelve"),
  presente atemporal. Un guion de video puede hablarle al alumno; las diapositivas, no.
- El orden lo da el guion o el apunte. Cerrá con una `sintesis` que retome los conceptos clave.

### 2. Generar
```bash
python <skill>/scripts/build.py presentacion.yaml -o salida --pdf --hoja
```
Deja en `salida/`: `<nombre>.pptx` (editable), `<nombre>.pdf`, `<nombre>_hoja.png` (hoja de contactos),
`<nombre>_salidas.txt` (bitácora de lo que se ejecutó, con versión de Python y hora) e `img/` con los
diagramas. Si `build.py` imprime `AVISO:`, tomalo como un desborde probable y miralo primero.

### 3. Exportar a PDF
`--pdf` usa LibreOffice headless (`soffice --headless --convert-to pdf`). Si falla sin mensaje, casi siempre
hay otra instancia de LibreOffice abierta: cerrala y repetí. El PDF es lo que se revisa, porque es lo único
que muestra cómo se ve de verdad.

### 4. Revisar CADA diapositiva por imagen — obligatorio
python-pptx no sabe cuánto ocupa un texto: **ningún script puede asegurar que nada desborde**. El juez es el
render. Con `Read` mirá la hoja de contactos y después, para cada diapositiva con texto denso, código o
tablas, la imagen grande:
```bash
python <skill>/scripts/revisar.py salida/<nombre>.pdf --diapo 4          # una, a 110 dpi
python <skill>/scripts/revisar.py salida/<nombre>.pdf --comparar viejo.pdf  # lado a lado con otra versión
```
Buscá, diapositiva por diapositiva: texto que se sale de su tarjeta o queda cortado; código que no entra (el
script achica la letra, pero bajo 10 pt ya no se lee en un video); superposiciones con el pie; tablas que se
meten en el pie; tarjetas casi vacías; operadores raros en el código (`==` convertido en un símbolo: ver
lecciones). **Corregí la spec y regenerá hasta que no quede ninguno.** No digas "listo" sin haber mirado
todas; decí cuáles miraste.

Arreglos típicos: bajar `tamano` de esa tarjeta o bloque; partir la diapositiva en dos; cambiar el `ancho`
de las columnas de una `fila`; mostrar un fragmento del archivo (`bloque`, `lineas`, `desde`) en vez del
archivo entero; abreviar una salida larga con `primeras`/`ultimas`.

### 5. Código: ejecutarlo y mostrar la salida REAL
- `salida:` ejecuta el `.py` en cada build desde una carpeta temporal neutra y muestra lo que imprimió.
  Si el programa lee con `input()`, poné `entrada: "3\n4\n"` y la salida muestra lo tipeado, como en la
  terminal. Para una salida muy larga: `primeras: 5, ultimas: 3` deja líneas reales y marca cuántas omitió.
- `imagen: {diagrama: pila|arbol, archivo, llamada}` traza la función de verdad (`scripts/diagramas.py`) y
  dibuja la pila de llamadas o el árbol de recursión desde ese registro.
- Para probar un programa suelto: `python <skill>/scripts/ejecutar_codigo.py archivo.py --entrada "..."`.
- Si un programa falla y **no** debía fallar, el problema está en el código, no en la diapositiva: avisale
  al usuario antes de seguir.

## Reglas, con su porqué

| Regla | Por qué |
|---|---|
| El código se lee de archivos `.py`; nunca se tipea en la spec | El texto tipeado se desfasa del programa la primera vez que alguien corrige el `.py`, y nadie lo nota hasta que un alumno lo ejecuta. `codigo: {texto: ...}` existe sólo para pseudocódigo y `build.py` avisa cuando se usa. |
| Las salidas y los diagramas salen de la ejecución real | Una salida "que debería dar" es una afirmación sin verificar. En la U10, la traza real mostró 999 números antes del `RecursionError`, no "infinitos". |
| Tipografía de código: **DejaVu Sans Mono**, nunca JetBrains Mono ni Fira Code | Con fuentes con ligaduras, LibreOffice dibuja `==`, `<=`, `!=` y `->` como un único símbolo que no existe en el teclado. Para alguien que está aprendiendo, es otro operador. |
| Ninguna ruta personal en pantalla | Un traceback muestra la ruta completa del archivo (`/home/<persona>/...`). `ejecutar_codigo.py` corre desde una carpeta neutra y reemplaza las rutas; si igual aparece una, no publiques. |
| Portada con materia, unidad, tema y revisor | Es el dato mínimo que pide la cátedra para todo material publicado; `build.py` no genera sin él. |
| Tercera persona o impersonal en el material escrito | Es el estilo de los apuntes de la cátedra; las diapositivas acompañan a esos apuntes. |
| Sin capturas inventadas de sitios, campus o programas | Una captura "recreada" se lee como real. Si hace falta una captura, la saca el usuario. |
| Sin imágenes generadas con texto adentro | Los generadores de imágenes deforman las letras; además el texto en una imagen no se puede corregir. Texto va como texto. |
| Revisar por imagen, siempre | Los desbordes, cortes y superposiciones sólo se ven en el render. |

## Retocar a mano después

El `.pptx` es editable en PowerPoint o Impress. Pero si después se regenera desde la spec, **los retoques
manuales se pierden**: preferí cambiar la spec. Si el usuario edita a mano, que lo sepa. PowerPoint y
LibreOffice no diagraman igual (ver `references/lecciones.md`): si la presentación se va a proyectar desde
PowerPoint, que la mire ahí antes de darla por buena.

## Usar la librería directamente

Para algo que la spec no cubre, `scripts/deck.py` se puede usar desde Python: `Deck.bloques(titulo,
[bloques])` arma cualquier diagramación con el motor de bloques (`fila`, `tarjeta`, `aviso`, `codigo`,
`salida`, `texto`, `tabla`, `imagen`), y `Deck.portada`, `Deck.seccion`, `Deck.sintesis` las oscuras. La paleta
y las tipografías son constantes del módulo. Lo mismo está disponible en la spec con `tipo: libre`.

## Qué leer y cuándo

| Archivo | Cuándo |
|---|---|
| `references/especificacion.md` | Siempre, antes de escribir o modificar una spec |
| `references/estilo.md` | Al decidir diagramación, colores o cuánto texto entra |
| `references/lecciones.md` | Ante cualquier resultado raro en el PDF, y antes de entregar |
| `examples/*/presentacion.yaml` | Como punto de partida; las `*_hoja.png` muestran el resultado esperado |
| `scripts/` | `preflight`, `build`, `ejecutar_codigo`, `diagramas`, `revisar`, `deck` (cada uno tiene `--help`) |

## Al entregar

Decile al usuario: dónde quedaron el `.pptx` y el `.pdf`; qué diapositivas miraste por imagen y qué
corregiste; qué salidas se ejecutaron (la bitácora `_salidas.txt`); qué quedó para que mire él (siempre:
la presentación completa, porque una revisión de la IA no reemplaza la de una persona) y, si hubo
`AVISO:` que no pudiste resolver, cuáles.
