// Número que cuenta hasta su valor (H4, HITO3.md). Lo usan contador.html (el número
// protagonista suelto) y codigo.html (los números de una salida real que cuentan).
// Ideas de los bloques `count-up` y `number-pop-in` de HyperFrames (Apache 2.0,
// github.com/heygen-com/hyperframes): arranca rápido y frena justo en el valor exacto,
// y aterriza con un pulso contenido. El código es propio.
(function () {
  // es-AR a mano (no toLocaleString: el agrupamiento de "es" cambia según la versión de
  // ICU, 1000 puede salir "1000"): punto de miles, coma decimal, el signo antes del prefijo.
  function formato(v, o = {}) {
    const [ent, frac] = Math.abs(v).toFixed(o.dec ?? 0).split('.');
    const n = (o.miles === false ? ent : ent.replace(/\B(?=(\d{3})+(?!\d))/g, '.')) + (frac ? ',' + frac : '');
    return (v < 0 && /[1-9]/.test(n) ? '-' : '') + (o.prefijo || '') + n + (o.sufijo || '');
  }

  // Suma a la timeline `tl` un conteo de `desde` a `hasta` que arranca en `t0` y dura `dur`;
  // `escribir(v)` arma el texto de cada valor. El texto inicial se fija ya (el seek a un t
  // anterior al conteo no dispara onUpdate) y el final es exactamente escribir(hasta).
  function contar(tl, el, { desde = 0, hasta, t0, dur = 1.6, escribir }) {
    const p = { v: desde };
    el.textContent = escribir(desde);
    tl.to(p, { v: hasta, duration: dur, ease: 'power3.out',
               onUpdate: () => { el.textContent = escribir(p.v); } }, t0);
    return t0 + dur;
  }

  window.Contador = { formato, contar };
})();
