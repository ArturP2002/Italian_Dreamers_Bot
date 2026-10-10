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
  ready: () => void;
  expand: () => void;
  themeParams: Record<string, string>;
  colorScheme: "light" | "dark";
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
  openTelegramLink?: (url: string) => void;
  openLink?: (url: string) => void;
  showAlert?: (message: string, callback?: () => void) => void;
  showConfirm?: (message: string, callback?: (ok: boolean) => void) => void;
  showPopup?: (params: {
    title?: string;
    message: string;
    buttons?: Array<{ id?: string; type?: string; text?: string }>;
  }, callback?: (id: string) => void) => void;
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
