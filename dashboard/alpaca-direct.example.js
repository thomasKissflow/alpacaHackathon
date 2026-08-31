/*
 * OPTIONAL, NOT WIRED IN BY DEFAULT.
 *
 * Calls Alpaca's Trading API directly from the browser instead of reading
 * the committed data/*.json files. Useful ONLY for a local demo recording
 * where you control the machine and never deploy this page publicly.
 *
 * DO NOT use this on a publicly hosted dashboard (GitHub Pages, Vercel,
 * etc.) with your real ALPACA_SECRET_KEY in it: any visitor can open dev
 * tools, read the key out of the page source, and place/cancel trades on
 * your paper account -- which would invalidate the P&L judges are scoring.
 * Alpaca has no separate "read-only" browser-safe key.
 *
 * To use locally: rename to alpaca-direct.js, fill in the keys, and add
 * <script src="alpaca-direct.js"></script> to index.html before app.js.
 */

const ALPACA_API_KEY = "PASTE_LOCAL_ONLY_KEY";
const ALPACA_SECRET_KEY = "PASTE_LOCAL_ONLY_SECRET";
const ALPACA_BASE_URL = "https://paper-api.alpaca.markets";

async function fetchAccountDirect() {
  const res = await fetch(`${ALPACA_BASE_URL}/v2/account`, {
    headers: {
      "APCA-API-KEY-ID": ALPACA_API_KEY,
      "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    },
  });
  if (!res.ok) throw new Error(`Alpaca account fetch failed: ${res.status}`);
  return res.json();
}

async function fetchPositionsDirect() {
  const res = await fetch(`${ALPACA_BASE_URL}/v2/positions`, {
    headers: {
      "APCA-API-KEY-ID": ALPACA_API_KEY,
      "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    },
  });
  if (!res.ok) throw new Error(`Alpaca positions fetch failed: ${res.status}`);
  return res.json();
}
