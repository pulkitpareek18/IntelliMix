import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Canvas } from '@react-three/fiber';
import { PerspectiveCamera } from '@react-three/drei';
import {
  ArrowRight,
  BadgeCheck,
  CheckCircle2,
  Clock3,
  FileMusic,
  Gauge,
  ShieldCheck,
  Sparkles,
  Users,
  Workflow,
} from 'lucide-react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import Logo3D from '../components/Logo3D';
import FeatureCard from '../components/FeatureCard';
import { colors } from '../utils/colors';

gsap.registerPlugin(ScrollTrigger);

const stats = [
  { label: 'Average Plan Turn', value: '58 sec' },
  { label: 'Constraint Accuracy', value: '96%' },
  { label: 'Revision Style', value: 'Natural Chat' },
  { label: 'Versioned Outputs', value: 'Every render' },
];

const workflowSteps = [
  {
    title: 'Describe the Mix',
    description: 'Tell IntelliMix your artist, vibe, duration, transitions, and sequence constraints in plain language.',
    icon: Sparkles,
  },
  {
    title: 'Adaptive Plan Drafting',
    description: 'The AI audio engineer drafts songs and timeline segments, then asks only the clarifications needed.',
    icon: Workflow,
  },
  {
    title: 'Revise Naturally',
    description: 'Keep revising in chat with full context continuity, so constraints stay aligned across turns.',
    icon: Gauge,
  },
  {
    title: 'Approve and Render',
    description: 'Approve the draft to generate the final output with version tracking and downloadable exports.',
    icon: CheckCircle2,
  },
];

const trustPoints = [
  {
    title: 'AI-First Planning',
    description: 'Prompt interpretation and revisions are handled by the AI audio engineer, not rigid templates.',
    icon: ShieldCheck,
  },
  {
    title: 'Reliable Execution',
    description: 'Queue-based workers with retry-safe status tracking keep long-running jobs predictable.',
    icon: Clock3,
  },
  {
    title: 'Context Memory by Chat',
    description: 'Draft continuity and version lineage preserve intent as users keep refining the same mix.',
    icon: Users,
  },
];

const launchChecklist = [
  'Natural chat-first planning and revision flow',
  'Strict constraint contract with clarification before violations',
  'Versioned outputs and media generation history',
  'Dockerized backend, worker, Redis, and Postgres stack',
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
            AI Audio Engineer
          </span>

          <h1
            data-hero-item
            className="text-4xl font-bold leading-tight sm:text-5xl lg:text-6xl"
            style={{ color: colors.deepRed }}
          >
            Build Better Mashups Through Natural Conversation
          </h1>

          <p data-hero-item className="max-w-2xl text-base leading-relaxed sm:text-lg" style={{ color: colors.textDark }}>
            IntelliMix turns your prompts into constraint-accurate mix plans, lets you revise naturally, and renders
            versioned outputs without losing context across turns.
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
                  Product Snapshot
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
                  Natural prompt-to-mix planning with assistant-led clarifications.
                </p>
              </div>
              <div className="rounded-xl p-3" style={{ backgroundColor: `${colors.softestYellow}` }}>
                <p className="text-sm font-semibold" style={{ color: colors.deepRed }}>
                  Constraint Contract
                </p>
                <p className="text-xs" style={{ color: colors.textDark }}>
                  Hard enforcement of songs, segments, order, and repeat instructions.
                </p>
              </div>
              <div className="rounded-xl p-3" style={{ backgroundColor: `${colors.softRed}55` }}>
                <p className="text-sm font-semibold" style={{ color: colors.deepRed }}>
                  Media Generations
                </p>
                <p className="text-xs" style={{ color: colors.textDark }}>
                  Account-level history of generated outputs with version references.
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
            Focused launch scope around the AI studio experience and reliable revision-to-render workflow.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          <FeatureCard
            icon={<FileMusic className="h-12 w-12" />}
            title="AI Music Studio"
            description="Create mashups from plain-language prompts and keep refining in the same intelligent thread."
            link="/ai-parody"
            color={colors.brightRed}
          />
          <FeatureCard
            icon={<Workflow className="h-12 w-12" />}
            title="Adaptive Plan Revisions"
            description="Use freeform revisions while preserving draft continuity, constraints, and sequence intent."
            link="/ai-parody"
            color={colors.vibrantYellow}
          />
          <FeatureCard
            icon={<Gauge className="h-12 w-12" />}
            title="Media Generations"
            description="Review generated outputs by account and chat with clear version and output codes."
            link="/media-generations"
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

      <section className="mt-14 rounded-3xl border bg-white p-6 shadow-sm sm:p-8" style={{ borderColor: `${colors.deepRed}18` }}>
        <div className="mb-5">
          <h3 className="text-2xl font-bold sm:text-3xl" style={{ color: colors.deepRed }}>
            Built to Launch, Not Just Demo
          </h3>
          <p className="mt-2 text-sm sm:text-base" style={{ color: colors.textDark }}>
            The platform is structured for real user operations with repeatable workflows and production-grade controls.
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {launchChecklist.map((item) => (
            <div
              key={item}
              className="flex items-center gap-3 rounded-xl border px-4 py-3"
              style={{ borderColor: `${colors.deepRed}22`, backgroundColor: `${colors.softestYellow}` }}
            >
              <BadgeCheck className="h-5 w-5" style={{ color: colors.deepRed }} />
              <p className="text-sm font-medium" style={{ color: colors.textDark }}>
                {item}
              </p>
            </div>
          ))}
        </div>
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
          Launch Faster with an AI Audio Engineer That Actually Listens
        </h3>
        <p data-reveal-item className="mx-auto mt-3 max-w-2xl text-sm sm:text-base" style={{ color: colors.textDark }}>
          Move from brief to approved mix in one thread, with strict constraint handling, clear progress, and versioned output delivery.
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
            to="/ai-parody"
            className="inline-flex items-center gap-2 rounded-xl border bg-white px-5 py-3 text-sm font-semibold"
            style={{ borderColor: `${colors.deepRed}40`, color: colors.deepRed }}
          >
            Open Studio
          </Link>
        </div>
      </section>
    </div>
  );
}
