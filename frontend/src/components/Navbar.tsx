import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { FileMusic, History, Menu, Music, Video, X } from 'lucide-react';
import { Canvas } from '@react-three/fiber';
import { PerspectiveCamera } from '@react-three/drei';
import Logo3D from './Logo3D';
import { colors } from '../utils/colors';
import { useAuth } from '../context/AuthContext';

interface NavigationItem {
  to: string;
  label: string;
  icon: React.ReactNode;
  protected: boolean;
}

const navItems: NavigationItem[] = [
  { to: '/ai-parody', label: 'AI Music Studio', icon: <FileMusic className="h-4 w-4" />, protected: true },
  { to: '/youtube-trimmer', label: 'Audio Mixer', icon: <Music className="h-4 w-4" />, protected: true },
  { to: '/video-downloader', label: 'Media Downloader', icon: <Video className="h-4 w-4" />, protected: true },
  { to: '/history', label: 'History', icon: <History className="h-4 w-4" />, protected: true },
  { to: '/pricing', label: 'Pricing', icon: <span className="text-sm">$</span>, protected: false },
];

function AppNavLink({ to, label, icon, active }: { to: string; label: string; icon: React.ReactNode; active: boolean }) {
  return (
    <Link
      to={to}
      className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors"
      style={{
        backgroundColor: active ? `${colors.deepRed}20` : colors.lightGray,
        color: active ? colors.deepRed : colors.darkGray,
        border: `1px solid ${active ? `${colors.deepRed}55` : `${colors.deepRed}20`}`,
      }}
    >
      {icon}
      <span>{label}</span>
    </Link>
  );
}

export default function NavBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, user, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  const visibleItems = navItems.filter((item) => (item.protected ? isAuthenticated : true));

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  return (
    <nav className="sticky top-0 z-50 border-b border-gray-200 bg-white/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link to="/" className="flex items-center gap-3">
          <div className="h-10 w-10">
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
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
              color: 'transparent',
            }}
          >
            IntelliMix
          </span>
        </Link>

        <div className="hidden items-center gap-2 md:flex">
          {visibleItems.map((item) => (
            <AppNavLink
              key={item.to}
              to={item.to}
              label={item.label}
              icon={item.icon}
              active={location.pathname === item.to}
            />
          ))}
        </div>

        <div className="hidden items-center gap-2 md:flex">
          {isAuthenticated ? (
            <>
              <span className="rounded-md bg-red-50 px-3 py-2 text-sm" style={{ color: colors.deepRed }}>
                {user?.name || 'Account'}
              </span>
              <button
                type="button"
                onClick={handleLogout}
                className="rounded-md px-3 py-2 text-sm font-semibold text-white"
                style={{ backgroundColor: colors.deepRed }}
              >
                Logout
              </button>
            </>
          ) : (
            <>
              <Link
                to="/login"
                className="rounded-md px-3 py-2 text-sm font-semibold"
                style={{ backgroundColor: colors.lightGray, color: colors.darkGray }}
              >
                Login
              </Link>
              <Link
                to="/signup"
                className="rounded-md px-3 py-2 text-sm font-semibold text-white"
                style={{ backgroundColor: colors.deepRed }}
              >
                Sign Up
              </Link>
            </>
          )}
        </div>

        <button
          type="button"
          className="rounded-md border border-red-100 p-2 md:hidden"
          onClick={() => setMobileOpen((prev) => !prev)}
          aria-label="Toggle navigation"
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {mobileOpen && (
        <div className="border-t border-gray-200 bg-white px-4 py-3 md:hidden">
          <div className="space-y-2">
            {visibleItems.map((item) => (
              <AppNavLink
                key={item.to}
                to={item.to}
                label={item.label}
                icon={item.icon}
                active={location.pathname === item.to}
              />
            ))}
          </div>

          <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-xs text-red-800">
            A product by GetUrStyle Technologies
          </p>

          <div className="mt-3 flex flex-col gap-2">
            {isAuthenticated ? (
              <>
                <p className="rounded-md bg-red-50 px-3 py-2 text-sm" style={{ color: colors.deepRed }}>
                  {user?.email}
                </p>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="rounded-md px-3 py-2 text-sm font-semibold text-white"
                  style={{ backgroundColor: colors.deepRed }}
                >
                  Logout
                </button>
              </>
            ) : (
              <>
                <Link
                  to="/login"
                  className="rounded-md px-3 py-2 text-center text-sm font-semibold"
                  style={{ backgroundColor: colors.lightGray, color: colors.darkGray }}
                >
                  Login
                </Link>
                <Link
                  to="/signup"
                  className="rounded-md px-3 py-2 text-center text-sm font-semibold text-white"
                  style={{ backgroundColor: colors.deepRed }}
                >
                  Sign Up
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </nav>
  );
}
