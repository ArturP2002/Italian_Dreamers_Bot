import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { dreamLocationLabel, type Language, t, tf } from "../i18n/messages";
import {
  buyMessageCredits,
  fetchConfig,
  fetchMessage,
  fileComplaint,
  mediaUrl,
  rejectMessage,
  replyMessage,
  unlockMessage,
  type MessageRequestItem,
  type PublicConfig,
} from "../lib/api";

type Props = { language: Language; onCreditsChange?: () => void };

export function MessageCardScreen({ language, onCreditsChange }: Props) {
  const { id } = useParams();
  const navigate = useNavigate();
  const requestId = Number(id);
  const [item, setItem] = useState<MessageRequestItem | null>(null);
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [showOriginal, setShowOriginal] = useState(false);
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [reportOpen, setReportOpen] = useState(false);
  const [reportReason, setReportReason] = useState("");

  const reload = async () => {
    if (!Number.isFinite(requestId)) return;
    const data = await fetchMessage(requestId);
    setItem(data);
  };

  useEffect(() => {
    void reload();
    void fetchConfig().then(setConfig);
  }, [requestId]);

  if (!item) {
    return (
      <section className="screen screen--milky">
        <Link to="/inbox" className="work-back">
          ← {t(language, "back")}
        </Link>
        <p className="home-meta">{t(language, "saving")}</p>
      </section>
    );
  }

  const isIncoming = item.direction === "incoming";
  const letterText = showOriginal ? item.text : item.text_translated || item.text;
  const replyShown = showOriginal
    ? item.reply_text
    : item.reply_text_translated || item.reply_text;

  const onReject = async () => {
    setBusy(true);
    setError(null);
    try {
      await rejectMessage(item.id);
      navigate("/inbox", { replace: true });
    } catch {
      setError(t(language, "errorGeneric"));
    } finally {
      setBusy(false);
    }
  };

  const onReply = async () => {
    if (!reply.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await replyMessage(item.id, reply.trim());
      setItem(updated);
      setReply("");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "";
      if (msg.includes("contact_forbidden")) setError(t(language, "contactForbidden"));
      else setError(t(language, "errorGeneric"));
    } finally {
      setBusy(false);
    }
  };

  const onUnlock = async () => {
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const updated = await unlockMessage(item.id);
      setItem(updated);
      onCreditsChange?.();
      navigate(`/chat/${item.id}`, { replace: true });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "";
      if (msg.includes("no_credits") || msg.includes("402")) {
        setError(null);
        setInfo(t(language, "unlockHint"));
      } else {
        setError(t(language, "errorGeneric"));
      }
    } finally {
      setBusy(false);
    }
  };

  const onBuy = async (pack: boolean) => {
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      await buyMessageCredits({ pack, messageRequestId: item.id });
      setInfo(t(language, "invoiceSent"));
    } catch {
      setError(t(language, "errorGeneric"));
    } finally {
      setBusy(false);
    }
  };

  const openTg = () => {
    const link = item.counterpart_telegram_link;
    if (!link) return;
    const tg = window.Telegram?.WebApp as { openTelegramLink?: (u: string) => void } | undefined;
    if (tg?.openTelegramLink) tg.openTelegramLink(link);
    else window.open(link, "_blank");
  };

  const onReport = async () => {
    if (!reportReason.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await fileComplaint({ reason: reportReason.trim(), message_request_id: item.id });
      setInfo(t(language, "reportSent"));
      setReportOpen(false);
      setReportReason("");
    } catch {
      setError(t(language, "errorGeneric"));
    } finally {
      setBusy(false);
    }
  };

  const photo = isIncoming ? item.sender_photo_url : item.profile_photo_url;
  const title = isIncoming
    ? `${item.sender_name ?? "—"}, ${item.sender_age ?? "—"}`
    : `${item.profile_name ?? "—"}, ${item.profile_age ?? "—"}`;

  return (
    <section className="screen screen--milky">
      <Link to="/inbox" className="work-back">
        ← {t(language, "back")}
      </Link>

      <article className="letter-card">
        <div className="letter-card__hero">
          {photo ? <img src={mediaUrl(photo)} alt="" /> : <div className="letter-card__placeholder" />}
          <div className="letter-card__hero-veil" />
          <div className="letter-card__hero-meta">
            <h1>{title}</h1>
            {!isIncoming && item.profile_city ? <p>{item.profile_city}</p> : null}
          </div>
        </div>

        {!isIncoming && item.profile_dream ? (
          <p className="letter-card__dream">
            {t(language, "cardDream")}: {dreamLocationLabel(language, item.profile_dream)}
          </p>
        ) : null}

        <div className="letter-card__toggle">
          <button
            type="button"
            className={!showOriginal ? "is-active" : ""}
            onClick={() => setShowOriginal(false)}
          >
            {t(language, "showTranslation")}
          </button>
          <button
            type="button"
            className={showOriginal ? "is-active" : ""}
            onClick={() => setShowOriginal(true)}
          >
            {t(language, "showOriginal")}
          </button>
        </div>

        <h2 className="letter-card__label">{t(language, "cardLetter")}</h2>
        <p className="letter-card__text">{letterText}</p>

        {!isIncoming && item.status === "pending" ? (
          <p className="home-meta" style={{ padding: "0 16px 12px" }}>
            {t(language, "writePushHint")}
          </p>
        ) : null}

        {replyShown ? (
          <>
            <h2 className="letter-card__label">{t(language, "reply")}</h2>
            <p className="letter-card__text">{replyShown}</p>
          </>
        ) : null}

        {item.can_reply ? (
          <div className="letter-card__actions">
            <p className="home-meta">{t(language, "replyFreeHint")}</p>
            <div className="field">
              <textarea
                rows={4}
                value={reply}
                onChange={(e) => setReply(e.target.value)}
                placeholder={t(language, "replyPlaceholder")}
              />
            </div>
            <button
              type="button"
              className="btn btn--block btn--dark"
              disabled={busy || !reply.trim()}
              onClick={() => void onReply()}
            >
              {t(language, "sendReply")}
            </button>
            <button
              type="button"
              className="btn btn--block btn--ghost"
              disabled={busy}
              onClick={() => void onReject()}
            >
              {t(language, "notInterested")}
            </button>
          </div>
        ) : null}

        {item.can_unlock ? (
          <div className="letter-card__actions letter-card__pay">
            <h2 className="work-title" style={{ fontSize: 28 }}>
              {t(language, "unlockTitle")}
            </h2>
            <p className="work-body">{t(language, "unlockHint")}</p>
            {item.message_credits >= 1 ? (
              <button
                type="button"
                className="btn btn--block btn--dark"
                disabled={busy}
                onClick={() => void onUnlock()}
              >
                {tf(language, "unlockWithCredit", { n: item.message_credits })}
              </button>
            ) : null}
            <button
              type="button"
              className="btn btn--block btn--champagne"
              disabled={busy}
              onClick={() => void onBuy(false)}
            >
              {tf(language, "buyOneCredit", {
                stars: config?.prices.message_credit_stars ?? "—",
              })}
            </button>
            <button
              type="button"
              className="btn btn--block btn--ghost"
              disabled={busy}
              onClick={() => void onBuy(true)}
            >
              {tf(language, "buyPack", {
                size: config?.prices.message_pack_size ?? 9,
                stars: config?.prices.message_pack_9_stars ?? "—",
              })}
            </button>
          </div>
        ) : null}

        {item.can_chat ? (
          <div className="letter-card__actions">
            <Link to={`/chat/${item.id}`} className="btn btn--block btn--dark">
              {t(language, "openChat")}
            </Link>
            {item.counterpart_telegram_link ? (
              <button type="button" className="btn btn--block btn--ghost" onClick={openTg}>
                {t(language, "openTelegram")}
              </button>
            ) : null}
          </div>
        ) : null}

        <div className="letter-card__actions">
          {!reportOpen ? (
            <button
              type="button"
              className="btn btn--block btn--ghost"
              disabled={busy}
              onClick={() => setReportOpen(true)}
            >
              {t(language, "report")}
            </button>
          ) : (
            <>
              <h2 className="letter-card__label">{t(language, "reportTitle")}</h2>
              <p className="home-meta">{t(language, "reportHint")}</p>
              <div className="field">
                <textarea
                  rows={3}
                  value={reportReason}
                  onChange={(e) => setReportReason(e.target.value)}
                  placeholder={t(language, "reportPlaceholder")}
                />
              </div>
              <button
                type="button"
                className="btn btn--block btn--dark"
                disabled={busy || !reportReason.trim()}
                onClick={() => void onReport()}
              >
                {t(language, "reportSend")}
              </button>
            </>
          )}
        </div>

        {info ? <p className="home-meta">{info}</p> : null}
        {error ? <p className="form-error">{error}</p> : null}
      </article>
    </section>
  );
}
