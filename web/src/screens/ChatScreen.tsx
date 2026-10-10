import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { type Language, t } from "../i18n/messages";
import {
  fetchChat,
  sendChatMessage,
  type ChatMessageItem,
  type ChatThread,
} from "../lib/api";

type Props = { language: Language };

export function ChatScreen({ language }: Props) {
  const { id } = useParams();
  const requestId = Number(id);
  const [thread, setThread] = useState<ChatThread | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
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
  }, [thread?.messages.length]);

  const onSend = async () => {
    if (!text.trim() || !Number.isFinite(requestId)) return;
    setBusy(true);
    setError(null);
    const draft = text.trim();
    setText("");
    try {
      const msg = await sendChatMessage(requestId, draft);
      setThread((prev) =>
        prev
          ? { ...prev, messages: [...prev.messages, msg] }
          : prev,
      );
    } catch {
      setError(t(language, "errorGeneric"));
      setText(draft);
    } finally {
      setBusy(false);
    }
  };

  const openTg = () => {
    const link = thread?.counterpart_telegram_link;
    if (!link) return;
    const tg = window.Telegram?.WebApp as { openTelegramLink?: (u: string) => void } | undefined;
    if (tg?.openTelegramLink) tg.openTelegramLink(link);
    else window.open(link, "_blank");
  };

  return (
    <section className="screen screen--milky chat-screen">
      <header className="chat-header">
        <Link to="/inbox" className="work-back">
          ← {t(language, "back")}
        </Link>
        <div>
          <h1 className="chat-header__title">{thread?.counterpart_name ?? t(language, "chatTitle")}</h1>
          {thread?.counterpart_telegram_link ? (
            <button type="button" className="chat-header__tg" onClick={openTg}>
              {t(language, "openTelegram")}
            </button>
          ) : null}
        </div>
      </header>

      <div className="chat-stream">
        {!thread?.messages.length ? (
          <p className="home-meta">{t(language, "chatEmpty")}</p>
        ) : null}
        {thread?.messages.map((m: ChatMessageItem) => (
          <div key={m.id} className={`chat-bubble ${m.is_mine ? "is-mine" : "is-theirs"}`}>
            <p className="chat-bubble__text">{m.text}</p>
            {m.text_translated && m.text_translated !== m.text ? (
              <p className="chat-bubble__translation">{m.text_translated}</p>
            ) : null}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {error ? <p className="form-error">{error}</p> : null}

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
          <button type="submit" className="btn btn--dark" disabled={busy || !text.trim()}>
            {t(language, "chatSend")}
          </button>
        </form>
      )}
    </section>
  );
}
