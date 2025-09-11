// Screenshots Page JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Create modal for full-size screenshots
    const modal = document.createElement('div');
    modal.className = 'screenshot-modal';
    modal.innerHTML = `
        <span class="modal-close">&times;</span>
        <img class="modal-content" src="" alt="">
    `;
    document.body.appendChild(modal);

    const modalImg = modal.querySelector('.modal-content');
    const closeBtn = modal.querySelector('.modal-close');

    // Add click handlers to screenshot items
    document.querySelectorAll('.screenshot-item img').forEach(img => {
        img.addEventListener('click', function(e) {
            e.stopPropagation();
            modal.classList.add('active');
            modalImg.src = this.src;
            modalImg.alt = this.alt;
            document.body.style.overflow = 'hidden';
        });
    });

    // Close modal handlers
    function closeModal() {
        modal.classList.remove('active');
        document.body.style.overflow = 'auto';
    }

    closeBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            closeModal();
        }
    });

    // Close modal with Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && modal.classList.contains('active')) {
            closeModal();
        }
    });

    // Smooth entrance animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '50px'
    };

    const screenshotObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
                screenshotObserver.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Apply animation to screenshot items
    document.querySelectorAll('.screenshot-item').forEach((item, index) => {
        item.style.opacity = '0';
        item.style.transform = 'translateY(50px)';
        item.style.transition = `opacity 0.6s ease ${index * 0.1}s, transform 0.6s ease ${index * 0.1}s`;
        screenshotObserver.observe(item);
    });

    // Add loading states for images
    document.querySelectorAll('.screenshot-item img').forEach(img => {
        img.addEventListener('load', function() {
            this.style.opacity = '1';
        });
        
        img.addEventListener('error', function() {
            this.style.opacity = '0.5';
            console.log('Failed to load image:', this.src);
        });
    });
});