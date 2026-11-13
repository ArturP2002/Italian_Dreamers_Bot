import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { type Language, t, tf } from "../i18n/messages";
import { buyCatalogTop, fetchConfig, type PublicConfig } from "../lib/api";
import { openStarsInvoice } from "../lib/telegramPay";

type Props = {
  language: Language;
  verified: boolean;
  isTop: boolean;
  topUntil?: string | null;
  starsOnly?: boolean;
  className?: string;
};

type PayMethod = "rub" | "stars";

function daysLeft(iso: string | null | undefined): number {
  if (!iso) return 0;
  const ms = new Date(iso).getTime() - Date.now();
  if (Number.isNaN(ms) || ms <= 0) return 0;
  return Math.max(1, Math.ceil(ms / (24 * 60 * 60 * 1000)));
}

export function BoostTopCta({
  language,
  verified,
  isTop,
  topUntil,
  starsOnly = language === "it",
  className = "",
}: Props) {
  const [open, setOpen] = useState(false);
  const [method, setMethod] = useState<PayMethod>(starsOnly ? "stars" : "rub");
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [config, setConfig] = useState<PublicConfig | null>(null);

  useEffect(() => {
    void fetchConfig().then(setConfig);
  }, []);

  useEffect(() => {
    setMethod(starsOnly ? "stars" : "rub");
  }, [starsOnly]);

  const stars = config?.prices.catalog_top_stars ?? 500;
  const rub = config?.prices.catalog_top_rub ?? 1000;
  const left = daysLeft(topUntil);

  if (!verified) {
    return (
      <Link to="/verify" className={`boost-top-cta${className ? ` ${className}` : ""}`}>
        <span className="boost-top-cta__icon" aria-hidden>
          ↑
        </span>
        <span className="boost-top-cta__copy">
          <strong>{t(language, "boostNeedVerifyTitle")}</strong>
          <span>{t(language, "boostNeedVerifyHint")}</span>
        </span>
        <span className="boost-top-cta__chevron" aria-hidden>
          ›
        </span>
      </Link>
    );
  }

  const onPay = async () => {
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      if (method === "rub") {
        setInfo(t(language, "boostRubSoon"));
        return;
      }
      const res = await buyCatalogTop();
      if (res.included || res.already) {
        setInfo(t(language, "boostIncluded"));
        setOpen(false);
        return;
      }
      if (!res.invoice_url) {
        setError(t(language, "errorGeneric"));
        return;
      }
      const status = await openStarsInvoice(res.invoice_url);
      if (status === "paid") {
        setInfo(t(language, "paymentPaid"));
        setOpen(false);
      } else if (status === "cancelled") {
        setInfo(t(language, "paymentCancelled"));
      } else if (status === "pending") {
        setInfo(t(language, "invoiceSent"));
        setOpen(false);
      } else {
        setError(t(language, "errorGeneric"));
      }
    } catch {
      setError(t(language, "errorGeneric"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {isTop && left > 0 ? (
        <p className="boost-top-active">
          <span className="boost-top-active__icon" aria-hidden>
            ↑
          </span>
          {tf(language, "boostActiveDays", { n: left })}
        </p>
      ) : null}

      <button
        type="button"
        className={`boost-top-cta${className ? ` ${className}` : ""}`}
        onClick={() => {
          setError(null);
          setInfo(null);
          setOpen(true);
        }}
      >
        <span className="boost-top-cta__icon" aria-hidden>
          ↑
        </span>
        <span className="boost-top-cta__copy">
          <strong>{t(language, "boostTitle")}</strong>
          <span>{t(language, "boostHint")}</span>
        </span>
        <span className="boost-top-cta__chevron" aria-hidden>
          ›
        </span>
      </button>

      {info ? <p className="home-meta">{info}</p> : null}
      {error ? <p className="form-error">{error}</p> : null}

      {open ? (
        <div className="balance-sheet" role="dialog" aria-modal="true" onClick={() => setOpen(false)}>
          <div className="balance-sheet__panel" onClick={(e) => e.stopPropagation()}>
            <p className="balance-sheet__eyebrow">{t(language, "boostPayEyebrow")}</p>
            <h2 className="balance-sheet__title">
              <span className="boost-sheet__mark" aria-hidden>
                ↑
              </span>{" "}
              {t(language, "boostTitle")}
            </h2>
            <p className="boost-sheet__note">{t(language, "boostPayNote")}</p>

            {!starsOnly ? (
              <button
                type="button"
                className={`balance-sheet__option${method === "rub" ? " is-active" : ""}`}
                onClick={() => setMethod("rub")}
              >
                <span>
                  <strong>
                    <span aria-hidden>🇷🇺 </span>
                    {rub.toLocaleString("ru-RU")} ₽
                  </strong>
                  <span className="balance-sheet__hint">{t(language, "balanceMethodRubHint")}</span>
                </span>
                <span className="balance-sheet__radio" aria-hidden />
              </button>
            ) : null}

            <button
              type="button"
              className={`balance-sheet__option${method === "stars" ? " is-active" : ""}`}
              onClick={() => setMethod("stars")}
            >
              <span>
                <strong>{stars} ★</strong>
                <span className="balance-sheet__hint">{t(language, "balanceMethodStarsHint")}</span>
              </span>
              <span className="balance-sheet__radio" aria-hidden />
            </button>

            {info ? <p className="home-meta">{info}</p> : null}
            {error ? <p className="form-error">{error}</p> : null}

            <button
              type="button"
              className="btn btn--block btn--dark"
              disabled={busy}
              onClick={() => void onPay()}
            >
              {method === "stars"
                ? tf(language, "balancePayStars", { n: stars })
                : tf(language, "balancePayRub", { n: rub })}
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}
