// Chronoromancer Website JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Character overlay animation on scroll
    function animateCharacters() {
        const scrollY = window.scrollY;
        const heroHeight = document.querySelector('.hero').offsetHeight;
        const scrollPercent = Math.min(scrollY / heroHeight, 1);
        
        const characters = document.querySelectorAll('.character-overlay');
        characters.forEach((char, index) => {
            const opacity = 0.15 - (scrollPercent * 0.1);
            const translateY = scrollPercent * 50 * (index + 1);
            char.style.opacity = Math.max(opacity, 0.05);
            char.style.transform = `translateY(${translateY}px)`;
        });
    }

    // Parallax effect for hero section
    window.addEventListener('scroll', animateCharacters);

    // Lazy loading for screenshots
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '50px'
    };

    const imageObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                if (img.dataset.src) {
                    img.src = img.dataset.src;
                    img.removeAttribute('data-src');
                }
                img.classList.add('loaded');
                imageObserver.unobserve(img);
            }
        });
    }, observerOptions);

    // Observe all images in screenshot gallery
    document.querySelectorAll('.screenshot-item img, .era-image img').forEach(img => {
        imageObserver.observe(img);
    });

    // Add loading animation to buttons
    document.querySelectorAll('.btn').forEach(button => {
        button.addEventListener('click', function(e) {
            if (this.classList.contains('primary') && this.getAttribute('href') === '#') {
                e.preventDefault();
                
                // Add loading state
                const originalText = this.textContent;
                this.textContent = 'Coming Soon...';
                this.style.pointerEvents = 'none';
                
                setTimeout(() => {
                    alert('Chronoromancer is currently in development!\n\nJoin our Discord community for the latest updates and early access information.');
                    this.textContent = originalText;
                    this.style.pointerEvents = 'auto';
                }, 500);
            }
        });
    });

    // Add hover effects to character cards
    document.querySelectorAll('.character-card').forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px) scale(1.02)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
        });
    });

    // Social media link handling (placeholder)
    document.querySelectorAll('.social-link').forEach(link => {
        link.addEventListener('click', function(e) {
            if (this.getAttribute('href') === '#') {
                e.preventDefault();
                const platform = this.querySelector('span').textContent;
                alert(`${platform} link will be available soon!\n\nJoin our Discord for the latest community updates.`);
            }
        });
    });

    // Add entrance animations
    const animateOnScroll = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, { threshold: 0.1 });

    // Apply animation to sections
    document.querySelectorAll('section:not(.hero)').forEach(section => {
        section.style.opacity = '0';
        section.style.transform = 'translateY(30px)';
        section.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        animateOnScroll.observe(section);
    });

    // Feature counter animation
    function animateCounters() {
        document.querySelectorAll('.feature-number').forEach(counter => {
            const target = counter.textContent;
            if (target !== '∞' && !counter.classList.contains('animated')) {
                counter.classList.add('animated');
                const targetNum = parseInt(target.replace('+', ''));
                let current = 0;
                const increment = targetNum / 30;
                
                const timer = setInterval(() => {
                    current += increment;
                    if (current >= targetNum) {
                        counter.textContent = target;
                        clearInterval(timer);
                    } else {
                        counter.textContent = Math.floor(current) + '+';
                    }
                }, 50);
            }
        });
    }

    // Trigger counter animation when features section is visible
    const featuresObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateCounters();
                featuresObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });

    const featuresSection = document.querySelector('.features-list');
    if (featuresSection) {
        featuresObserver.observe(featuresSection);
    }
});