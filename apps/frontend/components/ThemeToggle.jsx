"use client";

import { useEffect, useState } from "react";

// Toggle sáng/tối, lưu localStorage. Mặc định sáng (định vị thương mại).
export default function ThemeToggle() {
  const [theme, setTheme] = useState("light");

  useEffect(() => {
    try {
      setTheme(localStorage.getItem("theme") === "dark" ? "dark" : "light");
    } catch {
      /* bỏ qua */
    }
  }, []);

  useEffect(() => {
    if (theme === "dark") {
      document.documentElement.setAttribute("data-theme", "dark");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
  }, [theme]);

  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    try {
      localStorage.setItem("theme", next);
    } catch {
      /* bỏ qua */
    }
    setTheme(next);
  }

  return (
    <button
      className="theme-toggle"
      type="button"
      onClick={toggle}
      aria-label={theme === "dark" ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối"}
    >
      {theme === "dark" ? "☀️" : "🌙"}
    </button>
  );
}
