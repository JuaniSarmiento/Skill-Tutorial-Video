// Base común de las plantillas de escena.
//
// Contrato: window.DURATION + async window.seek(t) (no es el formato de HyperFrames,
// ver docs/explicador/HITO3.md). Todo lo que
// se ve es función pura de t: nada de Date.now, requestAnimationFrame, timers,
// transiciones CSS ni azar. seek(t) recalcula cada estilo desde cero, así que el
// orden en que se piden los cuadros no importa.
//
// La página recibe window.SPEC (con cada cue ya resuelta a `t`) y window.BRAND.
(function () {
  const S = window.SPEC || {};
  const B = window.BRAND || {};
  const C = B.colores || {};
  const M = B.movimiento || {};

  const raiz = document.documentElement.style;
  for (const [k, v] of Object.entries(C)) raiz.setProperty('--' + k, v);
  raiz.setProperty('--fuente', `"${B.fuente || 'Inter'}", "Noto Sans", sans-serif`);

  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));

  // Respuesta al escalón de un resorte amortiguado. Con amortiguamiento 0.72 pasa
  // ~4 % y vuelve: overshoot contenido, sin rebote. Cuando el resto ya no se ve
  // (< 1/1000) devuelve 1 exacto, para que un elemento quieto sea pixel-idéntico.
  function resorte(x, z = M.amortiguamiento ?? 0.72, f = M.frecuencia ?? 2.1) {
    if (x <= 0) return 0;
    const w = 2 * Math.PI * f;
    if (Math.exp(-Math.min(z, 1) * w * x) * (1 + w * x) < 1e-3) return 1;
    if (z >= 1) return 1 - Math.exp(-w * x) * (1 + w * x);
    const wd = w * Math.sqrt(1 - z * z);
    return 1 - Math.exp(-z * w * x) * (Math.cos(wd * x) + (z * w / wd) * Math.sin(wd * x));
  }
  const salida = x => 1 - Math.pow(1 - clamp(x), 3);          // ease-out cúbico, para trazos
  const aparecer = (t, t0, d = 0.28) => salida((t - t0) / d);  // opacidad de entrada

  // Segundo en que entra un elemento: su t resuelto, o su cue numérica, o el default.
  const tiempo = (el, porDefecto) =>
    el && el.t != null ? el.t : (el && typeof el.cue === 'number' ? el.cue : porDefecto);

  const medir = (() => {
    const ctx = document.createElement('canvas').getContext('2d');
    return (texto, px, peso = 600) => {
      ctx.font = `${peso} ${px}px ${getComputedStyle(document.documentElement).getPropertyValue('--fuente')}`;
      return ctx.measureText(texto).width;
    };
  })();

  const crear = (tag, clase, padre = document.body, texto) => {
    const e = document.createElement(tag);
    if (clase) e.className = clase;
    if (texto != null) e.textContent = texto;
    padre.appendChild(e);
    return e;
  };

  // Cabecera: kicker opcional + título que entra palabra por palabra.
  // techo(minimo, alto, hasta): dónde puede empezar el contenido. Debajo de la cabecera
  // MEDIDA (un título largo ocupa varios renglones), con aire, y nunca más arriba que
  // `minimo`. Si desde ahí no quedan `alto` px antes de `hasta`, falla nombrando el título.
  const AIRE_CAB = 40;
  function cabecera(titulo, kicker) {
    if (!titulo) return { tiempos: [], dibujar() {}, techo: minimo => minimo };
    const t0 = tiempo(titulo, 0);
    const caja = crear('header', 'cabecera');
    const k = kicker ? crear('div', 'kicker', caja, kicker.texto || kicker) : null;
    if (k) k.dataset.caja = 'kicker';
    const h = crear('h1', 'titulo', caja);
    h.dataset.caja = 'titulo';
    const palabras = String(titulo.texto || titulo).split(/\s+/).map(p => crear('span', 'palabra', h, p));
    return {
      tiempos: [t0],
      techo(minimo, alto = 0, hasta = 1080) {
        const abajo = caja.getBoundingClientRect().bottom;
        const y = Math.max(minimo, abajo + AIRE_CAB);
        if (y + alto > hasta)
          throw new Error(`el título ocupa hasta y=${Math.round(abajo)} y no deja lugar para el contenido ` +
                          `(hacen falta ${Math.round(alto)} px y quedan ${Math.round(hasta - y)}): acortá el título`);
        return y;
      },
      dibujar(t) {
        if (k) k.style.opacity = aparecer(t, t0);
        palabras.forEach((p, i) => {
          const ti = t0 + i * 0.07, v = resorte(t - ti);
          p.style.opacity = aparecer(t, ti);
          p.style.transform = `translateY(${((1 - v) * (M.subida ?? 28)).toFixed(2)}px)`;
        });
      },
    };
  }

  // montar() arma el DOM una vez (con las fuentes ya cargadas, para medir bien);
  // dibujar(t) sólo fija estilos en función de t.
  function contrato(tiempos, montar, dibujar) {
    window.DURATION = S.duracion ?? Math.max(0, ...tiempos) + 2.5;
    let montado = false;
    window.seek = async t => {
      if (!montado) { await document.fonts.ready; montar(); montado = true; }
      dibujar(t);
    };
  }

  // Puente GSAP -> contrato. construir() arma el DOM y devuelve una timeline de GSAP;
  // corre una sola vez, con las fuentes ya cargadas (SplitText y los trazos miden).
  // DURATION es la de la timeline (o la del spec, si el motor la pisa con el slot de
  // la voz) y seek(t) la deja en t con totalTime(t, false), sincrónico.
  // El reloj de GSAP no mueve nada: la timeline global queda en pausa, así que un
  // tween suelto (fuera de la timeline) tampoco avanza solo.
  function lineaDeTiempo(construir) {
    const g = window.gsap;
    if (!g) throw new Error('E.lineaDeTiempo necesita GSAP: cargá vendor/gsap/gsap.min.js antes que base.js');
    g.globalTimeline.pause();
    let tl;
    const lista = document.fonts.ready.then(() => {
      tl = construir().pause();
      // GSAP inicializa cada tween en su primer render (MorphSVG normaliza el path a
      // cúbicas, DrawSVG fija su dashoffset): sin esto el cuadro de t dependía de por
      // dónde pasó antes la timeline (medido en la prueba de H0). Se recorre entera una
      // vez, sin eventos, y vuelve a 0: desde ahí cada t se ve igual en cualquier orden.
      tl.totalTime(tl.totalDuration(), true).totalTime(0, true);
      window.DURATION = S.duracion ?? tl.duration();
    });
    window.seek = async t => { await lista; tl.totalTime(t, false); };
  }

  window.E = { S, B, C, M, clamp, resorte, salida, aparecer, tiempo, medir, crear, cabecera, contrato, lineaDeTiempo };
})();
