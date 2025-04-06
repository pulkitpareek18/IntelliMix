// API base URL from environment variable
export const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000';

// API endpoints
export const ENDPOINTS = {
  // YouTube Trimmer endpoints
  PROCESS_ARRAY: `${API_URL}/process-array`,
  PROCESS_CSV: `${API_URL}/process-csv`,
  
  // Video Downloader endpoints
  DOWNLOAD_VIDEO: `${API_URL}/download-video`,
  DOWNLOAD_AUDIO: `${API_URL}/download-audio`,
  
  // AI Parody endpoints
  GENERATE_AI: `${API_URL}/generate-ai`,
};