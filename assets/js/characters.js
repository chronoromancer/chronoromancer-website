// Characters Page JavaScript

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

    // Character item animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '50px'
    };

    const characterObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
                characterObserver.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Apply animation to character items
    document.querySelectorAll('.character-item').forEach((item, index) => {
        item.style.opacity = '0';
        item.style.transform = 'translateY(30px)';
        item.style.transition = `opacity 0.6s ease ${index * 0.1}s, transform 0.6s ease ${index * 0.1}s`;
        characterObserver.observe(item);
    });

    // Add click effects to character items
    document.querySelectorAll('.character-item').forEach(item => {
        item.addEventListener('click', function() {
            // Could add modal or expanded view functionality here
            // For now, just a subtle feedback
            this.style.transform = 'translateY(-8px) scale(0.98)';
            setTimeout(() => {
                this.style.transform = 'translateY(-8px) scale(1)';
            }, 150);
        });
    });

    // Add search functionality (basic)
    function addSearch() {
        const searchContainer = document.createElement('div');
        searchContainer.className = 'search-container';
        searchContainer.innerHTML = `
            <input type="text" placeholder="Search characters..." class="character-search">
        `;
        
        const gallery = document.querySelector('.character-gallery .container');
        gallery.insertBefore(searchContainer, gallery.firstChild);
        
        const searchInput = document.querySelector('.character-search');
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            const characters = document.querySelectorAll('.character-item');
            
            characters.forEach(character => {
                const name = character.querySelector('h3').textContent.toLowerCase();
                const description = character.querySelector('p').textContent.toLowerCase();
                
                if (name.includes(searchTerm) || description.includes(searchTerm)) {
                    character.style.display = 'block';
                } else {
                    character.style.display = 'none';
                }
            });
        });
    }

    // Add search after a short delay
    setTimeout(addSearch, 1000);
});