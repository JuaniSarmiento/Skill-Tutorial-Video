# Lecciones aprendidas (gotchas reales)

Salieron de armar las diapositivas de los videos y la microteaching de la Unidad 10 (Recursividad) de
Programación I. Cada una costó una vuelta de corrección.

## Las ligaduras cambian los operadores

JetBrains Mono es la monoespaciada de la plantilla de apuntes. En las diapositivas exportadas con
LibreOffice, `==` y `<=` se dibujaban como un único símbolo, porque LibreOffice aplica las ligaduras de la
fuente.
**Solución**: DejaVu Sans Mono, que no tiene ligaduras. No cambiarla por otra "más linda" sin renderizar
un `==`, `!=`, `<=`, `>=`, `->` y `//` y mirarlos por imagen.

## Los tracebacks muestran la carpeta personal

Al capturar la salida de `cuenta_regresiva_sin_caso_base.py` desde la carpeta del proyecto, el traceback
traía `File "/home/<usuario>/Proyectos/.../codigo/cuenta_regresiva_sin_caso_base.py"`. Eso no puede ir a
una diapositiva pública (dice el nombre de usuario y la estructura de carpetas). **Solución**:
`ejecutar_codigo.py` copia el programa a una carpeta temporal, lo ejecuta desde ahí y deja sólo el nombre
del archivo; además reemplaza cualquier `/home/<algo>` o `C:\Users\<algo>` que quede. Si copiás una salida
de otro lado (un `salidas.txt` viejo), revisala: puede traer la ruta.

## La salida "esperada" no es la salida

"Sin caso base, la cuenta sigue para siempre" es lo que uno escribiría sin ejecutar. La ejecución real de
`cuenta_regresiva_sin_caso_base.py` imprime 999 números (de 3 a −995) y corta con `RecursionError`, porque
el límite por defecto es 1000. El dato real es más preciso y es el que el alumno va a ver. Por eso `salida:` ejecuta siempre, y la
bitácora `_salidas.txt` deja la versión de Python y la hora: una salida de otra versión puede cambiar
(Python 3.11+ agrega las marcas `^^^^` bajo la expresión que falló, por ejemplo).

## Con stdin redirigido no se ve lo que se tipeó

Un programa con `input("a: ")` alimentado por una tubería imprime `a: b: suma: 7`, todo en una línea,
porque el valor tipeado no hace eco. Eso no es lo que ve el alumno en su terminal. `ejecutar_codigo.py`
hace eco de cada valor leído cuando hay `entrada:`, sin tocar el programa.

## Fuentes faltantes mueven la diagramación

Si Inter no está instalada, LibreOffice la sustituye por otra fuente con otras métricas: los cortes de
línea cambian y un título o una tarjeta que entraban pueden dejar de entrar. El `.pptx` es el mismo; el
render no.
Por eso `preflight.py` exige las dos fuentes, y la revisión se hace en la máquina donde se exporta. Si el
`.pptx` se abre en otra computadora sin Inter, avisar que puede verse distinto.

## LibreOffice y PowerPoint no diagraman igual

python-pptx escribe el archivo, pero no calcula cuánto ocupa el texto: lo hace cada programa al abrirlo.
PowerPoint y LibreOffice difieren en interlineado y en dónde cortan las líneas, en algunos casos por una
palabra. Los decks se revisaron en LibreOffice (es el que exporta el PDF). Si se van a proyectar desde
PowerPoint, mirarlos ahí también. No usar `autofit` de PowerPoint: LibreOffice lo ignora en parte y el
resultado difiere aún más.

## El texto desborda en silencio

python-pptx nunca da error si el texto no entra: la caja queda del mismo tamaño y el texto se sale por abajo,
encima de la tarjeta siguiente o del pie. `deck.py` estima alturas y avisa cuando el contenido pide más lugar
del que hay, pero es una estimación (ancho promedio de letra). **La única verificación real es mirar el
render.** Lo que más se desbordó: tarjetas con 4 o más oraciones, tablas con celdas largas, salidas de
consola con más de 15 líneas.

## Código que no entra a lo ancho

Una línea larga de código no se parte (el `word_wrap` la cortaría en cualquier lugar y cambiaría la
indentación). `deck.py` achica la letra del bloque hasta que la línea más larga entra. Con un traceback, la
línea `File "...", line 3, in cuenta_regresiva` baja la letra a 9 pt. Mejor: abreviar con
`primeras`/`ultimas` para que la línea larga no esté, o darle más ancho a la columna.

## Revisar siempre por imagen, todas

Los decks de la U10 se iteraron mirando el render: el alto del título de la portada, por ejemplo, tuvo que
pasar a calcularse según cuántas líneas ocupa, porque un título largo en dos líneas pisaba la descripción.
Ese tipo de problema no se ve en el código ni en el `.pptx` listado: sólo en el PDF. La hoja de contactos sirve para ver el conjunto; las diapositivas
con código o tablas se miran además en grande (`revisar.py --diapo N`).

## Imágenes claras sobre transparente

`assets/portada-marcos.png` y los logos blancos son blancos sobre transparente: sobre una diapositiva blanca
desaparecen. En diapositivas claras, ponerles `fondo: navy` (lo hace el tipo `numerados` con
`fondo_imagen`). El logo negro va en el pie de las claras; el blanco, en las oscuras.

## LibreOffice no convierte si ya hay una instancia abierta

`soffice --headless --convert-to pdf` puede terminar sin error y sin PDF si hay otro LibreOffice abierto
con el mismo perfil. `build.py` verifica que el PDF exista y, si no, lo dice; la solución suele ser cerrar
el otro.
