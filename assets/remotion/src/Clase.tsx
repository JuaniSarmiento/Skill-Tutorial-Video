// Formato «clase con personaje» (references/clase.md): un personaje presenta frente a una pizarra.
// Todo lo que se ve sale de las props que arma assets/scripts/clase.py (tiempos de la voz, boca,
// código real y su salida, reparto). Paleta pastel clara; la cámara corta entre el plano general,
// la pizarra y el primer plano del personaje: esos cortes dan el ritmo.
import React from 'react';
import {AbsoluteFill, Img, cancelRender, continueRender, delayRender, interpolate, staticFile, useCurrentFrame} from 'remotion';

// ---------- tipos (los mismos campos que escribe clase.py) ----------
type Palabra = {w: string; t0: number; t1: number};
type Plano = {t: number; camara: 'profe' | 'normal' | 'pizarra'};
type Escena = {tipo: 'pizarra' | 'diagrama' | 'codigo' | 'terminal'; [k: string]: any};
type Segmento = {texto: string; pose: string; luego: {pose: string; t: number}[]; planos: Plano[]; escena: Escena;
  inicio: number; fin: number; voz: number; dur: number; palabras: Palabra[]};
type Pose = {cerrada: string; abierta: string; boca: number[]};
export type PropsClase = {duracion: number; boca: number[][]; segmentos: Segmento[]; pizarra: number[];
  publico: {fondo: string; poses: Record<string, Pose>}; colores: {arriba: string; abajo: string}};

const FPS = 30;
const TINTA = '#2b2745', ROSA = '#e0487a', MENTA = '#1f9e84', LILA = '#6a5fd8', NARANJA = '#e9782c';
const ROSA_P = '#ffd9e4', MENTA_P = '#cdf3e6', LILA_P = '#e4e0ff', AMARILLO_P = '#fff0a0';
const MANO = 'ClaseMano', MONO = 'ClaseMono', MONOB = 'ClaseMonoB', SANS = 'ClaseSans';
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

// ---------- fuentes (OFL, assets/fuentes): el render espera a que carguen ----------
const fuente = (familia: string, archivo: string, peso = '400') => {
  const h = delayRender(`fuente ${archivo}`);
  const f = new FontFace(familia, `url('${staticFile('fuentes/' + archivo)}')`, {weight: peso});
  f.load().then(() => { document.fonts.add(f); continueRender(h); }).catch(e => cancelRender(e));
};
fuente(MANO, 'Kalam-Bold.ttf');
fuente(MONO, 'JetBrainsMono-Regular.ttf');
fuente(MONOB, 'JetBrainsMono-ExtraBold.ttf');
fuente(SANS, 'Fredoka.ttf', '300 700');

// ---------- escenario ----------
// El fondo (1080×1620) va corrido TOP hacia abajo; arriba y abajo se completa con su color.
const TOP = 140;
// El personaje abajo a la derecha: caja de 700×1050 (lienzo 960×1440, pies en 1400) → figura de
// ~920 px (48 % del alto), pies en y≈1888, cabeza en y≈970.
const PERSO = {x: 420, y: 867, w: 700, h: 1050};
const CABEZA = {x: 770, y: 1150};

type Cam = {s: number; x: number; y: number; sx: number; sy: number};
const camaraDe = (nombre: Plano['camara'], piz: {x: number; y: number; w: number; h: number}): Cam => {
  if (nombre === 'profe') return {s: 2.0, x: CABEZA.x, y: CABEZA.y, sx: 540, sy: 660};
  if (nombre === 'pizarra') return {s: Math.min(1.14, 1000 / piz.w), x: piz.x + piz.w / 2, y: piz.y + piz.h / 2, sx: 540, sy: 760};
  return {s: 1, x: 540, y: 960, sx: 540, sy: 960};
};
/** Transformación de la cámara: un acercamiento lento y continuo desde el corte (nada queda quieto). */
const transformar = (c: Cam, desde: number, t: number) => {
  const s = c.s * (1 + Math.min(0.06, 0.012 * Math.max(0, t - desde)));
  let tx = c.sx - c.x * s, ty = c.sy - c.y * s;
  tx = Math.min(0, Math.max(1080 - 1080 * s, tx));
  ty = Math.min(0, Math.max(1920 - 1920 * s, ty));
  return `translate(${tx}px, ${ty}px) scale(${s})`;
};

