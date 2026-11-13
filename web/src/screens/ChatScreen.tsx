import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { type Language, t, tf } from "../i18n/messages";
import {
  fetchChat,
  mediaUrl,
  sendChatMessage,
  shareTelegram,
  type ChatMessageItem,
  type ChatThread,
  type MeUser,
} from "../lib/api";
import { counterpartIsMale, openTelegramUrl } from "../lib/writePath";

type Props = { language: Language; me: MeUser | null };

function GiftIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="3.5" y="8.5" width="17" height="4" rx="1" />
      <path d="M5 12.5V20h14v-7.5M12 8.5V20" />
      <path d="M12 8.5C10.5 8.5 8 8 8 6a2 2 0 0 1 4 0c0 1 0 2.5 0 2.5Zm0 0c1.5 0 4-.5 4-2.5a2 2 0 0 0-4 0" />
    </svg>
  );
}

export function ChatScreen({ language, me }: Props) {
  const { id } = useParams();
  const requestId = Number(id);
  const [thread, setThread] = useState<ChatThread | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [shareBusy, setShareBusy] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const reload = async () => {
    if (!Number.isFinite(requestId)) return;
    const data = await fetchChat(requestId);
    setThread(data);
  };

  useEffect(() => {
    void reload();
    const timer = window.setInterval(() => void reload(), 8000);
    return () => window.clearInterval(timer);
  }, [requestId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thread?.messages.length, thread?.peer_shared_telegram]);

  const onSend = async () => {
    if (!text.trim() || !Number.isFinite(requestId)) return;
    setBusy(true);
    setError(null);
    const draft = text.trim();
    setText("");
    try {
      const msg = await sendChatMessage(requestId, draft);
      setThread((prev) => (prev ? { ...prev, messages: [...prev.messages, msg] } : prev));
    } catch {
      setError(t(language, "errorGeneric"));
      setText(draft);
    } finally {
      setBusy(false);
    }
  };

  const notify = (message: string) => {
    const tg = window.Telegram?.WebApp;
    if (tg?.showAlert) tg.showAlert(message);
    else window.alert(message);
  };

  const onShareTelegram = async () => {
    if (!thread || shareBusy) return;
    if (!thread.can_share_telegram) {
      // No @username yet — tell the user how to create one.
      notify(t(language, "giveTelegramNoUsername"));
      return;
    }
    setShareBusy(true);
    setError(null);
    try {
      await shareTelegram(requestId);
      await reload();
    } catch {
      setError(t(language, "errorGeneric"));
    } finally {
      setShareBusy(false);
    }
  };

  const name = thread?.counterpart_name ?? "";
  const title = thread?.counterpart_age ? `${name}, ${thread.counterpart_age}` : name;
  const photo = thread?.counterpart_photo_url ?? null;
  const gift = Boolean(thread?.unlock_from_gift);
  // `gift_credits_left` is the balance after this unlock, so the N-th gift is 3 − left (1..3).
  const giftN = Math.min(3, Math.max(1, 3 - (thread?.gift_credits_left ?? 0)));
  const peerLink = thread?.peer_telegram_link ?? thread?.counterpart_telegram_link ?? null;
  const canGiveTelegram = Boolean(thread && !thread.profile_deleted && !thread.i_shared_telegram);

  return (
    <section className="screen screen--milky chat-screen">
      <header className="chat-header">
        <Link to="/inbox" className="work-back work-back--gold">
          ← {t(language, "chatBack")}
        </Link>
        <div className="chat-header__who">
          <div className="chat-header__photo">
            {photo ? <img src={mediaUrl(photo)} alt="" /> : <span>{(name || "?").slice(0, 1)}</span>}
          </div>
          <div>
            <h1 className="chat-header__title">{title || t(language, "chatTitle")}</h1>
            {thread?.counterpart_city ? (
              <p className="chat-header__city">{thread.counterpart_city}</p>
            ) : null}
          </div>
        </div>
      </header>

      {thread ? (
        <div className="chat-open-bar">
          <GiftIcon />
          <span>
            {gift ? tf(language, "chatOpenGift", { n: giftN }) : t(language, "chatOpen")}
          </span>
        </div>
      ) : null}

      <div className="chat-toggle">
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

      <div className="chat-stream">
        {!thread?.messages.length ? (
          <p className="home-meta">{t(language, "chatEmpty")}</p>
        ) : null}
        {thread?.messages.map((m: ChatMessageItem) => {
          // My own messages stay as I wrote them; the toggle switches the other side's text.
          const shown = m.is_mine || showOriginal ? m.text : m.text_translated || m.text;
          return (
            <div key={m.id} className={`chat-bubble ${m.is_mine ? "is-mine" : "is-theirs"}`}>
              <p className="chat-bubble__text">{shown}</p>
            </div>
          );
        })}

        {thread?.peer_shared_telegram && peerLink ? (
          <div className="tg-peer-block">
            <strong>
              {tf(language, counterpartIsMale(me) ? "peerGaveTelegramM" : "peerGaveTelegramF", {
                name,
              })}
            </strong>
            <p>{t(language, "peerGaveTelegramHint")}</p>
            <button type="button" className="btn btn--white btn--pill" onClick={() => openTelegramUrl(peerLink)}>
              {t(language, "writeInTelegram")}
            </button>
          </div>
        ) : null}

        <div ref={bottomRef} />
      </div>

      {error ? <p className="form-error">{error}</p> : null}

      {canGiveTelegram ? (
        <button
          type="button"
          className="tg-give"
          disabled={shareBusy}
          onClick={() => void onShareTelegram()}
        >
          <span className="tg-give__text">
            <strong>{t(language, "giveTelegram")}</strong>
            <span>{tf(language, "giveTelegramHint", { name })}</span>
          </span>
          <span className="tg-give__chevron" aria-hidden>
            ›
          </span>
        </button>
      ) : thread?.i_shared_telegram ? (
        <p className="tg-given-note">{t(language, "giveTelegramDone")}</p>
      ) : null}

      {thread?.profile_deleted ? (
        <p className="chat-closed-note">{t(language, "chatProfileDeletedNote")}</p>
      ) : (
        <form
          className="chat-composer"
          onSubmit={(e) => {
            e.preventDefault();
            void onSend();
          }}
        >
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={t(language, "chatPlaceholder")}
            disabled={busy || !thread?.can_send}
          />
          <button
            type="submit"
            className="chat-composer__send"
            aria-label={t(language, "chatSend")}
            disabled={busy || !text.trim()}
          >
            ↑
          </button>
        </form>
      )}
    </section>
  );
}
