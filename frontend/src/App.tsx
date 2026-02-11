import React, { useEffect, useRef } from 'react';
import { BrowserRouter as Router, Route, Routes, useLocation } from 'react-router-dom';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera } from '@react-three/drei';
import gsap from 'gsap';
import AIParody from './pages/AIParody';
import YouTubeTrimmer from './pages/YouTubeTrimmer';
import VideoDownloader from './pages/VideoDownloader';
import HomePage from './pages/HomePage';
import Background3D from './components/Background3D';
import PricingPage from './pages/Pricing';
import NavBar from './components/Navbar';
import { colors } from './utils/colors';
import LoginPage from './pages/Login';
import SignupPage from './pages/Signup';
import HistoryPage from './pages/History';
import ProtectedRoute from './components/ProtectedRoute';

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

  useEffect(() => {
    const trailContainer = document.createElement('div');
    trailContainer.style.position = 'fixed';
    trailContainer.style.top = '0';
    trailContainer.style.left = '0';
    trailContainer.style.width = '100%';
    trailContainer.style.height = '100%';
    trailContainer.style.pointerEvents = 'none';
    trailContainer.style.zIndex = '1000';
    document.body.appendChild(trailContainer);

    const maxTrails = 15;
    const trails: HTMLDivElement[] = [];
    const trailColors = [colors.brightRed, colors.vibrantYellow, colors.deepRed, colors.softYellow];

    const handleMouseMove = (event: MouseEvent) => {
      const trail = document.createElement('div');
      trail.style.position = 'absolute';
      trail.style.width = `${Math.random() * 8 + 4}px`;
      trail.style.height = trail.style.width;
      trail.style.left = `${event.clientX}px`;
      trail.style.top = `${event.clientY}px`;
      trail.style.borderRadius = '50%';
      trail.style.backgroundColor = trailColors[Math.floor(Math.random() * trailColors.length)];
      trail.style.transform = 'translate(-50%, -50%)';
      trail.style.boxShadow = `0 0 ${parseInt(trail.style.width, 10) * 2}px ${trail.style.backgroundColor}`;
      trail.style.filter = 'blur(3px)';
      trail.style.mixBlendMode = 'screen';
      trail.style.opacity = '0.7';

      trailContainer.appendChild(trail);
      trails.push(trail);

      if (trails.length > maxTrails) {
        const oldestTrail = trails.shift();
        if (oldestTrail?.parentNode) {
          oldestTrail.parentNode.removeChild(oldestTrail);
        }
      }

      trails.forEach((item) => {
        gsap.to(item, {
          opacity: 0,
          width: parseInt(item.style.width, 10) * 0.5,
          height: parseInt(item.style.height, 10) * 0.5,
          duration: 1,
          onComplete: () => {
            if (item.parentNode) {
              item.parentNode.removeChild(item);
            }
          },
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
    if (!mainRef.current) {
      return;
    }

    gsap.fromTo(mainRef.current, { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.6, ease: 'power2.out' });
  }, [location]);

  return (
    <div className="relative min-h-screen bg-white">
      <div className="fixed inset-0 z-0">
        <Canvas>
          <PerspectiveCamera makeDefault position={[0, 0, 10]} />
          <ambientLight intensity={0.7} />
          <pointLight position={[10, 10, 10]} intensity={1.2} />
          <Background3D showWave={location.pathname !== '/'} />
          <OrbitControls enableZoom={false} enablePan={false} autoRotate autoRotateSpeed={0.5} />
        </Canvas>
      </div>

      <NavBar />

      <main
        ref={mainRef}
        className="relative z-10 mx-auto max-w-7xl px-2 pb-8 pt-20 sm:px-4 sm:pt-24 lg:px-8"
      >
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/pricing" element={<PricingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route
            path="/history"
            element={
              <ProtectedRoute>
                <HistoryPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/ai-parody"
            element={
              <ProtectedRoute>
                <AIParody />
              </ProtectedRoute>
            }
          />
          <Route
            path="/youtube-trimmer"
            element={
              <ProtectedRoute>
                <YouTubeTrimmer />
              </ProtectedRoute>
            }
          />
          <Route
            path="/video-downloader"
            element={
              <ProtectedRoute>
                <VideoDownloader />
              </ProtectedRoute>
            }
          />
        </Routes>
      </main>
    </div>
  );
}

export default App;