// ---------- piezas ----------
/** Fibrón: el contenido aparece de izquierda a derecha en `dur` s desde `desde`. */
const Escribe: React.FC<{t: number; desde: number; dur?: number; x: number; y: number; children: React.ReactNode; w?: number; centro?: boolean}> = ({t, desde, dur = 0.5, x, y, children, w, centro}) => {
  if (t < desde) return null;
  const p = interpolate(t, [desde, desde + dur], [0, 100], clamp);
  return <div style={{position: 'absolute', left: x, top: y, width: w, textAlign: centro ? 'center' : undefined,
    clipPath: `inset(-30px ${100 - p}% -30px -30px)`, whiteSpace: 'nowrap'}}>{children}</div>;
};
/** Golpe: entra de una y asienta (1,35 → 1) en 6 cuadros. */
const Golpe: React.FC<{t: number; desde: number; x: number; y: number; children: React.ReactNode; rot?: number}> = ({t, desde, x, y, children, rot = 0}) => {
  if (t < desde) return null;
  const s = interpolate((t - desde) * FPS, [0, 3, 6], [1.35, 0.95, 1], clamp);
  return <div style={{position: 'absolute', left: x, top: y, transform: `rotate(${rot}deg) scale(${s})`, whiteSpace: 'nowrap'}}>{children}</div>;
};
const Mano: React.FC<{tam?: number; color?: string; children: React.ReactNode; marca?: string; p?: number}> = ({tam = 64, color = TINTA, children, marca, p = 1}) => (
  <span style={{fontFamily: MANO, fontSize: tam, lineHeight: 1.15, color, position: 'relative', display: 'inline-block'}}>
    {marca && <span style={{position: 'absolute', left: -8, right: `${-8 + (1 - p) * 100}%`, top: '40%', bottom: '4%', background: marca, borderRadius: 10, zIndex: -1, transform: 'rotate(-1deg)'}}/>}
    <span style={{position: 'relative'}}>{children}</span>
  </span>
);
/** Trazo SVG que se dibuja (dasharray) entre `desde` y `desde + dur`. */
const Trazo: React.FC<{t: number; desde: number; dur?: number; d: string; color?: string; ancho?: number; flecha?: boolean; largo?: number; relleno?: string}> = ({t, desde, dur = 0.5, d, color = TINTA, ancho = 7, flecha, largo = 1600, relleno}) => {
  if (t < desde) return null;
  const p = interpolate(t, [desde, desde + dur], [0, 1], clamp);
  return <path d={d} fill={relleno && p > 0.98 ? relleno : 'none'} stroke={color} strokeWidth={ancho} strokeLinecap="round" strokeLinejoin="round"
    strokeDasharray={largo} strokeDashoffset={largo * (1 - p)} markerEnd={flecha && p > 0.95 ? `url(#punta-${color.slice(1)})` : undefined}/>;
};
const Lienzo: React.FC<{w: number; h: number; children: React.ReactNode}> = ({w, h, children}) => (
  <svg width={w} height={h} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}}>
    <defs>{[TINTA, ROSA, MENTA, LILA, NARANJA].map(c =>
      <marker key={c} id={`punta-${c.slice(1)}`} viewBox="0 0 10 10" refX="7" refY="5" markerWidth="4.5" markerHeight="4.5" orient="auto-start-reverse">
        <path d="M0,0 L10,5 L0,10 z" fill={c}/></marker>)}</defs>
    {children}
  </svg>
);
const Tilde: React.FC<{t: number; desde: number; x: number; y: number; tam?: number; color?: string}> = ({t, desde, x, y, tam = 70, color = MENTA}) => (
  <Trazo t={t} desde={desde} dur={0.3} color={color} ancho={tam / 6} largo={tam * 2} d={`M${x},${y + tam * 0.5} L${x + tam * 0.38},${y + tam * 0.85} L${x + tam},${y}`}/>
);
const Estrella: React.FC<{t: number; desde: number; x: number; y: number; tam?: number; color?: string}> = ({t, desde, x, y, tam = 60, color = NARANJA}) => {
  const pts = Array.from({length: 10}, (_, k) => {
    const r = k % 2 ? tam * 0.42 : tam, a = -Math.PI / 2 + k * Math.PI / 5;
    return `${(x + r * Math.cos(a)).toFixed(1)},${(y + r * Math.sin(a)).toFixed(1)}`;
  });
  return <Trazo t={t} desde={desde} dur={0.35} color={color} ancho={7} largo={tam * 12} relleno={AMARILLO_P} d={`M${pts.join(' L')} Z`}/>;
};

