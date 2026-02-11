import { useRef, useEffect, useState } from 'react';
import { useFrame, useLoader, Canvas } from '@react-three/fiber';
import { Plane } from '@react-three/drei';
import { Group, Mesh, TextureLoader, MeshStandardMaterial } from 'three';
import { useSpring, animated } from '@react-spring/three';
import gsap from 'gsap';
import { Suspense } from 'react';
import logo from "/src/assets/logo.png"

const AnimatedPlane = animated(Plane);

export default function Logo3D() {
  const groupRef = useRef<Group>(null);
  const materialRef = useRef<MeshStandardMaterial>(null);
  const [loaded, setLoaded] = useState(false);
  
  // Load the logo texture
  const texture = useLoader(TextureLoader, logo);
  
  // Animation spring for initial appearance
  const springs = useSpring({
    scale: loaded ? [1, 1, 1] : [0, 0, 0],
    rotation: loaded ? [0, 0, 0] : [0, -Math.PI, 0],
    config: { mass: 1, tension: 280, friction: 20 },
  });
  
  useEffect(() => {
    // Mark as loaded to trigger spring animation
    setLoaded(true);
    
    if (groupRef.current) {
      // Create a floating animation
      gsap.to(groupRef.current.position, {
        y: 0.2,
        duration: 2.5,
        ease: "sine.inOut",
        yoyo: true,
        repeat: -1
      });
      
      // Subtle rotation animation
      gsap.to(groupRef.current.rotation, {
        y: Math.PI * 0.1,
        duration: 3,
        ease: "power1.inOut",
        yoyo: true,
        repeat: -1
      });
    }
    
    if (materialRef.current) {
      // Pulsating glow effect
      gsap.to(materialRef.current, {
        emissiveIntensity: 1.5,
        duration: 2,
        yoyo: true,
        repeat: -1,
        ease: "sine.inOut",
      });
    }
  }, [loaded]);
  
  // Continuous subtle animation on each frame
  useFrame((state) => {
    if (groupRef.current) {
      // Add subtle movement based on mouse position
      const mouseX = state.mouse.x * 0.1;
      const mouseY = state.mouse.y * 0.1;
      
      groupRef.current.rotation.x = mouseY * 0.2;
      groupRef.current.rotation.y = mouseX * 0.3;
      
      // Add subtle breathing effect
      groupRef.current.scale.x = 1 + Math.sin(state.clock.elapsedTime * 0.8) * 0.03;
      groupRef.current.scale.y = 1 + Math.sin(state.clock.elapsedTime * 0.8) * 0.03;
    }
  });
  
  return (
    <animated.group 
      ref={groupRef} 
      rotation={springs.rotation as unknown as [number, number, number]}
    >
      {/* Main logo */}
      <AnimatedPlane 
        args={[3, 3]} // Width and height of the plane
        scale={springs.scale as unknown as [number, number, number]}
      >
        <meshStandardMaterial 
          ref={materialRef}
          map={texture} 
          transparent={true}
          emissive="#ffffff"
          emissiveIntensity={0.5}
          emissiveMap={texture}
        />
      </AnimatedPlane>
      
      {/* Glow effect plane (slightly larger) */}
      <Plane
        args={[3.2, 3.2]}
        position={[0, 0, -0.1]}
      >
        <meshBasicMaterial
          map={texture}
          transparent={true}
          opacity={0.2}
          color="#f4483a" // Use the brand's red color for the glow
        />
      </Plane>
      
      {/* Shadow plane */}
      <Plane
        args={[4, 4]}
        position={[0.2, -0.2, -0.2]}
        rotation={[0, 0, 0]}
      >
        <meshBasicMaterial
          transparent={true}
          opacity={0.1}
          color="#000000"
        />
      </Plane>
      
      {/* Highlight particles */}
      {[...Array(5)].map((_, i) => (
        <AnimatedParticle key={i} index={i} />
      ))}
    </animated.group>
  );
}

// Small animated particle that orbits around the logo
function AnimatedParticle({ index }: { index: number }) {
  const ref = useRef<Mesh>(null);
  
  useFrame((state) => {
    if (ref.current) {
      // Calculate position on an elliptical path
      const t = state.clock.elapsedTime * 0.5 + index;
      const x = Math.cos(t) * 1.8;
      const y = Math.sin(t) * 1.2;
      const z = Math.sin(t * 2) * 0.3;
           
      ref.current.position.set(x, y, z);
      
      // Pulsate the size
      const scale = 0.1 + Math.sin(t * 3) * 0.05;
      ref.current.scale.set(scale, scale, scale);
    }
  });
  
  return (
    <mesh ref={ref}>
      <sphereGeometry args={[0.1, 16, 16]} />
      <meshBasicMaterial color="#ffb92b" transparent opacity={0.7} />
    </mesh>
  );
}

export function LogoContainer() {
  return (
    <div className="w-full h-80">
      <Canvas>
        <ambientLight intensity={0.5} />
        <pointLight position={[10, 10, 10]} />
        <Suspense fallback={null}>
          <Logo3D />
        </Suspense>
      </Canvas>
    </div>
  );
}
