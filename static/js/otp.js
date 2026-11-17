// A visual countdown only: all limits and expiry checks are enforced on the server.
document.querySelectorAll('[data-resend-at]').forEach(button => {
  const until = Number(button.dataset.resendAt) * 1000;
  const label = button.parentElement.querySelector('.otp-countdown');
  const tick = () => {
    const remaining = Math.max(0, Math.ceil((until - Date.now()) / 1000));
    button.disabled = remaining > 0;
    if (label) label.textContent = remaining ? `${remaining} ثانیه تا ارسال مجدد` : '';
    if (!remaining) clearInterval(timer);
  };
  const timer = setInterval(tick, 1000);
  tick();
});
document.querySelectorAll('[data-otp-form]').forEach(form => {
  form.addEventListener('submit', () => {
    const button = form.querySelector('button[type="submit"]');
    if (!button) return;
    button.disabled = true;
    button.textContent = 'در حال بررسی…';
    // Permit a retry if navigation is interrupted; server-side limits still apply.
    setTimeout(() => { button.disabled = false; button.textContent = 'تلاش دوباره'; }, 20000);
  });
});
