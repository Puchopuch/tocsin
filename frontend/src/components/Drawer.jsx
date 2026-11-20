import { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { useLang } from '../lang.jsx';

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])';

/**
 * Slide-over panel from the right, used by "En savoir plus" and "Sources".
 *
 * Closes with Escape, the close button or a click on the blurred backdrop; keeps the keyboard
 * focus inside while open, starting on the close button, then gives it back to the button that
 * opened it; locks the page scroll meanwhile.
 */
export default function Drawer({ open, onClose, labelledBy, header, children }) {
  const { t } = useLang();
  const reduceMotion = useReducedMotion();
  const panelRef = useRef(null);
  const closeRef = useRef(null);

  // Focus: remember the opener, move to the close button, give focus back on close.
  useEffect(() => {
    if (!open) return undefined;
    const opener = document.activeElement;
    closeRef.current?.focus();
    return () => {
      if (opener instanceof HTMLElement && opener.isConnected) opener.focus();
    };
  }, [open]);

  // The page behind does not scroll while the panel is open.
  useEffect(() => {
    if (!open) return undefined;
    const root = document.documentElement;
    const previous = root.style.overflow;
    root.style.overflow = 'hidden';
    return () => {
      root.style.overflow = previous;
    };
  }, [open]);

  // Escape closes; Tab and Shift+Tab cycle inside the panel.
  useEffect(() => {
    if (!open) return undefined;

    function onKeyDown(event) {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      const panel = panelRef.current;
      if (event.key !== 'Tab' || !panel) return;
      const items = [...panel.querySelectorAll(FOCUSABLE)].filter((el) => el.getClientRects().length > 0);
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      const inside = panel.contains(document.activeElement);
      if (event.shiftKey && (!inside || document.activeElement === first)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (!inside || document.activeElement === last)) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="drawer-root" key="drawer">
          <motion.div
            className="drawer-backdrop"
            aria-hidden="true"
            onClick={onClose}
            initial={reduceMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={reduceMotion ? undefined : { opacity: 0 }}
            transition={{ duration: 0.22, ease: 'linear' }}
          />
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={labelledBy}
            className="drawer-panel"
            initial={reduceMotion ? false : { x: '100%' }}
            animate={{ x: 0 }}
            exit={reduceMotion ? undefined : { x: '100%' }}
            transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="drawer-head">
              <div className="min-w-0">{header}</div>
              <button ref={closeRef} type="button" className="drawer-close link" onClick={onClose}>
                {t.close}
              </button>
            </div>
            {children}
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

/** A titled part of a panel, with an optional element on the right of the title. */
export function DrawerSection({ title, aside, className = '', children }) {
  const id = useId();
  return (
    <section className={`drawer-section ${className}`} aria-labelledby={id}>
      <div className="drawer-section__head">
        <h3 id={id}>{title}</h3>
        {aside}
      </div>
      {children}
    </section>
  );
}
