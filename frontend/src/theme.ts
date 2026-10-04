import { useState } from "react";

/*
 * The light/dark theme. index.html sets <html data-theme> before the first paint (the saved choice, else the
 * system setting), index.css keys the dark token values on it, and the header's toggle flips it here.
 */

type Theme = "light" | "dark";

/** The theme showing now, as index.html (or the last toggle) set it on <html>. */
function currentTheme(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

/**
 * The theme and a function that flips it. Flipping sets <html data-theme> (every token follows at once) and
 * saves the choice in this browser, so a reload keeps it. Storage can be blocked (a private window): the
 * toggle still works, only until the page reloads. Output: [theme, toggle].
 */
export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(currentTheme);
  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("theme", next);
    } catch {
      // Not saved: the choice lasts until the page reloads.
    }
    setTheme(next);
  }
  return [theme, toggle];
}
