import React, { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { FileMusic, History, Menu, MessageSquare, X } from 'lucide-react';
import { Canvas } from '@react-three/fiber';
import { PerspectiveCamera } from '@react-three/drei';
import Logo3D from './Logo3D';
import { colors } from '../utils/colors';
import { useAuth } from '../context/useAuth';

interface NavigationItem {
  to: string;
  label: string;
  icon: React.ReactNode;
  protected: boolean;
}

interface NavBarProps {
  variant?: 'default' | 'studio';
}

const navItems: NavigationItem[] = [
  { to: '/ai-parody', label: 'AI Music Studio', icon: <FileMusic className="h-4 w-4" />, protected: true },
  { to: '/media-generations', label: 'Media Generations', icon: <History className="h-4 w-4" />, protected: true },
];

function isItemActive(pathname: string, itemTo: string): boolean {
  if (itemTo === '/media-generations') {
    return pathname === '/media-generations' || pathname === '/history';
  }
  return pathname === itemTo;
}

function AppNavLink({
  to,
  label,
  icon,
  active,
  compact = false,
}: {
  to: string;
  label: string;
  icon: React.ReactNode;
  active: boolean;
  compact?: boolean;
}) {
  return (
    <Link
      to={to}
      className={
        compact
          ? 'flex items-center gap-1.5 rounded-md px-2.5 py-2 text-xs font-semibold transition-colors'
          : 'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors'
      }
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

function dispatchStudioOpenThreads() {
  window.dispatchEvent(new CustomEvent('studio-open-threads'));
}

export default function NavBar({ variant = 'default' }: NavBarProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, user, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const isStudio = variant === 'studio';

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const visibleItems = useMemo(
    () => navItems.filter((item) => (item.protected ? isAuthenticated : true)),
    [isAuthenticated]
  );

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  const accountLabel = user?.name || user?.email || 'Account';

  return (
    <nav
      className={
        isStudio
          ? 'relative z-50 border-b border-gray-200 bg-white/95 backdrop-blur-md'
          : 'sticky top-0 z-50 border-b border-gray-200 bg-white/90 backdrop-blur-md'
      }
    >
      <div className={isStudio ? 'mx-auto flex h-14 items-center justify-between px-3 sm:px-4' : 'mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8'}>
        <div className="flex min-w-0 items-center gap-3">
          <Link to="/" className="flex items-center gap-3">
            <div className={isStudio ? 'h-8 w-8' : 'h-10 w-10'}>
              <Canvas>
                <PerspectiveCamera makeDefault position={[0, 0, 4]} />
                <ambientLight intensity={0.5} />
                <pointLight position={[10, 10, 10]} />
                <Logo3D />
              </Canvas>
            </div>
            <span
              className={isStudio ? 'text-base font-bold sm:text-lg' : 'text-xl font-bold'}
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
          {isStudio && (
            <span className="hidden text-xs font-semibold uppercase tracking-wide text-gray-500 sm:inline">
              AI Music Studio
            </span>
          )}
        </div>

        <div className={isStudio ? 'hidden min-w-0 items-center gap-1 md:flex' : 'hidden items-center gap-2 md:flex'}>
          {visibleItems.map((item) => (
            <AppNavLink
              key={item.to}
              to={item.to}
              label={item.label}
              icon={item.icon}
              active={isItemActive(location.pathname, item.to)}
              compact={isStudio}
            />
          ))}
        </div>

        <div className="flex items-center gap-2">
          {isStudio && (
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-md border border-red-200 px-2 py-1 text-xs font-semibold text-red-700 md:hidden"
              onClick={dispatchStudioOpenThreads}
            >
              <MessageSquare className="h-4 w-4" />
              Chats
            </button>
          )}

          <div className={isStudio ? 'hidden items-center gap-2 md:flex' : 'hidden items-center gap-2 md:flex'}>
            {isAuthenticated ? (
              <>
                <span
                  className={isStudio ? 'max-w-44 truncate rounded-md bg-red-50 px-2.5 py-1.5 text-xs' : 'rounded-md bg-red-50 px-3 py-2 text-sm'}
                  style={{ color: colors.deepRed }}
                  title={accountLabel}
                >
                  {accountLabel}
                </span>
                <button
                  type="button"
                  onClick={handleLogout}
                  className={isStudio ? 'rounded-md px-2.5 py-1.5 text-xs font-semibold text-white' : 'rounded-md px-3 py-2 text-sm font-semibold text-white'}
                  style={{ backgroundColor: colors.deepRed }}
                >
                  Logout
                </button>
              </>
            ) : (
              <>
                <Link
                  to="/login"
                  className={isStudio ? 'rounded-md px-2.5 py-1.5 text-xs font-semibold' : 'rounded-md px-3 py-2 text-sm font-semibold'}
                  style={{ backgroundColor: colors.lightGray, color: colors.darkGray }}
                >
                  Login
                </Link>
                <Link
                  to="/signup"
                  className={isStudio ? 'rounded-md px-2.5 py-1.5 text-xs font-semibold text-white' : 'rounded-md px-3 py-2 text-sm font-semibold text-white'}
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
      </div>

      {mobileOpen && (
        <div className="border-t border-gray-200 bg-white px-4 py-3 md:hidden">
          {isStudio && (
            <button
              type="button"
              className="mb-3 inline-flex w-full items-center justify-center gap-2 rounded-md border border-red-200 px-3 py-2 text-sm font-semibold text-red-700"
              onClick={() => {
                dispatchStudioOpenThreads();
                setMobileOpen(false);
              }}
            >
              <MessageSquare className="h-4 w-4" />
              Open Mix Chats
            </button>
          )}

          <div className="space-y-2">
            {visibleItems.map((item) => (
              <AppNavLink
                key={item.to}
                to={item.to}
                label={item.label}
                icon={item.icon}
                active={isItemActive(location.pathname, item.to)}
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
                  {accountLabel}
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
