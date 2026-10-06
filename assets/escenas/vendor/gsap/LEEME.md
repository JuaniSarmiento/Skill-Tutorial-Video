# GSAP vendorizado

**Versión 3.15.0**, bajada el 06/10/2026 con `npm pack gsap` (archivos de `package/dist/`). Los
cinco bytes a bytes coinciden con `https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/<archivo>`
(comparado por sha256 ese mismo día). Va acá porque el motor de escenas bloquea la red: las
plantillas lo cargan como archivo local.

| sha256 | archivo | qué es |
|---|---|---|
| `92bb9a96476f983d212a2bc4f54c889039c1696dd4461d40a736860938570fbb`  `gsap.min.js` | núcleo (timeline, tweens) |
| `beb19529f54c1212f1f5117d027be01afda2f363a4926d32aa979bc11140edc1`  `DrawSVGPlugin.min.js` | un trazo SVG que se dibuja |
| `19c891a412240d8521b13330813d9b551ea5b0f707907c365ffecaf1dfa0f5cf`  `MorphSVGPlugin.min.js` | una forma que se transforma en otra |
| `419f7027a5f086a12cb7988736d8fdd3a6ed2200229661de25b6628ca7ced344`  `SplitText.min.js` | texto partido en palabras/letras |
| `466e426a5c60c21c94b15a30a3dffacac9bb39ce8f4e07d071d7d4bb1be43390`  `CustomEase.min.js` | curvas de aceleración a medida |

`tests/test_gsap_vendor.py` verifica estos hashes y que cada archivo conserve su cabecera
`@license`. Para actualizar: bajar la versión nueva igual, reemplazar los cinco, actualizar la
tabla y correr los tests de escenas (el determinismo se mide, no se asume).

## Licencia

`LICENCIA.txt`: la **GSAP Standard "No Charge" License** (de Webflow, dueña de GSAP). Resumen de
la decisión del Hito 3 (`docs/explicador/HITO3.md`):

- Gratis para uso comercial, **plugins incluidos** (DrawSVG, MorphSVG y SplitText eran pagos antes).
- **Prohíbe** usarlo en herramientas para armar animaciones visualmente, sin código, que compitan
  con el constructor de animaciones de Webflow. Esta skill no lo es (las escenas se escriben en
  código).
- **No se quitan ni se alteran** los avisos de licencia de los archivos (cláusula III).
- Revisar la licencia si la skill se vende como servicio: el "Plain English Summary" de la misma
  página todavía habla de cobrarle al usuario final un acceso, aunque el FAQ y la cláusula II
  dicen que el uso comercial está cubierto sin cargo.
