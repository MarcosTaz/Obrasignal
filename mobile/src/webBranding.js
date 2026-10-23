import { BRAND } from './brand-palette.mjs';

const THEME_COLOR = BRAND.slate;

// Single flat mark for favicon and interface — no gradients or theme-dependent hue.
const MARK_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="${BRAND.paper}"/><path d="M52.35 19.28A24 24 0 1 1 46.78 12.99" fill="none" stroke="${BRAND.slate}" stroke-width="8" stroke-linecap="round"/><circle cx="32" cy="32" r="6.5" fill="${BRAND.copper}"/></svg>`;
const MARK_DATA_URI = `data:image/svg+xml,${encodeURIComponent(MARK_SVG)}`;

function ensureFavicon() {
  let link = document.querySelector('link[data-obrasignal-favicon]') || document.querySelector('link[rel~="icon"]');
  if (!link) {
    link = document.createElement('link');
    link.rel = 'icon';
    document.head.appendChild(link);
  }
  link.setAttribute('data-obrasignal-favicon', 'true');
  link.type = 'image/svg+xml';
  link.href = MARK_DATA_URI;
}

function ensureThemeColor() {
  let meta = document.querySelector('meta[name="theme-color"]');
  if (!meta) {
    meta = document.createElement('meta');
    meta.name = 'theme-color';
    document.head.appendChild(meta);
  }
  meta.content = THEME_COLOR;
}

function decorateWordmarks() {
  const nodes = document.querySelectorAll('div, span');
  nodes.forEach((node) => {
    if ((node.textContent || '').trim() !== 'ObraSignal') return;

    const computed = window.getComputedStyle(node);
    const fontSize = Number.parseFloat(computed.fontSize || '0');
    // Tiny legal/footer labels remain text-only; the primary product wordmarks get the mark.
    if (!Number.isFinite(fontSize) || fontSize < 17) return;

    const markSize = Math.max(22, Math.min(31, Math.round(fontSize + 5)));
    const expectedPadding = `${markSize + 8}px`;
    const expectedSize = `${markSize}px ${markSize}px`;

    if (node.style.backgroundImage !== `url("${MARK_DATA_URI}")`) {
      node.style.backgroundImage = `url("${MARK_DATA_URI}")`;
    }
    if (node.style.backgroundRepeat !== 'no-repeat') node.style.backgroundRepeat = 'no-repeat';
    if (node.style.backgroundPosition !== 'left center') node.style.backgroundPosition = 'left center';
    if (node.style.backgroundSize !== expectedSize) node.style.backgroundSize = expectedSize;
    if (node.style.paddingLeft !== expectedPadding) node.style.paddingLeft = expectedPadding;
    if (node.style.minHeight !== `${markSize}px`) node.style.minHeight = `${markSize}px`;

    // Never override per-account theme colours. Branding only supplies the icon.
    node.setAttribute('data-obrasignal-brand', 'wordmark');
  });
}

export function installWebBranding() {
  if (typeof window === 'undefined' || typeof document === 'undefined') return () => {};

  ensureFavicon();
  ensureThemeColor();

  let frame = 0;
  const schedule = () => {
    if (frame) return;
    frame = window.requestAnimationFrame(() => {
      frame = 0;
      decorateWordmarks();
    });
  };

  schedule();
  const observer = new MutationObserver(schedule);
  observer.observe(document.documentElement, { subtree: true, childList: true });

  return () => {
    observer.disconnect();
    if (frame) window.cancelAnimationFrame(frame);
  };
}

export const obrasignalMarkDataUri = MARK_DATA_URI;
