import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { homeAssets } from "../assets/backgrounds";
import { type Language, t, tf } from "../i18n/messages";
import {
  buyMessageCredits,
  buyUnlimited,
  fetchConfig,
  fetchMe,
  type MeUser,
  type PublicConfig,
} from "../lib/api";

type Props = { language: Language; onCreditsChange?: () => void };

type PayProduct = "one" | "pack" | "unlimited";
type PayMethod = "rub" | "stars";

function creditsWord(n: number, language: Language): string {
  if (language === "it") {
    return n === 1 ? "conoscenza" : "conoscenze";
  }
  const abs = Math.abs(n) % 100;
  const last = abs % 10;
  if (abs > 10 && abs < 20) return "знакомств";
  if (last === 1) return "знакомство";
  if (last >= 2 && last <= 4) return "знакомства";
  return "знакомств";
}

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
  const [credits, setCredits] = useState(0);
  const [me, setMe] = useState<MeUser | null>(null);
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sheet, setSheet] = useState<{ product: PayProduct; method: PayMethod } | null>(null);

  const reload = async () => {
    const user = await fetchMe();
    setMe(user);
    setCredits(user?.message_credits ?? 0);
  };

  useEffect(() => {
    void reload();
    void fetchConfig().then(setConfig);
  }, []);

  const prices = {
    oneStars: config?.prices.message_credit_stars ?? 100,
    oneRub: config?.prices.message_credit_rub ?? 200,
    packStars: config?.prices.message_pack_10_stars ?? 500,
    packRub: config?.prices.message_pack_10_rub ?? 1000,
    packSize: config?.prices.message_pack_size ?? 10,
    plusStars: config?.prices.unlimited_sub_stars ?? 1000,
    plusRub: config?.prices.unlimited_sub_rub ?? 2000,
  };

  const hasPlus = Boolean(me?.has_unlimited);
  const plusUntil = formatDate(me?.unlimited_until, language);

  const openSheet = (product: PayProduct, method: PayMethod = starsOnly ? "stars" : "rub") => {
    setError(null);
    setInfo(null);
    setSheet({ product, method: starsOnly ? "stars" : method });
  };

  const sheetTitle =
    sheet?.product === "pack"
      ? tf(language, "balancePackTitle", { n: prices.packSize })
      : sheet?.product === "unlimited"
        ? t(language, "balancePlusTitle")
        : t(language, "balanceOneTitle");

  const sheetRub =
    sheet?.product === "pack"
      ? prices.packRub
      : sheet?.product === "unlimited"
        ? prices.plusRub
        : prices.oneRub;
  const sheetStars =
    sheet?.product === "pack"
      ? prices.packStars
      : sheet?.product === "unlimited"
        ? prices.plusStars
        : prices.oneStars;

  const payLabel =
    sheet?.method === "stars"
      ? tf(language, "balancePayStars", { n: sheetStars })
      : tf(language, "balancePayRub", { n: sheetRub });

  const onConfirmPay = async () => {
    if (!sheet) return;
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      if (sheet.method === "rub") {
        setInfo(t(language, "balanceRubSoon"));
        return;
      }
      if (sheet.product === "unlimited") {
        const res = await buyUnlimited();
        setInfo(
          res.already
            ? tf(language, "unlimitedActive", { date: plusUntil })
            : t(language, "invoiceSent"),
        );
      } else {
        await buyMessageCredits({ pack: sheet.product === "pack" });
        setInfo(t(language, "invoiceSent"));
      }
      onCreditsChange?.();
      await reload();
      setSheet(null);
    } catch {
      setError(t(language, "errorGeneric"));
    } finally {
      setBusy(false);
    }
  };

  const priceButtons = (product: PayProduct, rub: number, stars: number) =>
    starsOnly ? (
      <div className="balance-pack__btns">
        <button type="button" className="balance-price" disabled={busy} onClick={() => openSheet(product, "stars")}>
          {stars} ★
        </button>
      </div>
    ) : (
      <div className="balance-pack__btns">
        <button type="button" className="balance-price" disabled={busy} onClick={() => openSheet(product, "rub")}>
          <span aria-hidden>🇷🇺</span> {rub} ₽
        </button>
        <button type="button" className="balance-price" disabled={busy} onClick={() => openSheet(product, "stars")}>
          <span aria-hidden>★</span> {stars} ★
        </button>
      </div>
    );

  return (
    <section className="screen screen--milky balance-screen">
      <Link to="/" className="work-back">
        ← {t(language, "backHome")}
      </Link>

      <article className="balance-hero">
        <img className="balance-hero__bg" src={homeAssets.credits} alt="" />
        <div className="balance-hero__veil" />
        <div className="balance-hero__body">
          <p className="balance-hero__eyebrow">{t(language, "balanceEyebrow")}</p>
          {hasPlus ? (
            <>
              <h1 className="balance-hero__title">
                Dreamers <span aria-hidden>✨</span> Plus
              </h1>
              <p className="balance-hero__sub">
                {tf(language, "balancePlusUntil", { date: plusUntil })}
              </p>
            </>
          ) : credits > 0 ? (
            <>
              <h1 className="balance-hero__title">
                {credits} {creditsWord(credits, language)}
              </h1>
              <p className="balance-hero__sub">{t(language, "balanceNoExpire")}</p>
            </>
          ) : (
            <>
              <h1 className="balance-hero__title">{t(language, "balanceEmptyTitle")}</h1>
              <p className="balance-hero__sub">{t(language, "balanceEmptyHint")}</p>
            </>
          )}
        </div>
      </article>

      <ul className="balance-rules">
        <li>
          <strong>{t(language, "balanceRule1Title")}</strong> {t(language, "balanceRule1Body")}
        </li>
        <li>
          <strong>{t(language, "balanceRule2Title")}</strong> {t(language, "balanceRule2Body")}
        </li>
        <li>
          <strong>{t(language, "balanceRule3Title")}</strong> {t(language, "balanceRule3Body")}
        </li>
      </ul>

      <h2 className="balance-section-label">{t(language, "balanceTopUp")}</h2>

      <div className="balance-packs">
        <article className="balance-pack">
          <p className="balance-pack__qty">
            <strong>1</strong>
            <span>{t(language, "balanceOneLabel")}</span>
          </p>
          {priceButtons("one", prices.oneRub, prices.oneStars)}
        </article>

        <article className="balance-pack balance-pack--dark">
          <span className="balance-pack__badge balance-pack__badge--sale">{t(language, "balanceSale")}</span>
          <p className="balance-pack__qty">
            <strong>{prices.packSize}</strong>
            <span>{t(language, "balancePackLabel")}</span>
          </p>
          {priceButtons("pack", prices.packRub, prices.packStars)}
        </article>

        <article className="balance-pack balance-pack--plus">
          <span className="balance-pack__badge">{t(language, "balancePlusBadge")}</span>
          <p className="balance-pack__qty balance-pack__qty--plus">
            <strong>
              Dreamers<span aria-hidden>✨</span>
            </strong>
            <span>{t(language, "balancePlusLabel")}</span>
          </p>
          {hasPlus ? (
            <p className="balance-pack__connected">
              {tf(language, "balancePlusConnected", { date: plusUntil })}
            </p>
          ) : (
            priceButtons("unlimited", prices.plusRub, prices.plusStars)
          )}
        </article>
      </div>

      <p className="balance-footnote">
        <strong>Dreamers Plus</strong> — {t(language, "balancePlusFootnote")}
      </p>
      <ul className="balance-pay-legend">
        {starsOnly ? (
          <li>
            <span aria-hidden>★</span> {t(language, "balancePayLegendStars")}
          </li>
        ) : (
          <>
            <li>
              <span aria-hidden>🇷🇺</span> {t(language, "balancePayLegendRub")}
            </li>
            <li>
              <span aria-hidden>★</span> {t(language, "balancePayLegendStars")}
            </li>
          </>
        )}
      </ul>

      {info ? <p className="home-meta">{info}</p> : null}
      {error ? <p className="form-error">{error}</p> : null}

      {sheet ? (
        <div className="balance-sheet" role="dialog" aria-modal="true" onClick={() => setSheet(null)}>
          <div className="balance-sheet__panel" onClick={(e) => e.stopPropagation()}>
            <p className="balance-sheet__eyebrow">{t(language, "balancePayEyebrow")}</p>
            <h2 className="balance-sheet__title">{sheetTitle}</h2>

            {!starsOnly ? (
              <button
                type="button"
                className={`balance-sheet__option${sheet.method === "rub" ? " is-active" : ""}`}
                onClick={() => setSheet({ ...sheet, method: "rub" })}
              >
                <span>
                  <strong>
                    <span aria-hidden>🇷🇺 </span>
                    {sheetRub} ₽
                  </strong>
                  <span className="balance-sheet__hint">{t(language, "balanceMethodRubHint")}</span>
                </span>
                <span className="balance-sheet__radio" aria-hidden />
              </button>
            ) : null}

            <button
              type="button"
              className={`balance-sheet__option${sheet.method === "stars" ? " is-active" : ""}`}
              onClick={() => setSheet({ ...sheet, method: "stars" })}
            >
              <span>
                <strong>{sheetStars} ★</strong>
                <span className="balance-sheet__hint">{t(language, "balanceMethodStarsHint")}</span>
              </span>
              <span className="balance-sheet__radio" aria-hidden />
            </button>

            {starsOnly ? <p className="balance-sheet__note">{t(language, "balancePayTgHint")}</p> : null}

            <button
              type="button"
              className="btn btn--block btn--dark"
              disabled={busy}
              onClick={() => void onConfirmPay()}
            >
              {payLabel}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
