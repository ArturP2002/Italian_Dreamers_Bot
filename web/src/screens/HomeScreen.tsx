import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { homeAssets } from "../assets/backgrounds";
import { AddToHomeCard } from "../components/AddToHomeCard";
import { BoostTopCta } from "../components/BoostTopCta";
import { LanguageToggle } from "../components/LanguageToggle";
import { greetingKey, type Language, t, tf } from "../i18n/messages";
import {
  fetchCatalogStats,
  fetchConfig,
  fetchInbox,
  fetchLikes,
  registerTravelInterest,
  requestPublishInvoice,
  type MeUser,
  type PublicConfig,
} from "../lib/api";
import { openStarsInvoice } from "../lib/telegramPay";

function formatMembers(n: number, language: Language): string {
  try {
    return n.toLocaleString(language === "it" ? "it-IT" : "ru-RU");
  } catch {
    return String(n);
  }
}

type Props = {
  language: Language;
  me: MeUser | null;
  onLanguageChange: (language: Language) => void;
};

const FUNNEL_STEPS = [
  "homeStepProfile",
  "homeStepReview",
  "homeStepPay",
  "homeStepApp",
  "homeStepChannel",
] as const;

/** currentStep: 0–4 active ring; 5 = all gold checks (published in channel). */
function funnelCurrent(status: string | null): number {
  switch (status) {
    case "new":
    case "rejected":
      return 1;
    case "approved":
    case "awaiting_payment":
      return 2;
    case "queued":
      return 4;
    case "published":
      return 5;
    case "draft":
    case "hidden":
    default:
      return 0;
  }
}

function formatChannelDate(iso: string | null | undefined, language: Language): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(language === "it" ? "it-IT" : "ru-RU", {
    day: "numeric",
    month: "long",
  });
}

