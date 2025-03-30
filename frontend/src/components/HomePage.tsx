function HomePage() {
  const featuresRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const descriptionRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    if (featuresRef.current) {
      gsap.fromTo(
        featuresRef.current.children,
        { y: 50, opacity: 0 }, // Initial state
        {
          y: 0,
          opacity: 1,
          duration: 0.8,
          stagger: 0.2,
          ease: "power3.out",
          scrollTrigger: {
            trigger: featuresRef.current,
            start: "top center+=100",
            toggleActions: "play none none none",
          },
        }
      );
    }

    if (titleRef.current && descriptionRef.current) {
      gsap.fromTo(
        titleRef.current,
        { y: 30, opacity: 0 }, // Initial state
        { y: 0, opacity: 1, duration: 1, ease: "power3.out" }
      );

      gsap.fromTo(
        descriptionRef.current,
        { y: 30, opacity: 0 }, // Initial state
        { y: 0, opacity: 1, duration: 1, delay: 0.3, ease: "power3.out" }
      );
    }
  }, []);

  return (
    <div className="text-center py-12">
      <div className="mb-16">
        <div className="relative inline-block mb-8">
          <div className="w-40 h-40 mx-auto">
            <Canvas>
              <PerspectiveCamera makeDefault position={[0, 0, 4]} />
              <ambientLight intensity={0.5} />
              <pointLight position={[10, 10, 10]} />
              <Logo3D />
            </Canvas>
          </div>
        </div>
        <h1 
          ref={titleRef}
          className="text-7xl font-bold mb-6 tracking-tight"
          style={{
            background: 'linear-gradient(to right, #22d3ee, #0ea5e9, #22d3ee)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text'
          }}
        >
          IntelliMix Studio
        </h1>
        <p 
          ref={descriptionRef}
          className="text-2xl text-gray-300 max-w-3xl mx-auto leading-relaxed"
        >
          Transform your creative vision into reality with our
          <span className="text-cyan-400"> AI-powered </span>
          audio suite
        </p>
      </div>

      <div ref={featuresRef} className="grid md:grid-cols-3 gap-8 mt-16">
        <FeatureCard
          icon={<FileMusic className="w-12 h-12" />}
          title="AI Music Studio"
          description="Create unique transformations of songs using advanced AI. Perfect for remixes, covers, and creative experiments."
          link="/ai-parody"
        />
        <FeatureCard
          icon={<Music className="w-12 h-12" />}
          title="Audio Trimmer"
          description="Extract and edit specific portions from audio tracks. Supports batch processing for efficient workflows."
          link="/youtube-trimmer"
        />
        <FeatureCard
          icon={<Video className="w-12 h-12" />}
          title="Media Downloader"
          description="Download high-quality audio and video content. Optimized for the best possible quality."
          link="/video-downloader"
        />
      </div>
    </div>
  );
}