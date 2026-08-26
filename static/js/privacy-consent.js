/* Optional GA4 analytics only starts after an explicit, reversible choice. */
(() => {
  const script = document.currentScript || document.querySelector('script[data-measurement-id]');
  const enabled = script?.dataset.analyticsEnabled === 'true';
  const measurementId = script?.dataset.measurementId || '';
  const banner = document.getElementById('expatus-consent-banner');
  const storageKey = 'expatus-cookie-consent-v1';
  let choice = '';

  try { choice = localStorage.getItem(storageKey) || ''; } catch (_) {}

  window.dataLayer = window.dataLayer || [];
  window.gtag = window.gtag || function gtag() { window.dataLayer.push(arguments); };
  window.gtag('consent', 'default', {
    analytics_storage: 'denied',
    ad_storage: 'denied',
    ad_user_data: 'denied',
    ad_personalization: 'denied'
  });

  function loadAnalytics() {
    if (!enabled || !/^G-[A-Z0-9]+$/.test(measurementId) || document.getElementById('expatus-ga4')) return;
    window.gtag('consent', 'update', {analytics_storage: 'granted'});
    const tag = document.createElement('script');
    tag.id = 'expatus-ga4';
    tag.async = true;
    tag.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(measurementId)}`;
    document.head.appendChild(tag);
    window.gtag('js', new Date());
    window.gtag('config', measurementId, {
      allow_google_signals: false,
      allow_ad_personalization_signals: false
    });
  }

  function storeChoice(value) {
    choice = value;
    try { localStorage.setItem(storageKey, value); } catch (_) {}
    if (banner) banner.hidden = true;
    if (value === 'analytics') {
      loadAnalytics();
    } else {
      window.gtag('consent', 'update', {analytics_storage: 'denied'});
    }
  }

  if (choice === 'analytics') loadAnalytics();
  if (!choice && enabled && banner) banner.hidden = false;
  document.querySelectorAll('[data-consent]').forEach(button => {
    button.addEventListener('click', () => storeChoice(button.dataset.consent));
  });
  document.querySelectorAll('[data-cookie-settings]').forEach(button => {
    button.addEventListener('click', () => {
      if (banner) banner.hidden = false;
    });
  });
})();
