import React, { useEffect, useRef } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Music, Video, FileMusic, Brain } from 'lucide-react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera } from '@react-three/drei';
import gsap from 'gsap';
import AIParody from './pages/AIParody';
import YouTubeTrimmer from './pages/YouTubeTrimmer';
import VideoDownloader from './pages/VideoDownloader';
import Logo3D from './components/Logo3D';
import Background3D from './components/Background3D';

// Define vibrant red and yellow color scheme
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
  black: "#000000",        // Black for important elements
  
  // Light theme additions
  lightGray: "#F0F3F5",    // Light gray for subtle backgrounds
  mediumGray: "#9AA0A6",   // Medium gray for less prominent text
  darkGray: "#353535",     // Dark gray for main text on white background
};

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
      
      <nav className="sticky top-0 z-50 border-b border-gray-200 bg-white/80 backdrop-blur-md"> {/* Changed to white navigation */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Link 
              to="/" 
              className="flex items-center space-x-3 group relative"
              onMouseEnter={(e) => {
                gsap.to(e.currentTarget, {
                  scale: 1.05,
                  duration: 0.3,
                  ease: "power2.out"
                });
              }}
              onMouseLeave={(e) => {
                gsap.to(e.currentTarget, {
                  scale: 1,
                  duration: 0.3,
                  ease: "power2.out"
                });
              }}
            >
              <div className="relative w-10 h-10">
                <Canvas>
                  <PerspectiveCamera makeDefault position={[0, 0, 4]} />
                  <ambientLight intensity={0.5} />
                  <pointLight position={[10, 10, 10]} />
                  <Logo3D />
                </Canvas>
              </div>
              <span 
                className="text-xl font-bold"
                style={{
                  background: `linear-gradient(to right, ${colors.brightRed}, ${colors.vibrantYellow})`,
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                  color: "transparent"
                }}
              >
                IntelliMix
              </span>
            </Link>
            <div className="flex space-x-4">
              <NavLink to="/ai-parody" icon={<FileMusic />} text="AI Music Studio" />
              <NavLink to="/youtube-trimmer" icon={<Music />} text="Audio Mixer" />
              <NavLink to="/video-downloader" icon={<Video />} text="Media Downloader" />
            </div>
          </div>
        </div>
      </nav>

      <main ref={mainRef} className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 pt-24">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/ai-parody" element={<AIParody />} />
          <Route path="/youtube-trimmer" element={<YouTubeTrimmer />} />
          <Route path="/video-downloader" element={<VideoDownloader />} />
        </Routes>
      </main>
    </div>
  );
}

function NavLink({ to, icon, text }: { to: string; icon: React.ReactNode; text: string }) {
  const linkRef = useRef<HTMLAnchorElement>(null);
  const location = useLocation();
  
  // Check if this link matches the current path
  const isActive = location.pathname === to;

  useEffect(() => {
    const link = linkRef.current;
    if (link) {
      const handleMouseEnter = () => {
        // Only animate if not already active
        if (!isActive) {
          gsap.to(link, {
            scale: 1.1,
            duration: 0.3,
            ease: "back.out(1.7)"
          });
        }
      };

      const handleMouseLeave = () => {
        // Only animate if not already active
        if (!isActive) {
          gsap.to(link, {
            scale: 1,
            duration: 0.3,
            ease: "power2.out"
          });
        }
      };

      link.addEventListener('mouseenter', handleMouseEnter);
      link.addEventListener('mouseleave', handleMouseLeave);

      return () => {
        link.removeEventListener('mouseenter', handleMouseEnter);
        link.removeEventListener('mouseleave', handleMouseLeave);
      };
    }
  }, [isActive]); // Re-run when active state changes

  useEffect(() => {
    // Apply the active state animation when component mounts and when isActive changes
    if (linkRef.current && isActive) {
      gsap.to(linkRef.current, {
        scale: 1.1,
        duration: 0.3,
        ease: "back.out(1.7)"
      });
    }
  }, [isActive]);

  return (
    <Link
      ref={linkRef}
      to={to}
      className={`flex items-center space-x-1 px-3 py-2 rounded-xl text-sm font-medium transition-colors relative overflow-hidden ${
        isActive ? 'text-gray-900' : 'text-gray-800'
      }`}
      style={{ 
        backgroundColor: isActive ? `${colors.deepRed}15` : colors.lightGray,
        border: `1px solid ${colors.deepRed}${isActive ? '50' : '30'}`,
        boxShadow: `0 0 ${isActive ? '12px' : '8px'} ${colors.deepRed}${isActive ? '30' : '20'}`
      }}
      onMouseEnter={(e) => {
        if (!isActive) {
          e.currentTarget.style.backgroundColor = `${colors.deepRed}15`;
          e.currentTarget.style.boxShadow = `0 0 12px ${colors.deepRed}30`;
        }
      }}
      onMouseLeave={(e) => {
        if (!isActive) {
          e.currentTarget.style.backgroundColor = colors.lightGray;
          e.currentTarget.style.boxShadow = `0 0 8px ${colors.deepRed}20`;
        }
      }}
    >
      <span className="text-darkGray" style={{ color: isActive ? colors.deepRed : undefined }}>
        {icon}
      </span>
      <span style={{ color: isActive ? colors.deepRed : undefined }}>
        {text}
      </span>
      
      {/* Active indicator */}
      {isActive && (
        <span 
          className="absolute bottom-0 left-1/2 transform -translate-x-1/2 h-0.5 rounded-full"
          style={{ 
            backgroundColor: colors.deepRed,
            width: '60%'
          }}
        ></span>
      )}
    </Link>
  );
}