export function HomeScreen({ language, me, onLanguageChange }: Props) {
  const name = me?.first_name ?? "";
  const status = me?.profile_status ?? null;
  const hasProfile = Boolean(status && status !== "draft");
  const isDraft = !status || status === "draft";
  const isRejected = status === "rejected";
  const awaitingPay = status === "awaiting_payment" || status === "approved";
  const isQueued = status === "queued";
  const isPublished = status === "published";
  const needsProfile = isDraft || !hasProfile;
  const greeting = `${t(language, greetingKey())}${name ? `, ${name}` : ""}`;
  const currentStep = funnelCurrent(status);
  const [payBusy, setPayBusy] = useState(false);
  const [payMsg, setPayMsg] = useState<string | null>(null);
  const [pendingLetters, setPendingLetters] = useState(0);
  const [likesReceived, setLikesReceived] = useState(0);
  const [newToday, setNewToday] = useState(0);
  const [channelUrl, setChannelUrl] = useState("https://t.me/italiandreamers");
  const [channelMembers, setChannelMembers] = useState<number | null>(null);
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [travelOpen, setTravelOpen] = useState(false);
  const [travelBusy, setTravelBusy] = useState(false);
  const [travelDone, setTravelDone] = useState(Boolean(me?.travel_interest));

  useEffect(() => {
    void fetchInbox().then((data) => {
      setPendingLetters(data?.pending_incoming ?? 0);
    });
    void fetchCatalogStats().then((stats) => {
      setNewToday(stats?.new_today_count ?? 0);
    });
    if (me?.is_registered === false) {
      setLikesReceived(0);
      return;
    }
    void fetchLikes("received").then((data) => {
      setLikesReceived(data.items?.length ?? 0);
    });
  }, [me?.id, me?.is_registered]);

  useEffect(() => {
    void fetchConfig().then((cfg) => {
      setConfig(cfg);
      const url = cfg?.channel_url?.trim();
      if (url) setChannelUrl(url);
      if (cfg?.channel_members && cfg.channel_members > 0) {
        setChannelMembers(cfg.channel_members);
      }
    });
  }, []);

  useEffect(() => {
    setTravelDone(Boolean(me?.travel_interest));
  }, [me?.travel_interest]);

  const onTravelNotify = async () => {
    setTravelBusy(true);
    try {
      await registerTravelInterest();
      setTravelDone(true);
    } catch {
      /* keep sheet open */
    } finally {
      setTravelBusy(false);
    }
  };

  const onPay = async () => {
    setPayBusy(true);
    setPayMsg(null);
    try {
      const res = await requestPublishInvoice();
      if (!res?.ok) {
        setPayMsg(t(language, "errorGeneric"));
        return;
      }
      if (res.queued) {
        setPayMsg(t(language, "homePaySent"));
        return;
      }
      if (!res.invoice_url) {
        setPayMsg(t(language, "errorGeneric"));
        return;
      }
      const status = await openStarsInvoice(res.invoice_url);
      if (status === "paid") {
        setPayMsg(t(language, "paymentPaid"));
      } else if (status === "cancelled") {
        setPayMsg(t(language, "paymentCancelled"));
      } else if (status === "pending") {
        setPayMsg(t(language, "homePaySent"));
      } else {
        setPayMsg(t(language, "errorGeneric"));
      }
    } catch {
      setPayMsg(t(language, "errorGeneric"));
    } finally {
      setPayBusy(false);
    }
  };

  const showVerify =
    hasProfile && status !== "draft" && me?.verification_status !== "verified";
  const stars = config?.prices.profile_publish_stars;
  const rub = config?.prices.profile_publish_rub;
  const channelDate = formatChannelDate(me?.profile_scheduled_at, language);

  let funnelTitle = t(language, "homeFillProfile");
  let funnelHint: string | null = t(language, "homeFillProfileHint");
  if (isRejected) {
    funnelTitle = t(language, "homeFunnelFix");
    funnelHint = null;
  } else if (status === "new") {
    funnelTitle = t(language, "homeFunnelReview");
    funnelHint = null;
  } else if (awaitingPay) {
    funnelTitle = t(language, "homeFunnelApproved");
    funnelHint = null;
  } else if (isQueued) {
    funnelTitle = t(language, "homeFunnelInApp");
    funnelHint = channelDate
      ? tf(language, "homeFunnelChannelApprox", { date: channelDate })
      : t(language, "homeQueuedHint");
  } else if (isPublished) {
    funnelTitle = t(language, "homeFunnelDoneTitle");
    funnelHint = t(language, "homeFunnelDoneHint");
  } else if (status === "hidden") {
    funnelTitle = t(language, "homeStatusHidden");
    funnelHint = null;
  }

  return (
    <section className="screen screen--milky home-screen">
      <LanguageToggle language={language} onChange={onLanguageChange} />

      <header className="home-header">
        <div className="home-brand">
          <span>{t(language, "homeBrand")}</span>
        </div>
        <div className="home-avatar" aria-hidden>
          {(name || "?").slice(0, 1).toUpperCase()}
        </div>
      </header>

      <h1 className="home-greeting">{greeting}</h1>

      <article className={`home-funnel${isPublished ? " home-funnel--published" : ""}`}>
        <p className="home-funnel__eyebrow">{t(language, "homeYourProfile")}</p>
        {!isPublished ? (
          <>
            <h2 className="home-funnel__title">{funnelTitle}</h2>
            {funnelHint ? <p className="home-funnel__hint">{funnelHint}</p> : null}
          </>
        ) : null}

        <ol className="home-stepper" aria-label={t(language, "homeYourProfile")}>
          {FUNNEL_STEPS.map((key, index) => {
            const done = index < currentStep;
            const current = index === currentStep && currentStep < 5;
            return (
              <li
                key={key}
                className={`home-stepper__item${done ? " is-done" : ""}${current ? " is-current" : ""}`}
              >
                <span className="home-stepper__dot" aria-hidden>
                  {done ? "✓" : current ? <span className="home-stepper__pip" /> : null}
                </span>
                <span className="home-stepper__label">{t(language, key)}</span>
              </li>
            );
          })}
        </ol>

        {needsProfile ? (
          <Link to="/profile" className="btn btn--block btn--dark home-funnel__cta">
            {t(language, "homeFillCta")}
          </Link>
        ) : null}

        {isRejected ? (
          <Link to="/profile" className="btn btn--block btn--dark home-funnel__cta">
            {t(language, "homeFunnelFixCta")}
          </Link>
        ) : null}

        {awaitingPay ? (
          <button
            type="button"
            className="btn btn--block btn--dark home-funnel__cta"
            disabled={payBusy || stars == null}
            onClick={() => void onPay()}
          >
            {stars == null
              ? "…"
              : rub && rub > 0
                ? tf(language, "homeFunnelPayCtaRub", {
                    rub: rub.toLocaleString("ru-RU"),
                    stars,
                  })
                : tf(language, "homeFunnelPayCta", { stars })}
          </button>
        ) : null}

        {isQueued || isPublished ? (
          <BoostTopCta
            language={language}
            verified={me?.verification_status === "verified"}
            isTop={Boolean(me?.is_top)}
            topUntil={me?.top_until}
            starsOnly={language === "it"}
            className="home-funnel__boost"
          />
        ) : null}

        {payMsg ? <p className="home-funnel__hint">{payMsg}</p> : null}
      </article>

      <AddToHomeCard language={language} />

      <div className="home-mosaic">
        <Link to="/catalog" className="home-card home-card--wide">
          <img className="home-card__bg" src={homeAssets.catalog} alt="" />
          <div className="home-card__veil" />
          {newToday > 0 ? (
            <span className="home-count-badge">
              {tf(language, "homeBadgeNewToday", { n: newToday })}
            </span>
          ) : null}
          <div className="home-card__body">
            <h3 className="home-card__title">
              {t(language, "homeMembersLead")} <em>Dreamers</em>
            </h3>
            <p className="home-card__hint">{t(language, "homeMembersHint")}</p>
          </div>
        </Link>

        <Link to="/inbox" className="home-card">
          <img className="home-card__bg" src={homeAssets.messages} alt="" />
          <div className="home-card__veil" />
          {pendingLetters > 0 ? (
            <span className="home-count-badge">{tf(language, "homeBadgeNew", { n: pendingLetters })}</span>
          ) : null}
          <div className="home-card__body">
            <h3 className="home-card__title">{t(language, "homeLettersTitle")}</h3>
            <p className="home-card__hint">{t(language, "homeLettersHint")}</p>
          </div>
        </Link>

        <Link to={me?.is_registered === false ? "/profile" : "/likes"} className="home-card">
          <img className="home-card__bg" src={homeAssets.likes} alt="" />
          <div className="home-card__veil" />
          {likesReceived > 0 && me?.is_registered !== false ? (
            <span className="home-count-badge">{tf(language, "homeBadgeNew", { n: likesReceived })}</span>
          ) : null}
          <div className="home-card__body">
            <h3 className="home-card__title">
              <span className="home-card__heart" aria-hidden>
                🤍
              </span>{" "}
              {t(language, "homeLikes")}
            </h3>
            <p className="home-card__hint">{t(language, "homeLikesHint")}</p>
          </div>
        </Link>

        <Link to="/profile" className="home-card">
          <img className="home-card__bg" src={homeAssets.profile} alt="" />
          <div className="home-card__veil" />
          <div className="home-card__body">
            <h3 className="home-card__title">
              {isRejected ? t(language, "homeFixProfile") : t(language, "homeMyProfile")}
            </h3>
            <p className="home-card__hint">{t(language, "homeProfileHint")}</p>
          </div>
        </Link>

        <Link to="/credits" className="home-card">
          <img className="home-card__bg" src={homeAssets.credits} alt="" />
          <div className="home-card__veil" />
          <div className="home-card__body">
            <h3 className="home-card__title">{t(language, "homeSubTitle")}</h3>
            <p className="home-card__hint">
              {me?.has_unlimited
                ? tf(language, "homeSubActiveHint", {
                    date: me.unlimited_until
                      ? new Date(me.unlimited_until).toLocaleDateString(
                          language === "it" ? "it-IT" : "ru-RU",
                          { day: "numeric", month: "short" },
                        )
                      : "—",
                  })
                : (me?.unread_locked_count ?? 0) > 0
                  ? tf(language, "homeSubLockedHint", { n: me?.unread_locked_count ?? 0 })
                  : t(language, "homeSubNoneHint")}
            </p>
          </div>
        </Link>
      </div>

      {showVerify ? (
        <Link to="/verify" className="home-row-link">
          <span className="home-row-link__icon" aria-hidden>
            ✓
          </span>
          <span className="home-row-link__text">
            <strong>{t(language, "homeVerify")}</strong>
            <span>{t(language, "homeVerifyHint")}</span>
          </span>
          <span className="home-row-link__chevron" aria-hidden>
            ›
          </span>
        </Link>
      ) : null}

      <div className="home-duo">
        <a className="home-channel-card" href={channelUrl} target="_blank" rel="noreferrer">
          <span className="home-channel-card__tg" aria-hidden>
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
              <path d="M9.8 15.5 9.6 19c.3 0 .5-.1.7-.3l1.7-1.6 3.5 2.6c.6.3 1.1.2 1.3-.6l2.3-10.9c.2-.9-.3-1.3-.9-1.1L4.2 11.2c-.9.3-.9.8-.2 1l3.5 1.1 8.1-5.1c.4-.2.7 0 .4.3l-6.2 7z" />
            </svg>
          </span>
          <span className="home-channel-card__count">
            {channelMembers != null ? formatMembers(channelMembers, language) : "…"}
          </span>
          <span className="home-channel-card__heart" aria-hidden>
            <img src={homeAssets.channelHeart} alt="" />
          </span>
          <div className="home-channel-card__copy">
            <h3 className="home-channel-card__title">{t(language, "homeChannelTitle")}</h3>
            <p className="home-channel-card__hint">{t(language, "homeChannelHint")}</p>
          </div>
        </a>

        <button type="button" className="home-travel-card" onClick={() => setTravelOpen(true)}>
          <img className="home-travel-card__bg" src={homeAssets.travel} alt="" />
          <span className="home-travel-card__veil" />
          <span className="home-travel-card__badge">{t(language, "homeTravelSoon")}</span>
          <span className="home-travel-card__body">
            <strong>{t(language, "homeTravelTitle")}</strong>
            <span>{t(language, "homeTravelHint")}</span>
          </span>
        </button>
      </div>

      <Link to="/referral" className="home-referral">
        <img className="home-referral__bg" src={homeAssets.referral} alt="" />
        <div className="home-referral__veil" />
        <div className="home-referral__body">
          <div className="home-referral__footer">
            <div className="home-referral__copy">
              <h3 className="home-referral__title">{t(language, "homeReferral")}</h3>
              <p className="home-referral__hint">{t(language, "homeReferralHint")}</p>
            </div>
            <span className="home-referral__cta">{t(language, "homeReferralCta")}</span>
          </div>
        </div>
      </Link>

      {travelOpen ? (
        <div className="balance-sheet" role="dialog" aria-modal="true" onClick={() => setTravelOpen(false)}>
          <div className="balance-sheet__panel" onClick={(e) => e.stopPropagation()}>
            <p className="balance-sheet__eyebrow">{t(language, "homeTravelTitle")}</p>
            <h2 className="balance-sheet__title">
              {travelDone ? t(language, "homeTravelModalThanks") : t(language, "homeTravelModalTitle")}
            </h2>
            {!travelDone ? (
              <button
                type="button"
                className="btn btn--block btn--dark"
                disabled={travelBusy}
                onClick={() => void onTravelNotify()}
              >
                {t(language, "homeTravelModalCta")}
              </button>
            ) : (
              <button type="button" className="btn btn--block btn--dark" onClick={() => setTravelOpen(false)}>
                OK
              </button>
            )}
          </div>
        </div>
      ) : null}

      <Link to="/ads" className="home-row-link">
        <span className="home-row-link__icon home-row-link__icon--mail" aria-hidden>
          ✉
        </span>
        <span className="home-row-link__text">
          <strong>{t(language, "homeAds")}</strong>
          <span>{t(language, "homeAdsHint")}</span>
        </span>
        <span className="home-row-link__chevron" aria-hidden>
          ›
        </span>
      </Link>

      {me?.has_unlimited && me.unlimited_until ? (
        <p className="home-meta">
          {tf(language, "unlimitedActive", {
            date: new Date(me.unlimited_until).toLocaleDateString(),
          })}
        </p>
      ) : null}

      {me?.is_soft_banned ? (
        <p className="home-meta">
          <Link className="home-link" to="/support">
            {t(language, "supportTitle")}
          </Link>
        </p>
      ) : null}
    </section>
  );
}
