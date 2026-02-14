import React, { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';

const colors = {
  deepRed: '#d24d34',
  brightRed: '#f4483a',
  vibrantYellow: '#ffb92b',
  softRed: '#fee2e1',
  textDark: '#444444',
};

export default function LoginPage() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const destination = useMemo(() => {
    const state = location.state as { from?: string } | null;
    return state?.from || '/ai-parody';
  }, [location.state]);

  useEffect(() => {
    if (isAuthenticated) {
      navigate(destination, { replace: true });
    }
  }, [isAuthenticated, destination, navigate]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    if (!email.trim() || !password.trim()) {
      setError('Email and password are required');
      return;
    }

    setSubmitting(true);
    try {
      await login(email, password);
      navigate(destination, { replace: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-md rounded-2xl border border-red-100 bg-white p-8 shadow-sm">
      <h1 className="mb-2 text-3xl font-bold" style={{ color: colors.deepRed }}>
        Sign in
      </h1>
      <p className="mb-6 text-sm" style={{ color: colors.textDark }}>
        Continue to your IntelliMix workspace.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium" style={{ color: colors.deepRed }}>
            Email
          </label>
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="w-full rounded-lg border border-red-100 px-3 py-2 outline-none focus:ring-2"
            style={{ color: colors.textDark }}
            placeholder="you@company.com"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium" style={{ color: colors.deepRed }}>
            Password
          </label>
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="w-full rounded-lg border border-red-100 px-3 py-2 outline-none focus:ring-2"
            style={{ color: colors.textDark }}
            placeholder="********"
          />
        </div>

        {error && (
          <p className="rounded-md px-3 py-2 text-sm" style={{ backgroundColor: colors.softRed, color: colors.brightRed }}>
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-lg px-4 py-2 font-semibold text-white transition-opacity disabled:opacity-70"
          style={{ backgroundColor: colors.deepRed }}
        >
          {submitting ? 'Signing in...' : 'Sign in'}
        </button>
      </form>

      <p className="mt-5 text-sm" style={{ color: colors.textDark }}>
        No account yet?{' '}
        <Link to="/signup" className="font-semibold" style={{ color: colors.deepRed }}>
          Create one
        </Link>
      </p>

      <div className="mt-6 rounded-lg px-3 py-2 text-xs" style={{ backgroundColor: '#fff9ec', color: '#7a5d1e' }}>
        <strong>Note:</strong> production secrets must be set in backend environment variables.
      </div>
    </div>
  );
}
