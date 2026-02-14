import React, { Suspense, lazy, useEffect, useRef } from 'react';
import { BrowserRouter as Router, Link, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import gsap from 'gsap';
import NavBar from './components/Navbar';
import { colors } from './utils/colors';
import ProtectedRoute from './components/ProtectedRoute';
import { useAuth } from './context/useAuth';

const HomeBackgroundScene = lazy(() => import('./components/HomeBackgroundScene'));
const AIParody = lazy(() => import('./pages/AIParody'));
const YouTubeTrimmer = lazy(() => import('./pages/YouTubeTrimmer'));
const VideoDownloader = lazy(() => import('./pages/VideoDownloader'));
const HomePage = lazy(() => import('./pages/HomePage'));
const LoginPage = lazy(() => import('./pages/Login'));
const SignupPage = lazy(() => import('./pages/Signup'));
const HistoryPage = lazy(() => import('./pages/History'));
const NotFoundPage = lazy(() => import('./pages/NotFound'));

function App() {
  return (
    <Router
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <AppContent />
    </Router>
  );
}

function AppContent() {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();
  const mainRef = useRef<HTMLDivElement>(null);
  const isHomePage = location.pathname === '/';
  const isAIMusicStudio = location.pathname === '/ai-parody';
  const rootStyle = isAIMusicStudio
    ? ({ '--studio-topbar-h': '56px' } as React.CSSProperties)
    : undefined;

  useEffect(() => {
    if (!mainRef.current) {
      return;
    }

    gsap.fromTo(mainRef.current, { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.6, ease: 'power2.out' });
  }, [location]);

  const pageFallback = (
    <div className="flex min-h-[220px] items-center justify-center text-sm" style={{ color: colors.darkGray }}>
      Loading...
    </div>
  );

  return (
    <div
      className={isAIMusicStudio ? 'relative h-[100dvh] overflow-hidden bg-white' : 'relative min-h-screen bg-white'}
      style={rootStyle}
    >
      {isHomePage ? (
        <div className="fixed inset-0 z-0">
          <Suspense fallback={<div className="h-full w-full bg-white" />}>
            <HomeBackgroundScene />
          </Suspense>
        </div>
      ) : (
        <div
          className="fixed inset-0 z-0"
          style={{
            background: `
              radial-gradient(circle at 8% 10%, rgba(244,72,58,0.13), transparent 28%),
              radial-gradient(circle at 92% 82%, rgba(255,185,43,0.17), transparent 30%),
              linear-gradient(180deg, #fffdf9 0%, #ffffff 100%)
            `,
          }}
        />
      )}

      <NavBar variant={isAIMusicStudio ? 'studio' : 'default'} />

      <main
        ref={mainRef}
        className={
          isAIMusicStudio
            ? 'relative z-10 w-full overflow-hidden p-0'
            : 'relative z-10 mx-auto max-w-7xl px-2 pb-14 pt-20 sm:px-4 sm:pt-24 lg:px-8'
        }
        style={isAIMusicStudio ? { height: 'calc(100dvh - var(--studio-topbar-h))' } : undefined}
      >
        <Suspense fallback={pageFallback}>
          <Routes>
            <Route path="/" element={!loading && isAuthenticated ? <Navigate to="/ai-parody" replace /> : <HomePage />} />
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
              path="/media-generations"
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
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Suspense>
      </main>

      {!isAIMusicStudio && (
        <footer className="relative z-10 border-t border-red-100 bg-white/92 backdrop-blur-sm">
          <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-5 text-sm sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
            <p style={{ color: colors.darkGray }}>A product by GetUrStyle Technologies</p>
            <div className="flex items-center gap-4 text-xs sm:text-sm">
              <Link className="hover:underline" style={{ color: colors.deepRed }} to="/login">
                Login
              </Link>
              <Link className="hover:underline" style={{ color: colors.deepRed }} to="/signup">
                Create Account
              </Link>
            </div>
          </div>
        </footer>
      )}
    </div>
  );
}

export default App;
