# Estilo institucional TUPaD para diapositivas

Es el mismo sistema visual de los apuntes de la cátedra (plantilla de teoría y TP): azul institucional,
acento azul medio, naranja para lo que importa, Inter para el texto y monoespaciada para el código. Las
constantes viven en `scripts/deck.py`; si cambian acá, cambian allá.

## Paleta

| Nombre en deck.py | Hex | Uso |
|---|---|---|
| `NAVY` | `#1B365D` | Títulos, banda superior, fondo de portada / sección / síntesis, encabezado de tabla, palabras clave del código |
| `ACC` | `#2F6FA7` | Subrayado del título, rótulos sobre código y tablas, barra de tarjetas, botones de la síntesis |
| `TXT` | `#1F2328` | Texto corrido |
| `GRIS` | `#5B6470` | Pie, epígrafes, notas, comentarios del código, comandos de consola |
| `CARD` | `#E8EEF6` | Fondo de tarjetas y filas impares de tabla |
| `BORDE` | `#C9D3DF` | Borde de código, línea del pie |
| `CODEBG` | `#F6F8FA` | Fondo de código y consola |
| `NARANJA` | `#B54708` | Caso base, advertencias, la fila que importa; **un solo uso fuerte por diapositiva** |
| `NARANJA_FONDO` | `#FDF1E8` | Fondo de avisos |
| `VERDE` | `#2E7D4F` | Cadenas en el código |
| `ROJO` | `#B42318` | Errores en la consola (`RecursionError: ...`) |
| `CLARO` | `#C3D5EA` | Subtítulo y pie sobre fondo navy |
| `LINEA` | `#8FB0D6` | Filete de la portada |

Es la paleta de `tupad.css` de la plantilla de apuntes (`--azul`, `--acento`, `--texto`, `--gris`, `--linea`,
`--codigo-fondo`, `--importante`, `--practica`).

## Tipografías

- **Inter** para todo el texto. Título de diapositiva 28 pt negrita navy; título de portada 40 pt; texto de
  tarjeta 14 a 18 pt; título de tarjeta 1 pt más que su texto; pie 10 pt.
- **DejaVu Sans Mono** para código, consola y código en línea. Código 15 pt por defecto (se achica solo si la
  línea más larga no entra); consola 12 pt. **Nada por debajo de 10 pt**: en un video a 1080p deja de leerse.
- Nunca una monoespaciada con ligaduras (JetBrains Mono, Fira Code, Cascadia Code): ver `lecciones.md`.

## Geometría (16:9, 13,333 × 7,5 in)

- Margen lateral 0,6 in. Banda navy superior de 0,12 in. Título en y = 0,38, subrayado acento 1,1 × 0,06 in.
- Área de contenido: x 0,6 → 12,73, y 1,45 → 6,75 (12,13 × 5,3 in).
- Separaciones: 0,25 in entre bloques apilados, 0,4 in entre columnas.
- Pie en y ≈ 7: filete, logo UTN negro (0,81 in de ancho), texto del pie y numeración "n / total" a la derecha.
  Las diapositivas oscuras (portada, sección, síntesis) no llevan pie con logo: llevan el logo blanco arriba.
- Tarjeta: fondo `CARD`, barra lateral de 0,07 in del color de acento, texto con 0,25 in de margen.
- Código: rótulo azul 12 pt negrita encima (el nombre del archivo, o "Salida"), caja `CODEBG` con borde.

## Jerarquía

1. Título de la diapositiva: una frase que dice de qué trata, no "Ejemplo 3".
2. Lo central (código, diagrama, tabla) ocupa el lugar más grande.
3. Tarjetas: explican o destacan; el título de la tarjeta resume, el cuerpo explica en 1 a 3 oraciones.
4. Notas en gris: lo accesorio.

## Qué hacer

- Una idea por diapositiva; 3 tarjetas como máximo por fila.
- Código real del `.py` y su salida real, uno junto al otro.
- Naranja sólo para lo que el alumno no puede pasar por alto (el caso base, el error, el límite).
- Portada con materia, unidad, tema y revisor; síntesis al final con los conceptos de la clase.
- Texto en tercera persona o impersonal, presente atemporal.
- Diagramas generados (pila, árbol) o propios; con epígrafe que diga qué se ve.

## Qué no hacer

- Párrafos largos en una tarjeta: si no se lee en 10 segundos, sobra texto.
- Código tipeado a mano, salidas "que deberían dar", capturas recreadas de sitios o programas.
- Imágenes generadas con texto adentro (las letras salen deformadas) o decorativas que no explican nada.
- Colores fuera de la paleta, degradados, sombras agregadas, emojis.
- Rutas personales (`/home/...`, `C:\Users\...`) en cualquier salida.
- Letra de código por debajo de 10 pt: partí el archivo en fragmentos.
