// Small DOM + formatting helpers shared across the dashboard.

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined) node.setAttribute(k, v);
  }
  for (const c of [].concat(children)) {
    if (c == null) continue;
    node.append(c.nodeType ? c : document.createTextNode(c));
  }
  return node;
}

const CR = 1e7; // 1 crore = 10,000,000

// Rupees -> "1.73 Cr" / "45.20 L" (crore for big, lakh for smaller).
export function fmtCr(rupees) {
  if (rupees == null) return "—";
  const v = Number(rupees);
  if (Math.abs(v) >= CR) return (v / CR).toFixed(2) + " Cr";
  if (Math.abs(v) >= 1e5) return (v / 1e5).toFixed(2) + " L";
  return "₹" + Math.round(v).toLocaleString("en-IN");
}

export const toCr = (rupees) => (rupees == null ? 0 : Number(rupees) / CR);

export function fmtInt(n) {
  if (n == null) return "—";
  return Math.round(Number(n)).toLocaleString("en-IN");
}

export function fmtPct(n) {
  return n == null ? "—" : Number(n).toFixed(2) + "%";
}

// "2026-04-29" -> "29 Apr 2026"
export function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso + "T00:00:00");
  if (isNaN(d)) return iso;
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export function daysAgoIso(days, from) {
  const d = from ? new Date(from + "T00:00:00") : new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

export function csvEscape(value) {
  const s = value == null ? "" : String(value);
  return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

export function downloadCsv(filename, rows) {
  const text = rows.map((r) => r.map(csvEscape).join(",")).join("\n");
  const blob = new Blob([text], { type: "text/csv;charset=utf-8;" });
  const a = el("a", { href: URL.createObjectURL(blob), download: filename });
  document.body.append(a);
  a.click();
  a.remove();
}

// Human labels for canonical enum codes.
export const LABELS = {
  BUY: "Buy", SELL: "Sell", PLEDGE: "Pledge", REVOKE: "Revoke", INVOKE: "Invoke", OTHER: "Other",
  PROMOTER: "Promoter", PROMOTER_GROUP: "Promoter Group", PROMOTER_DIRECTOR: "Promoter & Director",
  PROMOTER_DESIGNATED: "Promoter & Designated",
  DIRECTOR: "Director", KMP: "KMP", DESIGNATED_EMPLOYEE: "Designated/Employee",
  IMMEDIATE_RELATIVE: "Immediate Relative", TRUST: "Trust", CONNECTED_PERSON: "Connected Person",
  MARKET_PURCHASE: "Market Purchase", MARKET_SALE: "Market Sale", MARKET: "Market",
  ESOP: "ESOP", OFF_MARKET: "Off Market",
  PLEDGE_CREATION: "Pledge Creation", PLEDGE_INVOCATION: "Pledge Invocation", PLEDGE_REVOCATION: "Pledge Revocation",
  GIFT: "Gift", INTER_SE: "Inter-se Transfer", ALLOTMENT: "Allotment", PREFERENTIAL: "Preferential",
  CONVERSION: "Conversion", RIGHTS: "Rights", BUYBACK: "Buyback", BLOCK_DEAL: "Block Deal",
  INHERITANCE: "Inheritance", TRUST_TRANSFER: "Trust Transfer", SCHEME: "Scheme", OTHERS: "Others",
  DIVIDEND: "Dividend", BONUS: "Bonus", SPLIT: "Split", REIT_INVIT: "REIT/InvIT distribution",
  MERGER_DEMERGER: "Merger/Demerger", CAPITAL_RESTRUCTURE: "Capital Restructure", DEBT: "Debt/Interest",
  MEETING: "Meeting", OPEN_OFFER: "Open Offer",
};
export const label = (code) => LABELS[code] || code;
