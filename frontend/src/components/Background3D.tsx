import { useRef, useMemo, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import { Sphere, MeshDistortMaterial, Box, Trail } from '@react-three/drei';
import { Group, Vector3, MathUtils, Color } from 'three';
import { useSpring, animated } from '@react-spring/three';

const AnimatedSphere = animated(Sphere);
const AnimatedBox = animated(Box);

// Define vibrant red and yellow color palette
const colors = {
  // Red spectrum
  brightRed: "#f4483a",    // Primary accent or alert color
  slightlyDarkerRed: "#f45444", // Secondary accent or button color
  deepRed: "#d24d34",      // Emphasis or call-to-action color
  reddishOrange: "#d14324", // Highlight or warning color
  vividRed: "#f13521",     // Attention-grabbing elements
  
  // Yellow spectrum
  vibrantYellow: "#ffb92b", // Buttons, highlights, or warning
  softYellow: "#f7e5a0",   // Subtle background or hover effects
  paleYellow: "#ffe09c",   // Secondary background or muted accents
  
  // Base colors
  white: "#FFFFFF",        // Pure white for minimal elements
  black: "#ffffff",        // Black for important elements
};

const createWavePoints = (count: number, radius: number) => {
  return Array.from({ length: count }, (_, i) => {
    const angle = (i / count) * Math.PI * 2;
    return new Vector3(
      Math.cos(angle) * radius,
      Math.sin(angle) * radius,
      0
    );
  });
};

export default function Background3D() {
  const groupRef = useRef<Group>(null);
  const wavePointsRef = useRef<Vector3[]>([]);
  const particlesRef = useRef<Group>(null);

  // Create wave points
  const wavePoints = useMemo(() => createWavePoints(24, 15), []);
  wavePointsRef.current = wavePoints;

  // Create particles with vibrant colors
  const particles = useMemo(() =>
    Array.from({ length: 100 }, () => ({
      position: new Vector3(
        MathUtils.randFloatSpread(40),
        MathUtils.randFloatSpread(40),
        MathUtils.randFloatSpread(40)
      ),
      scale: MathUtils.randFloat(0.1, 0.4),
      speed: MathUtils.randFloat(0.2, 0.8),
      rotationSpeed: MathUtils.randFloat(-0.2, 0.2),
      phase: Math.random() * Math.PI * 2,
      // Assign a weighted random color from our vibrant palette
      color: (() => {
        const palette = [
          colors.brightRed, colors.slightlyDarkerRed, colors.deepRed, 
          colors.reddishOrange, colors.vividRed,
          colors.vibrantYellow, colors.softYellow, colors.paleYellow,
          colors.white
        ];
        // Weight colors to create vibrant effect
        const weights = [3, 2, 2, 2, 3, 3, 2, 2, 1]; // Higher numbers = more common
        let totalWeight = weights.reduce((a, b) => a + b, 0);
        let random = Math.random() * totalWeight;
        
        for (let i = 0; i < weights.length; i++) {
          if (random < weights[i]) return palette[i];
          random -= weights[i];
        }
        return palette[0];
      })()
    })), [colors]
  );

  // Animation spring - energetic for vibrant theme
  const springs = useSpring({
    scale: [1, 1, 1],
    from: { scale: [0, 0, 0] },
    config: { mass: 1, tension: 320, friction: 40 }, // More energetic spring
  });

  useFrame((state) => {
    const time = state.clock.getElapsedTime();

    // Animate wave points with more energetic waves
    wavePointsRef.current.forEach((point, i) => {
      const angle = (i / wavePointsRef.current.length) * Math.PI * 2;
      const amplitude = Math.sin(time * 0.4 + angle) * 2.5; // More pronounced waves
      point.y = Math.sin(angle) * 15 + amplitude;
    });

    // Animate particles with dynamic movement
    if (particlesRef.current) {
      particles.forEach((particle, i) => {
        const mesh = particlesRef.current!.children[i];
        if (mesh) {
          // More dynamic orbital movement
          const orbitSpeed = particle.speed * 0.7;
          const radius = particle.position.length();
          const angle = time * orbitSpeed;

          mesh.position.x = Math.cos(angle) * radius;
          mesh.position.z = Math.sin(angle) * radius;
          mesh.position.y = Math.sin(time * particle.speed + particle.phase) * 5;

          // More active rotation
          mesh.rotation.x += particle.rotationSpeed * 0.008;
          mesh.rotation.y += particle.rotationSpeed * 0.007;
          mesh.rotation.z += particle.rotationSpeed * 0.005;
        }
      });
    }

    // Rotate entire scene with slightly more energy
    if (groupRef.current) {
      groupRef.current.rotation.y = time * 0.04;
      groupRef.current.rotation.x = Math.sin(time * 0.07) * 0.09;
      groupRef.current.rotation.z = Math.cos(time * 0.06) * 0.03;
    }
  });

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (groupRef.current) {
        groupRef.current.clear();
      }
    };
  }, []);

  return (
    <group ref={groupRef} position={[0, 0, -20]}>
      {/* Audio wave visualization with vibrant color scheme */}
      {wavePointsRef.current.map((point, i) => (
        <Trail
          key={i}
          width={2.2}
          length={6}
          color={new Color(
            i % 5 === 0 ? colors.brightRed : 
            i % 5 === 1 ? colors.vibrantYellow : 
            i % 5 === 2 ? colors.deepRed : 
            i % 5 === 3 ? colors.softYellow : 
            colors.vividRed
          )}
          attenuation={(t) => t * t}
        >
          <AnimatedSphere
            position={point}
            scale={springs.scale.to(s => s * 0.2)}
          >
            <MeshDistortMaterial
              color={
                i % 5 === 0 ? colors.brightRed : 
                i % 5 === 1 ? colors.vibrantYellow : 
                i % 5 === 2 ? colors.deepRed : 
                i % 5 === 3 ? colors.softYellow : 
                colors.vividRed
              }
              speed={2.2}
              distort={0.18}  // More distortion for dynamic effect
              radius={1}
              roughness={0.12}
              metalness={0.75}
            />
          </AnimatedSphere>
        </Trail>
      ))}

      {/* Floating particles with vibrant color scheme */}
      <group ref={particlesRef}>
        {particles.map((particle, i) => (
          <AnimatedBox
            key={i}
            position={particle.position}
            scale={springs.scale.to(s => s * particle.scale)}
            args={[0.6, 0.6, 0.6, 4, 4, 4]}
          >
            <meshPhongMaterial
              color={particle.color}
              opacity={0.85}  // Higher opacity for more vibrant appearance
              transparent
              shininess={140}  // Higher shininess for more vibrant reflections
              emissive={particle.color}
              emissiveIntensity={0.3} // Add some glow effect
            />
          </AnimatedBox>
        ))}
      </group>
    </group>
  );
}