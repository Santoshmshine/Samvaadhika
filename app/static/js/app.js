/**
 * Samvaadhika — shared JS utilities
 * Loaded on every page via base.html
 */

// ── Auto-dismiss alerts after 5 seconds ──
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.alert').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity 0.5s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 500);
    }, 5000);
  });
});

// ── Copy-to-clipboard helper ──
function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    showToastGlobal('Copied to clipboard', 1800);
  });
}

// ── Global toast (used by any page) ──
function showToastGlobal(msg, duration = 3000) {
  let toast = document.getElementById('globalToast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'globalToast';
    toast.style.cssText = `
      position:fixed;bottom:1.5rem;left:50%;transform:translateX(-50%);
      background:var(--green-dark);color:white;
      padding:0.6rem 1.25rem;border-radius:8px;
      font-size:0.85rem;box-shadow:0 4px 16px rgba(0,0,0,0.2);
      z-index:9999;transition:opacity 0.3s;
    `;
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.style.opacity = '1';
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => { toast.style.opacity = '0'; }, duration);
}

// ── Confirm-before-delete helper ──
function confirmDelete(message, callback) {
  if (confirm(message || 'Are you sure?')) callback();
}

// ── Format file size ──
function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

// ── Relative time ──
function relativeTime(isoString) {
  if (!isoString) return '—';
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}
