import React, { useEffect, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Music, Video, FileMusic, DollarSign, Users } from 'lucide-react';
import { Canvas } from '@react-three/fiber';
import { PerspectiveCamera } from '@react-three/drei';
import gsap from 'gsap';
import Logo3D from './Logo3D';
import { colors } from '../utils/colors'; // Import centralized colors

function NavBar() {
  return (
    <nav className="sticky top-0 z-50 border-b border-gray-200 bg-white/80 backdrop-blur-md">
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
            <NavLink to="/pricing" icon={<DollarSign />} text="Pricing" />
            <NavLink to="/about" icon={<Users />} text="About Us" />
          </div>
        </div>
      </div>
    </nav>
  );
}

interface NavLinkProps {
  to: string;
  icon: React.ReactNode;
  text: string;
}

function NavLink({ to, icon, text }: NavLinkProps) {
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

export default NavBar;