import React, { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Canvas } from '@react-three/fiber';
import { PerspectiveCamera } from '@react-three/drei';
import {
  ArrowRight,
  CheckCircle2,
  Clock3,
  FileMusic,
  Gauge,
  Music,
  ShieldCheck,
  Sparkles,
  Users,
  Video,
  Workflow,
} from 'lucide-react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import Logo3D from '../components/Logo3D';
import FeatureCard from '../components/FeatureCard';
import { colors } from '../utils/colors';

gsap.registerPlugin(ScrollTrigger);

const stats = [
  { label: 'Average Generation Time', value: '41 sec' },
  { label: 'Workflow Speedup', value: '39x faster' },
  { label: 'Export Quality', value: 'Up to 4K' },
  { label: 'Creator Teams Using It', value: '200+' },
];

const workflowSteps = [
  {
    title: 'Describe or Upload',
    description: 'Use prompt-based AI mix generation, direct YouTube links, or CSV batch inputs.',
    icon: Sparkles,
  },
  {
    title: 'Process with Precision',
    description: 'IntelliMix handles trimming, transitions, merges, and output processing automatically.',
    icon: Workflow,
  },
  {
    title: 'Review and Iterate',
    description: 'Play, compare, and re-run quickly using saved per-user history and reusable prompts.',
    icon: Gauge,
  },
  {
    title: 'Deliver Production Output',
    description: 'Export finalized audio and media assets ready for social, events, and client delivery.',
    icon: CheckCircle2,
  },
];

const trustPoints = [
  {
    title: 'Secure User Access',
    description: 'JWT authentication, protected routes, and user-scoped generation history.',
    icon: ShieldCheck,
  },
  {
    title: 'Fast Batch Operations',
    description: 'Process multiple clips in one run using structured input and consistent timing logic.',
    icon: Clock3,
  },
  {
    title: 'Team-Friendly UX',
    description: 'Simple onboarding and tool-specific flows for creators, editors, and operators.',
    icon: Users,
  },
];

