document.addEventListener('DOMContentLoaded', () => {
    const SLIDE_TRANSITION = 800; // Transition duration in ms
    const SWIPE_THRESHOLD = 50; // Minimum swipe distance for mobile
    const SCROLL_LOCK_TIME = SLIDE_TRANSITION + 100; // Buffer to prevent multi-scrolls
    const SCROLL_THRESHOLD = 50; // Scroll sensitivity
    const SCROLL_COOLDOWN = 50; // Cooldown between scroll events in ms
    const EASING_FUNCTION = 'cubic-bezier(0.42, 0, 0.58, 1)'; // Smoother easing function

    const slidesContainer = document.querySelector('.slides-container');
    const slides = document.querySelectorAll('.slide');
    const headerContainer = document.querySelector('.header-container');
    
    let currentSlide = 0;
    let isAnimating = false;
    let lastScrollTime = 0;
    let scrollAccumulator = 0;

    function setupStyles() {
        document.body.style.margin = '0';
        document.body.style.height = '100%'; // Ensure full height for Safari
        document.body.style.overflow = 'hidden';
        document.documentElement.style.height = '100%'; // Safari fix
        document.documentElement.style.overflow = 'hidden';

        slidesContainer.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100vh;
            overflow: hidden;
            -webkit-overflow-scrolling: touch; /* Smooth scrolling in iOS Safari */
        `;

        slides.forEach((slide, index) => {
            // Set slide to exactly viewport height
            const viewportHeight = window.innerHeight;
            
            slide.style.cssText = `
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: ${viewportHeight}px;
                transition: transform ${SLIDE_TRANSITION}ms ${EASING_FUNCTION};
                will-change: transform;
                -webkit-transform: translateY(${index * viewportHeight}px); /* Prefixed for Safari */
                transform: translateY(${index * viewportHeight}px);
                overflow: hidden;  /* Prevent content from extending beyond slide */
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
            `;
            
            // Apply styles to ensure images fit within the slide
            const slideImages = slide.querySelectorAll('img');
            slideImages.forEach(img => {
                // Check if desktop or mobile
                const isMobile = window.innerWidth <= 768;
                
                img.style.cssText = isMobile ? 
                `
                    object-fit: contain;
                    max-width: 100%;
                    max-height: ${viewportHeight}px;
                    display: block;
                    width: auto;
                    height: auto;
                ` : 
                `
                    object-fit: cover;
                    width: 100%;
                    height: 100vh;
                    display: block;
                    max-width: 100vw;
                    max-height: 100vh;
                `;
                
                // When image loads, ensure it fits correctly
                if (img.complete) {
                    adjustImageSize(img, viewportHeight);
                } else {
                    img.onload = () => adjustImageSize(img, viewportHeight);
                }
            });
            
            // Ensure any slide content containers maintain proper size
            const contentContainers = slide.querySelectorAll('.slide-content');
            contentContainers.forEach(container => {
                container.style.cssText = `
                    max-height: ${viewportHeight}px;
                    overflow: hidden;
                    width: 100%;
                `;
            });
        });
        
        // Add resize handler to adjust on window size changes
        window.addEventListener('resize', adjustAllSlides);
    }

    // Function to adjust a single image to fit within viewport
    function adjustImageSize(img, maxHeight) {
        const isMobile = window.innerWidth <= 768;
        
        if (isMobile) {
            // Mobile behavior: contain within viewport
            if (img.offsetHeight > maxHeight) {
                img.style.height = maxHeight + 'px';
                img.style.width = 'auto';
                img.style.objectFit = 'contain';
            }
        } else {
            // Desktop behavior: fill viewport when fullscreen
            img.style.width = '100%';
            img.style.height = '100vh';
            img.style.objectFit = 'cover';
            
            // Check if the image is in a slide with specific display needs
            const slideParent = img.closest('.slide');
            if (slideParent && slideParent.classList.contains('contain-image')) {
                img.style.objectFit = 'contain';
            }
        }
    }

    // Function to adjust all slides and images when window resizes
    function adjustAllSlides() {
        const viewportHeight = window.innerHeight;
        
        slides.forEach((slide, index) => {
            // Update slide height to match viewport
            slide.style.height = viewportHeight + 'px';
            
            // Update transform to maintain position
            slide.style.webkitTransform = `translateY(${(index - currentSlide) * viewportHeight}px)`;
            slide.style.transform = `translateY(${(index - currentSlide) * viewportHeight}px)`;
            
            // Adjust images within the slide
            const slideImages = slide.querySelectorAll('img');
            slideImages.forEach(img => {
                adjustImageSize(img, viewportHeight);
            });
            
            // Adjust content containers
            const contentContainers = slide.querySelectorAll('.slide-content');
            contentContainers.forEach(container => {
                container.style.maxHeight = viewportHeight + 'px';
            });
        });
    }

    function updateHeaderStyles() {
        if (!headerContainer) return;

        const currentSlideElement = slides[currentSlide];
        headerContainer.classList.remove('header-light', 'header-dark');
        
        if (currentSlideElement.classList.contains('turn-header-dark')) {
            headerContainer.classList.add('header-dark');
            document.documentElement.style.setProperty('--header-color', '#333333');
        } else {
            headerContainer.classList.add('header-light');
            document.documentElement.style.setProperty('--header-color', '#ffffff');
        }
        
        // Update sticky footer styling as well
        updateStickyFooter();
    }
    
    function updateStickyFooter() {
        const currentSlideElement = slides[currentSlide];
        const brandNameElement = document.querySelector('#sticky-bottom-brand-name');
        const brandWorkElement = document.querySelector('#sticky-bottom-brand-work');
        const stickyContainer = document.querySelector('.sticky-text-container');
        
        // Update content using class selectors instead of h2 elements
        const brandName = currentSlideElement.querySelector('.brand-name');
        const brandWork = currentSlideElement.querySelector('.brand-work');
        
        if (brandName && brandNameElement) {
            brandNameElement.textContent = brandName.textContent;
        }
        
        if (brandWork && brandWorkElement) {
            brandWorkElement.textContent = brandWork.textContent;
        }
        
        // Update styling based on header style
        const isDark = currentSlideElement.classList.contains('turn-header-dark');
        
        // Handle brand name text styling
        if (brandNameElement) {
            if (isDark) {
                if (!brandNameElement.classList.contains('text-dark')) {
                    brandNameElement.classList.add('text-dark');
                }
                brandNameElement.classList.remove('text-light');
            } else {
                if (!brandNameElement.classList.contains('text-light')) {
                    brandNameElement.classList.add('text-light');
                }
                brandNameElement.classList.remove('text-dark');
            }
        }
        
        // Handle brand work text styling
        if (brandWorkElement) {
            if (isDark) {
                if (!brandWorkElement.classList.contains('text-dark')) {
                    brandWorkElement.classList.add('text-dark');
                }
                brandWorkElement.classList.remove('text-light');
            } else {
                if (!brandWorkElement.classList.contains('text-light')) {
                    brandWorkElement.classList.add('text-light');
                }
                brandWorkElement.classList.remove('text-dark');
            }
        }
        
        // Handle sticky container border styling
        if (stickyContainer) {
            if (isDark) {
                stickyContainer.classList.remove('border-light');
                if (!stickyContainer.classList.contains('border-dark')) {
                    stickyContainer.classList.add('border-dark');
                }
            } else {
                stickyContainer.classList.remove('border-dark');
                if (!stickyContainer.classList.contains('border-light')) {
                    stickyContainer.classList.add('border-light');
                }
            }
        }
    }

    function goToSlide(index) {
        if (isAnimating || index < 0 || index >= slides.length) return;

        isAnimating = true;
        currentSlide = index;

        const viewportHeight = window.innerHeight;
        const translateValue = -currentSlide * viewportHeight;
        
        slides.forEach((slide, i) => {
            slide.style.transition = `transform ${SLIDE_TRANSITION}ms ${EASING_FUNCTION}`;
            slide.style.webkitTransform = `translateY(${translateValue + (i * viewportHeight)}px)`; // Safari fix
            slide.style.transform = `translateY(${translateValue + (i * viewportHeight)}px)`;
        });

        updateHeaderStyles();
        scrollAccumulator = 0;

        setTimeout(() => {
            isAnimating = false;
        }, SCROLL_LOCK_TIME);
    }

    function handleWheel(e) {
        e.preventDefault();
        
        const now = Date.now();
        if (isAnimating || now - lastScrollTime < SCROLL_COOLDOWN) return;
        
        lastScrollTime = now;
        
        // Apply smooth accumulation with decay
        const decay = 0.85; // Smooth out rapid scrolling
        scrollAccumulator = scrollAccumulator * decay + e.deltaY;
        
        if (Math.abs(scrollAccumulator) >= SCROLL_THRESHOLD) {
            const direction = Math.sign(scrollAccumulator);
            if (direction > 0) {
                goToSlide(currentSlide + 1);
            } else if (direction < 0) {
                goToSlide(currentSlide - 1);
            }
            scrollAccumulator = 0;
        }
    }

    let touchStartY = 0;

    function handleTouchStart(e) {
        touchStartY = e.touches[0].clientY;
    }

    function handleTouchEnd(e) {
        if (isAnimating) return;

        const touchEndY = e.changedTouches[0].clientY;
        const deltaY = touchStartY - touchEndY;

        if (Math.abs(deltaY) > SWIPE_THRESHOLD) {
            if (deltaY > 0) {
                goToSlide(currentSlide + 1);
            } else {
                goToSlide(currentSlide - 1);
            }
        }
    }

    function handleKeydown(e) {
        if (isAnimating) return;

        switch (e.key) {
            case 'ArrowDown':
                goToSlide(currentSlide + 1);
                break;
            case 'ArrowUp':
                goToSlide(currentSlide - 1);
                break;
            case 'Home':
                goToSlide(0);
                break;
            case 'End':
                goToSlide(slides.length - 1);
                break;
        }
    }

    function init() {
        setupStyles();
        updateHeaderStyles(); // This will also call updateStickyFooter
        
        // Add debounced scroll handler for smoother experience
        let scrollTimeout;
        const debouncedWheel = (e) => {
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => handleWheel(e), 5);
        };
        
        // Event listeners with Safari compatibility
        window.addEventListener('wheel', debouncedWheel, { passive: false });
        window.addEventListener('touchstart', handleTouchStart, { passive: true });
        window.addEventListener('touchend', handleTouchEnd, { passive: false });
        window.addEventListener('keydown', handleKeydown);
        
        // Initial call to adjust all slides
        adjustAllSlides();
    }

    init();
});
