const locks = new Set<symbol>();
let alreadyLocked = false;

/** Each overlay owns its lock, so handing off between dialogs cannot unlock the page. */
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
