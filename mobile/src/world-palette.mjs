// Marketing keeps ObraSignal's stable night identity; the private command centre
// follows the customer's selected theme without independent fixed-colour panels.
import {createThemeColors, resolveTheme, DEFAULT_THEME} from './theme-system.mjs';

export function createWorldPalette(theme = DEFAULT_THEME) {
  const C = createThemeColors(theme);
  const isDark = resolveTheme(theme).mode === 'dark';
  return Object.freeze({
    bg: C.bg,
    panel: C.panel,
    line: C.line,
    blue: C.blue,
    copper: C.brandCopper,
    light: C.text,
    muted: C.muted,
    mint: C.green,
    soft: C.muted,
    isDark,
    sidebar: C.panel,
    sidebarActive: C.navActive,
    sidebarBottom: C.panel2,
    radar: C.panel2,
    secondaryButton: C.panel2,
    secondaryBorder: C.borderStrong,
    // Lighter copper is reserved for small text; the permanent brand copper remains unchanged.
    accentLabel: isDark ? '#DDA17C' : '#85401E',
  });
}
