/** Open a Stars invoice inside Telegram Mini App (or fall back to the invoice link). */

export type InvoiceStatus = "paid" | "cancelled" | "failed" | "pending";

export function openStarsInvoice(invoiceUrl: string): Promise<InvoiceStatus> {
  const url = (invoiceUrl || "").trim();
  if (!url) return Promise.resolve("failed");

  return new Promise((resolve) => {
    const tg = window.Telegram?.WebApp;
    if (tg?.openInvoice) {
      tg.openInvoice(url, (status) => {
        if (status === "paid" || status === "cancelled" || status === "failed" || status === "pending") {
          resolve(status);
          return;
        }
        resolve("failed");
      });
      return;
    }
    if (tg?.openTelegramLink) {
      tg.openTelegramLink(url);
      resolve("pending");
      return;
    }
    try {
      window.open(url, "_blank", "noopener,noreferrer");
      resolve("pending");
    } catch {
      resolve("failed");
    }
  });
}