// Resaltado de sintaxis de Python, tema claro.
const SINTAXIS = {kw: '#b03a8c', fn: '#5b4fd0', num: '#c55a11', str: '#1f8a5b', var: '#1d6fa5', op: '#4a4560', com: '#8a84a8'};
const KW = new Set(['if', 'elif', 'else', 'while', 'for', 'in', 'def', 'return', 'and', 'or', 'not', 'import', 'from', 'True', 'False', 'None', 'break', 'continue', 'class', 'pass', 'with', 'as', 'try', 'except', 'is', 'lambda']);
const tokens = (linea: string) => {
  const com = linea.indexOf('#');
  const partes = (com >= 0 ? linea.slice(0, com) : linea).split(/("[^"]*"?|'[^']*'?|\s+|[()\[\]{}<>=+\-*/:,.!%]+|\d+)/).filter(Boolean);
  const out = partes.map((x, k) => {
    const c = KW.has(x) ? SINTAXIS.kw : /^["']/.test(x) ? SINTAXIS.str : /^\d+$/.test(x) ? SINTAXIS.num
      : /^[A-Za-z_]\w*$/.test(x) ? (['print', 'range', 'input', 'len', 'int', 'str', 'float'].includes(x) ? SINTAXIS.fn : SINTAXIS.var) : SINTAXIS.op;
    return <span key={k} style={{color: c}}>{x}</span>;
  });
  if (com >= 0) out.push(<span key="c" style={{color: SINTAXIS.com}}>{linea.slice(com)}</span>);
  return out;
};

/** Editor claro con el código real; `tipeo` = caracteres visibles por línea. */
const Editor: React.FC<{nombre: string; lineas: string[]; tipeo?: number[]; marca?: number | null; t: number; ancho: number; tam: number}> = ({nombre, lineas, tipeo, marca, t, ancho, tam}) => {
  const alto = Math.round(tam * 1.55);
  return <div style={{width: ancho, background: '#fffefb', borderRadius: 22, overflow: 'hidden', border: `4px solid ${TINTA}`, boxShadow: '8px 10px 0 #2b274522',
    fontFamily: MONO, fontSize: tam, fontVariantLigatures: 'none', fontFeatureSettings: '"liga" 0, "calt" 0'}}>
    <div style={{height: 58, background: LILA_P, display: 'flex', alignItems: 'center', gap: 12, paddingLeft: 22, borderBottom: `3px solid ${TINTA}`}}>
      {[ROSA, NARANJA, MENTA].map(c => <div key={c} style={{width: 18, height: 18, borderRadius: 9, background: c}}/>)}
      <span style={{fontFamily: SANS, fontWeight: 600, fontSize: 34, color: TINTA, marginLeft: 14}}>{nombre}</span>
    </div>
    <div style={{padding: '12px 0'}}>
      {lineas.map((l, k) => {
        const n = tipeo ? Math.max(0, tipeo[k] ?? l.length) : l.length;
        const m = marca === k;
        const cursor = tipeo && n > 0 && n < l.length;
        return <div key={k} style={{height: alto, display: 'flex', alignItems: 'center', position: 'relative', background: m ? `${MENTA}22` : 'transparent'}}>
          {m && <div style={{position: 'absolute', left: 0, top: 0, bottom: 0, width: 10, background: MENTA}}/>}
          <span style={{width: 70, textAlign: 'right', paddingRight: 20, color: '#a8a3c0', fontSize: Math.round(tam * 0.7)}}>{k + 1}</span>
          <span style={{whiteSpace: 'pre'}}>{tokens(l.slice(0, n))}</span>
          {cursor && Math.floor(t * 4) % 2 === 0 && <span style={{width: 4, height: tam, background: TINTA, marginLeft: 2}}/>}
        </div>;
      })}
    </div>
  </div>;
};

/** Terminal clara: el comando y la salida real, línea por línea. */
const Terminal: React.FC<{lineas: React.ReactNode[]; ancho: number; tam: number; max: number}> = ({lineas, ancho, tam, max}) => (
  <div style={{width: ancho, background: '#f7f6ff', borderRadius: 18, overflow: 'hidden', border: `4px solid ${TINTA}`, boxShadow: '8px 10px 0 #2b274522',
    fontFamily: MONO, fontSize: tam, fontVariantLigatures: 'none', fontFeatureSettings: '"liga" 0, "calt" 0'}}>
    <div style={{height: 50, background: MENTA_P, display: 'flex', alignItems: 'center', paddingLeft: 18, borderBottom: `3px solid ${TINTA}`, fontFamily: SANS, fontWeight: 600, fontSize: 31, color: TINTA}}>terminal</div>
    <div style={{padding: '10px 22px', height: max * tam * 1.3 + 20, lineHeight: 1.3, color: TINTA, overflow: 'hidden'}}>
      {lineas.slice(-max).map((l, k) => <div key={k} style={{whiteSpace: 'pre'}}>{l}</div>)}
    </div>
  </div>
);

const tamCodigo = (lineas: string[], ancho: number, max = 52) =>
  Math.max(40, Math.min(max, Math.floor((ancho - 110) / (Math.max(...lineas.map(l => l.length), 8) * 0.6))));
const tamMano = (texto: string, ancho: number, max: number) => Math.min(max, Math.floor(ancho / (Math.max(texto.length, 4) * 0.56)));

// ---------- escenas de la pizarra (coordenadas del lienzo de la pizarra) ----------
const Pizarra: React.FC<{e: Escena; t: number; w: number; h: number; primero: boolean}> = ({e, t, w, h, primero}) => {
  const lineas: string[] = e.lineas;
  const tams = lineas.map((l, k) => tamMano(l, w - 60, k === 0 ? 150 : 96));
  const alto = tams.reduce((a, b) => a + b * 1.25, 0);
  let y = Math.max(10, (h - alto) / 2 - 30);
  const colores = [TINTA, LILA, ROSA, MENTA];
  const items = lineas.map((l, k) => {
    const desde = primero && k === 0 ? -1 : e.t[k];
    const yy = y;
    y += tams[k] * 1.25;
    return <Escribe key={k} t={t} desde={desde} dur={Math.min(1.1, Math.max(0.4, l.length * 0.045))} x={30} y={yy} w={w - 60} centro>
      <Mano tam={tams[k]} color={colores[k % colores.length]} marca={k === lineas.length - 1 && t >= e.t_subrayado ? AMARILLO_P : undefined}
        p={interpolate(t, [e.t_subrayado, e.t_subrayado + 0.4], [0, 1], clamp)}>{l}</Mano></Escribe>;
  });
  const ultimo = y + 10;
  return <>{items}
    <Lienzo w={w} h={h}>
      <Trazo t={t} desde={e.t_subrayado} dur={0.45} color={ROSA} ancho={10} d={`M${w * 0.18},${ultimo} C${w * 0.4},${ultimo - 14} ${w * 0.62},${ultimo + 12} ${w * 0.82},${ultimo - 4}`}/>
      <Estrella t={t} desde={e.t_adorno} x={w - 80} y={70} tam={50}/>
      <Estrella t={t} desde={e.t_adorno + 0.25} x={80} y={h - 80} tam={38} color={LILA}/>
    </Lienzo>
  </>;
};

const Diagrama: React.FC<{e: Escena; t: number; w: number; h: number}> = ({e, t, w, h}) => {
  const T = e.t;
  const R = {x: w / 2, y: Math.min(190, h * 0.27), a: Math.min(250, w * 0.27), b: 125};
  const caja = {w: Math.min(380, w * 0.42), h: 150, y: Math.min(h - 190, R.y + R.b + 190)};
  const xs = {si: w * 0.25, no: w * 0.75};
  const rombo = `M${R.x},${R.y - R.b} L${R.x + R.a},${R.y} L${R.x},${R.y + R.b} L${R.x - R.a},${R.y} Z`;
  const camino = (lado: 'si' | 'no') => {
    const vx = lado === 'si' ? R.x - R.a : R.x + R.a;
    return `M${vx},${R.y} L${xs[lado]},${R.y} L${xs[lado]},${caja.y - 10}`;
  };
  const sobre = (lado: 'si' | 'no', u: number): [number, number] => {
    const vx = lado === 'si' ? R.x - R.a : R.x + R.a;
    const pts: [number, number][] = [[R.x, R.y], [vx, R.y], [xs[lado], R.y], [xs[lado], caja.y + caja.h / 2]];
    const largos = pts.slice(1).map((p, k) => Math.hypot(p[0] - pts[k][0], p[1] - pts[k][1]));
    let d = Math.max(0, Math.min(1, u)) * largos.reduce((a, b) => a + b, 0);
    for (let k = 0; k < largos.length; k++) {
      if (d <= largos[k]) { const f = d / largos[k]; return [pts[k][0] + f * (pts[k + 1][0] - pts[k][0]), pts[k][1] + f * (pts[k + 1][1] - pts[k][1])]; }
      d -= largos[k];
    }
    return pts[pts.length - 1];
  };
  const cond: string = e.condicion;
  const tamCond = Math.max(40, Math.min(60, Math.floor(R.a * 1.25 / (cond.length * 0.6))));
  const lado: 'si' | 'no' = e.camino;
  const llega = T.ficha + 0.9;
  const ficha = t >= T.ficha ? sobre(lado, (t - T.ficha) / 0.9) : null;
  const pulso = (d: number) => t >= d && t < d + 0.6 ? 1 + 0.1 * Math.sin((t - d) * 18) : 1;
  const Caja = ({que, color, fondo}: {que: 'si' | 'no'; color: string; fondo: string}) => t >= T[que] ? (
    <Golpe t={t} desde={T[que] + 0.3} x={xs[que] - caja.w / 2} y={caja.y}>
      <div style={{width: caja.w, height: caja.h, background: fondo, border: `5px solid ${TINTA}`, borderRadius: 26, boxShadow: '8px 10px 0 #2b274522',
        display: 'flex', alignItems: 'center', justifyContent: 'center', transform: `scale(${lado === que ? pulso(llega) : 1})`,
        outline: lado === que && t >= llega ? `8px solid ${color}` : undefined, outlineOffset: 6}}>
        <Mano tam={tamMano(e[que], caja.w - 30, 64)} color={TINTA}>{e[que]}</Mano>
      </div>
    </Golpe>) : null;
  return <>
    <Lienzo w={w} h={h}>
      <Trazo t={t} desde={T.rombo - 0.01} dur={0.3} flecha d={`M${R.x},0 L${R.x},${R.y - R.b - 10}`} largo={300}/>
      {t >= T.rombo + 0.4 && <path d={rombo} fill={AMARILLO_P} opacity={interpolate(t, [T.rombo + 0.4, T.rombo + 0.6], [0, 1], clamp)}/>}
      <Trazo t={t} desde={T.rombo} dur={0.6} ancho={8} d={rombo} largo={1400}/>
      <Trazo t={t} desde={T.si} dur={0.45} flecha color={MENTA} ancho={8} d={camino('si')}/>
      <Trazo t={t} desde={T.no} dur={0.45} flecha color={ROSA} ancho={8} d={camino('no')}/>
      {ficha && <g transform={`translate(${ficha[0]} ${ficha[1]})`}><circle r={28} fill={NARANJA} stroke={TINTA} strokeWidth={5}/><circle r={8} fill="#fff"/></g>}
    </Lienzo>
    <Escribe t={t} desde={T.condicion} dur={0.5} x={R.x - R.a} y={R.y - tamCond * 0.7} w={R.a * 2} centro>
      <span style={{fontFamily: MONOB, fontSize: tamCond, color: TINTA, fontVariantLigatures: 'none', fontFeatureSettings: '"liga" 0, "calt" 0'}}>{cond}</span>
    </Escribe>
    <Golpe t={t} desde={T.si + 0.2} x={xs.si - 120} y={R.y - 92}><Mano tam={64} color={MENTA}>Sí</Mano></Golpe>
    <Golpe t={t} desde={T.no + 0.2} x={xs.no + 40} y={R.y - 92}><Mano tam={64} color={ROSA}>No</Mano></Golpe>
    <Caja que="si" color={MENTA} fondo={MENTA_P}/>
    <Caja que="no" color={ROSA} fondo={ROSA_P}/>
  </>;
};

const Codigo: React.FC<{e: Escena; t: number; w: number; h: number; primero: boolean}> = ({e, t, w, h, primero}) => {
  const lineas: string[] = e.lineas;
  const ancho = w - 20;
  const tam = tamCodigo(lineas, ancho);
  const tipeo = lineas.map((l, k) => Math.floor(interpolate(t, [primero && k === 0 ? -1 : e.t[k], (primero && k === 0 ? -1 : e.t[k]) + e.dur_linea], [0, l.length], clamp)));
  let marca: number | null = null;
  lineas.forEach((_, k) => { if (t >= e.t[k]) marca = k; });
  const fin = e.t[lineas.length - 1] + e.dur_linea;
  return <>
    <div style={{position: 'absolute', left: 10, top: 6}}><Editor t={t} nombre={e.nombre} lineas={lineas} tipeo={tipeo} marca={t < fin + 0.6 ? marca : null} ancho={ancho} tam={tam}/></div>
    <Lienzo w={w} h={h}><Tilde t={t} desde={fin + 0.4} x={w - 120} y={h - 130} tam={90}/></Lienzo>
  </>;
};

const TerminalEscena: React.FC<{e: Escena; t: number; w: number; h: number}> = ({e, t, w, h}) => {
  const codigo: string[] = e.codigo, salida: string[] = e.salida;
  const ancho = w - 20;
  const tam = Math.min(44, tamCodigo(codigo, ancho, 44));
  const altoEditor = 58 + 24 + codigo.length * Math.round(tam * 1.55);
  const comando = `$ python3 ${e.nombre}`;
  const n = Math.floor(interpolate(t, [e.t_comando, e.t_comando + 0.6], [0, comando.length], clamp));
  const vistas = salida.filter((_, k) => t >= e.t_salida[k]);
  const lineas: React.ReactNode[] = [<span key="c"><span style={{color: MENTA}}>{comando.slice(0, Math.min(n, 1))}</span>{comando.slice(1, n)}</span>,
    ...vistas.map((l, k) => <span key={k} style={{background: t >= e.t_remate ? AMARILLO_P : 'transparent', borderRadius: 8, padding: '0 6px'}}>{l}</span>)];
  const yTerm = Math.min(altoEditor + 24, h - 220);
  const max = Math.max(2, Math.floor((h - yTerm - 90) / (tam * 1.3)));
  const alta = Math.min(max, 1 + salida.length);
  return <>
    <div style={{position: 'absolute', left: 10, top: 6, opacity: 0.92}}><Editor t={t} nombre={e.nombre} lineas={codigo} ancho={ancho} tam={tam}/></div>
    <div style={{position: 'absolute', left: 10, top: yTerm, transform: `translateY(${interpolate(t, [e.t_comando - 0.25, e.t_comando], [40, 0], clamp)}px)`}}>
      <Terminal lineas={lineas} ancho={ancho} tam={tam} max={alta}/>
    </div>
    <Lienzo w={w} h={h}><Tilde t={t} desde={e.t_remate} x={w - 150} y={yTerm + 40} tam={100}/></Lienzo>
  </>;
};

// ---------- subtítulos: palabra por palabra, centrados, legibles sobre fondo claro ----------
const Subtitulos: React.FC<{palabras: Palabra[]; t: number}> = ({palabras, t}) => {
  const grupos: Palabra[][] = [];
  for (const w of palabras) {
    const prev = grupos[grupos.length - 1];
    if (!prev || prev.map(x => x.w).join(' ').length + w.w.length > 18 || /[.,:;?!…]$/.test(prev[prev.length - 1].w)) grupos.push([w]); else prev.push(w);
  }
  let k = grupos.findIndex((g, j) => t >= g[0].t0 - 0.05 && t < (grupos[j + 1]?.[0].t0 ?? g[g.length - 1].t1 + 0.3));
  if (k < 0 && grupos.length && t < grupos[0][0].t0) k = 0;
  if (k < 0) return null;
  return <div style={{position: 'absolute', top: 1386, left: 70, width: 940, height: 170, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
    <div style={{background: '#fffdf7f4', border: `5px solid ${TINTA}`, borderRadius: 30, padding: '10px 30px 16px', boxShadow: '0 8px 0 #2b274533',
      fontFamily: SANS, fontWeight: 600, fontSize: 64, lineHeight: 1.1, color: TINTA, textAlign: 'center', whiteSpace: 'nowrap'}}>
      {grupos[k].map((w, i) => {
        // una sola palabra resaltada: la última que ya empezó a sonar
        const suena = t >= w.t0 - 0.03 && !(grupos[k][i + 1] && t >= grupos[k][i + 1].t0 - 0.03) && t < w.t1 + 0.25;
        return <span key={i} style={{display: 'inline-block', margin: '0 0.2em', color: suena ? ROSA : TINTA, transform: suena ? 'scale(1.08)' : undefined}}>{w.w}</span>;
      })}
    </div>
  </div>;
};

// ---------- personaje: el único movimiento al hablar es el parche de la boca ----------
const Personaje: React.FC<{pose: Pose; habla: boolean; cambio: number}> = ({pose, habla, cambio}) => {
  const [x, y, w, h] = pose.boca;
  const rebote = [0.92, 1.08, 0.96, 1.035, 0.99, 1.01][Math.floor(cambio)] ?? 1;
  return <div style={{position: 'relative', width: '100%', height: '100%', transform: `scale(${1 / rebote}, ${rebote})`, transformOrigin: '50% 97.22%'}}>
    <Img src={staticFile(pose.cerrada)} style={{position: 'absolute', width: '100%', height: '100%'}}/>
    {habla && <div style={{position: 'absolute', left: `${x / 960 * 100}%`, top: `${y / 1440 * 100}%`, width: `${w / 960 * 100}%`, height: `${h / 1440 * 100}%`, overflow: 'hidden'}}>
      <Img src={staticFile(pose.abierta)} style={{position: 'absolute', width: `${960 / w * 100}%`, height: `${1440 / h * 100}%`, maxWidth: 'none', left: `${-x / w * 100}%`, top: `${-y / h * 100}%`}}/>
    </div>}
  </div>;
};

// ---------- la clase ----------
export const Clase: React.FC<PropsClase> = ({boca, segmentos: S, pizarra, publico, colores}) => {
  const f = useCurrentFrame(), t = f / FPS;
  if (!S.length) return <AbsoluteFill style={{background: colores.arriba}}/>;
  let i = S.findIndex(s => t >= s.inicio && t < s.fin);
  if (i < 0) i = t < S[0].inicio ? 0 : S.length - 1;
  const s = S[i];
  const PIZ = {x: pizarra[0] + 30, y: pizarra[1] + TOP + 26, w: pizarra[2] - 60, h: pizarra[3] - 52};
  const marco = {x: pizarra[0], y: pizarra[1] + TOP, w: pizarra[2], h: pizarra[3]};

  // plano
  const vigentes = s.planos.filter(p => t >= p.t - 1e-6);
  const plano = vigentes[vigentes.length - 1] ?? s.planos[0];
  const cam = camaraDe(plano.camara, marco);

  // pose (con rebote sólo cuando cambia)
  const poseEn = (k: number, tt: number) => { let p = S[k].pose, d = S[k].inicio; for (const l of S[k].luego) if (tt >= l.t) { p = l.pose; d = l.t; } return [p, d] as [string, number]; };
  let [pose, desdePose] = poseEn(i, t);
  if (i > 0 && desdePose === s.inicio && poseEn(i - 1, S[i - 1].fin)[0] === pose) desdePose = -10;
  const cambio = (t - desdePose) * FPS / 2;
  const habla = boca.some(([a, b]) => t >= a && t < b);
  const respira = Math.sin(t * 1.9) * 4 - (habla ? Math.abs(Math.sin(t * 9)) * 8 : 0);
  const golpePose = interpolate(cambio, [0, 6], [1, 0], clamp);
  const ficha = publico.poses[pose];

  const e = s.escena;
  const primero = i === 0;
  let piz: React.ReactNode = null;
  if (e.tipo === 'pizarra') piz = <Pizarra e={e} t={t} w={PIZ.w} h={PIZ.h} primero={primero}/>;
  else if (e.tipo === 'diagrama') piz = <Diagrama e={e} t={primero ? Math.max(t, e.t.rombo + 0.7) : t} w={PIZ.w} h={PIZ.h}/>;
  else if (e.tipo === 'codigo') piz = <Codigo e={e} t={t} w={PIZ.w} h={PIZ.h} primero={primero}/>;
  else if (e.tipo === 'terminal') piz = <TerminalEscena e={e} t={t} w={PIZ.w} h={PIZ.h}/>;

  return <AbsoluteFill style={{background: colores.arriba, overflow: 'hidden', fontVariantLigatures: 'none'}}>
    <div style={{position: 'absolute', left: 0, top: 0, width: 1080, height: 1920, transformOrigin: '0 0', transform: transformar(cam, plano.t, t)}}>
      <div style={{position: 'absolute', left: 0, top: 0, width: 1080, height: TOP + 2, background: colores.arriba}}/>
      <div style={{position: 'absolute', left: 0, top: TOP + 1616, width: 1080, height: 1920 - TOP - 1616, background: colores.abajo}}/>
      <Img src={staticFile(publico.fondo)} style={{position: 'absolute', left: 0, top: TOP, width: 1080, height: 1620}}/>
      <div style={{position: 'absolute', left: PIZ.x, top: PIZ.y, width: PIZ.w, height: PIZ.h}}>{piz}</div>
      {ficha && <div style={{position: 'absolute', left: PERSO.x, top: PERSO.y, width: PERSO.w, height: PERSO.h, transform: `translateY(${respira - golpePose * 26}px)`, transformOrigin: '50% 100%'}}>
        <Personaje pose={ficha} habla={habla} cambio={cambio}/>
      </div>}
    </div>
    <Subtitulos palabras={s.palabras} t={t}/>
  </AbsoluteFill>;
};
