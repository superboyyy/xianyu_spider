const PAUSE_ICON =
  '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><rect x="6" y="5" width="4" height="14" rx="1" fill="currentColor"/><rect x="14" y="5" width="4" height="14" rx="1" fill="currentColor"/></svg>';
const PLAY_ICON =
  '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M8 5l11 7-11 7z" fill="currentColor"/></svg>';

function initReveal(root) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    root.querySelectorAll('.nrg-reveal').forEach((el) => el.classList.add('is-in'));
    return;
  }

  const reveal = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-in');
          reveal.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12, rootMargin: '0px 0px -8% 0px' },
  );

  const vh = window.innerHeight;
  root.querySelectorAll('.nrg-reveal').forEach((el) => {
    if (el.getBoundingClientRect().top < vh * 0.95) {
      el.style.transition = 'none';
      el.classList.add('is-in');
    } else {
      reveal.observe(el);
    }
  });
}

function initCarousels(root) {
  root.querySelectorAll('[data-nrg-carousel]').forEach((carousel) => {
    const track = carousel.querySelector('[data-nrg-track]');
    const prev = carousel.querySelector('[data-nrg-prev]');
    const next = carousel.querySelector('[data-nrg-next]');
    if (!track) return;
    const card = track.querySelector('article, [data-nrg-card]');
    const step = () => (card ? card.getBoundingClientRect().width + 20 : 320);

    const update = () => {
      const max = track.scrollWidth - track.clientWidth - 2;
      if (prev) prev.disabled = track.scrollLeft <= 2;
      if (next) next.disabled = track.scrollLeft >= max;
    };

    prev?.addEventListener('click', () => track.scrollBy({ left: -step(), behavior: 'smooth' }));
    next?.addEventListener('click', () => track.scrollBy({ left: step(), behavior: 'smooth' }));
    track.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    update();
  });
}

function initHero(root) {
  const hero = root.querySelector('.nrg-hero');
  const content = root.querySelector('[data-nrg-parallax]');
  const pause = root.querySelector('[data-nrg-hero-pause]');

  if (content && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    let ticking = false;
    window.addEventListener(
      'scroll',
      () => {
        if (ticking) return;
        ticking = true;
        requestAnimationFrame(() => {
          const y = window.scrollY;
          if (y < 900) {
            content.style.transform = `translateY(${y * 0.35}px)`;
            content.style.opacity = String(Math.max(0, 1 - y / 560));
          }
          ticking = false;
        });
      },
      { passive: true },
    );
  }

  pause?.addEventListener('click', () => {
    const paused = hero?.classList.toggle('is-paused');
    pause.innerHTML = paused ? PLAY_ICON : PAUSE_ICON;
    pause.setAttribute('aria-label', paused ? 'Play background' : 'Pause background');
  });
}

function initModals(root) {
  const dialogs = [...root.querySelectorAll('dialog.nrg-modal')];
  if (!dialogs.length) return;

  const sync = () => {
    const id = decodeURIComponent(location.hash.replace('#', ''));
    dialogs.forEach((dialog) => {
      const want = dialog.getAttribute('data-nrg-modal') === id;
      if (want && !dialog.open && typeof dialog.showModal === 'function') dialog.showModal();
      else if (!want && dialog.open) dialog.close();
    });
  };

  const clearHash = () => {
    history.replaceState(null, '', location.pathname + location.search);
    sync();
  };

  dialogs.forEach((dialog) => {
    dialog.querySelector('[data-nrg-close]')?.addEventListener('click', clearHash);
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog) clearHash();
    });
    dialog.addEventListener('cancel', (event) => {
      event.preventDefault();
      clearHash();
    });
  });

  window.addEventListener('hashchange', sync);
  sync();
}

export function initNrg(root = document) {
  initReveal(root);
  initCarousels(root);
  initHero(root);
  initModals(root);
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initNrg());
  } else {
    initNrg();
  }
}
