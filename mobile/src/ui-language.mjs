/** Product copy defaults to English irrespective of IP, browser or account country.
 * Until translations are complete, only English is exposed as a fully supported UI
 * language. Geographic procurement coverage remains an independent account setting.
 */
export const DEFAULT_LANGUAGE = 'en';
export const PUBLIC_MARKET_LABEL = 'International';
export const SUPPORTED_LANGUAGES = Object.freeze(['en']);
export function normalizeLanguage(value) { return value === 'en' ? value : DEFAULT_LANGUAGE; }
