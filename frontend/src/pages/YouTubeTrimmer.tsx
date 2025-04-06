import React, { useState } from 'react';
import { Music, Upload, Clock, Plus, X, Play, Loader, Download, CheckCircle, AlertCircle } from 'lucide-react';
import { ENDPOINTS } from '../utils/api';

// Define vibrant red and yellow color palette with softer application
const colors = {
  brightRed: "#f4483a",       // Primary accent
  slightlyDarkerRed: "#f45444", // Secondary accent
  deepRed: "#d24d34",         // Emphasis/CTA
  reddishOrange: "#d14324",   // Highlight
  vividRed: "#f13521",        // Attention-grabbing
  vibrantYellow: "#ffb92b",   // Buttons/highlights
  softYellow: "#f7e5a0",      // Subtle background
  paleYellow: "#ffe09c",      // Secondary background
  white: "#FFFFFF",           // White elements
  black: "#000000",           // Black elements
  
  // Additional softer colors
  softRed: "#fee2e1",         // Very light red background
  softerRed: "#fbeae9",       // Even lighter red for larger areas
  softestYellow: "#fff8e8",   // Very light yellow for backgrounds
  textDark: "#444444",        // Softer than pure black for text
  grayLight: "#f6f6f6"        // Light gray for neutral backgrounds
};

interface VideoEntry {
  id: string;
  url: string;
  startTime: string;
  endTime: string;
}

interface ProcessingResult {
  merged_file_path: string;
  message: string;
}

