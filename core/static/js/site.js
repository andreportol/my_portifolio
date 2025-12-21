document.addEventListener('DOMContentLoaded', () => {
    const navToggle = document.querySelector('.nav-toggle');
    const navMenu = document.querySelector('.nav-menu');
    const navLinks = document.querySelectorAll('.nav-menu .nav-link');

    let menuTimer = null;

    const closeMenu = () => {
        navMenu?.classList.remove('open');
        navToggle?.setAttribute('aria-expanded', 'false');
        if (menuTimer) {
            clearTimeout(menuTimer);
            menuTimer = null;
        }
    };

    if (navToggle && navMenu) {
        navToggle.addEventListener('click', () => {
            const isOpen = navMenu.classList.toggle('open');
            navToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
            if (isOpen) {
                if (menuTimer) clearTimeout(menuTimer);
                menuTimer = setTimeout(closeMenu, 10000);
            } else if (menuTimer) {
                clearTimeout(menuTimer);
                menuTimer = null;
            }
        });
    }

    if (navLinks.length) {
        navLinks.forEach(link => {
            link.addEventListener('click', closeMenu);
        });
    }

    const phoneInput = document.getElementById('id_telefone');
    const formatPhone = (value) =>
        value
            .replace(/\D/g, '')
            .slice(0, 11)
            .replace(
                /^(\d{0,2})(\d{0,5})(\d{0,4}).*/,
                (_m, g1, g2, g3) =>
                    `${g1 ? `(${g1}${g1.length === 2 ? ') ' : ''}` : ''}${g2 || ''}${g3 ? `-${g3}` : ''}`
            );

    if (phoneInput) {
        const applyMask = () => {
            phoneInput.value = formatPhone(phoneInput.value);
        };
        applyMask();
        phoneInput.addEventListener('input', applyMask);
        phoneInput.addEventListener('blur', applyMask);
    }
});
