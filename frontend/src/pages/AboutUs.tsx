import React from 'react';

const colors = {
  brightRed: "#f4483a",       // Primary accent
  deepRed: "#d24d34",         // Emphasis/CTA
  vibrantYellow: "#ffb92b",   // Buttons/highlights
  textDark: "#444444"         // Softer than pure black for text
};

const AboutUsPage = () => {
  return (
    <div className="max-w-4xl mx-auto py-12 px-4">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold mb-3" style={{ color: colors.deepRed }}>About IntelliMix</h1>
        <div className="w-24 h-1 mx-auto rounded-full mb-6" style={{ backgroundColor: colors.vibrantYellow }}></div>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto">
          Engineering solutions for real-world audio challenges
        </p>
      </div>
      
      <div className="backdrop-blur-sm rounded-2xl p-8 border border-white/20 mb-12" 
           style={{ background: 'rgba(255, 255, 255, 0.15)' }}>
        <h2 className="text-2xl font-semibold mb-4" style={{ color: colors.brightRed }}>Our Mission</h2>
        <p className="text-gray-700 mb-6">
        At IntelliMix, we're dedicated to revolutionizing audio processing through intelligent automation. 
        Our mission is to empower content creators, musicians, and audio professionals by eliminating 
        technical barriers and time-consuming tasks. We combine cutting-edge AI with practical engineering 
        to create tools that enhance creativity, improve productivity, and deliver professional-quality 
        audio results with minimal effort. By making advanced audio technology accessible to everyone, 
        we aim to democratize professional sound production and help creators focus on what matters most—their art.
        </p>
        
        <h2 className="text-2xl font-semibold mb-4" style={{ color: colors.brightRed }}>Our Story</h2>
        <p className="text-gray-700 mb-6">
            IntelliMix was born from a real challenge we faced during our college festival. As audio volunteers, we needed to create custom dance tracks for over 200 participants, each requiring multiple songs to be downloaded, split, merged, and crossfaded. Using traditional digital audio workstations, each track took approximately 40 minutes to produce, resulting in nearly two weeks of tedious editing work. This experience revealed a clear opportunity: automate the repetitive aspects of audio production. Today, what once took us 40 minutes per track can be accomplished in just 40 seconds with IntelliMix, allowing creators to focus on creativity rather than technical tasks.
        </p>
      </div>
      
    <h2 className="text-3xl font-bold mb-8 text-center" style={{ color: colors.deepRed }}>The Engineering Team</h2>
    <div className="grid md:grid-cols-2 gap-6">
      <div className="backdrop-blur-sm rounded-xl p-6 border border-white/20" 
         style={{ background: 'rgba(255, 255, 255, 0.15)' }}>
        <div className="w-24 h-24 rounded-full bg-gradient-to-tr from-red-400 to-red-500 mx-auto mb-4 flex items-center justify-center text-white text-3xl font-bold">PP</div>
        <h3 className="text-xl font-semibold text-center" style={{ color: colors.brightRed }}>Pulkit Pareek</h3>
        <p className="text-gray-500 text-center mb-2">Development & Implementation</p>
        <p className="text-gray-700 text-center">Leads the core development and implementation of IntelliMix's audio processing technologies.</p>
      </div>
      
      <div className="backdrop-blur-sm rounded-xl p-6 border border-white/20" 
         style={{ background: 'rgba(255, 255, 255, 0.15)' }}>
        <div className="w-24 h-24 rounded-full bg-gradient-to-tr from-yellow-400 to-yellow-500 mx-auto mb-4 flex items-center justify-center text-white text-3xl font-bold">CB</div>
        <h3 className="text-xl font-semibold text-center" style={{ color: colors.vibrantYellow }}>Chetna Bhardwaj</h3>
        <p className="text-gray-500 text-center mb-2">Research & Development</p>
        <p className="text-gray-700 text-center">Drives innovation through research and development of new audio algorithms and AI integration.</p>
      </div>
      
      <div className="backdrop-blur-sm rounded-xl p-6 border border-white/20" 
         style={{ background: 'rgba(255, 255, 255, 0.15)' }}>
        <div className="w-24 h-24 rounded-full bg-gradient-to-tr from-red-500 to-red-600 mx-auto mb-4 flex items-center justify-center text-white text-3xl font-bold">DR</div>
        <h3 className="text-xl font-semibold text-center" style={{ color: colors.deepRed }}>Devesh Rawat</h3>
        <p className="text-gray-500 text-center mb-2">Deployment Optimization</p>
        <p className="text-gray-700 text-center">Specializes in optimizing system performance and streamlining deployment processes.</p>
      </div>

      <div className="backdrop-blur-sm rounded-xl p-6 border border-white/20" 
         style={{ background: 'rgba(255, 255, 255, 0.15)' }}>
        <div className="w-24 h-24 rounded-full bg-gradient-to-tr from-yellow-500 to-yellow-600 mx-auto mb-4 flex items-center justify-center text-white text-3xl font-bold">PS</div>
        <h3 className="text-xl font-semibold text-center" style={{ color: colors.vibrantYellow }}>Praveen Kumar Sharma</h3>
        <p className="text-gray-500 text-center mb-2">Designing & Presenting</p>
        <p className="text-gray-700 text-center">Creates intuitive user interfaces and presents IntelliMix solutions to partners and clients.</p>
      </div>
    </div>
      
      <div className="mt-16 backdrop-blur-sm rounded-2xl p-8 border border-white/20" 
           style={{ background: 'rgba(255, 255, 255, 0.15)' }}>
        <h2 className="text-2xl font-semibold mb-4" style={{ color: colors.brightRed }}>Our Engineering Approach</h2>
        <p className="text-gray-700 mb-6">
          We approach challenges with a practical engineering mindset:
        </p>
        <div className="grid md:grid-cols-2 gap-6">
          <div className="flex">
            <div className="w-10 h-10 rounded-full flex-shrink-0 flex items-center justify-center" 
                 style={{ backgroundColor: `${colors.brightRed}30` }}>
              <span className="text-xl font-bold" style={{ color: colors.brightRed }}>1</span>
            </div>
            <div className="ml-4">
              <h3 className="text-lg font-semibold" style={{ color: colors.textDark }}>Problem Identification</h3>
              <p className="text-gray-600">Analyzing inefficient workflows in audio production and pinpointing automation opportunities.</p>
            </div>
          </div>
          <div className="flex">
            <div className="w-10 h-10 rounded-full flex-shrink-0 flex items-center justify-center" 
                 style={{ backgroundColor: `${colors.brightRed}30` }}>
              <span className="text-xl font-bold" style={{ color: colors.brightRed }}>2</span>
            </div>
            <div className="ml-4">
              <h3 className="text-lg font-semibold" style={{ color: colors.textDark }}>Algorithm Development</h3>
              <p className="text-gray-600">Creating efficient processing methods that deliver professional results without complexity.</p>
            </div>
          </div>
          <div className="flex">
            <div className="w-10 h-10 rounded-full flex-shrink-0 flex items-center justify-center" 
                 style={{ backgroundColor: `${colors.brightRed}30` }}>
              <span className="text-xl font-bold" style={{ color: colors.brightRed }}>3</span>
            </div>
            <div className="ml-4">
              <h3 className="text-lg font-semibold" style={{ color: colors.textDark }}>User-Centered Design</h3>
              <p className="text-gray-600">Building interfaces that make advanced technology accessible to everyone.</p>
            </div>
          </div>
          <div className="flex">
            <div className="w-10 h-10 rounded-full flex-shrink-0 flex items-center justify-center" 
                 style={{ backgroundColor: `${colors.brightRed}30` }}>
              <span className="text-xl font-bold" style={{ color: colors.brightRed }}>4</span>
            </div>
            <div className="ml-4">
              <h3 className="text-lg font-semibold" style={{ color: colors.textDark }}>Continuous Improvement</h3>
              <p className="text-gray-600">Iterating based on user feedback to refine and enhance our solutions.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AboutUsPage;