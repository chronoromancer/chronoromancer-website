// Screenshots page functionality
document.addEventListener('DOMContentLoaded', function() {

    // Create lightbox HTML
    const lightboxHTML = `
        <div class="lightbox" id="lightbox">
            <span class="lightbox-close" id="lightbox-close">&times;</span>
            <img class="lightbox-content" id="lightbox-img" src="" alt="">
        </div>
    `;
    
    // Add lightbox to page
    document.body.insertAdjacentHTML('beforeend', lightboxHTML);
    
    // Get lightbox elements
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightbox-img');
    const lightboxClose = document.getElementById('lightbox-close');
    
    // Add click event to all gallery images
    const galleryImages = document.querySelectorAll('.gallery-image');
    
    galleryImages.forEach(image => {
        image.addEventListener('click', function() {
            lightbox.classList.add('active');
            lightboxImg.src = this.src;
            lightboxImg.alt = this.alt;
            document.body.style.overflow = 'hidden'; // Prevent background scrolling
        });
    });
    
    // Close lightbox functionality
    function closeLightbox() {
        lightbox.classList.remove('active');
        document.body.style.overflow = 'auto'; // Restore scrolling
    }
    
    // Close on X button click
    lightboxClose.addEventListener('click', closeLightbox);
    
    // Close on background click
    lightbox.addEventListener('click', function(e) {
        if (e.target === lightbox) {
            closeLightbox();
        }
    });
    
    // Close on Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && lightbox.classList.contains('active')) {
            closeLightbox();
        }
    });
    
    // Add smooth scroll for navigation
    const navLinks = document.querySelectorAll('.nav-links a');
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            if (this.getAttribute('href').startsWith('#')) {
                e.preventDefault();
                const targetId = this.getAttribute('href').substring(1);
                const targetElement = document.getElementById(targetId);
                if (targetElement) {
                    targetElement.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            }
        });
    });
    
    // Add loading animation for images
    const images = document.querySelectorAll('.gallery-image');
    images.forEach(img => {
        // Remove the loading animation - just show images normally
        img.style.opacity = '1';
    });
    
});