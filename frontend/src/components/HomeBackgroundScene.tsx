import React from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera } from '@react-three/drei';
import Background3D from './Background3D';

export default function HomeBackgroundScene() {
  return (
    <Canvas dpr={[1, 1.5]}>
      <PerspectiveCamera makeDefault position={[0, 0, 10]} />
      <ambientLight intensity={0.7} />
      <pointLight position={[10, 10, 10]} intensity={1.1} />
      <Background3D showWave />
      <OrbitControls enableZoom={false} enablePan={false} autoRotate autoRotateSpeed={0.35} />
    </Canvas>
  );
}
