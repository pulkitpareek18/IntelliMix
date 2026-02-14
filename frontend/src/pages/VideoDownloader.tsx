import React, { useState } from 'react';
import { Video, Download, Check, AlertCircle, Loader } from 'lucide-react';
import { ENDPOINTS, apiRequest, getAuthenticatedFileUrl } from '../utils/api';

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

interface DownloadResult {
  filepath: string;
  message: string;
}

export default function VideoDownloader() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedFormat, setSelectedFormat] = useState('mp4');
  const [error, setError] = useState<string | null>(null);
  const [downloadResult, setDownloadResult] = useState<DownloadResult | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadType, setDownloadType] = useState<'video' | 'audio'>('video');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!url.trim()) {
      setError("Please enter a valid YouTube URL");
      return;
    }
    
    setLoading(true);
    setError(null);
    setDownloadResult(null);
    
    try {
      // Choose the appropriate endpoint based on download type
      const endpoint = downloadType === 'video' 
        ? ENDPOINTS.DOWNLOAD_VIDEO 
        : ENDPOINTS.DOWNLOAD_AUDIO;

      const result = await apiRequest<{ filepath: string; message: string }>(
        endpoint,
        {
          method: 'POST',
          body: JSON.stringify({
            url: url,
            format: selectedFormat
          }),
        }
      );
      
      setDownloadResult({
        filepath: result.filepath,
        message: result.message || `${downloadType === 'video' ? 'Video' : 'Audio'} downloaded successfully!`
      });
      
    } catch (err) {
      console.error(`Error downloading ${downloadType}:`, err);
      setError(err instanceof Error ? err.message : `Failed to download ${downloadType}`);
    } finally {
      setLoading(false);
    }
  };
  
  const downloadVideo = () => {
    if (!downloadResult?.filepath) return;
    
    setIsDownloading(true);
    
    // Create a function to handle the actual download
    const startDownload = () => {
      // Create a download link
      const link = document.createElement('a');
      link.href = getAuthenticatedFileUrl(downloadResult.filepath);
      
      // Extract filename from the URL or use a default name
      const filename = downloadResult.filepath.split('/').pop() || `video.${selectedFormat}`;
      link.download = filename;
      
      // Trigger download
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      setTimeout(() => {
        setIsDownloading(false);
      }, 1000);
    };
    
    // Start the download
    startDownload();
  };

  return (
    <div className="max-w-3xl mx-auto h-full">
      <div className="text-center mb-8">
        <div className="relative inline-block">
          <div 
            className="absolute -inset-1 rounded-full blur opacity-30 animate-pulse"
            style={{ 
              background: `linear-gradient(to right, ${colors.brightRed}, ${colors.vibrantYellow})`
            }}
          ></div>
          <Video 
            className="relative w-16 h-16 mx-auto mb-4" 
            style={{ color: colors.deepRed }}
          />
        </div>
        <h1 
          className="text-3xl font-bold mb-2" 
          style={{ color: colors.deepRed }}
        >
          Media Downloader
        </h1>
        <p style={{ color: colors.textDark }}>
          Download YouTube videos/audio in the highest quality - Max. Support 2160p
        </p>
      </div>

      <div 
        className="bg-white rounded-xl p-6 shadow-sm"
        style={{ 
          borderColor: colors.softRed,
          borderWidth: '1px',
          boxShadow: "0 4px 8px rgba(0,0,0,0.05)"
        }}
      >
        {downloadResult ? (
          // Download result display
          <div className="text-center py-4">
            <div 
              className="w-16 h-16 mx-auto mb-4 rounded-full flex items-center justify-center"
              style={{ backgroundColor: colors.softRed }}
            >
              <Check 
                className="w-8 h-8" 
                style={{ color: colors.deepRed }}
              />
            </div>
            <h3 
              className="text-xl font-medium mb-2" 
              style={{ color: colors.deepRed }}
            >
              Download Ready
            </h3>
            <p className="mb-6" style={{ color: colors.textDark }}>
              {downloadResult.message}
            </p>
            <div className="flex justify-center">
              <button
                type="button"
                onClick={downloadVideo}
                disabled={isDownloading}
                className="font-medium py-3 px-6 rounded-md transition-all flex items-center space-x-2"
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
                    <span>Download {downloadType === 'video' ? 'Video' : 'Audio'}</span>
                  </>
                )}
              </button>
            </div>
            <button
              type="button"
              onClick={() => {
                setDownloadResult(null);
                setUrl('');
              }}
              className="mt-4 text-sm underline"
              style={{ color: colors.textDark }}
            >
              Download another video
            </button>
          </div>
        ) : (
          // Download form
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label 
                className="block text-sm font-medium mb-2"
                style={{ color: colors.deepRed }}
              >
                YouTube URL
              </label>
              <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="w-full px-3 py-2 rounded-md focus:outline-none focus:ring-2 placeholder-gray-400"
                style={{ 
                  backgroundColor: colors.white,
                  borderColor: colors.softRed,
                  borderWidth: '1px',
                  color: colors.textDark,
                }}
                placeholder="https://youtube.com/watch?v=..."
                disabled={loading}
              />
              
              {error && (
                <div className="mt-2 text-sm flex items-center" style={{ color: colors.vividRed }}>
                  <AlertCircle className="w-4 h-4 mr-1" />
                  {error}
                </div>
              )}
            </div>
            
            {/* Download Type Toggle */}
            <div>
              <label 
                className="block text-sm font-medium mb-2"
                style={{ color: colors.deepRed }}
              >
                Download Type
              </label>
              <div className="flex space-x-2">
                <button
                  type="button"
                  onClick={() => {
                    setDownloadType('video');
                    setSelectedFormat('mp4');
                  }}
                  className="flex-1 px-4 py-3 rounded-md flex items-center justify-center transition-colors"
                  style={{ 
                    backgroundColor: downloadType === 'video' ? colors.softRed : colors.softerRed,
                    borderColor: colors.softRed,
                    borderWidth: '1px',
                    color: downloadType === 'video' ? colors.deepRed : colors.textDark
                  }}
                  onMouseEnter={(e) => {
                    if (downloadType !== 'video') {
                      e.currentTarget.style.backgroundColor = colors.softRed;
                      e.currentTarget.style.color = colors.deepRed;
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (downloadType !== 'video') {
                      e.currentTarget.style.backgroundColor = colors.softerRed;
                      e.currentTarget.style.color = colors.textDark;
                    }
                  }}
                >
                  <Video className="w-5 h-5 mr-2" />
                  <span>Video</span>
                  {downloadType === 'video' && (
                    <Check className="ml-2 w-4 h-4" style={{ color: colors.deepRed }} />
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setDownloadType('audio');
                    setSelectedFormat('mp4-audio');
                  }}
                  className="flex-1 px-4 py-3 rounded-md flex items-center justify-center transition-colors"
                  style={{ 
                    backgroundColor: downloadType === 'audio' ? colors.softRed : colors.softerRed,
                    borderColor: colors.softRed,
                    borderWidth: '1px',
                    color: downloadType === 'audio' ? colors.deepRed : colors.textDark
                  }}
                  onMouseEnter={(e) => {
                    if (downloadType !== 'audio') {
                      e.currentTarget.style.backgroundColor = colors.softRed;
                      e.currentTarget.style.color = colors.deepRed;
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (downloadType !== 'audio') {
                      e.currentTarget.style.backgroundColor = colors.softerRed;
                      e.currentTarget.style.color = colors.textDark;
                    }
                  }}
                >
                  <svg 
                    className="w-5 h-5 mr-2" 
                    viewBox="0 0 24 24" 
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M12 2a3 3 0 0 0-3 3v9.379a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"></path>
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                    <line x1="12" y1="19" x2="12" y2="22"></line>
                  </svg>
                  <span>Audio</span>
                  {downloadType === 'audio' && (
                    <Check className="ml-2 w-4 h-4" style={{ color: colors.deepRed }} />
                  )}
                </button>
              </div>
            </div>
            
            <button
              type="submit"
              disabled={loading || !url.trim()}
              className="w-full font-medium py-3 px-4 rounded-md transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
              style={{
                backgroundColor: colors.deepRed,
                color: colors.white,
                boxShadow: `0 2px 6px ${colors.deepRed}30`
              }}
            >
              {loading ? (
                <>
                  <Loader className="animate-spin -ml-1 mr-2 h-5 w-5" />
                  <span>Processing...</span>
                </>
              ) : (
                <>
                  <Download className="-ml-1 mr-2 h-5 w-5" />
                  <span>Download {downloadType === 'video' ? 'Video' : 'Audio'}</span>
                </>
              )}
            </button>
          </form>
        )}

        <div className="mt-8">
          <h2 
            className="text-xl font-semibold mb-4 flex items-center"
            style={{ color: colors.deepRed }}
          >
            <div 
              className="h-6 w-1 rounded mr-3"
              style={{ backgroundColor: colors.deepRed }}
            ></div>
            Features
          </h2>
          <ul className="space-y-2" style={{ color: colors.textDark }}>
            <li className="flex items-center">
              <span 
                className="w-1.5 h-1.5 rounded-full mr-2"
                style={{ backgroundColor: colors.deepRed }}
              ></span>
              Highest quality video downloads - 2160p with audio | First time on web
            </li>
            <li className="flex items-center">
              <span 
                className="w-1.5 h-1.5 rounded-full mr-2"
                style={{ backgroundColor: colors.deepRed }}
              ></span>
              Download audio in the best quality
            </li>
            <li className="flex items-center">
              <span 
                className="w-1.5 h-1.5 rounded-full mr-2"
                style={{ backgroundColor: colors.deepRed }}
              ></span>
              Fast download speeds
            </li>
            <li className="flex items-center">
              <span 
                className="w-1.5 h-1.5 rounded-full mr-2"
                style={{ backgroundColor: colors.deepRed }}
              ></span>
              No quality loss
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
