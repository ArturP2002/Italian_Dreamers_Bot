/// <reference types="vite/client" />

export {};

declare module "*.css";
declare module "*.jpg" {
  const src: string;
  export default src;
}
declare module "*.jpeg" {
  const src: string;
  export default src;
}
declare module "*.png" {
  const src: string;
  export default src;
}
declare module "*.webp" {
  const src: string;
  export default src;
}

type TelegramWebApp = {
  initData: string;
  initDataUnsafe: {
    start_param?: string;
    [key: string]: unknown;
  };
  platform?: string;
  version?: string;
  isFullscreen?: boolean;
  isVerticalSwipesEnabled?: boolean;
  requestWriteAccess?: (callback?: (granted: boolean) => void) => void;
  ready: () => void;
  expand: () => void;
  requestFullscreen?: () => void;
  exitFullscreen?: () => void;
  disableVerticalSwipes?: () => void;
  enableVerticalSwipes?: () => void;
  isVersionAtLeast?: (version: string) => boolean;
  onEvent?: (event: string, handler: (...args: unknown[]) => void) => void;
  offEvent?: (event: string, handler: (...args: unknown[]) => void) => void;
  themeParams: Record<string, string>;
  colorScheme: "light" | "dark";
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
  setBottomBarColor?: (color: string) => void;
  openTelegramLink?: (url: string) => void;
  openLink?: (url: string) => void;
  showAlert?: (message: string, callback?: () => void) => void;
  showConfirm?: (message: string, callback?: (ok: boolean) => void) => void;
  showPopup?: (params: {
    title?: string;
    message: string;
    buttons?: Array<{ id?: string; type?: string; text?: string }>;
  }, callback?: (id: string) => void) => void;
  HapticFeedback?: {
    impactOccurred?: (style: "light" | "medium" | "heavy" | "rigid" | "soft") => void;
    notificationOccurred?: (type: "error" | "success" | "warning") => void;
  };
};

declare global {
  interface Window {
    Telegram?: {
      WebApp: TelegramWebApp;
    };
  }

  interface ImportMetaEnv {
    readonly VITE_API_BASE_URL?: string;
    readonly VITE_DEV_TELEGRAM_ID?: string;
  }

  interface ImportMeta {
    readonly env: ImportMetaEnv;
  }
}