export default function HomePage() {
  const heroRef = useRef<HTMLDivElement>(null);
  const statsRef = useRef<HTMLDivElement>(null);
  const workflowRef = useRef<HTMLDivElement>(null);
  const trustRef = useRef<HTMLDivElement>(null);
  const ctaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (heroRef.current) {
      gsap.fromTo(
        heroRef.current.querySelectorAll('[data-hero-item]'),
        { y: 24, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          duration: 0.8,
          stagger: 0.12,
          ease: 'power3.out',
        }
      );
    }

    [statsRef.current, workflowRef.current, trustRef.current, ctaRef.current].forEach((section) => {
      if (!section) {
        return;
      }

      gsap.fromTo(
        section.querySelectorAll('[data-reveal-item]'),
        { y: 30, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          duration: 0.7,
          stagger: 0.1,
          ease: 'power2.out',
          scrollTrigger: {
            trigger: section,
            start: 'top 80%',
            toggleActions: 'play none none none',
          },
        }
      );
    });
  }, []);

  return (
    <div className="mx-auto max-w-7xl py-4 sm:py-8">
      <div className="mb-8 flex justify-center sm:mb-10">
        <div className="relative">
          <div
            className="relative h-44 w-44 sm:h-56 sm:w-56"
            style={{ borderColor: `${colors.deepRed}30` }}
          >
            <Canvas>
              <PerspectiveCamera makeDefault position={[0, 0, 4]} />
              <ambientLight intensity={0.65} />
              <pointLight position={[8, 8, 8]} />
              <Logo3D />
            </Canvas>
          </div>
        </div>
      </div>

      <section ref={heroRef} className="grid items-center gap-8 lg:grid-cols-2">
        <div className="space-y-5">
          <span
            data-hero-item
            className="inline-flex rounded-full px-4 py-1 text-xs font-semibold uppercase tracking-wide"
            style={{ backgroundColor: `${colors.vibrantYellow}25`, color: colors.deepRed }}
          >
            Production Audio Workflow Platform
          </span>

          <h1
            data-hero-item
            className="text-4xl font-bold leading-tight sm:text-5xl lg:text-6xl"
            style={{ color: colors.deepRed }}
          >
            Ship Studio-Quality Audio and Media in Minutes
          </h1>

          <p data-hero-item className="max-w-2xl text-base leading-relaxed sm:text-lg" style={{ color: colors.textDark }}>
            IntelliMix combines AI-assisted mashup generation, precision clip mixing, and high-quality media downloads
            into one product workflow. Built for teams that need speed, quality, and repeatability.
          </p>

          <div data-hero-item className="flex flex-wrap gap-3">
            <Link
              to="/signup"
              className="inline-flex items-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold text-white transition-opacity hover:opacity-90"
              style={{ backgroundColor: colors.deepRed }}
            >
              Start Free
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              to="/ai-parody"
              className="inline-flex items-center gap-2 rounded-xl border px-5 py-3 text-sm font-semibold"
              style={{ borderColor: `${colors.deepRed}40`, color: colors.deepRed, backgroundColor: 'white' }}
            >
              Open Product
            </Link>
          </div>

          <p data-hero-item className="text-xs sm:text-sm" style={{ color: colors.mediumGray }}>
            A product by GetUrStyle Technologies
          </p>
        </div>

        <div data-hero-item className="relative">
          <div
            className="absolute -left-8 -top-8 h-36 w-36 rounded-full blur-3xl"
            style={{ backgroundColor: `${colors.brightRed}40` }}
          />
          <div
            className="absolute -bottom-10 -right-6 h-40 w-40 rounded-full blur-3xl"
            style={{ backgroundColor: `${colors.vibrantYellow}45` }}
          />

          <div
            className="relative rounded-3xl border bg-white/90 p-6 shadow-lg backdrop-blur-sm"
            style={{ borderColor: `${colors.deepRed}25` }}
          >
            <div className="mb-4 flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: colors.mediumGray }}>
                  Product Snapshot
                </p>
                <p className="text-lg font-bold" style={{ color: colors.deepRed }}>
                  Unified Audio Operations
                </p>
              </div>
              <div className="h-20 w-20">
                <Canvas>
                  <PerspectiveCamera makeDefault position={[0, 0, 4]} />
                  <ambientLight intensity={0.6} />
                  <pointLight position={[8, 8, 8]} />
                  <Logo3D />
                </Canvas>
              </div>
            </div>

            <div className="space-y-3">
              <div className="rounded-xl p-3" style={{ backgroundColor: `${colors.softRed}70` }}>
                <p className="text-sm font-semibold" style={{ color: colors.deepRed }}>
                  AI Music Studio
                </p>
                <p className="text-xs" style={{ color: colors.textDark }}>
                  Prompt to mashup with downloadable output and saved history.
                </p>
              </div>
              <div className="rounded-xl p-3" style={{ backgroundColor: `${colors.softestYellow}` }}>
                <p className="text-sm font-semibold" style={{ color: colors.deepRed }}>
                  Audio Mixer + CSV Batch
                </p>
                <p className="text-xs" style={{ color: colors.textDark }}>
                  Multi-clip extraction and merge with timestamp accuracy.
                </p>
              </div>
              <div className="rounded-xl p-3" style={{ backgroundColor: `${colors.softRed}55` }}>
                <p className="text-sm font-semibold" style={{ color: colors.deepRed }}>
                  Media Downloader
                </p>
                <p className="text-xs" style={{ color: colors.textDark }}>
                  Highest quality video/audio delivery for production pipelines.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section ref={statsRef} className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <div
            key={stat.label}
            data-reveal-item
            className="rounded-2xl border bg-white px-5 py-4 shadow-sm"
            style={{ borderColor: `${colors.deepRed}20` }}
          >
            <p className="text-xs font-medium uppercase tracking-wide" style={{ color: colors.mediumGray }}>
              {stat.label}
            </p>
            <p className="mt-2 text-2xl font-bold" style={{ color: colors.deepRed }}>
              {stat.value}
            </p>
          </div>
        ))}
      </section>

      <section className="mt-14">
        <div className="mb-8 text-center">
          <h2 className="text-3xl font-bold sm:text-4xl" style={{ color: colors.deepRed }}>
            Core Product Capabilities
          </h2>
          <p className="mx-auto mt-3 max-w-3xl text-sm sm:text-base" style={{ color: colors.textDark }}>
            Purpose-built feature modules for creative teams that need predictable output quality and faster turnaround.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          <FeatureCard
            icon={<FileMusic className="h-12 w-12" />}
            title="AI Music Studio"
            description="Create mashups from plain-language prompts and iterate quickly with history-backed workflows."
            link="/ai-parody"
            color={colors.brightRed}
          />
          <FeatureCard
            icon={<Music className="h-12 w-12" />}
            title="Audio Mixer"
            description="Trim, stitch, and batch-process clip sets with timestamp precision and CSV imports."
            link="/youtube-trimmer"
            color={colors.vibrantYellow}
          />
          <FeatureCard
            icon={<Video className="h-12 w-12" />}
            title="Media Downloader"
            description="Download high-quality video and audio assets optimized for production delivery."
            link="/video-downloader"
            color={colors.deepRed}
          />
        </div>
      </section>

      <section ref={workflowRef} className="mt-14 rounded-3xl border bg-white p-6 shadow-sm sm:p-8" style={{ borderColor: `${colors.deepRed}18` }}>
        <div className="mb-6">
          <h3 className="text-2xl font-bold sm:text-3xl" style={{ color: colors.deepRed }}>
            Workflow Built for Shipping
          </h3>
          <p className="mt-2 text-sm sm:text-base" style={{ color: colors.textDark }}>
            A predictable pipeline from idea to final output, designed to reduce manual editing overhead.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {workflowSteps.map((step, index) => {
            const Icon = step.icon;
            return (
              <div
                key={step.title}
                data-reveal-item
                className="rounded-2xl border p-4"
                style={{ borderColor: `${colors.deepRed}20`, backgroundColor: index % 2 === 0 ? `${colors.softRed}40` : 'white' }}
              >
                <div className="mb-3 flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full" style={{ backgroundColor: `${colors.deepRed}18` }}>
                    <Icon className="h-5 w-5" style={{ color: colors.deepRed }} />
                  </div>
                  <p className="text-sm font-semibold uppercase tracking-wide" style={{ color: colors.deepRed }}>
                    Step {index + 1}
                  </p>
                </div>
                <h4 className="text-lg font-semibold" style={{ color: colors.deepRed }}>
                  {step.title}
                </h4>
                <p className="mt-1 text-sm" style={{ color: colors.textDark }}>
                  {step.description}
                </p>
              </div>
            );
          })}
        </div>
      </section>

      <section ref={trustRef} className="mt-14 grid gap-5 md:grid-cols-3">
        {trustPoints.map((point) => {
          const Icon = point.icon;
          return (
            <div
              key={point.title}
              data-reveal-item
              className="rounded-2xl border bg-white p-5 shadow-sm"
              style={{ borderColor: `${colors.deepRed}20` }}
            >
              <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-full" style={{ backgroundColor: `${colors.vibrantYellow}30` }}>
                <Icon className="h-5 w-5" style={{ color: colors.deepRed }} />
              </div>
              <h4 className="text-lg font-semibold" style={{ color: colors.deepRed }}>
                {point.title}
              </h4>
              <p className="mt-1 text-sm" style={{ color: colors.textDark }}>
                {point.description}
              </p>
            </div>
          );
        })}
      </section>

      <section
        ref={ctaRef}
        className="mt-14 rounded-3xl border p-7 text-center sm:p-10"
        style={{
          borderColor: `${colors.deepRed}30`,
          background: `linear-gradient(135deg, ${colors.softRed}90, ${colors.softestYellow})`,
        }}
      >
        <h3 data-reveal-item className="text-3xl font-bold sm:text-4xl" style={{ color: colors.deepRed }}>
          Launch Your Production Workflow with IntelliMix
        </h3>
        <p data-reveal-item className="mx-auto mt-3 max-w-2xl text-sm sm:text-base" style={{ color: colors.textDark }}>
          Stop switching between disconnected tools. Run AI generation, editing, downloading, and history tracking in one product experience.
        </p>
        <div data-reveal-item className="mt-6 flex flex-wrap justify-center gap-3">
          <Link
            to="/signup"
            className="inline-flex items-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold text-white transition-opacity hover:opacity-90"
            style={{ backgroundColor: colors.deepRed }}
          >
            Create Account
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            to="/pricing"
            className="inline-flex items-center gap-2 rounded-xl border bg-white px-5 py-3 text-sm font-semibold"
            style={{ borderColor: `${colors.deepRed}40`, color: colors.deepRed }}
          >
            View Pricing
          </Link>
        </div>
      </section>
    </div>
  );
}
