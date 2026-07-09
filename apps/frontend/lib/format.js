// Định dạng giá/% dùng chung cho ticker tape + market list.
export function formatPrice(price) {
  return Number(price).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function formatChange(changePct) {
  if (changePct === null || Number.isNaN(changePct)) return "--";
  const sign = changePct > 0 ? "+" : "";
  return `${sign}${changePct.toFixed(2)}%`;
}

export function directionOf(changePct) {
  if (changePct === null || Number.isNaN(changePct)) return "flat";
  if (changePct > 0) return "up";
  if (changePct < 0) return "down";
  return "flat";
}
