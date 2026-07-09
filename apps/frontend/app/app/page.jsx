"use client";

import dynamic from "next/dynamic";

// Chart dùng lightweight-charts + WebSocket (chỉ chạy được ở client) -> tải
// động, tắt SSR để không import thư viện browser trong lúc render phía server.
const ChartApp = dynamic(() => import("../../components/ChartApp"), { ssr: false });

export default function AppPage() {
  return <ChartApp />;
}
