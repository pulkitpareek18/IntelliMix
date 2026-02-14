import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';

const colors = {
  deepRed: '#d24d34',
  brightRed: '#f4483a',
  softRed: '#fee2e1',
  textDark: '#444444',
};

export default function SignupPage() {
  const { signup, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/ai-parody', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    if (!name.trim() || !email.trim() || !password.trim()) {
      setError('All fields are required');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setSubmitting(true);
    try {
      await signup(name, email, password);
      navigate('/ai-parody', { replace: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Signup failed';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-md rounded-2xl border border-red-100 bg-white p-8 shadow-sm">
      <h1 className="mb-2 text-3xl font-bold" style={{ color: colors.deepRed }}>
        Create account
      </h1>
      <p className="mb-6 text-sm" style={{ color: colors.textDark }}>
        Start generating and keep your history synced.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium" style={{ color: colors.deepRed }}>
            Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="w-full rounded-lg border border-red-100 px-3 py-2 outline-none focus:ring-2"
            style={{ color: colors.textDark }}
            placeholder="Your name"
          />
        </div>

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
            placeholder="Minimum 8 characters"
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
          {submitting ? 'Creating account...' : 'Create account'}
        </button>
      </form>

      <p className="mt-5 text-sm" style={{ color: colors.textDark }}>
        Already have an account?{' '}
        <Link to="/login" className="font-semibold" style={{ color: colors.deepRed }}>
          Sign in
        </Link>
      </p>
    </div>
  );
}
