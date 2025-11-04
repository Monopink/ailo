// Ensure timezone cookie is set to device timezone, then reload once.
// Works with server-side CookieTimezoneMiddleware or starlette-admin TimezoneConfig.
(function () {
  try {
    var cookieName = 'timezone';
    var current = (typeof Cookies !== 'undefined') ? Cookies.get(cookieName) : null;
    var deviceTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (!current && deviceTz) {
      if (typeof Cookies !== 'undefined') {
        Cookies.set(cookieName, String(deviceTz));
        // Avoid reload loop
        if (!sessionStorage.getItem('tz_cookie_set')) {
          sessionStorage.setItem('tz_cookie_set', '1');
          window.location.reload();
        }
      }
    }
  } catch (e) {
    // no-op
  }
})();

