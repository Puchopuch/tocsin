// French typography for every text shown on the page.

const NBSP = ' ';
const NARROW_NBSP = ' ';

/**
 * Uses the typographic apostrophe, adds a non-breaking space before high punctuation and inside
 * guillemets, and a narrow one as thousands separator, so that "?" or "000" never start a line
 * on their own.
 */
export function typo(text) {
  if (typeof text !== 'string') return text;
  return text
    .replace(/'/g, '’')
    .replace(/ ([:;!?»])/g, `${NBSP}$1`)
    .replace(/« /g, `«${NBSP}`)
    .replace(/(\d) (?=\d{3}(?!\d))/g, `$1${NARROW_NBSP}`);
}
