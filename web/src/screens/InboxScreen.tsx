import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { type Language, t } from "../i18n/messages";
import { fetchInbox, mediaUrl, type MessageRequestItem } from "../lib/api";

type Props = { language: Language };

function statusKey(item: MessageRequestItem): Parameters<typeof t>[1] {
  if (item.profile_deleted) return "inboxStatusProfileDeleted";
  switch (item.status) {
    case "pending":
      return "inboxStatusPending";
    case "replied":
      return "inboxStatusReplied";
    case "unlocked":
      return "inboxStatusUnlocked";
    case "chatting":
      return "inboxStatusChatting";
    case "rejected":
      return "inboxStatusRejected";
    default:
      return "inboxStatusPending";
  }
}

function cardTitle(item: MessageRequestItem): string {
  if (item.direction === "incoming") {
    return `${item.sender_name ?? "—"}, ${item.sender_age ?? "—"}`;
  }
  if (item.profile_deleted) return item.profile_name ?? "—";
  return `${item.profile_name ?? "—"}, ${item.profile_age ?? "—"}`;
}

function cardPhoto(item: MessageRequestItem): string | null {
  if (item.direction === "incoming") return item.sender_photo_url;
  return item.profile_photo_url;
}

function previewText(item: MessageRequestItem, language: Language): string {
  const showTranslated = language === "ru" || language === "it";
  if (item.direction === "incoming") {
    return (showTranslated && item.text_translated) || item.text;
  }
  if (item.reply_text) {
    return (showTranslated && item.reply_text_translated) || item.reply_text;
  }
  return item.text;
}

export function InboxScreen({ language }: Props) {
  const [items, setItems] = useState<MessageRequestItem[]>([]);
  const [pending, setPending] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      setLoading(true);
      const data = await fetchInbox();
      setItems(data?.items ?? []);
      setPending(data?.pending_incoming ?? 0);
      setLoading(false);
    })();
  }, []);

  const incoming = items.filter((i) => i.direction === "incoming");
  const outgoing = items.filter((i) => i.direction === "outgoing");

  return (
    <section className="screen screen--milky">
      <Link to="/" className="work-back">
        ← {t(language, "backHome")}
      </Link>
      <h1 className="work-title">{t(language, "inboxTitle")}</h1>
      {pending > 0 ? (
        <p className="home-meta">
          {t(language, "homeLettersBadge")}: {pending}
        </p>
      ) : null}

      {loading ? <p className="home-meta">{t(language, "saving")}</p> : null}

      {!loading && items.length === 0 ? (
        <p className="work-body">{t(language, "inboxEmpty")}</p>
      ) : null}

      {incoming.length > 0 ? (
        <div className="inbox-section">
          <h2 className="inbox-section__title">{t(language, "inboxIncoming")}</h2>
          <ul className="inbox-list">
            {incoming.map((item) => (
              <li key={item.id}>
                <Link to={`/inbox/${item.id}`} className="inbox-card">
                  <div className="inbox-card__photo">
                    {cardPhoto(item) ? (
                      <img src={mediaUrl(cardPhoto(item)!)} alt="" />
                    ) : (
                      <span>{(item.sender_name || "?").slice(0, 1)}</span>
                    )}
                  </div>
                  <div className="inbox-card__body">
                    <strong>{cardTitle(item)}</strong>
                    <span className="inbox-card__status">{t(language, statusKey(item))}</span>
                    <p>{previewText(item, language)}</p>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {outgoing.length > 0 ? (
        <div className="inbox-section">
          <h2 className="inbox-section__title">{t(language, "inboxOutgoing")}</h2>
          <ul className="inbox-list">
            {outgoing.map((item) => (
              <li key={item.id}>
                <Link
                  to={item.can_chat ? `/chat/${item.id}` : `/inbox/${item.id}`}
                  className="inbox-card"
                >
                  <div className="inbox-card__photo">
                    {cardPhoto(item) ? (
                      <img src={mediaUrl(cardPhoto(item)!)} alt="" />
                    ) : (
                      <span>{(item.profile_name || "?").slice(0, 1)}</span>
                    )}
                  </div>
                  <div className="inbox-card__body">
                    <strong>{cardTitle(item)}</strong>
                    <span className="inbox-card__status">{t(language, statusKey(item))}</span>
                    <p>{previewText(item, language)}</p>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
