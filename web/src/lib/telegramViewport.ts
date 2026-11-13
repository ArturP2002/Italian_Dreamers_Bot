/** Enter expanded / fullscreen Telegram Mini App viewport. */

type TgViewport = {
  ready: () => void;
  expand: () => void;
  requestFullscreen?: () => void;
  exitFullscreen?: () => void;
  disableVerticalSwipes?: () => void;
  isVersionAtLeast?: (version: string) => boolean;
  isFullscreen?: boolean;
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
  setBottomBarColor?: (color: string) => void;
  onEvent?: (event: string, handler: (...args: unknown[]) => void) => void;
  offEvent?: (event: string, handler: (...args: unknown[]) => void) => void;
};

const HEADER = "#1A1511";
const BG = "#1A1511";

function syncSafeAreaCssVars() {
  const root = document.documentElement;
  const top = getComputedStyle(root).getPropertyValue("--tg-content-safe-area-inset-top").trim();
  const bottom = getComputedStyle(root).getPropertyValue("--tg-content-safe-area-inset-bottom").trim();
  const safeTop = getComputedStyle(root).getPropertyValue("--tg-safe-area-inset-top").trim();
  const safeBottom = getComputedStyle(root).getPropertyValue("--tg-safe-area-inset-bottom").trim();
  // Telegram injects these; keep a combined fallback for our --safe-* tokens.
  if (top || safeTop) {
    root.style.setProperty(
      "--safe-top",
      `calc(${safeTop || "0px"} + ${top || "0px"})`,
    );
  }
  if (bottom || safeBottom) {
    root.style.setProperty(
      "--safe-bottom",
      `calc(${safeBottom || "0px"} + ${bottom || "0px"})`,
    );
  }
}

export function initTelegramFullscreen(): () => void {
  const tg = window.Telegram?.WebApp as TgViewport | undefined;
  if (!tg) return () => undefined;

  tg.ready();
  tg.expand();
  tg.setHeaderColor?.(HEADER);
  tg.setBackgroundColor?.(BG);
  tg.setBottomBarColor?.(BG);
  tg.disableVerticalSwipes?.();

  const supportsFs =
    typeof tg.requestFullscreen === "function" &&
    (typeof tg.isVersionAtLeast !== "function" || tg.isVersionAtLeast("8.0"));

  if (supportsFs && !tg.isFullscreen) {
    try {
      tg.requestFullscreen?.();
    } catch {
      // Older / unsupported clients stay on expand().
    }
  }

  syncSafeAreaCssVars();

  const onSafeArea = () => syncSafeAreaCssVars();
  const onFs = () => syncSafeAreaCssVars();

  tg.onEvent?.("safeAreaChanged", onSafeArea);
  tg.onEvent?.("contentSafeAreaChanged", onSafeArea);
  tg.onEvent?.("fullscreenChanged", onFs);
  tg.onEvent?.("viewportChanged", onSafeArea);

  // Retry once shortly after boot — some clients apply fullscreen after ready.
  const retry = window.setTimeout(() => {
    if (supportsFs && !tg.isFullscreen) {
      try {
        tg.requestFullscreen?.();
      } catch {
        /* ignore */
      }
    }
    syncSafeAreaCssVars();
  }, 400);

  return () => {
    window.clearTimeout(retry);
    tg.offEvent?.("safeAreaChanged", onSafeArea);
    tg.offEvent?.("contentSafeAreaChanged", onSafeArea);
    tg.offEvent?.("fullscreenChanged", onFs);
    tg.offEvent?.("viewportChanged", onSafeArea);
  };
}
