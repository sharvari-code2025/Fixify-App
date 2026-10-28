/**
 * Fixify — Smart Mobile Repair Management System
 * Core Client-Side Logic & Theme Controller
 */

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initMobileNav();
    initAlerts();
    initPasswordToggles();
    initServiceTypeToggle();
    initStarRating();
    initCharts();
});

// ============================================================
// THEME CONTROLLER (Dark / Light with LocalStorage persistence)
// ============================================================
function initTheme() {
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const currentTheme = localStorage.getItem('fixify_theme') || 'dark';

    // Apply saved or default theme
    applyTheme(currentTheme);

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const activeTheme = document.documentElement.getAttribute('data-theme') || 'dark';
            const newTheme = activeTheme === 'dark' ? 'light' : 'dark';
            applyTheme(newTheme);
            localStorage.setItem('fixify_theme', newTheme);
        });
    }
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const sunIcon = document.getElementById('theme-icon-sun');
    const moonIcon = document.getElementById('theme-icon-moon');

    if (sunIcon && moonIcon) {
        if (theme === 'dark') {
            sunIcon.style.display = 'block';
            moonIcon.style.display = 'none';
        } else {
            sunIcon.style.display = 'none';
            moonIcon.style.display = 'block';
        }
    }
}

// ============================================================
// MOBILE NAVIGATION
// ============================================================
function initMobileNav() {
    const toggleBtn = document.getElementById('mobile-nav-toggle');
    const navLinks = document.getElementById('nav-links');

    if (toggleBtn && navLinks) {
        toggleBtn.addEventListener('click', () => {
            navLinks.classList.toggle('active');
            const isOpen = navLinks.classList.contains('active');
            toggleBtn.setAttribute('aria-expanded', isOpen);
        });
    }
}

// ============================================================
// ALERTS DISMISSAL
// ============================================================
function initAlerts() {
    const closeButtons = document.querySelectorAll('.alert-close');
    closeButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const alert = e.target.closest('.alert');
            if (alert) {
                alert.style.opacity = '0';
                alert.style.transform = 'translateY(-10px)';
                alert.style.transition = 'all 0.25s ease';
                setTimeout(() => alert.remove(), 250);
            }
        });
    });
}

// ============================================================
// PASSWORD VISIBILITY TOGGLE
// ============================================================
function initPasswordToggles() {
    const toggleBtns = document.querySelectorAll('.password-toggle-btn');
    toggleBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-target');
            const input = document.getElementById(targetId);
            if (input) {
                const isPassword = input.getAttribute('type') === 'password';
                input.setAttribute('type', isPassword ? 'text' : 'password');
                btn.textContent = isPassword ? 'Hide' : 'Show';
            }
        });
    });
}

// ============================================================
// SERVICE TYPE TOGGLE (Pickup & Delivery vs Walk-In)
// ============================================================
function initServiceTypeToggle() {
    const serviceTypeRadios = document.querySelectorAll('input[name="service_type"]');
    const pickupAddressContainer = document.getElementById('pickup-address-container');
    const pickupAddressInput = document.getElementById('pickup_address');

    if (serviceTypeRadios.length && pickupAddressContainer) {
        const updateVisibility = () => {
            const selected = document.querySelector('input[name="service_type"]:checked');
            if (selected && selected.value === 'pickup_delivery') {
                pickupAddressContainer.style.display = 'block';
                if (pickupAddressInput) pickupAddressInput.required = true;
            } else {
                pickupAddressContainer.style.display = 'none';
                if (pickupAddressInput) pickupAddressInput.required = false;
            }
        };

        serviceTypeRadios.forEach(radio => {
            radio.addEventListener('change', updateVisibility);
        });

        // Initial state
        updateVisibility();
    }
}

// ============================================================
// STAR RATING INPUT WIDGET
// ============================================================
function initStarRating() {
    const starContainer = document.querySelector('.star-rating-input');
    if (!starContainer) return;

    const stars = starContainer.querySelectorAll('.star-btn');
    const hiddenInput = document.getElementById('rating-input');

    stars.forEach(star => {
        star.addEventListener('click', (e) => {
            e.preventDefault();
            const val = parseInt(star.getAttribute('data-value'), 10);
            if (hiddenInput) hiddenInput.value = val;

            stars.forEach(s => {
                const sVal = parseInt(s.getAttribute('data-value'), 10);
                if (sVal <= val) {
                    s.classList.add('active');
                    s.textContent = '★';
                } else {
                    s.classList.remove('active');
                    s.textContent = '☆';
                }
            });
        });
    });
}

// ============================================================
// REAL DATABASE CHARTS (Chart.js Integration)
// ============================================================
function initCharts() {
    const chartCanvas = document.getElementById('repairStatusChart');
    if (!chartCanvas || typeof Chart === 'undefined') return;

    const rawData = chartCanvas.getAttribute('data-status-counts');
    if (!rawData) return;

    try {
        const statusMap = JSON.parse(rawData);
        const labels = Object.keys(statusMap);
        const dataValues = Object.values(statusMap);

        const ctx = chartCanvas.getContext('2d');
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: dataValues,
                    backgroundColor: [
                        '#0ea5e9', '#3b82f6', '#f59e0b', '#a855f7',
                        '#10b981', '#06b6d4', '#64748b', '#ef4444'
                    ],
                    borderColor: 'transparent',
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: getComputedStyle(document.documentElement).getPropertyValue('--text-secondary').trim() || '#94a3b8',
                            font: { size: 12, family: 'system-ui' }
                        }
                    }
                }
            }
        });
    } catch (e) {
        console.error('Error rendering chart:', e);
    }
}
