import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { type Language, type MessageKey, t, tf } from "../i18n/messages";
import { fetchInbox, hideMessage, mediaUrl, type MeUser, type MessageRequestItem } from "../lib/api";
import { counterpartIsMale, openTelegramUrl } from "../lib/writePath";
import { ensureWriteAccess } from "../lib/writeAccess";

type Props = {
  language: Language;
  me: MeUser | null;
  onMeRefresh?: () => void;
};

type Pill = { key: MessageKey; tone: "plum" | "beige" | "green" };

function pillFor(item: MessageRequestItem, me: MeUser | null): Pill {
  if (item.moved_to_telegram) return { key: "movedToTelegram", tone: "green" };
  if (item.profile_deleted) return { key: "inboxStatusProfileDeleted", tone: "beige" };
  const answered: MessageKey = counterpartIsMale(me) ? "inboxStatusAnsweredM" : "inboxStatusAnsweredF";
  if (item.direction === "incoming") {
    switch (item.status) {
      case "pending":
        return { key: "inboxStatusNewIncoming", tone: "plum" };
      case "expired":
        return { key: "inboxStatusExpired", tone: "beige" };
      case "rejected":
        return { key: "inboxStatusRejected", tone: "beige" };
      default:
        return { key: "inboxStatusChatting", tone: "beige" };
    }
  }
  switch (item.status) {
    case "pending":
      return { key: "inboxStatusWaiting", tone: "beige" };
    case "replied":
    case "unlocked":
    case "chatting":
      return { key: answered, tone: "plum" };
    case "expired":
      return { key: "inboxStatusRefunded", tone: "beige" };
    case "rejected":
      return { key: "inboxStatusRejected", tone: "beige" };
    default:
      return { key: "inboxStatusWaiting", tone: "beige" };
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
  if (item.content_locked) {
    return t(language, "inboxLockedPreview");
  }
  const showTranslated = language === "ru" || language === "it";
  if (item.direction === "incoming") {
    return (showTranslated && item.text_translated) || item.text;
  }
  // Late reply before re-open: text stays hidden for the initiator.
  if (item.status === "replied") {
    return t(language, "letterReplyHidden");
  }
  if (item.reply_text) {
    return (showTranslated && item.reply_text_translated) || item.reply_text;
  }
  return item.text;
}

function itemPath(item: MessageRequestItem): string {
  return item.can_chat ? `/chat/${item.id}` : `/inbox/${item.id}`;
}

const SWIPE_OPEN = -88;
const SWIPE_THRESHOLD = -48;

/** Swipe left to reveal «Скрыть». Threads are only hidden, never deleted. */
function SwipeRow({
  hideLabel,
  onHide,
  children,
}: {
  hideLabel: string;
  onHide: () => void;
  children: ReactNode;
}) {
  const [offset, setOffset] = useState(0);
  const [dragging, setDragging] = useState(false);
  const startRef = useRef<{ x: number; y: number; base: number } | null>(null);
  const movedRef = useRef(false);
  const lockedRef = useRef<"x" | "y" | null>(null);

  const onTouchStart = (e: React.TouchEvent) => {
    const touch = e.touches[0];
    startRef.current = { x: touch.clientX, y: touch.clientY, base: offset };
    movedRef.current = false;
    lockedRef.current = null;
    setDragging(true);
  };

  const onTouchMove = (e: React.TouchEvent) => {
    const start = startRef.current;
    if (!start) return;
    const touch = e.touches[0];
    const dx = touch.clientX - start.x;
    const dy = touch.clientY - start.y;
    if (!lockedRef.current) {
      if (Math.abs(dx) < 6 && Math.abs(dy) < 6) return;
      lockedRef.current = Math.abs(dx) > Math.abs(dy) ? "x" : "y";
    }
    if (lockedRef.current !== "x") return;
    movedRef.current = true;
    setOffset(Math.max(SWIPE_OPEN, Math.min(0, start.base + dx)));
  };

  const onTouchEnd = () => {
    startRef.current = null;
    setDragging(false);
    if (lockedRef.current === "x") setOffset((o) => (o <= SWIPE_THRESHOLD ? SWIPE_OPEN : 0));
  };

  return (
    <div className="swipe-row">
      <button type="button" className="swipe-row__action" onClick={onHide} tabIndex={offset === 0 ? -1 : 0}>
        {hideLabel}
      </button>
      <div
        className={`swipe-row__content${dragging ? " is-dragging" : ""}`}
        style={{ transform: `translateX(${offset}px)` }}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
        onTouchCancel={onTouchEnd}
        onClickCapture={(e) => {
          // A swipe (or a tap on an opened row) must not navigate.
          if (movedRef.current) {
            e.preventDefault();
            e.stopPropagation();
            movedRef.current = false;
          } else if (offset !== 0) {
            e.preventDefault();
            e.stopPropagation();
            setOffset(0);
          }
        }}
      >
        {children}
      </div>
    </div>
  );
}

export function InboxScreen({ language, me, onMeRefresh }: Props) {
  const [items, setItems] = useState<MessageRequestItem[]>([]);
  const [pending, setPending] = useState(0);
  const [loading, setLoading] = useState(true);
  const [tgCollapsed, setTgCollapsed] = useState(false);
  const [notifBusy, setNotifBusy] = useState(false);

  useEffect(() => {
    void (async () => {
      setLoading(true);
      const data = await fetchInbox();
      setItems(data?.items ?? []);
      setPending(data?.pending_incoming ?? 0);
      setLoading(false);
    })();
  }, []);

  const onHide = useCallback(async (id: number) => {
    // Optimistic: the row disappears right away, restored if the API fails.
    let snapshot: MessageRequestItem[] = [];
    setItems((prev) => {
      snapshot = prev;
      return prev.filter((i) => i.id !== id);
    });
    try {
      await hideMessage(id);
    } catch {
      setItems(snapshot);
    }
  }, []);

  const onEnableNotifications = async () => {
    setNotifBusy(true);
    try {
      await ensureWriteAccess();
      onMeRefresh?.();
    } finally {
      setNotifBusy(false);
    }
  };

  const chats = items.filter((i) => !i.moved_to_telegram);
  const inTelegram = items.filter((i) => i.moved_to_telegram);
  const showNotifChip = me !== null && !me.bot_write_access;

  const renderRow = (item: MessageRequestItem, moved: boolean) => {
    const pill = pillFor(item, me);
    const photo = cardPhoto(item);
    const initial = (item.direction === "incoming" ? item.sender_name : item.profile_name) || "?";
    const tgLink = moved ? item.counterpart_telegram_link : null;
    return (
      <li key={item.id}>
        <SwipeRow hideLabel={t(language, "hideThread")} onHide={() => void onHide(item.id)}>
          <Link to={itemPath(item)} className={`inbox-card${moved ? " inbox-card--moved" : ""}`}>
            <div className="inbox-card__photo">
              {photo ? <img src={mediaUrl(photo)} alt="" /> : <span>{initial.slice(0, 1)}</span>}
            </div>
            <div className="inbox-card__body">
              <strong>{cardTitle(item)}</strong>
              <span className={`inbox-card__status inbox-card__status--${pill.tone}`}>
                {t(language, pill.key)}
              </span>
              {moved ? (
                tgLink ? (
                  <span
                    role="link"
                    tabIndex={0}
                    className="inbox-card__tg-link"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      openTelegramUrl(tgLink);
                    }}
                  >
                    {t(language, "openInTelegram")}
                  </span>
                ) : null
              ) : (
                <p>{previewText(item, language)}</p>
              )}
            </div>
          </Link>
        </SwipeRow>
      </li>
    );
  };

  return (
    <section className="screen screen--milky">
      <Link to="/" className="work-back work-back--sticky">
        ← {t(language, "backHome")}
      </Link>
      <h1 className="work-title">{t(language, "inboxTitle")}</h1>
      {(me?.unread_locked_count ?? 0) > 0 && !me?.has_unlimited ? (
        <p className="inbox-locked-banner">
          {tf(language, "inboxLockedBanner", { n: me?.unread_locked_count ?? 0 })}{" "}
          <Link to="/credits">{t(language, "waitingPlusCta")}</Link>
        </p>
      ) : null}
      {pending > 0 ? (
        <p className="home-meta">
          {t(language, "homeLettersBadge")}: {pending}
        </p>
      ) : null}

      {showNotifChip ? (
        <button
          type="button"
          className="chip chip--plum"
          disabled={notifBusy}
          onClick={() => void onEnableNotifications()}
        >
          🔔 {t(language, "enableNotifications")}
        </button>
      ) : null}

      {loading ? <p className="home-meta">{t(language, "saving")}</p> : null}

      {!loading && items.length === 0 ? (
        <p className="work-body">{t(language, "inboxEmpty")}</p>
      ) : null}

      {chats.length > 0 ? (
        <div className="inbox-section">
          <h2 className="inbox-section__title">{t(language, "inboxSectionChats")}</h2>
          <ul className="inbox-list">{chats.map((item) => renderRow(item, false))}</ul>
        </div>
      ) : null}

      {inTelegram.length > 0 ? (
        <div className="inbox-section">
          <div className="inbox-section__head">
            <h2 className="inbox-section__title">
              {tf(language, "inboxSectionTelegram", { n: inTelegram.length })}
            </h2>
            <button
              type="button"
              className="inbox-section__toggle"
              aria-expanded={!tgCollapsed}
              onClick={() => setTgCollapsed((v) => !v)}
            >
              {t(language, tgCollapsed ? "inboxExpand" : "inboxCollapse")}
            </button>
          </div>
          {!tgCollapsed ? (
            <ul className="inbox-list">{inTelegram.map((item) => renderRow(item, true))}</ul>
          ) : null}
        </div>
      ) : null}

    </section>
  );
}