export default function YouTubeTrimmer() {
  const [videoEntries, setVideoEntries] = useState<VideoEntry[]>([
    { id: '1', url: '', startTime: '', endTime: '' }
  ]);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [selectedVideo, setSelectedVideo] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [processingResult, setProcessingResult] = useState<ProcessingResult | null>(null);
  const [processingError, setProcessingError] = useState<string | null>(null);
  const [isManualProcessing, setIsManualProcessing] = useState<boolean>(false);
  const [manualProcessingResult, setManualProcessingResult] = useState<ProcessingResult | null>(null);
  const [manualProcessingError, setManualProcessingError] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState<boolean>(false);

  const addVideoEntry = () => {
    setVideoEntries([
      ...videoEntries,
      { id: Date.now().toString(), url: '', startTime: '', endTime: '' }
    ]);
  };

  const removeVideoEntry = (id: string) => {
    setVideoEntries(videoEntries.filter(entry => entry.id !== id));
  };

  const updateVideoEntry = (id: string, field: keyof VideoEntry, value: string) => {
    setVideoEntries(videoEntries.map(entry =>
      entry.id === id ? { ...entry, [field]: value } : entry
    ));
  };

  // Modified handleSubmit function to match the new backend API format
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate entries
    const hasEmptyFields = videoEntries.some(
      entry => !entry.url.trim()
    );
    
    if (hasEmptyFields) {
      alert("Please provide YouTube URL for each entry");
      return;
    }
    
    // Use separate loading state for manual processing
    setIsManualProcessing(true);
    setManualProcessingResult(null);
    setManualProcessingError(null);
    
    try {
      // Format data as expected by the updated backend API
      const formattedData = {
        urls: videoEntries.map(entry => ({
          url: entry.url,
          start: entry.startTime || "00:00", // Default to 00:00 if empty
          end: entry.endTime || "00:30"      // Default to 00:30 if empty
        }))
      };
      
      console.log("Sending data to process-array endpoint:", formattedData);
      
      const response = await fetch(ENDPOINTS.PROCESS_ARRAY, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formattedData),
      });
      
      if (!response.ok) {
        throw new Error(`Server responded with status: ${response.status}`);
      }
      
      const result = await response.json();
      console.log("Received result:", result);
      
      setManualProcessingResult({
        merged_file_path: result.merged_file_path,
        message: result.message
      });
      
    } catch (error) {
      console.error("Error processing videos:", error);
      setManualProcessingError(error instanceof Error ? error.message : "An unknown error occurred");
    } finally {
      setIsManualProcessing(false);
    }
  };
  
  const handleCsvUpload = async (file: File | null) => {
    if (!file) return;
    
    setIsProcessing(true);
    setProcessingResult(null);
    setProcessingError(null);
    
    try {
      const formData = new FormData();
      formData.append("file", file);
      
      const response = await fetch(ENDPOINTS.PROCESS_CSV, {
        method: 'POST',
        body: formData,
      });
      
      if (!response.ok) {
        throw new Error(`Server responded with status: ${response.status}`);
      }
      
      const result = await response.json();
      setProcessingResult({
        merged_file_path: result.merged_file_path,
        message: result.message
      });
    } catch (error) {
      console.error("Error processing CSV:", error);
      setProcessingError(error instanceof Error ? error.message : "An unknown error occurred");
    } finally {
      setIsProcessing(false);
    }
  };
  
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    setCsvFile(file);
  };

  const downloadAudio = (url: string) => {
    // Use isDownloading instead of isProcessing
    setIsDownloading(true);
    
    fetch(url)
      .then(response => {
        if (!response.ok) {
          throw new Error(`Failed to download: ${response.statusText}`);
        }
        return response.blob();
      })
      .then(blob => {
        // Create blob URL
        const blobUrl = window.URL.createObjectURL(blob);
        
        // Create download link
        const link = document.createElement('a');
        link.href = blobUrl;
        link.download = 'combined_audio.mp3';
        
        // Trigger download
        document.body.appendChild(link);
        link.click();
        
        // Clean up
        setTimeout(() => {
          document.body.removeChild(link);
          window.URL.revokeObjectURL(blobUrl);
          setIsDownloading(false);
        }, 100);
      })
      .catch(error => {
        console.error("Download error:", error);
        // Don't update processingError, use a different state or notification approach
        alert(`Download failed: ${error.message}`);
        setIsDownloading(false);
        
        // Fallback - open in new tab
        window.open(url, '_blank');
      });
  };

  return (
    <div className="max-w-6xl mx-auto h-full">
      <div className="text-center mb-12">
        <div className="relative inline-block">
          <div 
            className="absolute -inset-1 rounded-full blur opacity-30 animate-pulse"
            style={{ background: `linear-gradient(to right, ${colors.brightRed}, ${colors.vibrantYellow})` }}
          ></div>
          <Music 
            className="relative w-20 h-20 mx-auto mb-4" 
            style={{ color: colors.deepRed }}
          />
        </div>
        <h1 className="text-4xl font-bold mb-2" style={{ color: colors.deepRed }}>Audio Mixer</h1>
        <p className="text-lg" style={{ color: colors.textDark }}>Extract perfect clips from multiple videos simultaneously</p>
      </div>

      <div className="grid lg:grid-cols-2 gap-8">
        <div className="space-y-6">
          <form onSubmit={handleSubmit} className="space-y-6">
            {videoEntries.map((entry, index) => (
              <div
                key={entry.id}
                className="bg-white rounded-2xl p-6 relative group shadow-sm"
                style={{ 
                  boxShadow: "0 4px 8px rgba(0,0,0,0.05)",
                  borderColor: `${colors.softRed}`, 
                  borderWidth: '1px' 
                }}
              >
                <div className="absolute -top-3 -right-3 opacity-0 group-hover:opacity-100 transition-opacity">
                  {index > 0 && (
                    <button
                      type="button"
                      onClick={() => removeVideoEntry(entry.id)}
                      className="rounded-full p-1.5"
                      style={{ 
                        backgroundColor: colors.deepRed, 
                        color: colors.white,
                        opacity: 0.9
                      }}
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2" style={{ color: colors.deepRed }}>
                      YouTube URL
                    </label>
                    <div className="flex space-x-2">
                      <input
                        type="text"
                        value={entry.url}
                        onChange={(e) => updateVideoEntry(entry.id, 'url', e.target.value)}
                        className="flex-1 px-4 py-2 rounded-xl focus:outline-none focus:ring-2 placeholder-gray-400"
                        style={{ 
                          backgroundColor: colors.white,
                          borderColor: colors.softRed, 
                          borderWidth: '1px',
                          color: colors.textDark
                        }}
                        placeholder="https://youtube.com/watch?v=..."
                      />
                      <button
                        type="button"
                        onClick={() => setSelectedVideo(entry.url)}
                        className="rounded-xl px-4 flex items-center space-x-2 transition-colors"
                        style={{ 
                          backgroundColor: colors.deepRed,
                          color: colors.white,
                          boxShadow: `0 2px 4px ${colors.deepRed}40`
                        }}
                      >
                        <Play className="w-4 h-4" />
                        <span>Preview</span>
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium mb-2" style={{ color: colors.deepRed }}>
                        Start Time
                      </label>
                      <div className="relative">
                        <Clock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" style={{ color: colors.reddishOrange }} />
                        <input
                          type="text"
                          value={entry.startTime}
                          onChange={(e) => updateVideoEntry(entry.id, 'startTime', e.target.value)}
                          className="w-full pl-10 pr-3 py-2 rounded-xl focus:outline-none focus:ring-2 placeholder-gray-400"
                          style={{ 
                            backgroundColor: colors.white,
                            borderColor: colors.softRed, 
                            borderWidth: '1px',
                            color: colors.textDark
                          }}
                          placeholder="0:00"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-2" style={{ color: colors.deepRed }}>
                        End Time
                      </label>
                      <div className="relative">
                        <Clock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" style={{ color: colors.reddishOrange }} />
                        <input
                          type="text"
                          value={entry.endTime}
                          onChange={(e) => updateVideoEntry(entry.id, 'endTime', e.target.value)}
                          className="w-full pl-10 pr-3 py-2 rounded-xl focus:outline-none focus:ring-2 placeholder-gray-400"
                          style={{ 
                            backgroundColor: colors.white,
                            borderColor: colors.softRed, 
                            borderWidth: '1px',
                            color: colors.textDark
                          }}
                          placeholder="1:00"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}

            <button
              type="button"
              onClick={addVideoEntry}
              className="w-full font-medium py-3 px-4 rounded-xl border transition-colors flex items-center justify-center space-x-2"
              style={{ 
                backgroundColor: colors.softerRed,
                borderColor: colors.softRed,
                borderWidth: '1px',
                color: colors.deepRed
              }}
            >
              <Plus className="w-5 h-5" />
              <span>Add Another Video</span>
            </button>

            <button
              type="submit"
              disabled={isManualProcessing}
              className="w-full font-medium py-3 px-4 rounded-xl transition-all hover:shadow-md flex items-center justify-center"
              style={{
                backgroundColor: colors.deepRed,
                color: colors.white,
                boxShadow: `0 2px 6px ${colors.deepRed}30`,
                opacity: isManualProcessing ? 0.7 : 1
              }}
            >
              {isManualProcessing ? (
                <>
                  <Loader className="w-5 h-5 mr-2 animate-spin" />
                  <span>Processing Videos...</span>
                </>
              ) : (
                <>
                  <Music className="w-5 h-5 mr-2" />
                  <span>Process All Videos</span>
                </>
              )}
            </button>

            {/* Manual processing result */}
            {manualProcessingResult && (
              <div className="mt-4 rounded-xl p-6 text-center" style={{ backgroundColor: colors.softerRed }}>
                <CheckCircle className="w-12 h-12 mx-auto mb-4" style={{ color: colors.deepRed }} />
                <h3 className="text-lg font-medium mb-2" style={{ color: colors.deepRed }}>
                  Manual Processing Complete!
                </h3>
                <p className="mb-4" style={{ color: colors.textDark }}>
                  {manualProcessingResult.message}
                </p>
                <button
                  type="button" // Explicitly set button type
                  onClick={() => downloadAudio(manualProcessingResult.merged_file_path)}
                  disabled={isDownloading}
                  className="inline-flex items-center space-x-2 font-medium py-2 px-6 rounded-xl transition-all"
                  style={{ 
                    backgroundColor: colors.deepRed,
                    color: colors.white,
                    boxShadow: `0 2px 6px ${colors.deepRed}30`,
                    opacity: isDownloading ? 0.7 : 1
                  }}
                >
                  {isDownloading ? (
                    <>
                      <Loader className="w-5 h-5 animate-spin" />
                      <span>Downloading...</span>
                    </>
                  ) : (
                    <>
                      <Download className="w-5 h-5" />
                      <span>Download Audio</span>
                    </>
                  )}
                </button>
              </div>
            )}

            {/* Manual processing error */}
            {manualProcessingError && (
              <div className="mt-4 rounded-xl p-6 text-center" style={{ backgroundColor: colors.softRed }}>
                <AlertCircle className="w-12 h-12 mx-auto mb-4" style={{ color: colors.vividRed }} />
                <h3 className="text-lg font-medium mb-2" style={{ color: colors.vividRed }}>
                  Processing Error
                </h3>
                <p className="mb-4" style={{ color: colors.textDark }}>
                  {manualProcessingError}
                </p>
                <button
                  onClick={() => setManualProcessingError(null)}
                  className="inline-flex items-center space-x-2 font-medium py-2 px-6 rounded-xl transition-all"
                  style={{ 
                    backgroundColor: colors.deepRed,
                    color: colors.white
                  }}
                >
                  <Play className="w-5 h-5" />
                  <span>Try Again</span>
                </button>
              </div>
            )}

            {/* Manual processing loading state */}
            {isManualProcessing && (
              <div className="mt-4 rounded-xl p-6 text-center" style={{ backgroundColor: colors.softerRed }}>
                <div className="flex justify-center mb-4">
                  <Loader className="w-12 h-12 animate-spin" style={{ color: colors.deepRed }} />
                </div>
                <h3 className="text-lg font-medium mb-2" style={{ color: colors.deepRed }}>
                  Processing Your Videos
                </h3>
                <p style={{ color: colors.textDark }}>
                  This might take a moment depending on the number of videos...
                </p>
              </div>
            )}
          </form>
        </div>

        <div className="space-y-6">
          {/* Video Preview Area */}
          <div 
            className="bg-white rounded-2xl p-6 shadow-sm"
            style={{ 
              borderColor: colors.softRed, 
              borderWidth: '1px',
              boxShadow: "0 4px 8px rgba(0,0,0,0.05)"
            }}
          >
            <h2 className="text-xl font-semibold mb-4" style={{ color: colors.deepRed }}>
              Video Preview
            </h2>
            <div className="aspect-video rounded-xl overflow-hidden">
              {selectedVideo ? (
                <iframe
                  src={`https://www.youtube.com/embed/${selectedVideo.split('v=')[1]}`}
                  className="w-full h-full rounded-lg"
                  allowFullScreen
                ></iframe>
              ) : (
                <div className="w-full h-full bg-gray-100 rounded-lg flex items-center justify-center text-gray-500">
                  Select a video to preview
                </div>
              )}
            </div>
          </div>

          {/* Batch Processing */}
          <div 
            className="bg-white rounded-2xl p-6 shadow-sm"
            style={{ 
              borderColor: colors.softRed, 
              borderWidth: '1px',
              boxShadow: "0 4px 8px rgba(0,0,0,0.05)"
            }}
          >
            <h2 className="text-xl font-semibold mb-4" style={{ color: colors.deepRed }}>
              Batch Processing
            </h2>
            
            {/* Batch Processing section */}
            {processingResult && csvFile ? (
              // Results display after successful CSV processing
              <div className="rounded-xl p-6 text-center" style={{ backgroundColor: colors.softerRed }}>
                <CheckCircle className="w-12 h-12 mx-auto mb-4" style={{ color: colors.deepRed }} />
                <h3 className="text-lg font-medium mb-2" style={{ color: colors.deepRed }}>
                  CSV Processing Complete!
                </h3>
                <p className="mb-4" style={{ color: colors.textDark }}>
                  {processingResult.message}
                </p>
                <button
                  onClick={() => downloadAudio(processingResult.merged_file_path)}
                  disabled={isDownloading}
                  className="inline-flex items-center space-x-2 font-medium py-2 px-6 rounded-xl transition-all"
                  style={{ 
                    backgroundColor: colors.deepRed,
                    color: colors.white,
                    boxShadow: `0 2px 6px ${colors.deepRed}30`,
                    opacity: isDownloading ? 0.7 : 1
                  }}
                >
                  {isDownloading ? (
                    <>
                      <Loader className="w-5 h-5 animate-spin" />
                      <span>Downloading...</span>
                    </>
                  ) : (
                    <>
                      <Download className="w-5 h-5" />
                      <span>Download Audio</span>
                    </>
                  )}
                </button>
              </div>
            ) : processingError ? (
              // Error display - keep this for CSV processing only
              <div className="rounded-xl p-6 text-center" style={{ backgroundColor: colors.softRed }}>
                <AlertCircle className="w-12 h-12 mx-auto mb-4" style={{ color: colors.vividRed }} />
                <h3 className="text-lg font-medium mb-2" style={{ color: colors.vividRed }}>
                  CSV Processing Error
                </h3>
                <p className="mb-4" style={{ color: colors.textDark }}>
                  {processingError}
                </p>
                <button
                  onClick={() => {
                    setProcessingError(null);
                    setCsvFile(null);
                  }}
                  className="inline-flex items-center space-x-2 font-medium py-2 px-6 rounded-xl transition-all"
                  style={{ 
                    backgroundColor: colors.deepRed,
                    color: colors.white
                  }}
                >
                  <Upload className="w-5 h-5" />
                  <span>Try Again</span>
                </button>
              </div>
            ) : isProcessing && csvFile ? (
              // Loading state - only show while CSV is being processed
              <div className="rounded-xl p-6 text-center" style={{ backgroundColor: colors.softerRed }}>
                <div className="flex justify-center mb-4">
                  <Loader className="w-12 h-12 animate-spin" style={{ color: colors.deepRed }} />
                </div>
                <h3 className="text-lg font-medium mb-2" style={{ color: colors.deepRed }}>
                  Processing Your CSV File
                </h3>
                <p style={{ color: colors.textDark }}>
                  This might take a moment depending on the number of videos...
                </p>
              </div>
            ) : (
              // Initial upload state
              <div 
                className="border-2 border-dashed rounded-xl p-6 text-center"
                style={{ borderColor: colors.softRed, backgroundColor: colors.softerRed }}
              >
                <Upload className="w-12 h-12 mx-auto mb-4" style={{ color: colors.deepRed }} />
                <p className="mb-2" style={{ color: colors.textDark }}>Upload your CSV file with video details</p>
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleFileChange}
                  className="hidden"
                  id="csv-upload"
                />
                <div className="space-y-3">
                  <label
                    htmlFor="csv-upload"
                    className="inline-block font-medium py-2 px-4 rounded-xl transition-colors cursor-pointer shadow-sm"
                    style={{ 
                      backgroundColor: colors.deepRed,
                      color: colors.white
                    }}
                  >
                    Choose CSV File
                  </label>
                  
                  {csvFile && (
                    <div>
                      <p className="mb-2 text-sm" style={{ color: colors.deepRed }}>
                        Selected: {csvFile.name}
                      </p>
                      <button
                        onClick={() => handleCsvUpload(csvFile)}
                        className="inline-flex items-center space-x-2 font-medium py-2 px-4 rounded-xl transition-all"
                        style={{ 
                          backgroundColor: colors.deepRed,
                          color: colors.white
                        }}
                      >
                        <Play className="w-4 h-4" />
                        <span>Process CSV</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
          
          {/* Added Feature Section */}
          <div 
            className="bg-white rounded-2xl p-6 shadow-sm"
            style={{ 
              borderColor: colors.softRed, 
              borderWidth: '1px',
              boxShadow: "0 4px 8px rgba(0,0,0,0.05)"
            }}
          >
            <h2 className="text-xl font-semibold mb-4" style={{ color: colors.deepRed }}>
              Features
            </h2>
            <ul className="space-y-3">
              <li className="flex items-center">
                <span 
                  className="flex-shrink-0 w-1.5 h-1.5 rounded-full mr-2"
                  style={{ backgroundColor: colors.deepRed }}
                ></span>
                <span style={{ color: colors.textDark }}>Process multiple videos simultaneously</span>
              </li>
              <li className="flex items-center">
                <span 
                  className="flex-shrink-0 w-1.5 h-1.5 rounded-full mr-2"
                  style={{ backgroundColor: colors.deepRed }}
                ></span>
                <span style={{ color: colors.textDark }}>Precise time selection with preview</span>
              </li>
              <li className="flex items-center">
                <span 
                  className="flex-shrink-0 w-1.5 h-1.5 rounded-full mr-2"
                  style={{ backgroundColor: colors.deepRed }}
                ></span>
                <span style={{ color: colors.textDark }}>Batch processing via CSV import</span>
              </li>
              <li className="flex items-center">
                <span 
                  className="flex-shrink-0 w-1.5 h-1.5 rounded-full mr-2"
                  style={{ backgroundColor: colors.deepRed }}
                ></span>
                <span style={{ color: colors.textDark }}>High-quality audio extraction</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}