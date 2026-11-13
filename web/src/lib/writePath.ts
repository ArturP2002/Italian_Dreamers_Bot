import { type Language, type MessageKey } from "../i18n/messages";
import type { MeUser } from "./api";

/** RU plural form for «N знакомств(о/а) в подарок»; IT uses one/other. */
export function giftBannerKey(language: Language, n: number): MessageKey {
  if (language === "it") return n === 1 ? "giftBannerOne" : "giftBannerMany";
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "giftBannerOne";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "giftBannerFew";
  return "giftBannerMany";
}

/** The app pairs men with women, so the counterpart is the opposite gender of the viewer. */
export function counterpartIsMale(me: MeUser | null): boolean {
  return me?.gender === "female";
}

export function formatCount(n: number, language: Language): string {
  try {
    return n.toLocaleString(language === "it" ? "it-IT" : "ru-RU");
  } catch {
    return String(n);
  }
}

export function isGuest(me: MeUser | null): boolean {
  return me !== null && me.is_registered === false;
}

export function openTelegramUrl(url: string): void {
  const tg = window.Telegram?.WebApp;
  if (tg?.openTelegramLink && url.startsWith("https://t.me/")) tg.openTelegramLink(url);
  else window.open(url, "_blank");
}
