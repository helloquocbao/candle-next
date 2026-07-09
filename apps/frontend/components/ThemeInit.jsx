"use client";

import { useEffect } from "react";

// Khôi phục theme tối từ localStorage khi tải trang (mặc định sáng).
export default function ThemeInit() {
  useEffect(() => {
    try {
      if (localStorage.getItem("theme") === "dark") {
        document.documentElement.setAttribute("data-theme", "dark");
      }
    } catch {
      /* localStorage không dùng được -> giữ theme sáng mặc định */
    }
  }, []);
  return null;
}
