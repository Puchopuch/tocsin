import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { APP_NAME } from './src/config.js';

// The page title comes from the same constant as the rest of the site.
const appName = {
  name: 'app-name',
  transformIndexHtml: (html) => html.replaceAll('__APP_NAME__', APP_NAME),
};

// Content-Security-Policy added to built pages only (the dev server needs inline scripts for hot
// reload). Scripts, styles, fonts and data/cards.json all come from the site itself, and the
// browser refuses any request to another domain. No inline script and no eval. Trusted Types:
// no string can reach a script or HTML sink (innerHTML and the like), and no policy may be created
// to allow one. Inline styles are allowed because React and motion set style attributes.
// frame-ancestors, ignored in a <meta> tag, will be an HTTP header of the host.
const CSP = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "font-src 'self'",
  "img-src 'self' data:",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
  "require-trusted-types-for 'script'",
  "trusted-types 'none'",
];

// The tag is written by hand, right after <meta charset>, so that the quotes of the policy stay
// readable ('self' rather than &#39;self&#39;). The build fails if the tag cannot be placed: a
// security control must never disappear silently.
const contentSecurityPolicy = {
  name: 'content-security-policy',
  apply: 'build',
  transformIndexHtml(html) {
    const charset = '<meta charset="UTF-8" />';
    if (!html.includes(charset)) throw new Error('index.html: <meta charset="UTF-8" /> not found, CSP not added');
    return html.replace(charset, `${charset}\n    <meta http-equiv="Content-Security-Policy" content="${CSP.join('; ')}" />`);
  },
};

// One mode only: `npm run dev` and `npm run build` both read data/cards.json, written by the
// collector in public/data/ (ignored by git).
export default defineConfig({
  // Relative paths: the built site works from any folder or sub-path.
  base: './',
  plugins: [react(), tailwindcss(), appName, contentSecurityPolicy],
  build: { outDir: 'dist', emptyOutDir: true },
  // The dev and preview servers answer this computer only, never the local network.
  server: { host: '127.0.0.1' },
  preview: { host: '127.0.0.1' },
});