function HomePage() {
  const featuresRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const descriptionRef = useRef<HTMLParagraphElement>(null);
  const benefitsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (featuresRef.current) {
      gsap.fromTo(
        featuresRef.current.children,
        { y: 50, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          duration: 0.8,
          stagger: 0.2,
          ease: "power3.out",
          scrollTrigger: {
            trigger: featuresRef.current,
            start: "top center+=100",
            toggleActions: "play none none none",
          },
        }
      );
    }

    if (benefitsRef.current) {
      gsap.fromTo(
        benefitsRef.current.children,
        { y: 50, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          duration: 0.8,
          stagger: 0.2,
          ease: "power3.out",
          scrollTrigger: {
            trigger: benefitsRef.current,
            start: "top center+=100",
            toggleActions: "play none none none",
          },
        }
      );
    }

    if (titleRef.current && descriptionRef.current) {
      gsap.fromTo(
        titleRef.current,
        { y: 30, opacity: 0 },
        { y: 0, opacity: 1, duration: 1, ease: "power3.out" }
      );

      gsap.fromTo(
        descriptionRef.current,
        { y: 30, opacity: 0 },
        { y: 0, opacity: 1, duration: 1, delay: 0.3, ease: "power3.out" }
      );
    }
  }, []);

  return (
    <div className="text-center py-12">
      <div className="mb-16">
        {/* Existing title section */}
        <div className="relative inline-block mb-8">
          <div className="w-40 h-40 mx-auto">
            <Canvas>
              <PerspectiveCamera makeDefault position={[0, 0, 4]} />
              <ambientLight intensity={0.5} />
              <pointLight position={[10, 10, 10]} />
              <Logo3D />
            </Canvas>
          </div>
        </div>
        <h1 
          ref={titleRef}
          className="text-7xl font-bold mb-6 tracking-tight text-transparent bg-clip-text"
          style={{
            background: `linear-gradient(to right, ${colors.brightRed}, ${colors.vibrantYellow}, ${colors.brightRed})`,
            backgroundClip: 'text'
          }}
        >
          IntelliMix
        </h1>
        <p 
          ref={descriptionRef}
          className="text-2xl text-gray-700 max-w-3xl mx-auto leading-relaxed"
        >
          Transform your creative vision into reality with our
          <span style={{ color: colors.deepRed }}> AI-powered </span>
          audio suite
        </p>
      </div>

      {/* New benefits section */}
      <div 
        className="max-w-5xl mx-auto mb-24 px-4"
        ref={benefitsRef}
      >
        <div 
          className="rounded-2xl p-8 relative overflow-hidden"
          style={{ 
            backgroundColor: `${colors.deepRed}05`,
            border: `1px solid ${colors.deepRed}30`,
            boxShadow: `0 0 30px ${colors.deepRed}10`
          }}
        >
          <div className="flex flex-col items-center mb-8">
            <div 
              className="w-16 h-16 rounded-full flex items-center justify-center mb-4"
              style={{ 
                background: `linear-gradient(to right, ${colors.brightRed}, ${colors.vibrantYellow})`,
                boxShadow: `0 10px 20px ${colors.brightRed}30`
              }}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="white">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <h2 
              className="text-3xl font-bold mb-2" 
              style={{ color: colors.deepRed }}
            >
              Speed Up Your Workflow
            </h2>
            <div 
              className="w-24 h-1 rounded-full mb-6"
              style={{ background: `linear-gradient(to right, ${colors.brightRed}, ${colors.vibrantYellow})` }}
            ></div>
          </div>

          <div className="grid md:grid-cols-2 gap-8 mb-8">
            <div className="bg-white rounded-xl p-6 shadow-sm">
              <div className="flex items-center mb-4">
                <div 
                  className="w-12 h-12 rounded-full flex items-center justify-center mr-4"
                  style={{ backgroundColor: `${colors.deepRed}15` }}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke={colors.deepRed}>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <h3 className="text-xl font-semibold" style={{ color: colors.deepRed }}>
                  Traditional DAW
                </h3>
              </div>
              <p className="text-gray-700">
                Editing audio in a traditional Digital Audio Workstation can be time-consuming and complex.
              </p>
              <div 
                className="mt-4 py-3 px-4 rounded-lg text-2xl font-bold text-center"
                style={{ backgroundColor: `${colors.deepRed}15`, color: colors.deepRed }}
              >
                27 minutes
              </div>
            </div>

            <div className="bg-white rounded-xl p-6 shadow-sm">
              <div className="flex items-center mb-4">
                <div 
                  className="w-12 h-12 rounded-full flex items-center justify-center mr-4"
                  style={{ 
                    background: `linear-gradient(to right, ${colors.brightRed}, ${colors.vibrantYellow})`,
                  }}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="white">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <h3 className="text-xl font-semibold" style={{ color: colors.deepRed }}>
                  With IntelliMix
                </h3>
              </div>
              <p className="text-gray-700">
                Our AI-powered platform automates the process and delivers professional results instantly.
              </p>
              <div 
                className="mt-4 py-3 px-4 rounded-lg text-2xl font-bold text-center"
                style={{ 
                  background: `linear-gradient(to right, ${colors.brightRed}, ${colors.vibrantYellow})`,
                  color: colors.white 
                }}
              >
                Just 41 seconds
              </div>
            </div>
          </div>

          <div className="flex justify-center">
            <div className="bg-white rounded-xl p-6 shadow-sm max-w-2xl">
              <div className="flex items-start">
                <div 
                  className="w-10 h-10 rounded-full flex items-center justify-center mt-1 mr-4 flex-shrink-0"
                  style={{ backgroundColor: `${colors.vibrantYellow}30` }}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke={colors.vibrantYellow}>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-lg font-medium mb-2" style={{ color: colors.deepRed }}>
                    Based on Real Testing
                  </h3>
                  <p className="text-gray-700 text-left">
                    Our platform completes in <span className="font-bold">41 seconds</span> what would normally take <span className="font-bold">27 minutes</span> in a traditional DAW. That's <span className="font-bold">39x faster</span> workflow for the same quality results, letting you focus on creativity instead of technical tasks.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Key Functionality Highlight */}
      <div className="max-w-5xl mx-auto mb-20 px-4">
        <h2 
          className="text-3xl font-bold mb-12 text-center"
          style={{ color: colors.deepRed }}
        >
          Core Functionality
        </h2>
        <div className="grid md:grid-cols-2 gap-8">
          {/* Intelligent Mashup Creator */}
          <div 
            className="rounded-2xl p-8 relative overflow-hidden"
            style={{ 
              backgroundColor: 'white',
              border: `1px solid ${colors.brightRed}40`,
              boxShadow: `0 10px 30px ${colors.brightRed}15`
            }}
          >
            <div 
              className="absolute -right-16 -top-16 w-40 h-40 rounded-full opacity-10"
              style={{ background: `radial-gradient(circle, ${colors.brightRed}, transparent)` }}
            ></div>
            
            <div className="flex items-start mb-6">
              <div 
                className="w-14 h-14 rounded-lg flex items-center justify-center mr-4 flex-shrink-0"
                style={{ 
                  background: `linear-gradient(135deg, ${colors.brightRed}, ${colors.reddishOrange})`,
                  boxShadow: `0 6px 12px ${colors.brightRed}30`
                }}
              >
                <Brain className="w-8 h-8 text-white" />
              </div>
              <div>
                <h3 
                  className="text-xl font-bold mb-1"
                  style={{ color: colors.brightRed }}
                >
                  Intelligent Mashup Creator
                </h3>
                <p className="text-gray-600">Create amazing music transformations with just a prompt</p>
              </div>
            </div>
            
            <div className="pl-18">
              <ul className="space-y-3 text-gray-700">
                <li className="flex items-start">
                  <span 
                    className="w-5 h-5 rounded-full flex items-center justify-center mr-2 mt-0.5 flex-shrink-0"
                    style={{ backgroundColor: `${colors.brightRed}20` }}
                  >
                    <span 
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: colors.brightRed }}
                    ></span>
                  </span>
                  <span>Automatically creates mashups from simple text prompts</span>
                </li>
                <li className="flex items-start">
                  <span 
                    className="w-5 h-5 rounded-full flex items-center justify-center mr-2 mt-0.5 flex-shrink-0"
                    style={{ backgroundColor: `${colors.brightRed}20` }}
                  >
                    <span 
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: colors.brightRed }}
                    ></span>
                  </span>
                  <span>AI understands musical styles, genres, and instruments</span>
                </li>
                <li className="flex items-start">
                  <span 
                    className="w-5 h-5 rounded-full flex items-center justify-center mr-2 mt-0.5 flex-shrink-0"
                    style={{ backgroundColor: `${colors.brightRed}20` }}
                  >
                    <span 
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: colors.brightRed }}
                    ></span>
                  </span>
                  <span>Generate genre-bending remixes without technical knowledge</span>
                </li>
              </ul>
            </div>
          </div>
          
          {/* Batch Processing Mixer */}
          <div 
            className="rounded-2xl p-8 relative overflow-hidden"
            style={{ 
              backgroundColor: 'white',
              border: `1px solid ${colors.vibrantYellow}40`,
              boxShadow: `0 10px 30px ${colors.vibrantYellow}15`
            }}
          >
            <div 
              className="absolute -right-16 -top-16 w-40 h-40 rounded-full opacity-10"
              style={{ background: `radial-gradient(circle, ${colors.vibrantYellow}, transparent)` }}
            ></div>
            
            <div className="flex items-start mb-6">
              <div 
                className="w-14 h-14 rounded-lg flex items-center justify-center mr-4 flex-shrink-0"
                style={{ 
                  background: `linear-gradient(135deg, ${colors.vibrantYellow}, ${colors.softYellow})`,
                  boxShadow: `0 6px 12px ${colors.vibrantYellow}30`
                }}
              >
                <Music className="w-8 h-8 text-white" />
              </div>
              <div>
                <h3 
                  className="text-xl font-bold mb-1"
                  style={{ color: colors.vibrantYellow }}
                >
                  Batch Processing Mixer
                </h3>
                <p className="text-gray-600">Our core technology for processing multiple tracks efficiently</p>
              </div>
            </div>
            
            <div className="pl-18">
              <ul className="space-y-3 text-gray-700">
                <li className="flex items-start">
                  <span 
                    className="w-5 h-5 rounded-full flex items-center justify-center mr-2 mt-0.5 flex-shrink-0"
                    style={{ backgroundColor: `${colors.vibrantYellow}20` }}
                  >
                    <span 
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: colors.vibrantYellow }}
                    ></span>
                  </span>
                  <span>Process dozens of tracks simultaneously with exact timestamps</span>
                </li>
                <li className="flex items-start">
                  <span 
                    className="w-5 h-5 rounded-full flex items-center justify-center mr-2 mt-0.5 flex-shrink-0"
                    style={{ backgroundColor: `${colors.vibrantYellow}20` }}
                  >
                    <span 
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: colors.vibrantYellow }}
                    ></span>
                  </span>
                  <span>Import via CSV for mass processing of audio cuts</span>
                </li>
                <li className="flex items-start">
                  <span 
                    className="w-5 h-5 rounded-full flex items-center justify-center mr-2 mt-0.5 flex-shrink-0"
                    style={{ backgroundColor: `${colors.vibrantYellow}20` }}
                  >
                    <span 
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: colors.vibrantYellow }}
                    ></span>
                  </span>
                  <span>Save hours of manual editing with our automated workflow</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <div ref={featuresRef} className="grid md:grid-cols-3 gap-8 mt-16">
        {/* Existing feature cards */}
        <FeatureCard
          icon={<FileMusic className="w-12 h-12" />}
          title="AI Music Studio"
          description="Create unique transformations of songs using advanced AI. Perfect for remixes, covers, and creative experiments."
          link="/ai-parody"
          color={colors.brightRed}
        />
        <FeatureCard
          icon={<Music className="w-12 h-12" />}
          title="Audio Mixer"
          description="Extract and edit specific portions from audio tracks. Supports batch processing for efficient workflows."
          link="/youtube-trimmer"
          color={colors.vibrantYellow}
        />
        <FeatureCard
          icon={<Video className="w-12 h-12" />}
          title="Media Downloader"
          description="Download high-quality audio and video content. Optimized for the best possible quality."
          link="/video-downloader"
          color={colors.deepRed}
        />
      </div>
    </div>
  );
}

