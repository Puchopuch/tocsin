// The language of the page: the browser's by default, then the reader's choice, kept in this
// browser only. The <html lang> attribute follows it.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { browserLang, LANG_KEY, UI, validLang } from './lib/i18n.js';

const LangContext = createContext(null);

/** The choice kept in this browser, if any; only "fr" or "en" is accepted. */
function rememberedLang() {
  try {
    return validLang(window.localStorage.getItem(LANG_KEY));
  } catch {
    return null;
  }
}

export function LangProvider({ children }) {
  const [lang, setLangState] = useState(() => rememberedLang() ?? browserLang(navigator.languages ?? [navigator.language]));

  const setLang = useCallback((next) => {
    const chosen = validLang(next);
    if (!chosen) return;
    setLangState(chosen);
    try {
      window.localStorage.setItem(LANG_KEY, chosen);
    } catch {
      // Storage unavailable (private mode, blocked site data): the choice lasts for this visit.
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const value = useMemo(() => ({ lang, setLang, t: UI[lang] }), [lang, setLang]);
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

/** { lang, setLang, t }: the language, how to change it, and the texts of the interface. */
export function useLang() {
  return useContext(LangContext);
}
