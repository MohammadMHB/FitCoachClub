// FitCoach Main JS

// ===== THEME =====
const themeToggle = document.getElementById('themeToggle');
const themeIcon = document.getElementById('themeIcon');
const html = document.documentElement;

function setTheme(theme) {
  html.setAttribute('data-theme', theme);
  localStorage.setItem('fc_theme', theme);
  if (themeIcon) {
    themeIcon.className = theme === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
  }
}

// Init theme
const savedTheme = localStorage.getItem('fc_theme') || 'dark';
setTheme(savedTheme);

if (themeToggle) {
  themeToggle.addEventListener('click', () => {
    const current = html.getAttribute('data-theme');
    setTheme(current === 'dark' ? 'light' : 'dark');
  });
}

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
  document.body.style.overflow = sidebar?.classList.contains('open') ? 'hidden' : '';
}

menuToggle?.addEventListener('click', toggleSidebar);
overlay.addEventListener('click', toggleSidebar);

// ===== AUTO DISMISS ALERTS =====
setTimeout(() => {
  document.querySelectorAll('.alert').forEach(a => {
    a.style.transition = 'opacity 0.5s';
    a.style.opacity = '0';
    setTimeout(() => a.remove(), 500);
  });
}, 4000);

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
const currentPath = window.location.pathname;
document.querySelectorAll('.nav-item, .bottom-nav-item').forEach(item => {
  const href = item.getAttribute('href');
  if (href && currentPath.startsWith(href) && href !== '/') {
    item.classList.add('active');
  }
});

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
