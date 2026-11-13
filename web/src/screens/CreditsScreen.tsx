import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { homeAssets } from "../assets/backgrounds";
import { type Language, t, tf } from "../i18n/messages";
import {
  buyUnlimited,
  cancelUnlimited,
  fetchConfig,
  fetchMe,
  type MeUser,
  type PublicConfig,
} from "../lib/api";

type Props = { language: Language; onCreditsChange?: () => void };

type PayMethod = "rub" | "stars";

function formatDate(iso: string | null | undefined, language: Language): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(language === "it" ? "it-IT" : "ru-RU", {
      day: "numeric",
      month: "long",
    });
  } catch {
    return "—";
  }
}

export function CreditsScreen({ language, onCreditsChange }: Props) {
  const starsOnly = language === "it";
  const [me, setMe] = useState<MeUser | null>(null);
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [method, setMethod] = useState<PayMethod>(starsOnly ? "stars" : "rub");

  const reload = async () => {
    const user = await fetchMe();
    setMe(user);
  };

  useEffect(() => {
    void reload();
    void fetchConfig().then(setConfig);
  }, []);

  const plusStars = config?.prices.unlimited_sub_stars ?? 1000;
  const plusRub = config?.prices.unlimited_sub_rub ?? 2000;
  const hasPlus = Boolean(me?.has_unlimited);
  const canceled = Boolean(me?.subscription_canceled);
  const plusUntil = formatDate(me?.unlimited_until, language);
  const locked = me?.unread_locked_count ?? 0;

  const state: "active" | "expired" | "none" = hasPlus
    ? "active"
    : me?.unlimited_until
      ? "expired"
      : "none";

  const onBuy = async () => {
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      if (method === "rub") {
        setInfo(t(language, "balanceRubSoon"));
        return;
      }
      const res = await buyUnlimited();
      setInfo(
        res.already
          ? tf(language, "unlimitedActive", { date: plusUntil })
          : t(language, "invoiceSent"),
      );
      onCreditsChange?.();
      await reload();
      setSheetOpen(false);
    } catch {
      setError(t(language, "errorGeneric"));
    } finally {
      setBusy(false);
    }
  };

  const onCancel = async () => {
    setBusy(true);
    setError(null);
    try {
      await cancelUnlimited();
      setInfo(t(language, "subCancelOk"));
      onCreditsChange?.();
      await reload();
    } catch {
      setError(t(language, "errorGeneric"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="screen screen--milky balance-screen">
      <Link to="/" className="work-back work-back--sticky">
        ← {t(language, "backHome")}
      </Link>

      <article className="balance-hero">
        <img className="balance-hero__bg" src={homeAssets.credits} alt="" />
        <div className="balance-hero__veil" />
        <div className="balance-hero__body">
          <p className="balance-hero__eyebrow">{t(language, "subEyebrow")}</p>
          {state === "active" ? (
            <>
              <h1 className="balance-hero__title">
                Dreamers <span aria-hidden>✨</span> Plus
              </h1>
              <p className="balance-hero__sub">
                {canceled
                  ? tf(language, "subActiveCanceled", { date: plusUntil })
                  : tf(language, "balancePlusUntil", { date: plusUntil })}
              </p>
            </>
          ) : state === "expired" ? (
            <>
              <h1 className="balance-hero__title">{t(language, "subExpiredTitle")}</h1>
              <p className="balance-hero__sub">{t(language, "subExpiredHint")}</p>
            </>
          ) : (
            <>
              <h1 className="balance-hero__title">{t(language, "subNoneTitle")}</h1>
              <p className="balance-hero__sub">{t(language, "subNoneHint")}</p>
            </>
          )}
        </div>
      </article>

      {locked > 0 && !hasPlus ? (
        <p className="home-meta">{tf(language, "subLockedIncoming", { n: locked })}</p>
      ) : null}

      <ul className="balance-rules">
        <li>
          <strong>{t(language, "subRule1Title")}</strong> {t(language, "subRule1Body")}
        </li>
        <li>
          <strong>{t(language, "subRule2Title")}</strong> {t(language, "subRule2Body")}
        </li>
        <li>
          <strong>{t(language, "subRule3Title")}</strong> {t(language, "subRule3Body")}
        </li>
      </ul>

      <article className="balance-pack balance-pack--plus">
        <span className="balance-pack__badge">{t(language, "balancePlusBadge")}</span>
        <p className="balance-pack__qty balance-pack__qty--plus">
          <strong>
            Dreamers<span aria-hidden>✨</span>
          </strong>
          <span>{t(language, "balancePlusLabel")}</span>
        </p>
        {hasPlus && !canceled ? (
          <p className="balance-pack__connected">
            {tf(language, "balancePlusConnected", { date: plusUntil })}
          </p>
        ) : (
          <div className="balance-pack__btns">
            {starsOnly ? (
              <button
                type="button"
                className="balance-price"
                disabled={busy}
                onClick={() => {
                  setMethod("stars");
                  setSheetOpen(true);
                }}
              >
                {plusStars} ★
              </button>
            ) : (
              <>
                <button
                  type="button"
                  className="balance-price"
                  disabled={busy}
                  onClick={() => {
                    setMethod("rub");
                    setSheetOpen(true);
                  }}
                >
                  <span aria-hidden>🇷🇺</span> {plusRub} ₽
                </button>
                <button
                  type="button"
                  className="balance-price"
                  disabled={busy}
                  onClick={() => {
                    setMethod("stars");
                    setSheetOpen(true);
                  }}
                >
                  <span aria-hidden>★</span> {plusStars} ★
                </button>
              </>
            )}
          </div>
        )}
      </article>

      <p className="balance-footnote">
        <strong>Dreamers Plus</strong> — {t(language, "balancePlusFootnote")}
      </p>

      {hasPlus && !canceled ? (
        <button
          type="button"
          className="btn btn--block btn--ghost"
          disabled={busy}
          onClick={() => void onCancel()}
        >
          {t(language, "subCancel")}
        </button>
      ) : null}

      {info ? <p className="home-meta">{info}</p> : null}
      {error ? <p className="form-error">{error}</p> : null}

      {sheetOpen ? (
        <div className="balance-sheet" role="dialog" aria-modal="true" onClick={() => setSheetOpen(false)}>
          <div className="balance-sheet__panel" onClick={(e) => e.stopPropagation()}>
            <p className="balance-sheet__eyebrow">{t(language, "balancePayEyebrow")}</p>
            <h2 className="balance-sheet__title">{t(language, "balancePlusTitle")}</h2>

            {!starsOnly ? (
              <button
                type="button"
                className={`balance-sheet__option${method === "rub" ? " is-active" : ""}`}
                onClick={() => setMethod("rub")}
              >
                <span>
                  <strong>
                    <span aria-hidden>🇷🇺 </span>
                    {plusRub} ₽
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
                <strong>{plusStars} ★</strong>
                <span className="balance-sheet__hint">{t(language, "balanceMethodStarsHint")}</span>
              </span>
              <span className="balance-sheet__radio" aria-hidden />
            </button>

            <button
              type="button"
              className="btn btn--block btn--dark"
              disabled={busy}
              onClick={() => void onBuy()}
            >
              {method === "stars"
                ? tf(language, "balancePayStars", { n: plusStars })
                : tf(language, "balancePayRub", { n: plusRub })}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
