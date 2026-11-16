import React from 'react';
import {Composition} from 'remotion';
import {Clase, PropsClase} from './Clase';

const FPS = 30;
const vacio: PropsClase = {duracion: 2, boca: [], segmentos: [], pizarra: [54, 103, 972, 764],
  publico: {fondo: 'fondo.png', poses: {}}, colores: {arriba: '#fef4df', abajo: '#bfe7fa'}};

export const Raiz: React.FC = () => (
  <Composition id="Clase" component={Clase} width={1080} height={1920} fps={FPS} durationInFrames={60}
    defaultProps={vacio}
    calculateMetadata={({props}) => ({durationInFrames: Math.max(1, Math.ceil(props.duracion * FPS))})}/>
);