function FeatureCard({ icon, title, description, link, color }: {
  icon: React.ReactNode;
  title: string;
  description: string;
  link: string;
  color: string;
}) {
  const cardRef = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    const card = cardRef.current;
    if (card) {
      const handleMouseMove = (e: MouseEvent) => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        const rotateX = (y - rect.height / 2) / 20;
        const rotateY = (rect.width / 2 - x) / 20;

        gsap.to(card, {
          rotateX: rotateX,
          rotateY: rotateY,
          duration: 0.5,
          ease: "power2.out",
        });
      };

      const handleMouseLeave = () => {
        gsap.to(card, {
          rotateX: 0,
          rotateY: 0,
          duration: 0.5,
          ease: "power2.out",
        });
      };

      card.addEventListener('mousemove', handleMouseMove);
      card.addEventListener('mouseleave', handleMouseLeave);

      return () => {
        card.removeEventListener('mousemove', handleMouseMove);
        card.removeEventListener('mouseleave', handleMouseLeave);
      };
    }
  }, []);

  // Determine the gradient color based on the card's theme color
  const getGradientColor = () => {
    // Use the passed color but ensure it's in the red/yellow theme
    if (color === colors.brightRed) {
      return `linear-gradient(to bottom right, white, ${colors.brightRed}15)`;
    } else if (color === colors.vibrantYellow) {
      return `linear-gradient(to bottom right, white, ${colors.vibrantYellow}15)`;
    } else if (color === colors.deepRed) {
      return `linear-gradient(to bottom right, white, ${colors.deepRed}15)`;
    } else {
      // Default fallback using the input color
      return `linear-gradient(to bottom right, white, ${color}15)`;
    }
  };

  return (
    <Link 
      ref={cardRef} 
      to={link} 
      className="block group rounded-2xl feature-card transform transition-all duration-300 hover:-translate-y-1 perspective-1000"
    >
      <div 
        className="bg-white backdrop-blur-sm rounded-2xl p-8 relative overflow-hidden h-full transition-all duration-300"
        style={{ 
          border: `1px solid ${color}30`,
          boxShadow: `0 0 15px ${color}20`
        }}
        onMouseEnter={(e) => {
          // Use the explicit gradient function to ensure correct colors
          e.currentTarget.style.background = getGradientColor();
          e.currentTarget.style.borderColor = `${color}60`;
          e.currentTarget.style.boxShadow = `0 0 25px ${color}30`;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'white';
          e.currentTarget.style.borderColor = `${color}30`;
          e.currentTarget.style.boxShadow = `0 0 15px ${color}20`;
        }}
      >
        <div className="relative z-10">
          <div className="mb-4 transform transition-transform duration-300 ease-out group-hover:scale-110">
            <div style={{ color: color }} className="transition-colors duration-300">
              <div className="flex justify-center">
                {React.cloneElement(icon as React.ReactElement, {
                  className: "w-12 h-12"
                })}
              </div>
            </div>
          </div>
          <h3 
            className="text-xl font-semibold mb-2 transition-colors duration-300"
            style={{ color }}
          >
            {title}
          </h3>
          <p className="text-gray-700 group-hover:text-gray-900 transition-colors duration-300">
            {description}
          </p>
        </div>
      </div>
    </Link>
  );
}

export default App;