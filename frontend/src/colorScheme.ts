export type ColorScheme = 'dark' | 'light'

/** index.html reads the same key before the page paints, so a saved light theme never flashes dark. */
const SCHEME_STORAGE_KEY = 'f1ra-color-scheme'

/** Dark unless the visitor chose light. */
export function loadScheme(): ColorScheme {
  try {
    return localStorage.getItem(SCHEME_STORAGE_KEY) === 'light' ? 'light' : 'dark'
  } catch {
    return 'dark'
  }
}

export function applyScheme(scheme: ColorScheme) {
  document.documentElement.dataset.theme = scheme
}

export function saveScheme(scheme: ColorScheme) {
  try {
    localStorage.setItem(SCHEME_STORAGE_KEY, scheme)
  } catch {
    // Storage can be blocked. The theme still applies for this visit.
  }
}
