// Navigation Dropdown Management
// This script handles dropdown menus and active state management for the navigation bar

// Toggle dropdown visibility
function toggleDropdown(dropdownId) {
    const dropdown = document.getElementById(dropdownId);
    const allDropdowns = document.querySelectorAll('[id^="dropdown-"]');

    // Close other dropdowns
    allDropdowns.forEach(d => {
        if (d.id !== dropdownId) {
            d.classList.add('hidden');
        }
    });

    // Toggle current dropdown
    dropdown.classList.toggle('hidden');
}

// Close dropdowns when clicking outside
document.addEventListener('click', function(event) {
    // Check if click is outside dropdown containers
    if (!event.target.closest('.dropdown-container')) {
        const allDropdowns = document.querySelectorAll('[id^="dropdown-"]');
        allDropdowns.forEach(d => {
            d.classList.add('hidden');
        });
    }
});

// Mobile menu toggle
function toggleMobileMenu() {
    const mobileMenu = document.getElementById('mobile-menu');
    mobileMenu.classList.toggle('hidden');
}

// Mobile accordion toggle
function toggleAccordion(section) {
    const accordion = document.getElementById(`accordion-${section}`);
    const allAccordions = document.querySelectorAll('[id^="accordion-"]');

    // Close other accordions
    allAccordions.forEach(a => {
        if (a.id !== `accordion-${section}`) {
            a.classList.add('hidden');
        }
    });

    // Toggle current accordion
    accordion.classList.toggle('hidden');
}

// Set active navigation state based on current page
function setActiveNavigation() {
    const currentPath = window.location.pathname;

    // Remove active classes from all nav links
    document.querySelectorAll('nav a').forEach(link => {
        link.classList.remove('text-white', 'font-medium');
        link.classList.add('text-blue-100', 'font-light');
    });

    // Add active class to current page link
    const activeLink = document.querySelector(`nav a[href="${currentPath}"]`);
    if (activeLink) {
        activeLink.classList.remove('text-blue-100', 'font-light');
        activeLink.classList.add('text-white', 'font-medium');
    }

    // Highlight parent dropdown button if child page is active
    if (currentPath.includes('/campaign')) {
        const campaignButton = document.querySelector('[data-dropdown="campaign"]');
        if (campaignButton) {
            campaignButton.classList.remove('text-blue-100', 'font-light');
            campaignButton.classList.add('text-white', 'font-medium');
        }
    } else if (currentPath.includes('/payroll')) {
        const payrollButton = document.querySelector('[data-dropdown="payroll"]');
        if (payrollButton) {
            payrollButton.classList.remove('text-blue-100', 'font-light');
            payrollButton.classList.add('text-white', 'font-medium');
        }
    }
}

// Initialize navigation on page load
document.addEventListener('DOMContentLoaded', function() {
    setActiveNavigation();

    // Prevent dropdown buttons from submitting forms
    document.querySelectorAll('[onclick^="toggleDropdown"]').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
        });
    });
});
