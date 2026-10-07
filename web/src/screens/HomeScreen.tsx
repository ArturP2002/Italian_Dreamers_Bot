import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { homeAssets, backgroundAssets } from "../assets/backgrounds";
import { TricolorHeart } from "../components/TricolorHeart";
import { LanguageToggle } from "../components/LanguageToggle";
import { greetingKey, type Language, t } from "../i18n/messages";
import { fetchInbox, requestPublishInvoice, type MeUser } from "../lib/api";

type Props = {
  language: Language;
  me: MeUser | null;
  onLanguageChange: (language: Language) => void;
};

function statusLabel(language: Language, status: string | null): string | null {
  if (!status) return null;
  const map: Record<string, Parameters<typeof t>[1]> = {
    draft: "homeStatusDraft",
    new: "homeStatusNew",
    approved: "homeStatusApproved",
    awaiting_payment: "homeStatusAwaitingPayment",
    queued: "homeStatusQueued",
    published: "homeStatusPublished",
    rejected: "homeStatusRejected",
    hidden: "homeStatusHidden",
  };
  const key = map[status];
  return key ? t(language, key) : status;
}

export function HomeScreen({ language, me, onLanguageChange }: Props) {
  const name = me?.first_name ?? "";
  const status = me?.profile_status ?? null;
  const hasProfile = Boolean(status && status !== "draft");
  const isDraft = !status || status === "draft";
  const isRejected = status === "rejected";
  const awaitingPay = status === "awaiting_payment";
  const isQueued = status === "queued";
  const greeting = `${t(language, greetingKey())}${name ? `, ${name}` : ""}`;
  const statusText = statusLabel(language, status);
  const [payBusy, setPayBusy] = useState(false);
  const [payMsg, setPayMsg] = useState<string | null>(null);
  const [pendingLetters, setPendingLetters] = useState(0);

  const primaryIsCreate = isDraft || isRejected || !hasProfile;

  useEffect(() => {
    void fetchInbox().then((data) => {
      setPendingLetters(data?.pending_incoming ?? 0);
    });
  }, [me?.id]);

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

  return (
    <section className="screen screen--milky">
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

      {statusText ? <div className="home-status">{statusText}</div> : null}

      {awaitingPay ? (
        <div className="home-pay-box">
          <p>{t(language, "homePayHint")}</p>
          <button
            type="button"
            className="btn btn--block btn--dark"
            disabled={payBusy}
            onClick={() => void onPay()}
          >
            {t(language, "homePayPublish")}
          </button>
          {payMsg ? <p className="home-meta">{payMsg}</p> : null}
        </div>
      ) : null}

      {isQueued ? <p className="home-meta">{t(language, "homeQueuedHint")}</p> : null}

      {primaryIsCreate ? (
        <Link to="/profile" className="home-hero-card">
          <img className="home-hero-card__bg" src={homeAssets.create} alt="" />
          <div className="home-hero-card__veil" />
          <div className="home-hero-card__body">
            <span className="home-badge">
              {isRejected ? t(language, "homeFixProfile") : t(language, "homeContinueDraft")}
            </span>
            <h2 className="home-hero-card__title">{t(language, "homeCreateTitle")}</h2>
            <p className="home-hero-card__hint">{t(language, "homeCreateHint")}</p>
          </div>
        </Link>
      ) : (
        <Link to="/inbox" className="home-hero-card">
          <img className="home-hero-card__bg" src={homeAssets.letters} alt="" />
          <div className="home-hero-card__veil" />
          <div className="home-hero-card__body">
            <span className="home-badge">
              {pendingLetters > 0
                ? `${t(language, "homeLettersBadge")} · ${pendingLetters}`
                : t(language, "homeLettersSoon")}
            </span>
            <h2 className="home-hero-card__title">{t(language, "homeLettersTitle")}</h2>
            <p className="home-hero-card__hint">{t(language, "homeLettersHint")}</p>
          </div>
        </Link>
      )}

      <div className="home-grid">
        {!primaryIsCreate ? (
          <Link to="/profile" className="home-tile">
            <img className="home-tile__bg" src={homeAssets.create} alt="" />
            <div className="home-tile__veil" />
            <span className="home-tile__label">
              {isRejected ? t(language, "homeFixProfile") : t(language, "homeMyProfile")}
            </span>
          </Link>
        ) : (
          <Link to="/inbox" className="home-tile">
            <img className="home-tile__bg" src={homeAssets.letters} alt="" />
            <div className="home-tile__veil" />
            <span className="home-tile__label">{t(language, "homeLettersTitle")}</span>
          </Link>
        )}
        <Link to="/credits" className="home-tile">
          <img className="home-tile__bg" src={backgroundAssets.bg_positano_run} alt="" />
          <div className="home-tile__veil" />
          <span className="home-tile__label">
            ★ {me?.message_credits ?? 0} · {t(language, "homeCredits")}
          </span>
        </Link>
      </div>

      <p className="home-meta">
        <Link className="home-link" to="/referral">
          {t(language, "homeReferral")}
        </Link>
        {" · "}
        <Link className="home-link" to="/ads">
          {t(language, "homeAds")}
        </Link>
      </p>

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
