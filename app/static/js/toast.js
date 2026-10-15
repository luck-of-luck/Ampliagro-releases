/**
 * Toast Notifications System
 */

function showToast(message, type = 'info', duration = 4000) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast--${type}`;

  let iconClass = 'bi-info-circle';
  if (type === 'success') iconClass = 'bi-check-circle';
  if (type === 'error') iconClass = 'bi-x-circle';
  if (type === 'warning') iconClass = 'bi-exclamation-triangle';

  toast.innerHTML = `
    <span class="toast__icon"><i class="bi ${iconClass}"></i></span>
    <div class="toast__content">
      <span class="toast__message">${message}</span>
    </div>
    <button class="toast__close" onclick="this.closest('.toast').remove()">&times;</button>
  `;

  container.appendChild(toast);

  // Trigger animation
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      toast.classList.add('toast--visible');
    });
  });

  setTimeout(() => {
    toast.classList.remove('toast--visible');
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

const showSuccess = (msg) => showToast(msg, 'success');
const showError = (msg) => showToast(msg, 'error');
const showWarning = (msg) => showToast(msg, 'warning');
const showInfo = (msg) => showToast(msg, 'info');

// Make it available globally if not using modules
window.showToast = showToast;
window.showSuccess = showSuccess;
window.showError = showError;
window.showWarning = showWarning;
window.showInfo = showInfo;
