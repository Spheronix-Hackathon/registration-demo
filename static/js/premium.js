document.addEventListener('DOMContentLoaded', () => {
    // Reveal animations on scroll
    const reveals = document.querySelectorAll('.reveal');

    const revealObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('active');
            }
        });
    }, {
        threshold: 0.1
    });

    reveals.forEach(reveal => {
        revealObserver.observe(reveal);
    });

    // Check if registrations are open
    async function checkRegistrationStatus() {
        try {
            const res = await fetch("/api/public-settings/");
            if (res.ok) {
                const data = await res.json();
                if (data.registrationOpen === false) {
                    const registerButtons = document.querySelectorAll('a[href="./index.html"]');
                    registerButtons.forEach(btn => {
                        btn.style.display = "none";
                        const closedBadge = document.createElement("div");
                        closedBadge.className = "btn-premium";
                        closedBadge.style.background = "#ff4444";
                        closedBadge.style.color = "white";
                        closedBadge.style.cursor = "not-allowed";
                        closedBadge.innerText = "Registrations Closed";
                        btn.parentNode.insertBefore(closedBadge, btn);
                    });
                }
            }
        } catch (e) {
            console.error("Failed to fetch settings", e);
        }
    }
    checkRegistrationStatus();

    // Countdown Timer
    const countdown = () => {
        const targetDate = new Date('August 14, 2026 00:00:00').getTime();
        
        const updateTimer = () => {
            const now = new Date().getTime();
            const distance = targetDate - now;

            const days = Math.floor(distance / (1000 * 60 * 60 * 24));
            const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((distance % (1000 * 60)) / 1000);

            const daysEl = document.querySelector('.days');
            const hoursEl = document.querySelector('.hours');
            const minutesEl = document.querySelector('.minutes');
            const secondsEl = document.querySelector('.seconds');

            if (daysEl) daysEl.innerText = days < 10 ? '0' + days : days;
            if (hoursEl) hoursEl.innerText = hours < 10 ? '0' + hours : hours;
            if (minutesEl) minutesEl.innerText = minutes < 10 ? '0' + minutes : minutes;
            if (secondsEl) secondsEl.innerText = seconds < 10 ? '0' + seconds : seconds;

            if (distance < 0) {
                clearInterval(timerInterval);
                if (daysEl) daysEl.innerText = '00';
                if (hoursEl) hoursEl.innerText = '00';
                if (minutesEl) minutesEl.innerText = '00';
                if (secondsEl) secondsEl.innerText = '00';
            }
        };

        const timerInterval = setInterval(updateTimer, 1000);
        updateTimer();
    };

    countdown();

    // Smooth scroll
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });

    // Parallax effect for blobs
    document.addEventListener('mousemove', (e) => {
        const blobs = document.querySelectorAll('.blob');
        const mouseX = e.clientX;
        const mouseY = e.clientY;

        blobs.forEach((blob, index) => {
            const speed = (index + 1) * 0.02;
            const x = (window.innerWidth - mouseX * speed) / 100;
            const y = (window.innerHeight - mouseY * speed) / 100;
            blob.style.transform = `translate(${x}px, ${y}px)`;
        });
    });

    // Prize Pool Count-up Animation
    const animateValue = (id, start, end, duration) => {
        const obj = document.getElementById(id);
        if (!obj) return;

        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            const value = Math.floor(progress * (end - start) + start);
            obj.innerHTML = '₹' + value.toLocaleString('en-IN');
            if (progress < 1) {
                window.requestAnimationFrame(step);
            }
        };
        window.requestAnimationFrame(step);
    };

    const prizeObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateValue("prize-min", 0, 200000, 1500);
                animateValue("prize-max", 0, 500000, 1500);
                prizeObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });

    const prizeBanner = document.querySelector('.prize-banner');
    if (prizeBanner) prizeObserver.observe(prizeBanner);
});
