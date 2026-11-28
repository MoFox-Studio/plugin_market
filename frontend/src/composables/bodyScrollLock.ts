const locks = new Set<symbol>();
let alreadyLocked = false;

/** 每个浮层持有独立的锁，避免切换对话框时解除页面滚动锁定。 */
export function lockBodyScroll(): () => void {
  if (typeof document === 'undefined') return () => {};
  const body = document.body;
  const token = Symbol('modal-scroll-lock');
  if (!locks.size) alreadyLocked = body.classList.contains('modal-open');
  locks.add(token);
  body.classList.add('modal-open');
  return () => {
    if (!locks.delete(token)) return;
    if (!locks.size && !alreadyLocked) body.classList.remove('modal-open');
  };
}
