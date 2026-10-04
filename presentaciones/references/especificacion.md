# Formato de la especificación

YAML (o JSON con la misma estructura, si no hay PyYAML). Todas las rutas son **relativas al archivo de la
especificación**. Los programas se buscan primero en la carpeta `codigo` y después junto a la spec.

## Contenido

1. Claves generales
2. Marcado de texto
3. Tipos de diapositiva (un ejemplo de cada uno)
4. Bloques (para `tipo: libre` y para armar columnas)
5. Referencias a código, salidas y diagramas

## 1. Claves generales

```yaml
nombre: diapositivas          # nombre base de los archivos de salida (por defecto: el de la spec)
titulo: Listas en Python      # metadato del .pptx
pie: "Programación I · Unidad 5: Listas · Video 1"   # texto del pie de cada diapositiva
revisor: Nombre Apellido      # va a la portada y al autor del .pptx
autor: Nombre Apellido        # opcional; si falta, se usa revisor
codigo: codigo                # carpeta de los .py (relativa a la spec)
carpeta_salida: salida        # opcional; -o en la línea de comandos manda
numeracion: true              # true: "3 / 8"; false: sin número; o una lista de etiquetas propias
diapositivas: [...]
```

## 2. Marcado de texto

En cualquier texto (tarjetas, viñetas, tablas, notas):

| Escribís | Se ve |
|---|---|
| `**negrita**` | **negrita** |
| `` `len()` `` | `len()` en DejaVu Sans Mono, azul |
| `{naranja}texto{/}` | texto en naranja (navy, acento, naranja, verde, rojo, gris, texto, blanco, claro) |
| `{naranja}**`if n == 0:`**{/}` | código naranja en negrita |

