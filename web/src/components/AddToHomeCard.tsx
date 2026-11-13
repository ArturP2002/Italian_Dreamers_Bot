import { useEffect, useState } from "react";
import { type Language, t } from "../i18n/messages";

type Props = { language: Language };

/**
 * Standalone home card between funnel/boost and «Участники».
 * Click → Telegram.WebApp.addToHomeScreen().
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
      /* unavailable */
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
      <span className="add-home-card__icon" aria-hidden>
        <img
          src="/photos/add_home_cyan_heart.jpg"
          alt=""
          width={44}
          height={44}
          decoding="async"
        />
      </span>
      <div className="add-home-card__text">
        <strong className="add-home-card__title">{t(language, "addToHomeTitle")}</strong>
        <span className="add-home-card__hint">{t(language, "addToHomeHint")}</span>
      </div>
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
