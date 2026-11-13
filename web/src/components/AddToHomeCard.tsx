import { useEffect, useState } from "react";
import { type Language, t } from "../i18n/messages";

type Props = { language: Language };

/** Light-blue heart with rough ink outline — matches bot/home-screen icon from TZ. */
function BlueHeart() {
  return (
    <svg viewBox="0 0 64 64" width="28" height="28" aria-hidden>
      <path
        d="M32 54.5C18 43 10 34.2 10 24.2 10 16.6 15.8 11 22.8 11c4.2 0 7.9 2.1 9.2 5.4C33.3 13.1 37 11 41.2 11 48.2 11 54 16.6 54 24.2 54 34.2 46 43 32 54.5Z"
        fill="#6EB6F0"
      />
      <path
        d="M22.5 12.2c-5.8.6-10.2 5.4-10.2 11.8 0 9.2 7.2 17.4 19.7 28.4 12.5-11 19.7-19.2 19.7-28.4 0-6.4-4.4-11.2-10.2-11.8-3.6-.4-6.9 1.4-8.5 4.4-1.6-3-4.9-4.8-8.5-4.4Z"
        fill="none"
        stroke="#1a1511"
        strokeWidth="2.4"
        strokeLinejoin="round"
        strokeLinecap="round"
        opacity="0.92"
      />
      <path
        d="M18 18c-2.2 1.4-3.6 3.8-3.6 6.4"
        fill="none"
        stroke="#fff"
        strokeWidth="2.2"
        strokeLinecap="round"
        opacity="0.7"
      />
    </svg>
  );
}

/**
 * Home card «Добавь Dreamers на экран телефона».
 * Click → Telegram.WebApp.addToHomeScreen() immediately.
 * Hidden when unsupported or already added.
 */
export function AddToHomeCard({ language }: Props) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (!tg?.checkHomeScreenStatus || !tg.addToHomeScreen) return;
    let cancelled = false;
    try {
      tg.checkHomeScreenStatus((status) => {
        if (!cancelled) setVisible(status === "missed" || status === "unknown");
      });
    } catch {
      /* feature unavailable in this client */
    }
    const onAdded = () => setVisible(false);
    tg.onEvent?.("homeScreenAdded", onAdded);
    return () => {
      cancelled = true;
      tg.offEvent?.("homeScreenAdded", onAdded);
    };
  }, []);

  if (!visible) return null;

  return (
    <div className="add-home-card">
      <span className="add-home-card__icon">
        <BlueHeart />
      </span>
      <span className="add-home-card__text">
        <strong>{t(language, "addToHomeTitle")}</strong>
        <span>{t(language, "addToHomeHint")}</span>
      </span>
      <button
        type="button"
        className="add-home-card__btn"
        onClick={() => {
          try {
            window.Telegram?.WebApp?.addToHomeScreen?.();
          } catch {
            setVisible(false);
          }
        }}
      >
        {t(language, "addToHomeCta")}
      </button>
    </div>
  );
}
