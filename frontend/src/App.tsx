import React, { useEffect, useRef } from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera } from '@react-three/drei';
import gsap from 'gsap';
import AIParody from './pages/AIParody';
import YouTubeTrimmer from './pages/YouTubeTrimmer';
import VideoDownloader from './pages/VideoDownloader';
import HomePage from './pages/HomePage';
import Background3D from './components/Background3D';
import PricingPage from './pages/Pricing';
import AboutUsPage from './pages/AboutUs';
import NavBar from './components/Navbar';
import { colors } from './utils/colors'; // Import from centralized file

function App() {
  return (
    <Router>
      <AppContent />
    </Router>
  );
}

function AppContent() {
  const location = useLocation();
  const mainRef = useRef<HTMLDivElement>(null);

  // Add cursor trail effect
  useEffect(() => {
    // Create cursor trail container
    const trailContainer = document.createElement('div');
    trailContainer.style.position = 'fixed';
    trailContainer.style.top = '0';
    trailContainer.style.left = '0';
    trailContainer.style.width = '100%';
    trailContainer.style.height = '100%';
    trailContainer.style.pointerEvents = 'none';
    trailContainer.style.zIndex = '1000';
    document.body.appendChild(trailContainer);

    // Trail settings
    const maxTrails = 15;
    const trails: HTMLDivElement[] = [];
    // Updated trail colors to match our vibrant red and yellow theme
    const trailColors = [colors.brightRed, colors.vibrantYellow, colors.deepRed, colors.softYellow];
    let mouseX = 0;
    let mouseY = 0;

    // Track mouse position
    const handleMouseMove = (e: MouseEvent) => {
      mouseX = e.clientX;
      mouseY = e.clientY;

      // Create a new trail element
      const trail = document.createElement('div');
      trail.style.position = 'absolute';
      trail.style.width = `${Math.random() * 8 + 4}px`;
      trail.style.height = trail.style.width;
      trail.style.left = `${mouseX}px`;
      trail.style.top = `${mouseY}px`;
      trail.style.borderRadius = '50%';
      trail.style.backgroundColor = trailColors[Math.floor(Math.random() * trailColors.length)];
      trail.style.transform = 'translate(-50%, -50%)';
      trail.style.boxShadow = `0 0 ${parseInt(trail.style.width) * 2}px ${trail.style.backgroundColor}`;
      trail.style.filter = 'blur(3px)';
      trail.style.mixBlendMode = 'screen';
      trail.style.opacity = '0.7'; // Slightly reduced opacity for white background

      trailContainer.appendChild(trail);
      trails.push(trail);

      // Limit the number of trails
      if (trails.length > maxTrails) {
        const oldestTrail = trails.shift();
        if (oldestTrail && oldestTrail.parentNode) {
          oldestTrail.parentNode.removeChild(oldestTrail);
        }
      }

      // Animate each trail
      trails.forEach((item, index) => {
        gsap.to(item, {
          opacity: 0,
          width: parseInt(item.style.width) * 0.5,
          height: parseInt(item.style.height) * 0.5,
          duration: 1,
          onComplete: () => {
            if (item.parentNode) {
              item.parentNode.removeChild(item);
              trails.splice(trails.indexOf(item), 1);
            }
          }
        });
      });
    };

    window.addEventListener('mousemove', handleMouseMove);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      if (trailContainer.parentNode) {
        trailContainer.parentNode.removeChild(trailContainer);
      }
    };
  }, []);

  useEffect(() => {
    if (mainRef.current) {
      gsap.fromTo(
        mainRef.current,
        { opacity: 0, y: 20 },
        { opacity: 1, y: 0, duration: 0.6, ease: "power2.out" }
      );
    }
  }, [location]);

  return (
    <div className="min-h-screen bg-white relative"> {/* Changed to white background */}
      <div className="fixed inset-0 z-0">
        <Canvas>
          <PerspectiveCamera makeDefault position={[0, 0, 10]} />
          <ambientLight intensity={0.7} /> {/* Increased light intensity */}
          <pointLight position={[10, 10, 10]} intensity={1.2} /> {/* Increased light intensity */}
          <Background3D />
          <OrbitControls enableZoom={false} enablePan={false} autoRotate autoRotateSpeed={0.5} />
        </Canvas>
      </div>
      
      {/* Using the NavBar component */}
      <NavBar />

      <main ref={mainRef} className="relative z-10 max-w-7xl mx-auto px-2 sm:px-4 md:px-6 lg:px-8 py-4 sm:py-6 lg:py-8 pt-20 sm:pt-24">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/ai-parody" element={<AIParody />} />
          <Route path="/youtube-trimmer" element={<YouTubeTrimmer />} />
          <Route path="/video-downloader" element={<VideoDownloader />} />
          <Route path="/pricing" element={<PricingPage />} />
          <Route path="/about" element={<AboutUsPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;