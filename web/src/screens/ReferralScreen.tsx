import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { type Language, t, tf } from "../i18n/messages";
import { fetchReferral, type ReferralInfo } from "../lib/api";

type Props = { language: Language };

export function ReferralScreen({ language }: Props) {
  const [info, setInfo] = useState<ReferralInfo | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    void fetchReferral().then(setInfo);
  }, []);

  const onCopy = async () => {
    if (!info?.link) return;
    try {
      await navigator.clipboard.writeText(info.link);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  const onShare = () => {
    if (!info?.link) return;
    const url = `https://t.me/share/url?url=${encodeURIComponent(info.link)}&text=${encodeURIComponent(
      t(language, "referralShareText"),
    )}`;
    const tg = window.Telegram?.WebApp;
    if (tg?.openTelegramLink) tg.openTelegramLink(url);
    else window.open(url, "_blank", "noopener");
  };

  const invited = info?.invited_count ?? 0;
  const perFriend = info?.bonus_top_days ?? 3;
  const topDays = info?.top_days_earned ?? invited * perFriend;

  return (
    <section className="screen screen--milky">
      <Link to="/" className="work-back">
        ← {t(language, "backHome")}
      </Link>
      <h1 className="work-title">{t(language, "referralTitle")}</h1>
      <p className="work-body">{t(language, "referralBody")}</p>

      {info ? (
        <div className="referral-box">
          <div className="referral-reward">
            <strong>{t(language, "referralRewardTitle")}</strong>
            <span>{t(language, "referralRewardHint")}</span>
          </div>

          <div className="referral-stats">
            <div className="referral-stat">
              <span>{t(language, "referralInvited")}</span>
              <strong>{invited}</strong>
            </div>
            <div className="referral-stat">
              <span>{t(language, "referralTopDays")}</span>
              <strong>{topDays}</strong>
            </div>
          </div>

          {info.bonus_credits > 0 ? (
            <p className="referral-box__bonus">{tf(language, "referralBonus", { n: info.bonus_credits })}</p>
          ) : null}

          <code className="referral-box__link">{info.link}</code>
          <button type="button" className="btn btn--block btn--dark" onClick={onShare}>
            {t(language, "referralShare")}
          </button>
          <button
            type="button"
            className="btn btn--block btn--ghost referral-box__copy"
            onClick={() => void onCopy()}
          >
            {copied ? t(language, "referralCopied") : t(language, "referralCopy")}
          </button>
        </div>
      ) : (
        <p className="home-meta">{t(language, "saving")}</p>
      )}
    </section>
  );
}
