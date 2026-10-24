// Stable timing geometry for the public ObraSignal radar introduction.
// Positions are an abstract visual signal, never a real location or tender.
export const INTRO_SCAN_MS = 6200;
export const INTRO_BRAND_HOLD_MS = 920;
export const INTRO_EXIT_MS = 760;
export const INTRO_WATCHDOG_GRACE_MS = 1200;
export const INTRO_TOTAL_MS = INTRO_SCAN_MS + INTRO_BRAND_HOLD_MS + INTRO_EXIT_MS;
export const INTRO_WATCHDOG_MS = INTRO_TOTAL_MS + INTRO_WATCHDOG_GRACE_MS;

// The beam begins 58 degrees above the x axis. A full sweep arrives at the
// upper-right signal at roughly 42% through the scan, not after the marker.
export const INTRO_SWEEP_START_DEG = -315;
export const INTRO_SWEEP_END_DEG = 465;
export const INTRO_SIGNAL_PROGRESS = 0.42;

export function sweepDegreesAt(progress) {
  const p = Math.max(0, Math.min(1, Number.isFinite(progress) ? progress : 0));
  return INTRO_SWEEP_START_DEG + (INTRO_SWEEP_END_DEG - INTRO_SWEEP_START_DEG) * p;
}
