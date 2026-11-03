import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { homeAssets } from "../assets/backgrounds";
import { TricolorHeart } from "../components/TricolorHeart";
import { LanguageToggle } from "../components/LanguageToggle";
import { greetingKey, type Language, t, tf } from "../i18n/messages";
import {
  fetchConfig,
  fetchInbox,
  fetchLikes,
  requestPublishInvoice,
  type MeUser,
  type PublicConfig,
} from "../lib/api";

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
  const [channelUrl, setChannelUrl] = useState("https://t.me/italiandreamers");
  const [config, setConfig] = useState<PublicConfig | null>(null);

  useEffect(() => {
    void fetchInbox().then((data) => {
      setPendingLetters(data?.pending_incoming ?? 0);
    });
    void fetchLikes("received").then((data) => {
      setLikesReceived(data.items?.length ?? 0);
    });
  }, [me?.id]);

  useEffect(() => {
    void fetchConfig().then((cfg) => {
      setConfig(cfg);
      const url = cfg?.channel_url?.trim();
      if (url) setChannelUrl(url);
    });
  }, []);

  const onPay = async () => {
    setPayBusy(true);
    setPayMsg(null);
    const res = await requestPublishInvoice();
    setPayBusy(false);
    if (res?.ok) {
      setPayMsg(t(language, "homePaySent"));
    } else {
      setPayMsg(t(language, "errorGeneric"));
    }
  };

  const credits = me?.message_credits ?? 0;
  const showVerify =
    hasProfile && status !== "draft" && me?.verification_status !== "verified";
  const stars = config?.prices.profile_publish_stars ?? 1000;
  const rub = config?.prices.profile_publish_rub ?? 0;
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
          <TricolorHeart className="tricolor-heart" />
          <span>{t(language, "homeBrand")}</span>
        </div>
        <div className="home-avatar" aria-hidden>
          {(name || "?").slice(0, 1).toUpperCase()}
        </div>
      </header>

      <h1 className="home-greeting">{greeting}</h1>
      <a className="home-channel-link" href={channelUrl} target="_blank" rel="noreferrer">
        {t(language, "homeOpenChannelArrow")}
      </a>

      <article className="home-funnel">
        <p className="home-funnel__eyebrow">{t(language, "homeYourProfile")}</p>
        <h2 className="home-funnel__title">{funnelTitle}</h2>
        {funnelHint ? <p className="home-funnel__hint">{funnelHint}</p> : null}

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
            disabled={payBusy}
            onClick={() => void onPay()}
          >
            {rub > 0
              ? tf(language, "homeFunnelPayCtaRub", { rub: rub.toLocaleString("ru-RU"), stars })
              : tf(language, "homeFunnelPayCta", { stars })}
          </button>
        ) : null}
        {payMsg ? <p className="home-funnel__hint">{payMsg}</p> : null}
      </article>

      <div className="home-mosaic">
        <Link to="/catalog" className="home-card home-card--wide">
          <img className="home-card__bg" src={homeAssets.catalog} alt="" />
          <div className="home-card__veil" />
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

        <Link to="/likes" className="home-card">
          <img className="home-card__bg" src={homeAssets.likes} alt="" />
          <div className="home-card__veil" />
          {likesReceived > 0 ? (
            <span className="home-count-badge">{tf(language, "homeBadgeNew", { n: likesReceived })}</span>
          ) : null}
          <div className="home-card__body">
            <h3 className="home-card__title">
              <span aria-hidden>🤍 </span>
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
            <h3 className="home-card__title">{t(language, "homeCredits")}</h3>
            <p className="home-card__hint">{tf(language, "homeCreditsHint", { n: credits })}</p>
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

      <Link to="/referral" className="home-referral">
        <img className="home-referral__bg" src={homeAssets.referral} alt="" />
        <div className="home-referral__veil" />
        <div className="home-referral__body">
          <div>
            <h3 className="home-referral__title">{t(language, "homeReferral")}</h3>
            <p className="home-referral__hint">{t(language, "homeReferralHint")}</p>
          </div>
          <span className="home-referral__cta">{t(language, "homeReferralCta")}</span>
        </div>
      </Link>

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
