/*!
 * Cookie banner setup.
 * Library: vanilla-cookieconsent v3 - https://cookieconsent.orestbida.com
 */

(function () {
  'use strict';

  const root = document.documentElement;

  // Chirpy sets data-bs-theme on <html>. CookieConsent uses a class.
  // Keep the two in step so the banner follows the site's light/dark mode.
  function syncTheme() {
    root.classList.toggle('cc--darkmode', root.dataset.bsTheme === 'dark');
  }

  syncTheme();

  new MutationObserver(syncTheme).observe(root, {
    attributes: true,
    attributeFilter: ['data-bs-theme']
  });

  CookieConsent.run({
    // Nothing runs until the visitor says yes.
    mode: 'opt-in',

    guiOptions: {
      consentModal: {
        layout: 'box',
        position: 'bottom right',
        equalWeightButtons: true
      },
      preferencesModal: {
        layout: 'box',
        equalWeightButtons: true
      }
    },

    categories: {
      necessary: {
        enabled: true,
        readOnly: true
      },
      analytics: {}
    },

    language: {
      default: 'en',
      translations: {
        en: {
          consentModal: {
            title: 'Cookies',
            description:
              'This site uses a few cookies. Some keep it working. One counts visits. You decide.',
            acceptAllBtn: 'Accept all',
            acceptNecessaryBtn: 'Reject all',
            showPreferencesBtn: 'Let me choose',
            footer: '<a href="/privacy/">Privacy</a>'
          },

          preferencesModal: {
            title: 'Cookie settings',
            acceptAllBtn: 'Accept all',
            acceptNecessaryBtn: 'Reject all',
            savePreferencesBtn: 'Save choices',
            closeIconLabel: 'Close',
            sections: [
              {
                description:
                  'Pick what you are happy with. You can change this later on the <a href="/privacy/">Privacy</a> page.'
              },
              {
                title: 'Needed to run the site',
                description:
                  'Remembers small things, like whether you picked light or dark mode. The site needs these, so they stay on.',
                linkedCategory: 'necessary'
              },
              {
                title: 'Visit stats',
                description:
                  'Google Analytics counts visits and shows me which posts people read. Off until you turn it on.',
                linkedCategory: 'analytics'
              }
            ]
          }
        }
      }
    }
  });
})();
