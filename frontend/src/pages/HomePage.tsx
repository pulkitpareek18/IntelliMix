import React, { useEffect, useRef } from 'react';
import { Music, Video, FileMusic, Brain } from 'lucide-react';
import { Canvas } from '@react-three/fiber';
import { PerspectiveCamera } from '@react-three/drei';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import Logo3D from '../components/Logo3D';
import FeatureCard from '../components/FeatureCard';

// Register ScrollTrigger plugin
gsap.registerPlugin(ScrollTrigger);

// Define color palette for the red and yellow theme
const colors = {
  brightRed: "#f4483a",       // Primary accent
  slightlyDarkerRed: "#f45444", // Secondary accent
  deepRed: "#d24d34",         // Emphasis/CTA
  reddishOrange: "#d14324",   // Highlight
  vividRed: "#f13521",        // Attention-grabbing
  vibrantYellow: "#ffb92b",   // Buttons/highlights
  softYellow: "#f7e5a0",      // Subtle background
  paleYellow: "#ffe09c",      // Secondary background
  white: "#FFFFFF",
  black: "#000000",
  softRed: "#fee2e1",         // Very light red background
  softerRed: "#fbeae9",       // Even lighter red for larger areas
  textDark: "#444444"         // Softer than pure black for text
};

function HomePage() {
  const featuresRef = useRef(null);
  const titleRef = useRef(null);
  const descriptionRef = useRef(null);
  const benefitsRef = useRef(null);

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
    <div className="text-center py-6 sm:py-12">
      <div className="mb-8 sm:mb-16">
        {/* Existing title section */}
        <div className="relative inline-block mb-6 sm:mb-8">
          <div className="w-32 h-32 sm:w-40 sm:h-40 mx-auto">
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
          className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold mb-4 sm:mb-6 tracking-tight text-transparent bg-clip-text px-4"
          style={{
            background: `linear-gradient(to right, ${colors.brightRed}, ${colors.vibrantYellow}, ${colors.brightRed})`,
            backgroundClip: 'text'
          }}
        >
          IntelliMix
        </h1>
        <p 
          ref={descriptionRef}
          className="text-lg sm:text-xl md:text-2xl text-gray-700 max-w-3xl mx-auto leading-relaxed px-4"
        >
          Transform your creative vision into reality with our
          <span style={{ color: colors.deepRed }}> AI-powered </span>
          audio suite
        </p>
      </div>

      {/* Benefits section */}
      <div 
        className="max-w-5xl mx-auto mb-12 sm:mb-24 px-4"
        ref={benefitsRef}
      >
        <div 
          className="rounded-2xl p-6 sm:p-8 relative overflow-hidden"
          style={{ 
            backgroundColor: `${colors.deepRed}05`,
            border: `1px solid ${colors.deepRed}30`,
            boxShadow: `0 0 30px ${colors.deepRed}10`
          }}
        >
          <div className="flex flex-col items-center mb-6 sm:mb-8">
            <div 
              className="w-12 h-12 sm:w-16 sm:h-16 rounded-full flex items-center justify-center mb-4"
              style={{ 
                background: `linear-gradient(to right, ${colors.brightRed}, ${colors.vibrantYellow})`,
                boxShadow: `0 10px 20px ${colors.brightRed}30`
              }}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 sm:h-8 sm:w-8" fill="none" viewBox="0 0 24 24" stroke="white">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <h2 
              className="text-2xl sm:text-3xl font-bold mb-2" 
              style={{ color: colors.deepRed }}
            >
              Speed Up Your Workflow
            </h2>
            <div 
              className="w-16 sm:w-24 h-1 rounded-full mb-6"
              style={{ background: `linear-gradient(to right, ${colors.brightRed}, ${colors.vibrantYellow})` }}
            ></div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 sm:gap-8 mb-6 sm:mb-8">
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
      <div className="max-w-5xl mx-auto mb-12 sm:mb-20 px-4">
        <h2 
          className="text-2xl sm:text-3xl font-bold mb-8 sm:mb-12 text-center"
          style={{ color: colors.deepRed }}
        >
          Core Functionality
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 sm:gap-8">
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

      <div ref={featuresRef} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8 mt-12 sm:mt-16">
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

export default HomePage;