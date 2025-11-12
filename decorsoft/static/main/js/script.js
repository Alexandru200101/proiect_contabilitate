// Animations for scroll-triggered elements
document.addEventListener('DOMContentLoaded', function() {
    // Intersection Observer for fade-in animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-fadeIn');
            }
        });
    }, observerOptions);
    
    // Observe all feature cards
    document.querySelectorAll('.feature-card').forEach(card => {
        observer.observe(card);
    });
    
    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            
            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                window.scrollTo({
                    top: targetElement.offsetTop - 80,
                    behavior: 'smooth'
                });
            }
        });
    });
    
    // Add animation class to hero content for sequential animation
    const heroContent = document.querySelector('.hero-content');
    if (heroContent) {
        const heroTitle = heroContent.querySelector('.hero-title');
        const heroDescription = heroContent.querySelector('.hero-description');
        const heroButtons = heroContent.querySelector('.hero-buttons');
        
        if (heroTitle) heroTitle.style.animationDelay = '0.2s';
        if (heroDescription) heroDescription.style.animationDelay = '0.4s';
        if (heroButtons) heroButtons.style.animationDelay = '0.6s';
    }
    
    // Add hover effect to buttons
    const buttons = document.querySelectorAll('.btn');
    buttons.forEach(button => {
        button.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px)';
        });
        
        button.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });
    
    // Add loading animation
    window.addEventListener('load', function() {
        document.body.classList.add('loaded');
    });
});

// Add CSS for fadeIn animation
const style = document.createElement('style');
style.textContent = `
    .feature-card {
        opacity: 0;
        transform: translateY(30px);
        transition: opacity 0.6s ease, transform 0.6s ease;
    }
    
    .feature-card.animate-fadeIn {
        opacity: 1;
        transform: translateY(0);
    }
    
    .hero-content > * {
        opacity: 0;
        animation: slideIn 1s ease-out forwards;
    }
    
    body.loaded .hero-content > * {
        opacity: 1;
    }
`;
document.head.appendChild(style);