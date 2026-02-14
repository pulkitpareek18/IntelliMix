import { Link } from 'react-router-dom';
import { ArrowLeft, Search } from 'lucide-react';
import { colors } from '../utils/colors';

export default function NotFoundPage() {
  return (
    <div className="mx-auto flex min-h-[55vh] max-w-3xl items-center justify-center px-4 py-10">
      <div
        className="w-full rounded-3xl border bg-white/95 p-8 text-center shadow-sm backdrop-blur-sm sm:p-10"
        style={{ borderColor: `${colors.deepRed}22` }}
      >
        <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full" style={{ backgroundColor: `${colors.softRed}` }}>
          <Search className="h-7 w-7" style={{ color: colors.deepRed }} />
        </div>
        <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: colors.mediumGray }}>
          404
        </p>
        <h1 className="mt-2 text-3xl font-bold sm:text-4xl" style={{ color: colors.deepRed }}>
          Page Not Found
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-sm sm:text-base" style={{ color: colors.textDark }}>
          The link may be outdated or the page may have moved. Go back to the product home and continue your workflow.
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          <Link
            to="/"
            className="inline-flex items-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold text-white transition-opacity hover:opacity-90"
            style={{ backgroundColor: colors.deepRed }}
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Home
          </Link>
          <Link
            to="/ai-parody"
            className="inline-flex items-center rounded-xl border bg-white px-5 py-3 text-sm font-semibold"
            style={{ borderColor: `${colors.deepRed}35`, color: colors.deepRed }}
          >
            Open Studio
          </Link>
        </div>
      </div>
    </div>
  );
}
