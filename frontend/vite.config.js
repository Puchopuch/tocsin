import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { viteSingleFile } from 'vite-plugin-singlefile';
import { APP_NAME } from './src/config.js';

// The page title comes from the same constant as the rest of the site.
const appName = {
  name: 'app-name',
  transformIndexHtml: (html) => html.replaceAll('__APP_NAME__', APP_NAME),
};

// Content-Security-Policy added to built pages only (the dev server needs inline scripts for hot
// reload). Both policies make the browser refuse any request to another domain (brief B5.8).
const CSP = {
  // Real site: scripts, styles, fonts and data/cards.json all come from the site itself.
  // Inline styles are allowed because React and motion set style attributes.
  site: [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "font-src 'self'",
    "img-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'none'",
  ],
  // Single-file demo: everything is inlined, and the demo never fetches anything.
  demo: [
    "default-src 'none'",
    "script-src 'unsafe-inline'",
    "style-src 'unsafe-inline'",
    'font-src data:',
    'img-src data:',
    "connect-src 'none'",
    "base-uri 'none'",
    "form-action 'none'",
  ],
};

// The tag is written by hand, right after <meta charset>, so that the quotes of the policy stay
// readable ('self' rather than &#39;self&#39;). The build fails if the tag cannot be placed: a
// security control must never disappear silently.
function contentSecurityPolicy(directives) {
  const charset = '<meta charset="UTF-8" />';
  const tag = `<meta http-equiv="Content-Security-Policy" content="${directives.join('; ')}" />`;
  return {
    name: 'content-security-policy',
    apply: 'build',
    transformIndexHtml(html) {
      if (!html.includes(charset)) throw new Error('index.html: <meta charset="UTF-8" /> not found, CSP not added');
      return html.replace(charset, `${charset}\n    ${tag}`);
    },
  };
}

export default defineConfig(({ mode }) => {
  const demo = mode === 'demo';
  return {
    // Relative paths: the built site works from any folder or sub-path.
    base: './',
    plugins: [
      react(),
      tailwindcss(),
      appName,
      contentSecurityPolicy(demo ? CSP.demo : CSP.site),
      // "demo" mode: one self-contained HTML file that can be opened or sent as is.
      demo && viteSingleFile(),
    ],
    build: {
      outDir: demo ? 'dist-demo' : 'dist',
      emptyOutDir: true,
    },
  };
});
