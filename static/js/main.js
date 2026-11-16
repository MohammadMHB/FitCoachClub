// FitCoach Main JS

// FitCoach uses one light appearance across every account and device.
document.documentElement.setAttribute('data-theme', 'light');
try { localStorage.setItem('fc_theme', 'light'); } catch (_) {}

// ===== SIDEBAR TOGGLE =====
const sidebar = document.getElementById('sidebar');
const menuToggle = document.getElementById('menuToggle');

// Create overlay
const overlay = document.createElement('div');
overlay.className = 'sidebar-overlay';
overlay.id = 'sidebarOverlay';
document.body.appendChild(overlay);

function toggleSidebar() {
  sidebar?.classList.toggle('open');
  overlay.classList.toggle('active');
  menuToggle?.setAttribute('aria-expanded', String(sidebar?.classList.contains('open') || false));
  document.body.style.overflow = sidebar?.classList.contains('open') ? 'hidden' : '';
}

menuToggle?.addEventListener('click', toggleSidebar);
overlay.addEventListener('click', toggleSidebar);

// ===== AUTO DISMISS ALERTS =====
setTimeout(() => {
  document.querySelectorAll('.alert-success').forEach(a => {
    a.style.transition = 'opacity 0.5s';
    a.style.opacity = '0';
    setTimeout(() => a.remove(), 500);
  });
}, 6000);

// ===== CONFIRM DELETE MODAL =====
function confirmDelete(formId, message) {
  const modal = document.getElementById('confirmModal');
  const msgEl = document.getElementById('confirmMessage');
  const confirmBtn = document.getElementById('confirmBtn');
  if (!modal) return;
  msgEl.textContent = message || 'آیا مطمئن هستید؟';
  modal.classList.add('active');
  confirmBtn.onclick = () => {
    document.getElementById(formId)?.submit();
    modal.classList.remove('active');
  };
}

function closeModal(id) {
  document.getElementById(id)?.classList.remove('active');
}

// Close modal on overlay click
document.querySelectorAll('.modal-overlay').forEach(m => {
  m.addEventListener('click', (e) => {
    if (e.target === m) m.classList.remove('active');
  });
});

// ===== ACTIVE NAV =====
// Match the most specific section, so /coach/ is not active on every page.
const currentPath = window.location.pathname;
const sectionPath = currentPath.replace(/^\/coach\/(programs|nutrition)\//, '/coach/trainees/');
for (const container of document.querySelectorAll('.sidebar-nav, .bottom-nav')) {
  const items = [...container.querySelectorAll('a.nav-item, a.bottom-nav-item')];
  const matches = items.filter(item => {
    const path = new URL(item.href, location.origin).pathname;
    return sectionPath === path ||
      (!['/', '/coach/', '/trainee/', '/admin-panel/'].includes(path) && sectionPath.startsWith(path));
  }).sort((a, b) => b.pathname.length - a.pathname.length);
  items.forEach(item => {
    item.classList.toggle('active', item === matches[0]);
    if (item === matches[0]) item.setAttribute('aria-current', 'page');
    else item.removeAttribute('aria-current');
  });
}
const dateLabel = document.getElementById('localDate');
if (dateLabel) dateLabel.textContent = new Intl.DateTimeFormat('fa-IR', {
  weekday: 'long', day: 'numeric', month: 'long', timeZone: 'Asia/Tehran'
}).format(new Date());

// ===== FILE INPUT PREVIEW =====
document.querySelectorAll('.file-input-styled').forEach(input => {
  input.addEventListener('change', function() {
    const label = this.nextElementSibling;
    if (label && this.files[0]) {
      label.textContent = this.files[0].name;
    }
  });
});

// ===== شیت جزئیات به سبک مخاطبین (لیست شاگردان/مربیان در موبایل) =====
function openDetailSheet(id) {
  const sheet = document.getElementById(id);
  const backdrop = document.getElementById('sheetBackdrop');
  if (!sheet || !backdrop) return;
  sheet.classList.add('open');
  backdrop.classList.add('active');
  document.body.style.overflow = 'hidden';
}

function closeAllSheets() {
  document.querySelectorAll('.detail-sheet.open').forEach(s => s.classList.remove('open'));
  const backdrop = document.getElementById('sheetBackdrop');
  if (backdrop) backdrop.classList.remove('active');
  document.body.style.overflow = '';
}

// ===== کپی متن دعوت/اطلاعات ورود (برای شاگرد یا مربی) در کلیپ‌بورد =====
function copyTextToClipboard(text) {
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(showInviteCopiedToast).catch(() => fallbackCopy(text));
  } else {
    fallbackCopy(text);
  }
}

function fallbackCopy(text) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  let ok = false;
  try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
  document.body.removeChild(ta);
  if (ok) {
    showInviteCopiedToast();
  } else {
    // کپی خودکار شکست خورد؛ متن همچنان تو پنجره‌ی قابل‌مشاهده هست تا دستی انتخاب/کپی بشه
    showInviteCopiedToast(true);
  }
}

function showInviteCopiedToast(failed) {
  let toast = document.getElementById('inviteToast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'inviteToast';
    toast.style.cssText = 'position:fixed;bottom:90px;left:50%;transform:translateX(-50%);'
      + 'color:white;padding:0.7rem 1.4rem;border-radius:30px;'
      + 'font-size:0.85rem;font-weight:600;z-index:10000;box-shadow:0 8px 24px rgba(0,0,0,0.3);'
      + 'opacity:0;transition:opacity 0.25s;white-space:nowrap';
    document.body.appendChild(toast);
  }
  if (failed) {
    toast.style.background = 'var(--warning)';
    toast.innerHTML = '<i class="fas fa-exclamation-circle"></i> کپی خودکار انجام نشد — دوباره امتحان کن';
  } else {
    toast.style.background = 'var(--success)';
    toast.innerHTML = '<i class="fas fa-check"></i> پیام کپی شد';
  }
  toast.style.opacity = '1';
  clearTimeout(toast._t);
  toast._t = setTimeout(() => toast.style.opacity = '0', failed ? 3500 : 2200);
}
