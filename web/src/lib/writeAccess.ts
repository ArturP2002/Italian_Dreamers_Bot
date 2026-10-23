import { patchWriteAccess } from "./api";

export function telegramPlatform(): string {
  const tg = window.Telegram?.WebApp as { platform?: string } | undefined;
  return (tg?.platform || "").toLowerCase();
}

export async function ensureWriteAccess(): Promise<boolean> {
  const tg = window.Telegram?.WebApp;
  const request = tg?.requestWriteAccess;
  if (!request) {
    return true;
  }
  const granted = await new Promise<boolean>((resolve) => {
    const done = (value: boolean) => {
      window.clearTimeout(timer);
      resolve(value);
    };
    const timer = window.setTimeout(() => done(false), 12_000);
    try {
      request((ok) => done(Boolean(ok)));
    } catch {
      done(true);
    }
  });
  await patchWriteAccess(granted);
  return granted;
}

export function usernameHowtoSrcs(language: "ru" | "it", platform?: string): string[] {
  const lang = language === "it" ? "it" : "ru";
  const plat = (platform || telegramPlatform()).toLowerCase();
  if (plat === "ios" || plat === "macos" || plat === "iphone") {
    return [`/username_howto/iphone_${lang}.jpg`];
  }
  if (plat === "android" || plat === "android_x") {
    return [`/username_howto/android_${lang}.jpg`];
  }
  return [`/username_howto/iphone_${lang}.jpg`, `/username_howto/android_${lang}.jpg`];
}
