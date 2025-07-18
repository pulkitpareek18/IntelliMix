import React, { useState, useRef } from 'react';
import { Music, Loader, History, Sparkles, Brain, Wand2, Play, Download, AlertCircle } from 'lucide-react';
import { ENDPOINTS } from '../utils/api';

// Define color palette for easier reference
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

// Add this style tag at the beginning of your component
const customAudioStyles = `
  .custom-audio-player {
    color: ${colors.deepRed};
  }
  
  .custom-audio-player::-webkit-media-controls-panel {
    background-color: ${colors.softerRed};
  }
  
  .custom-audio-player::-webkit-media-controls-play-button {
    background-color: ${colors.deepRed};
    border-radius: 50%;
    color: white;
  }
  
  .custom-audio-player::-webkit-media-controls-current-time-display,
  .custom-audio-player::-webkit-media-controls-time-remaining-display {
    color: ${colors.textDark};
  }
`;

interface GeneratedAudio {
  filePath: string;
  status: string;
}

export default function AIParody() {
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [generatedAudio, setGeneratedAudio] = useState<GeneratedAudio | null>(null);
  const [error, setError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  
  // Mock data for demonstration
  const searchHistory = [
    { id: 1, prompt: "Jazz version of pop songs with nature themes", date: "2 hours ago" },
    { id: 2, prompt: "Electronic remix with cyberpunk elements", date: "1 day ago" },
    { id: 3, prompt: "Classical interpretation of rock ballads", date: "3 days ago" }
  ];

  const recommendations = [
    { id: 1, title: "Synthwave Remix", description: "Based on your electronic music interests" },
    { id: 2, title: "Jazz Fusion", description: "Similar to your recent searches" },
    { id: 3, title: "Neo-Classical", description: "Matches your style preferences" }
  ];

  // Updated handleSubmit function to correctly handle the backend response
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!prompt.trim()) {
      setError("Please enter a prompt for the AI");
      return;
    }
    
    setLoading(true);
    setError(null);
    setGeneratedAudio(null);
    
    try {
      console.log("Sending request to generate AI audio with prompt:", prompt);
      
      const response = await fetch(ENDPOINTS.GENERATE_AI, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ prompt }),
      });
      
      if (!response.ok) {
        throw new Error(`Server responded with status: ${response.status}`);
      }
      
      const data = await response.json();
      console.log("Received response:", data);
      
      // Updated to match the backend response format
      setGeneratedAudio({
        filePath: data.filepath, // Using the correct property name from backend
        status: 'success'
      });
      
    } catch (err) {
      console.error('Error generating audio:', err);
      setError(err instanceof Error ? err.message : "Failed to generate audio");
    } finally {
      setLoading(false);
    }
  };

  const downloadAudio = () => {
    if (!generatedAudio?.filePath) return;
    
    // Fetch the file first to ensure proper download
    fetch(generatedAudio.filePath)
      .then(response => response.blob())
      .then(blob => {
        // Create a blob URL
        const blobUrl = window.URL.createObjectURL(blob);
        
        // Create download link
        const link = document.createElement('a');
        link.href = blobUrl;
        
        // Extract filename from path or use default
        const filename = generatedAudio.filePath.split('/').pop() || 'generated-parody.mp3';
        link.download = filename;
        
        // Append, click and remove
        document.body.appendChild(link);
        link.click();
        
        // Clean up
        setTimeout(() => {
          document.body.removeChild(link);
          window.URL.revokeObjectURL(blobUrl);
        }, 100);
      })
      .catch(error => {
        console.error("Error downloading file:", error);
        // Fallback to direct download if fetch fails
        window.open(generatedAudio.filePath, '_blank');
      });
  };

  return (
    <div className="max-w-6xl mx-auto h-full">
      <style dangerouslySetInnerHTML={{ __html: customAudioStyles }} />
      <div className="text-center mb-12">
        <div className="relative inline-block">
          <div 
            className="absolute -inset-1 rounded-full blur opacity-30 animate-pulse"
            style={{ background: `linear-gradient(to right, ${colors.brightRed}, ${colors.vibrantYellow})` }}
          ></div>
          <Music 
            className="relative w-20 h-20 mx-auto mb-4" 
            style={{ color: colors.brightRed }}
          />
        </div>
        <h1 className="text-4xl font-bold mb-2" style={{ color: colors.deepRed }}>AI Music Transformation Studio</h1>
        <p className="text-lg" style={{ color: colors.textDark }}>Transform music with AI magic - create high quality Mashups in seconds</p>
      </div>

      <div className="grid lg:grid-cols-3 gap-4 sm:gap-8">
        {/* Main Creation Area */}
        <div className="lg:col-span-2">
          <form onSubmit={handleSubmit} className="space-y-4 sm:space-y-6">
            <div className="bg-white rounded-2xl p-4 sm:p-8 shadow-sm" 
              style={{ 
                borderColor: colors.softRed,
                borderWidth: '1px',
                boxShadow: "0 4px 8px rgba(0,0,0,0.05)"
              }}
            >
              <div className="flex items-center mb-4">
                <Brain 
                  className="w-6 h-6 mr-2" 
                  style={{ color: colors.brightRed }}
                />
                <label className="text-lg font-medium" style={{ color: colors.deepRed }}>
                  Describe Your Vision
                </label>
              </div>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                className="w-full h-40 px-4 py-3 rounded-xl resize-none focus:outline-none focus:ring-2"
                placeholder="Describe your musical vision (e.g., 'A mashup of 5 Honey Singh songs.')"
                style={{ 
                  backgroundColor: colors.white,
                  borderColor: colors.softRed,
                  borderWidth: '1px',
                  color: colors.textDark,
                }}
              />
              
              {error && (
                <div className="mt-2 text-sm flex items-center" style={{ color: colors.vividRed }}>
                  <AlertCircle className="w-4 h-4 mr-1" />
                  {error}
                </div>
              )}
              
              <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center space-x-4 flex-wrap gap-2">
                 
                </div>
                
                {/* Make sure the generate button is clearly visible */}
                <button
                  type="submit"
                  disabled={loading}
                  className="font-medium px-6 py-3 rounded-xl transition-all disabled:opacity-50 flex items-center space-x-2 shadow-sm"
                  style={{ 
                    backgroundColor: colors.deepRed,
                    color: colors.white,
                    boxShadow: `0 4px 10px ${colors.deepRed}40`
                  }}
                >
                  {loading ? (
                    <>
                      <Loader className="animate-spin w-5 h-5" />
                      <span>Generating...</span>
                    </>
                  ) : (
                    <>
                      <Wand2 className="w-5 h-5" />
                      <span>Generate Music</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>

          <div 
            className="mt-6 sm:mt-8 bg-white rounded-2xl p-4 sm:p-8 shadow-sm" 
            style={{ 
              borderColor: colors.softRed,
              borderWidth: '1px',
              boxShadow: "0 4px 8px rgba(0,0,0,0.05)"
            }}
          >
            <h2 className="text-2xl font-semibold mb-6 flex items-center" style={{ color: colors.deepRed }}>
              <Sparkles className="w-6 h-6 mr-2" style={{ color: colors.brightRed }} />
              Generated Music
            </h2>
            
            {/* Enhanced audio player section */}
            {loading ? (
              // Loading state
              <div className="rounded-xl p-6" style={{ backgroundColor: colors.softerRed }}>
                <div className="flex flex-col items-center justify-center space-y-4">
                  <Loader className="animate-spin w-12 h-12" style={{ color: colors.deepRed }} />
                  <p style={{ color: colors.textDark }}>Creating your parody... This may take a moment</p>
                </div>
              </div>
            ) : generatedAudio?.filePath ? (
              // Generated audio display
              <div className="rounded-xl p-4 sm:p-6" style={{ backgroundColor: colors.softerRed }}>
                <div className="flex flex-col space-y-3 sm:space-y-6">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center space-x-2">
                      <div 
                        className="w-8 h-8 sm:w-10 sm:h-10 rounded-full flex items-center justify-center" 
                        style={{ backgroundColor: colors.deepRed }}
                      >
                        <Music className="w-4 h-4 sm:w-5 sm:h-5" style={{ color: colors.white }} />
                      </div>
                      <div>
                        <h3 className="font-medium text-sm sm:text-base" style={{ color: colors.deepRed }}>Your AI Parody</h3>
                        <p className="text-xs" style={{ color: colors.textDark }}>Generated just now</p>
                      </div>
                    </div>
                    <button 
                      onClick={downloadAudio}
                      className="flex items-center space-x-1 sm:space-x-2 px-3 py-2 sm:px-4 sm:py-2 rounded-lg transition-all hover:shadow-md text-sm"
                      style={{ 
                        backgroundColor: colors.deepRed,
                        color: colors.white,
                        boxShadow: `0 2px 4px ${colors.deepRed}30`
                      }}
                    >
                      <Download className="w-4 h-4" />
                      <span className="hidden sm:inline">Download</span>
                    </button>
                  </div>
                  
                  {/* Stylized audio player */}
                  <div 
                    className="w-full rounded-xl p-2 sm:p-4" 
                    style={{ 
                      backgroundColor: colors.white,
                      borderColor: colors.softRed,
                      borderWidth: '1px'
                    }}
                  >
                    <div className="flex items-center space-x-2 sm:space-x-3 mb-2 sm:mb-3">
                      <div 
                        className="w-6 h-6 sm:w-8 sm:h-8 rounded-full flex items-center justify-center animate-pulse"
                        style={{ 
                          background: `linear-gradient(to right, ${colors.brightRed}, ${colors.vibrantYellow})`,
                        }}
                      >
                        <Play className="w-3 h-3 sm:w-4 sm:h-4" style={{ color: colors.white }} />
                      </div>
                      <div className="h-1 flex-grow rounded-full" style={{ backgroundColor: colors.softRed }}>
                        <div 
                          className="h-1 rounded-full w-1/3" 
                          style={{ 
                            background: `linear-gradient(to right, ${colors.brightRed}, ${colors.vibrantYellow})`,
                          }}
                        ></div>
                      </div>
                    </div>
                    
                    <audio 
                      ref={audioRef}
                      controls 
                      className="w-full custom-audio-player" 
                      src={generatedAudio.filePath}
                      autoPlay
                    >
                      Your browser does not support the audio element.
                    </audio>
                    
                    <p className="mt-2 sm:mt-3 text-xs sm:text-sm text-center" style={{ color: colors.textDark }}>
                      AI-generated parody based on your prompt
                    </p>
                  </div>
                  
                  {/* Song info */}
                  <div className="flex items-center justify-between px-1 sm:px-2 text-xs sm:text-sm">
                    <div className="flex items-center space-x-1 sm:space-x-2">
                      <Brain className="w-3 h-3 sm:w-4 sm:h-4" style={{ color: colors.brightRed }} />
                      <span style={{ color: colors.textDark }}>
                        AI Generated
                      </span>
                    </div>
                    <div className="flex items-center space-x-1 sm:space-x-2">
                      <Sparkles className="w-3 h-3 sm:w-4 sm:h-4" style={{ color: colors.brightRed }} />
                      <span style={{ color: colors.textDark }}>
                        High Quality
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              // Empty state
              <div className="rounded-xl p-8 text-center" style={{ backgroundColor: colors.softerRed }}>
                <Music 
                  className="w-12 h-12 mx-auto mb-3 opacity-50" 
                  style={{ color: colors.deepRed }} 
                />
                <p className="mb-2" style={{ color: colors.textDark }}>
                  No audio generated yet
                </p>
                <p className="text-sm" style={{ color: colors.textDark, opacity: 0.8 }}>
                  Your generated audio will appear here. Start by describing your musical vision and click "Generate Music".
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-8">
          {/* Search History */}
          <div 
            className="bg-white rounded-2xl p-6 shadow-sm"
            style={{ 
              borderColor: colors.softRed,
              borderWidth: '1px',
              boxShadow: "0 4px 8px rgba(0,0,0,0.05)"
            }}
          >
            <h3 className="text-xl font-semibold mb-4 flex items-center" style={{ color: colors.deepRed }}>
              <History className="w-5 h-5 mr-2" style={{ color: colors.brightRed }} />
              Recent Creations
            </h3>
            <div className="space-y-4">
              {searchHistory.map((item) => (
                <div
                  key={item.id}
                  className="rounded-xl p-4 hover:bg-opacity-60 transition-colors cursor-pointer"
                  style={{ 
                    backgroundColor: colors.softerRed,
                  }}
                  onClick={() => setPrompt(item.prompt)}
                >
                  <p className="text-sm mb-1" style={{ color: colors.textDark }}>{item.prompt}</p>
                  <p className="text-xs" style={{ color: '#666666' }}>{item.date}</p>
                </div>
              ))}
            </div>
          </div>

          {/* AI Recommendations */}
          <div 
            className="bg-white rounded-2xl p-6 shadow-sm"
            style={{ 
              borderColor: colors.softRed,
              borderWidth: '1px',
              boxShadow: "0 4px 8px rgba(0,0,0,0.05)"
            }}
          >
            <h3 className="text-xl font-semibold mb-4 flex items-center" style={{ color: colors.deepRed }}>
              <Brain className="w-5 h-5 mr-2" style={{ color: colors.brightRed }} />
              AI Suggestions
            </h3>
            <div className="space-y-4">
              {recommendations.map((item) => (
                <div
                  key={item.id}
                  className="rounded-xl p-4 transition-colors cursor-pointer"
                  style={{ 
                    backgroundColor: colors.softerRed,
                    borderColor: colors.softRed,
                    borderWidth: '1px'
                  }}
                >
                  <h4 className="font-medium mb-1" style={{ color: colors.deepRed }}>{item.title}</h4>
                  <p className="text-sm" style={{ color: colors.textDark }}>{item.description}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}