Un texto puede ser un string (un párrafo) o una lista (un párrafo por elemento). Ojo: `**` siempre abre o
cierra negrita; para mostrar `x ** 2` ponelo entre backticks. En YAML, un texto que empieza con `` ` ``, `{`,
`*` o tiene `: ` va entre comillas.

## 3. Tipos de diapositiva

Todos menos `portada`, `seccion` y `sintesis` llevan `titulo` y aceptan `nota:` (texto gris al pie del
contenido) y `tamano:` (pt del texto de las tarjetas).

### portada
```yaml
- tipo: portada
  materia: Programación I                 # obligatorio
  unidad: "Unidad 10: Recursividad"       # obligatorio
  actividad: Actividad 1                  # opcional
  titulo: Introducción a la recursividad  # obligatorio (el tema)
  descripcion:                            # 1 a 3 párrafos cortos
    - Qué es una función recursiva y cómo la ejecuta Python.
  revisor: Nombre Apellido                # si falta, se usa el general; sin ninguno, no genera
  rol_revisor: Revisor de la unidad       # por defecto
  subtitulo: "..."                        # opcional: reemplaza "materia · unidad · actividad"
  decoracion: true                        # true = assets/portada-marcos.png; false = sin; o una ruta
```

### seccion
Separador oscuro entre partes.
```yaml
- tipo: seccion
  subtitulo: Parte 2
  titulo: Recursión e iteración
```

### viñetas
```yaml
- tipo: viñetas            # también: vinetas
  titulo: Para recordar
  items:
    - Una lista guarda varios valores en orden.
    - "`len()` devuelve la cantidad de elementos."
  nota: Siempre que se pida mostrar una lista, usar un bucle.   # recuadro naranja debajo
  imagen: img/esquema.png   # opcional: va a la derecha
  tamano: 22                # por defecto
```

### tarjetas
Plano (se reparte en `columnas`, máximo 3 por defecto) o por filas explícitas.
```yaml
- tipo: tarjetas
  titulo: ¿Qué es la recursividad?
  tamano: 18
  filas:
    - - titulo: Definición
        texto: Una función que se llama a sí misma.
    - - titulo: La idea
        texto: [Cada llamada resuelve una parte más chica., El conjunto llega a la solución.]
      - titulo: Cuidado
        acento: naranja
        texto: Sin caso base no termina.
# o bien:
#  columnas: 2
#  tarjetas: [{titulo: A, texto: ...}, {titulo: B, texto: ...}, ...]
```
Cada tarjeta acepta `acento` (color), `aviso: true` (fondo cálido naranja), `tamano`, `alto`.

### numerados
Pasos "1. …", "2. …", con imagen opcional a la izquierda.
```yaml
- tipo: numerados
  titulo: "Analogía: las muñecas rusas"
  imagen: ../../assets/portada-marcos.png
  fondo_imagen: navy        # para imágenes claras sobre transparente
  ancho_imagen: 0.72        # peso de la columna de la imagen frente a la de los pasos (1)
  pasos:
    - {titulo: Abrir, texto: Se abre una muñeca que contiene otra.}
    - {titulo: La última no se abre, texto: Es el caso base., acento: naranja}
```

### codigo
```yaml
- tipo: codigo
  titulo: La función completa
  codigo: {archivo: fibonacci.py, desde: "def fibonacci", cantidad: 4}
  tamano_codigo: 15
  tarjetas:                 # opcional: van al costado
    - {titulo: Casos base, texto: "`n == 0` o `n == 1`"}
  codigo_a_la_derecha: false
```

### codigo_salida
```yaml
- tipo: codigo_salida
  titulo: Crear, agregar y recorrer
  codigo: listas.py
  salida: listas.py         # o {archivo, entrada, primeras, ultimas}
  tarjetas:                 # opcional; sin tarjetas, código y salida van lado a lado
    - {titulo: Índices, texto: "`frutas[0]` es el primero."}
```

### imagen
```yaml
- tipo: imagen
  titulo: El árbol de llamadas de fibonacci(5)
  texto: Cada F(n) llama a F(n-1) y F(n-2).          # opcional, arriba
  imagen: {diagrama: arbol, archivo: fibonacci.py, llamada: "fibonacci(5)", formato: "F({n})"}
  epigrafe: "Azul: primera vez que se calcula; naranja: se recalcula."
```
`imagen` también puede ser una ruta a un PNG o JPG propio (un diagrama, nunca una captura inventada).

### tabla
```yaml
- tipo: tabla
  titulo: Recursión e iteración
  rotulo: Comparación                 # rótulo azul encima (opcional)
  tabla:
    encabezado: [Aspecto, Recursión, Iteración]
    filas:
      - [Memoria, Mayor (apila llamadas), Menor]
      - [Ideal para, Estructuras anidadas, Recorridos largos]
    anchos: [1, 2, 2]                 # pesos de cada columna
    primera_negrita: true             # primera columna en azul y negrita
    resaltar: [2]                     # filas de datos (desde 1) en naranja negrita
    centrar: [1]                      # columnas (desde 1) centradas
```

### cita / aviso
```yaml
- tipo: cita                 # aviso: igual, en naranja
  titulo: Para tener en cuenta
  encabezado: ""             # título dentro del recuadro (opcional)
  texto: Una solución más elegante no siempre es la más eficiente.
  fuente: apunte de la unidad
```

### sintesis
Cierre oscuro con botones de conceptos (hasta 6 entran bien) y un texto final.
```yaml
- tipo: sintesis
  titulo: Síntesis
  botones: [Caso base, Paso recursivo, Pila de llamadas, RecursionError]
  texto:
    - "Lectura obligatoria: apunte de la Actividad 1."
    - "Próximo video: el factorial paso a paso."
```

### libre
Cualquier diagramación con bloques (sección 4).
```yaml
- tipo: libre
  titulo: Los dos componentes
  bloques:
    - fila:
        - ancho: 5.6
          bloques:
            - {tarjeta: Caso base, acento: naranja, texto: Detiene la recursión.}
            - {tarjeta: Paso recursivo, texto: Se llama con un problema más chico.}
        - ancho: 6.13
          bloques:
            - codigo: {archivo: cuenta_regresiva.py, bloque: 1}
            - {texto: "{naranja}**`if n == 0:`**{/}  caso base.", tamano: 14}
```

## 4. Bloques

Se apilan de arriba hacia abajo; `fila` los pone en columnas (cada columna es otra pila). El alto que sobra se
reparte entre los bloques elásticos (tarjeta, aviso, código, salida), cada uno hasta 1,2 in más que su alto
natural; si falta lugar, primero se achican las imágenes y después `build.py` imprime un `AVISO:`.

| Bloque | Claves |
|---|---|
| `tarjeta: Título` | `texto`, `acento`, `tamano` (15), `tamano_titulo` |
| `aviso: Título` | igual que tarjeta, en naranja con fondo cálido |
| `codigo: <ref>` | `titulo` (por defecto el nombre del archivo), `tamano` (15) |
| `salida: <ref>` | `titulo` (por defecto "Salida"), `tamano` (12) |
| `texto: ...` | `tamano` (16), `color`, `negrita`, `alinear: centro|derecha`, `separacion` |
| `tabla: {...}` | `titulo`, `tamano` (14) — mismas claves que el tipo `tabla` |
| `imagen: <ruta o diagrama>` | `epigrafe`, `fondo` (color detrás), `margen` |
| `fila: [{ancho, bloques}, ...]` | `ancho` es un peso relativo |

Cualquier bloque acepta `alto` (pulgadas, fijo) y `fijo: true` (no se estira). El área útil mide 12,13 × 5,3 in.

## 5. Referencias a código, salidas y diagramas

**codigo** — un nombre de archivo o un dict:
```yaml
codigo: factorial.py                                  # el archivo entero
codigo: {archivo: factorial.py, bloque: 1}            # 1.er bloque separado por líneas en blanco ([1, 3] = varios)
codigo: {archivo: factorial.py, lineas: "3-9"}        # rango de líneas
codigo: {archivo: factorial.py, desde: "def factorial", cantidad: 6}
codigo: {archivo: factorial.py, bloque: 1, rotulo: factorial.py}   # rótulo propio (sin "(fragmento)")
codigo: {texto: "si n es 0: devolver 1"}              # SOLO pseudocódigo; build.py avisa
```

**salida** — se ejecuta en cada build:
```yaml
salida: factorial.py
salida: {archivo: suma.py, entrada: "3\n4\n"}         # stdin; se muestra el eco como en la terminal
salida: {archivo: sin_caso_base.py, primeras: 5, ultimas: 3}   # "… (N líneas omitidas)"
salida: {archivo: x.py, comando: false, rotulo: Consola, timeout: 30}
```
La primera línea es `$ python3 archivo.py` (salvo `comando: false`). Los errores se muestran en rojo.

**diagrama** — dentro de `imagen:`:
```yaml
imagen: {diagrama: pila, archivo: cuenta_regresiva.py, llamada: "cuenta_regresiva(3)", formato: "n = {n}"}
imagen: {diagrama: arbol, archivo: fibonacci.py, llamada: "fibonacci(5)", formato: "F({n})"}
```
- `pila`: una columna por evento (llamada o retorno), hasta 16 eventos. El rótulo de cada columna sale de la
  traza: "imprime X" si esa llamada imprimió algo, "llama", "devuelve V" o "termina". `etiquetas: [...]`
  los reemplaza.
- `arbol`: hasta 60 llamadas. Azul la primera vez que aparece un argumento, naranja las repeticiones
  (`marcar_repetidos: false` lo apaga).
- `funcion`: si la función trazada no es la que aparece en `llamada`.
- `formato`: cómo se escribe cada llamada, con los nombres de los parámetros.
El archivo se ejecuta entero una vez (sin mostrar lo que imprime) y después se evalúa `llamada` con la función
envuelta: la traza es la de la ejecución real.
