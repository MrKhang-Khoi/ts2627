// ===== TOAST NOTIFICATIONS =====
function showToast(message, type = 'info', duration = 3500) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = message;
  toast.className = 'toast toast-' + type;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => { toast.className = 'toast hidden'; }, duration);
}

// ===== MODAL CONFIRM =====
let _modalCallback = null;
function showModal(message, onConfirm) {
  document.getElementById('modal-message').textContent = message;
  document.getElementById('modal-overlay').classList.remove('hidden');
  _modalCallback = onConfirm;
}
function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
  _modalCallback = null;
}
document.addEventListener('DOMContentLoaded', () => {
  const confirmBtn = document.getElementById('modal-confirm');
  if (confirmBtn) {
    confirmBtn.addEventListener('click', () => {
      const cb = _modalCallback;  // lưu trước khi closeModal() xóa nó
      closeModal();
      if (cb) cb();
    });
  }
});
