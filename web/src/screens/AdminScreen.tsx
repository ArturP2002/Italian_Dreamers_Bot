import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { dreamLocationLabel, type Language, t } from "../i18n/messages";
import {
  adminActivateAdNow,
  adminApproveAd,
  adminApproveProfile,
  adminBlockUser,
  adminFetchAd,
  adminFetchAds,
  adminFetchComplaints,
  adminFetchPayments,
  adminFetchProfile,
  adminFetchProfiles,
  adminFetchStats,
  adminFetchUsers,
  adminGrantCredits,
  adminMarkAdPaid,
  adminMarkPaid,
  adminPublishNow,
  adminRejectAd,
  adminRejectProfile,
  adminResolveComplaint,
  adminScheduleProfile,
  adminUnblockUser,
  mediaUrl,
  type AdminAd,
  type AdminComplaint,
  type AdminPayment,
  type AdminProfileDetail,
  type AdminProfileListItem,
  type AdminStats,
  type AdminUser,
} from "../lib/api";

type Props = { language: Language };

type Tab =
  | "new"
  | "queue"
  | "published"
  | "ads"
  | "complaints"
  | "users"
  | "payments"
  | "stats";

const AD_CATEGORY_RU: Record<string, string> = {
  restaurants: "рестораны",
  mens_goods: "товары для мужчин",
  language_courses: "языковые курсы",
  other: "другое",
};

function adCategoryRu(category: string): string {
  return AD_CATEGORY_RU[category] ?? category;
}

type ActionOutcome = {
  tone: "ok" | "rejected";
  title: string;
  subject: string;
  lines: string[];
  reopenLabel: string;
};

type AdFilter = "pending" | "queue" | "all";

const AD_FILTERS: { id: AdFilter; label: string }[] = [
  { id: "pending", label: "Новые" },
  { id: "queue", label: "Очередь/активные" },
  { id: "all", label: "Все" },
];

const TABS: { id: Tab; label: string }[] = [
  { id: "new", label: "Новые" },
  { id: "queue", label: "Очередь" },
  { id: "published", label: "Опубликованы" },
  { id: "ads", label: "Реклама" },
  { id: "complaints", label: "Жалобы" },
  { id: "users", label: "Пользователи" },
  { id: "payments", label: "Платежи" },
  { id: "stats", label: "Статистика" },
];

/** Page size for admin profile lists (Новые / Очередь / Опубликованы). */
const PROFILE_PAGE_SIZE = 10;
/** Page size for admin users list. */
const USER_PAGE_SIZE = 10;

function profileBelongsToTab(status: string, tab: Tab): boolean {
  if (tab === "new") return status === "new";
  if (tab === "queue") return status === "queued" || status === "awaiting_payment";
  if (tab === "published") return status === "published";
  return true;
}

function adBelongsToFilter(status: string, filter: AdFilter): boolean {
  if (filter === "all") return true;
  if (filter === "pending") return status === "pending";
  if (filter === "queue") {
    return status === "awaiting_payment" || status === "queued" || status === "active";
  }
  return true;
}

function toListItem(d: AdminProfileDetail): AdminProfileListItem {
  return {
    id: d.id,
    status: d.status,
    name: d.name,
    age: d.age,
    gender: d.gender,
    city: d.city,
    country: d.country,
    telegram_username: d.telegram_username,
    user_telegram_id: d.user_telegram_id,
    user_id: d.user_id,
    moderation_feedback: d.moderation_feedback,
    scheduled_at: d.scheduled_at,
    paid_at: d.paid_at,
    published_at: d.published_at,
    approved_at: d.approved_at,
    created_at: d.created_at,
    photo_url: d.photo_url,
  };
}

function isProfileDetail(value: unknown): value is AdminProfileDetail {
  return (
    typeof value === "object" &&
    value !== null &&
    "photos" in value &&
    "message_credits" in value &&
    "user_id" in value &&
    "name" in value
  );
}

function isAdminAd(value: unknown): value is AdminAd {
  return (
    typeof value === "object" &&
    value !== null &&
    "category" in value &&
    "title" in value &&
    "user_id" in value &&
    !("photos" in value)
  );
}

function isAdminUser(value: unknown): value is AdminUser {
  return (
    typeof value === "object" &&
    value !== null &&
    "telegram_id" in value &&
    "message_credits" in value &&
    "is_blocked" in value &&
    !("photos" in value) &&
    !("category" in value)
  );
}

function isAdminComplaint(value: unknown): value is AdminComplaint {
  return (
    typeof value === "object" &&
    value !== null &&
    "reason" in value &&
    "reporter_user_id" in value
  );
}

function statusRu(status: string): string {
  const map: Record<string, string> = {
    draft: "черновик",
    new: "на модерации",
    approved: "одобрена",
    awaiting_payment: "ждёт оплаты",
    queued: "в очереди",
    published: "опубликована",
    rejected: "отклонена",
    hidden: "скрыта",
    pending: "на модерации",
    active: "активна",
    expired: "завершена",
    open: "открыта",
    reviewed: "просмотрена",
    resolved: "решена",
    dismissed: "отклонена",
  };
  return map[status] ?? status;
}

function familyLineRu(p: AdminProfileDetail): string {
  const female = p.gender === "female";
  const marital =
    p.marital_status === "divorced"
      ? female
        ? "разведена"
        : "разведён"
      : female
        ? "не замужем"
        : "не женат";
  const wants =
    { yes: "хочет детей", no: "не хочет детей", unsure: female ? "не уверена насчёт детей" : "не уверен насчёт детей" }[
      p.wants_children
    ] ?? p.wants_children;
  return [
    p.height_cm ? `${p.height_cm} см` : null,
    marital,
    p.has_children ? "есть дети" : "детей нет",
    wants,
  ]
    .filter(Boolean)
    .join(" · ");
}

function paymentProductRu(product: string): string {
  const map: Record<string, string> = {
    message_credit: "кредит на письмо",
    message_pack_9: "пакет из 9 писем",
    profile_publish: "публикация анкеты",
    ad_slot: "реклама",
  };
  return map[product] ?? product;
}

function paymentStatusRu(status: string): string {
  const map: Record<string, string> = {
    pending: "ждёт оплаты",
    completed: "оплачен",
    failed: "ошибка",
    refunded: "возврат",
  };
  return map[status] ?? status;
}

function formatDt(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("ru-RU", { timeZone: "Europe/Moscow" });
}

export function AdminScreen({ language }: Props) {
  const [tab, setTab] = useState<Tab>("new");
  const [items, setItems] = useState<AdminProfileListItem[]>([]);
  const [profilesHasMore, setProfilesHasMore] = useState(false);
  const [profilesTotal, setProfilesTotal] = useState(0);
  const [profilesLoadingMore, setProfilesLoadingMore] = useState(false);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [usersHasMore, setUsersHasMore] = useState(false);
  const [usersTotal, setUsersTotal] = useState(0);
  const [usersLoadingMore, setUsersLoadingMore] = useState(false);
  const [payments, setPayments] = useState<AdminPayment[]>([]);
  const [ads, setAds] = useState<AdminAd[]>([]);
  const [complaints, setComplaints] = useState<AdminComplaint[]>([]);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedAdId, setSelectedAdId] = useState<number | null>(null);
  const [detail, setDetail] = useState<AdminProfileDetail | null>(null);
  const [adDetail, setAdDetail] = useState<AdminAd | null>(null);
  const [query, setQuery] = useState("");
  const [adFilter, setAdFilter] = useState<AdFilter>("pending");
  const [feedback, setFeedback] = useState("");
  const [scheduleLocal, setScheduleLocal] = useState("");
  const [creditsDelta, setCreditsDelta] = useState("9");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [result, setResult] = useState<ActionOutcome | null>(null);

  const syncScheduleLocal = (d: AdminProfileDetail | null) => {
    if (d?.scheduled_at) {
      const local = new Date(d.scheduled_at);
      const pad = (n: number) => String(n).padStart(2, "0");
      setScheduleLocal(
        `${local.getFullYear()}-${pad(local.getMonth() + 1)}-${pad(local.getDate())}T${pad(local.getHours())}:${pad(local.getMinutes())}`,
      );
    } else {
      setScheduleLocal("");
    }
  };

  const applyProfileUpdate = useCallback(
    (d: AdminProfileDetail) => {
      setDetail(d);
      syncScheduleLocal(d);
      setItems((prev) => {
        if (!profileBelongsToTab(d.status, tab)) {
          setProfilesTotal((t) => Math.max(0, t - 1));
          const next = prev.filter((i) => i.id !== d.id);
          setProfilesHasMore(next.length < Math.max(0, profilesTotal - 1));
          return next;
        }
        const mapped = toListItem(d);
        const idx = prev.findIndex((i) => i.id === d.id);
        if (idx === -1) return prev;
        const next = prev.slice();
        next[idx] = mapped;
        return next;
      });
    },
    [tab, profilesTotal],
  );

  const applyAdUpdate = useCallback(
    (ad: AdminAd) => {
      setAdDetail(ad);
      setAds((prev) => {
        if (!adBelongsToFilter(ad.status, adFilter)) {
          return prev.filter((i) => i.id !== ad.id);
        }
        const idx = prev.findIndex((i) => i.id === ad.id);
        if (idx === -1) return prev;
        const next = prev.slice();
        next[idx] = ad;
        return next;
      });
    },
    [adFilter],
  );

  const loadList = useCallback(async () => {
    setError(null);
    try {
      if (tab === "new" || tab === "queue" || tab === "published") {
        const status = tab === "new" ? "new" : tab === "queue" ? "queue" : "published";
        const page = await adminFetchProfiles(status, {
          limit: PROFILE_PAGE_SIZE,
          offset: 0,
        });
        setItems(page.items);
        setProfilesTotal(page.total);
        setProfilesHasMore(page.has_more);
      } else if (tab === "ads") {
        setAds(await adminFetchAds(adFilter === "all" ? undefined : adFilter));
      } else if (tab === "complaints") {
        setComplaints(await adminFetchComplaints("open"));
      } else if (tab === "users") {
        const page = await adminFetchUsers(query, { limit: USER_PAGE_SIZE, offset: 0 });
        setUsers(page.items);
        setUsersTotal(page.total);
        setUsersHasMore(page.has_more);
      } else if (tab === "payments") {
        setPayments(await adminFetchPayments());
      } else if (tab === "stats") {
        setStats(await adminFetchStats());
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Load failed");
    }
  }, [tab, query, adFilter]);

  const loadMoreProfiles = async () => {
    if (profilesLoadingMore || !profilesHasMore) return;
    if (tab !== "new" && tab !== "queue" && tab !== "published") return;
    setProfilesLoadingMore(true);
    setError(null);
    try {
      const status = tab === "new" ? "new" : tab === "queue" ? "queue" : "published";
      const page = await adminFetchProfiles(status, {
        limit: PROFILE_PAGE_SIZE,
        offset: items.length,
      });
      setItems((prev) => {
        const seen = new Set(prev.map((i) => i.id));
        return [...prev, ...page.items.filter((i) => !seen.has(i.id))];
      });
      setProfilesTotal(page.total);
      setProfilesHasMore(page.has_more);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Load failed");
    } finally {
      setProfilesLoadingMore(false);
    }
  };

  const loadMoreUsers = async () => {
    if (usersLoadingMore || !usersHasMore || tab !== "users") return;
    setUsersLoadingMore(true);
    setError(null);
    try {
      const page = await adminFetchUsers(query, {
        limit: USER_PAGE_SIZE,
        offset: users.length,
      });
      setUsers((prev) => {
        const seen = new Set(prev.map((u) => u.id));
        return [...prev, ...page.items.filter((u) => !seen.has(u.id))];
      });
      setUsersTotal(page.total);
      setUsersHasMore(page.has_more);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Load failed");
    } finally {
      setUsersLoadingMore(false);
    }
  };

  useEffect(() => {
    void loadList();
  }, [loadList]);

  useEffect(() => {
    if (selectedId == null) {
      setDetail(null);
      return;
    }
    void (async () => {
      const d = await adminFetchProfile(selectedId);
      setDetail(d);
      syncScheduleLocal(d);
    })();
  }, [selectedId]);

  useEffect(() => {
    if (selectedAdId == null) {
      setAdDetail(null);
      return;
    }
    void (async () => {
      setAdDetail(await adminFetchAd(selectedAdId));
    })();
  }, [selectedAdId]);

  const title = useMemo(() => t(language, "adminTitle"), [language]);

  async function run(action: () => Promise<unknown>, okMsg: string, outcome?: ActionOutcome) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const payload = await action();
      if (outcome) {
        setResult(outcome);
        setFeedback("");
      } else {
        setNotice(okMsg);
      }
      window.scrollTo({ top: 0 });

      if (isProfileDetail(payload)) {
        applyProfileUpdate(payload);
      } else if (isAdminAd(payload)) {
        applyAdUpdate(payload);
      } else if (isAdminUser(payload)) {
        if (detail && detail.user_id === payload.id) {
          setDetail({
            ...detail,
            message_credits: payload.message_credits,
            is_blocked: payload.is_blocked,
          });
        }
        setUsers((prev) => prev.map((u) => (u.id === payload.id ? { ...u, ...payload } : u)));
      } else if (isAdminComplaint(payload)) {
        setComplaints((prev) =>
          payload.status === "open" ? prev.map((c) => (c.id === payload.id ? payload : c)) : prev.filter((c) => c.id !== payload.id),
        );
      } else {
        await loadList();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
      window.scrollTo({ top: 0 });
    } finally {
      setBusy(false);
    }
  }

  const closeResult = (toList: boolean) => {
    setResult(null);
    if (toList) {
      setSelectedId(null);
      setSelectedAdId(null);
    }
  };

  return (
    <section className="screen screen--work admin-screen">
      <header className="admin-top">
        <div>
          <h1 className="heading-display" style={{ fontSize: 28, margin: 0 }}>
            {title}
          </h1>
          <p className="admin-sub">Модерация · реклама · жалобы</p>
        </div>
        <Link to="/" className="admin-home-link">
          {t(language, "backHome")}
        </Link>
      </header>

      <nav className="admin-tabs" aria-label="Admin sections">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`admin-tab${tab === item.id ? " is-active" : ""}`}
            onClick={() => {
              setTab(item.id);
              setSelectedId(null);
              setSelectedAdId(null);
              setNotice(null);
              setError(null);
              setResult(null);
            }}
          >
            {item.label}
          </button>
        ))}
      </nav>

      {error ? <div className="admin-banner admin-banner--err">{error}</div> : null}
      {notice ? <div className="admin-banner admin-banner--ok">{notice}</div> : null}

      {result ? (
        <article className={`admin-card admin-result admin-result--${result.tone}`}>
          <div className="admin-result__icon" aria-hidden>
            {result.tone === "ok" ? "✓" : "✕"}
          </div>
          <h2 className="admin-name">{result.title}</h2>
          <p className="admin-result__subject">{result.subject}</p>
          <ul className="admin-result__lines">
            {result.lines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <button type="button" className="admin-btn admin-btn--primary" onClick={() => closeResult(true)}>
            К списку
          </button>
          <button type="button" className="admin-btn" onClick={() => closeResult(false)}>
            {result.reopenLabel}
          </button>
        </article>
      ) : (
        <>
      {tab === "users" ? (
        <div className="admin-search-row">
          <input
            className="admin-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Имя, @ник или ID в Telegram"
          />
          <button type="button" className="admin-btn" disabled={busy} onClick={() => void loadList()}>
            Найти
          </button>
        </div>
      ) : null}

      {tab === "ads" && selectedAdId == null ? (
        <div className="admin-search-row admin-filters" role="group" aria-label="Фильтр заявок">
          {AD_FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              className={`admin-btn admin-filter${adFilter === f.id ? " is-active" : ""}`}
              aria-pressed={adFilter === f.id}
              disabled={busy}
              onClick={() => setAdFilter(f.id)}
            >
              {f.label}
            </button>
          ))}
        </div>
      ) : null}

      {selectedId != null && detail ? (
        <article className="admin-card admin-detail">
          <button type="button" className="admin-linkish" onClick={() => setSelectedId(null)}>
            ← К списку
          </button>
          {detail.photo_url ? (
            <img className="admin-hero-photo" src={mediaUrl(detail.photo_url)} alt="" />
          ) : null}
          <h2 className="admin-name">
            {detail.name}, {detail.age}
          </h2>
          <p className="admin-meta">
            {statusRu(detail.status)} · @{detail.telegram_username || "—"} · ID {detail.user_telegram_id}
          </p>
          <p className="admin-meta">
            {detail.city}, {detail.country} · {detail.profession}
          </p>
          <p className="admin-meta">{familyLineRu(detail)}</p>
          {detail.dream_location ? (
            <p className="admin-meta">Мечтает увидеть: {dreamLocationLabel("ru", detail.dream_location)}</p>
          ) : null}
          <h3 className="admin-section-label">О себе</h3>
          <p className="admin-body">{detail.about}</p>
          {detail.hobbies ? (
            <>
              <h3 className="admin-section-label">Увлечения</h3>
              <p className="admin-body">{detail.hobbies}</p>
            </>
          ) : null}
          <h3 className="admin-section-label">
            Кого ищет · {detail.age_min}–{detail.age_max} лет
          </h3>
          <p className="admin-body">{detail.desired_partner}</p>
          {detail.cover_answer ? (
            <>
              <h3 className="admin-section-label">Ответ для заставки</h3>
              <p className="admin-body">{detail.cover_answer}</p>
            </>
          ) : null}
          <h3 className="admin-section-label">Все фото · {detail.photos.length}</h3>
          <div className="admin-photo-row">
            {detail.photos.map((p) => (
              <img key={p.id} src={mediaUrl(p.url)} alt="" />
            ))}
          </div>

          {detail.status === "new" ? (
            <div className="admin-actions">
              <button
                type="button"
                className="admin-btn admin-btn--primary"
                disabled={busy}
                onClick={() =>
                  void run(() => adminApproveProfile(detail.id), "Одобрено, счёт на оплату отправлен", {
                    tone: "ok",
                    title: "Анкета одобрена",
                    subject: `${detail.name}, ${detail.age}`,
                    lines: [
                      "Пользователю отправлен счёт на оплату публикации.",
                      "После оплаты анкета появится во вкладке «Очередь» — там можно назначить дату или опубликовать сразу.",
                    ],
                    reopenLabel: "Открыть анкету",
                  })
                }
              >
                Одобрить → оплата
              </button>
              <textarea
                className="admin-input admin-textarea"
                placeholder="Причина отклонения"
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
              />
              <button
                type="button"
                className="admin-btn"
                disabled={busy || feedback.trim().length < 3}
                onClick={() =>
                  void run(() => adminRejectProfile(detail.id, feedback.trim()), "Отклонено", {
                    tone: "rejected",
                    title: "Анкета отклонена",
                    subject: `${detail.name}, ${detail.age}`,
                    lines: [
                      `Пользователь получил причину: «${feedback.trim()}».`,
                      "Он может исправить анкету и снова отправить её на модерацию.",
                    ],
                    reopenLabel: "Открыть анкету",
                  })
                }
              >
                Отклонить
              </button>
            </div>
          ) : null}

          {detail.status === "awaiting_payment" ? (
            <div className="admin-actions">
              <button
                type="button"
                className="admin-btn"
                disabled={busy}
                onClick={() =>
                  void run(() => adminMarkPaid(detail.id), "Оплата отмечена вручную", {
                    tone: "ok",
                    title: "Оплата отмечена",
                    subject: `${detail.name}, ${detail.age}`,
                    lines: [
                      "Анкета в очереди на публикацию.",
                      "Назначьте дату или опубликуйте сейчас — кнопки в карточке анкеты.",
                    ],
                    reopenLabel: "Открыть анкету",
                  })
                }
              >
                Отметить оплату вручную
              </button>
            </div>
          ) : null}

          {detail.status === "queued" ? (
            <div className="admin-actions">
              <label className="admin-label">Дата публикации (МСК)</label>
              <input
                type="datetime-local"
                className="admin-input admin-input--date"
                value={scheduleLocal}
                onChange={(e) => setScheduleLocal(e.target.value)}
              />
              <button
                type="button"
                className="admin-btn admin-btn--primary"
                disabled={busy || !scheduleLocal}
                onClick={() => {
                  const iso = `${scheduleLocal}:00+03:00`;
                  void run(() => adminScheduleProfile(detail.id, iso), "Дата назначена (МСК)", {
                    tone: "ok",
                    title: "Дата назначена",
                    subject: `${detail.name}, ${detail.age}`,
                    lines: [
                      `Анкета выйдет в канале ${formatDt(iso)} МСК.`,
                      "Пользователю отправлено уведомление с датой.",
                    ],
                    reopenLabel: "Открыть анкету",
                  });
                }}
              >
                Назначить дату
              </button>
              <button
                type="button"
                className="admin-btn"
                disabled={busy}
                onClick={() =>
                  void run(() => adminPublishNow(detail.id), "Опубликовано в канал", {
                    tone: "ok",
                    title: "Анкета опубликована",
                    subject: `${detail.name}, ${detail.age}`,
                    lines: [
                      "Заставка, фото и текст с кнопкой «Написать» уже в канале.",
                      "Пользователю отправлено уведомление.",
                    ],
                    reopenLabel: "Открыть анкету",
                  })
                }
              >
                Опубликовать сейчас
              </button>
              {detail.scheduled_at ? (
                <p className="admin-meta">Запланировано: {formatDt(detail.scheduled_at)} МСК</p>
              ) : null}
            </div>
          ) : null}

          <div className="admin-actions">
            <p className="admin-label">Пользователь · кредиты {detail.message_credits}</p>
            <div className="admin-row">
              <input
                className="admin-input"
                value={creditsDelta}
                onChange={(e) => setCreditsDelta(e.target.value)}
                inputMode="numeric"
              />
              <button
                type="button"
                className="admin-btn"
                disabled={busy}
                onClick={() =>
                  void run(
                    () => adminGrantCredits(detail.user_id, Number(creditsDelta) || 0),
                    "Кредиты обновлены",
                  )
                }
              >
                Начислить
              </button>
            </div>
            {detail.is_blocked ? (
              <button
                type="button"
                className="admin-btn"
                disabled={busy}
                onClick={() => void run(() => adminUnblockUser(detail.user_id), "Разблокирован")}
              >
                Разблокировать
              </button>
            ) : (
              <button
                type="button"
                className="admin-btn"
                disabled={busy}
                onClick={() => void run(() => adminBlockUser(detail.user_id), "Заблокирован")}
              >
                Заблокировать
              </button>
            )}
          </div>
        </article>
      ) : null}

      {selectedAdId != null && adDetail ? (
        <article className="admin-card admin-detail">
          <button type="button" className="admin-linkish" onClick={() => setSelectedAdId(null)}>
            ← К списку
          </button>
          <h2 className="admin-name">{adDetail.title}</h2>
          <p className="admin-meta">
            {statusRu(adDetail.status)} · {adCategoryRu(adDetail.category)} · @{adDetail.username || "—"} · tg{" "}
            {adDetail.user_telegram_id}
          </p>
          <p className="admin-body">{adDetail.body}</p>
          <p className="admin-meta">Контакт: {adDetail.contact || "—"}</p>
          <p className="admin-meta">Желаемая дата: {adDetail.desired_date || "—"}</p>
          {adDetail.scheduled_at ? (
            <p className="admin-meta">Слот: {formatDt(adDetail.scheduled_at)} МСК</p>
          ) : null}
          {adDetail.expires_at ? (
            <p className="admin-meta">Истекает: {formatDt(adDetail.expires_at)} МСК</p>
          ) : null}
          {adDetail.status === "rejected" && adDetail.moderation_feedback ? (
            <p className="admin-meta">Причина отклонения: {adDetail.moderation_feedback}</p>
          ) : null}

          {adDetail.status === "pending" ? (
            <div className="admin-actions">
              <button
                type="button"
                className="admin-btn admin-btn--primary"
                disabled={busy}
                onClick={() =>
                  void run(() => adminApproveAd(adDetail.id), "Реклама одобрена", {
                    tone: "ok",
                    title: "Реклама одобрена",
                    subject: adDetail.title,
                    lines: [
                      "Рекламодателю отправлен счёт на оплату слота.",
                      "После оплаты заявка встанет в очередь на ближайший свободный слот 10:00 МСК.",
                    ],
                    reopenLabel: "Открыть заявку",
                  })
                }
              >
                Одобрить → оплата
              </button>
              <textarea
                className="admin-input admin-textarea"
                placeholder="Причина отклонения"
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
              />
              <button
                type="button"
                className="admin-btn"
                disabled={busy || feedback.trim().length < 3}
                onClick={() =>
                  void run(() => adminRejectAd(adDetail.id, feedback.trim()), "Реклама отклонена", {
                    tone: "rejected",
                    title: "Реклама отклонена",
                    subject: adDetail.title,
                    lines: [
                      `Рекламодатель получил причину: «${feedback.trim()}».`,
                      "Заявка закрыта. Рекламодатель может отправить новую.",
                    ],
                    reopenLabel: "Открыть заявку",
                  })
                }
              >
                Отклонить
              </button>
            </div>
          ) : null}

          {adDetail.status === "awaiting_payment" ? (
            <div className="admin-actions">
              <button
                type="button"
                className="admin-btn"
                disabled={busy}
                onClick={() =>
                  void run(() => adminMarkAdPaid(adDetail.id), "Оплата рекламы отмечена", {
                    tone: "ok",
                    title: "Оплата рекламы отмечена",
                    subject: adDetail.title,
                    lines: [
                      "Заявка встала в очередь на ближайший свободный слот 10:00 МСК.",
                      "Пост выйдет автоматически, либо нажмите «Активировать сейчас» в карточке.",
                    ],
                    reopenLabel: "Открыть заявку",
                  })
                }
              >
                Отметить оплату вручную
              </button>
            </div>
          ) : null}

          {adDetail.status === "queued" ? (
            <div className="admin-actions">
              <button
                type="button"
                className="admin-btn admin-btn--primary"
                disabled={busy}
                onClick={() =>
                  void run(() => adminActivateAdNow(adDetail.id), "Реклама в канале", {
                    tone: "ok",
                    title: "Реклама опубликована",
                    subject: adDetail.title,
                    lines: [
                      "Пост уже в канале и снимется автоматически через 48 часов.",
                      "Рекламодателю отправлено уведомление.",
                    ],
                    reopenLabel: "Открыть заявку",
                  })
                }
              >
                Активировать сейчас
              </button>
            </div>
          ) : null}
        </article>
      ) : null}

      {selectedId == null &&
      selectedAdId == null &&
      (tab === "new" || tab === "queue" || tab === "published") ? (
        <>
          <ul className="admin-list">
            {items.length === 0 ? <li className="admin-empty">Пусто</li> : null}
            {items.map((item) => (
              <li key={item.id}>
                <button type="button" className="admin-list-item" onClick={() => setSelectedId(item.id)}>
                  {item.photo_url ? (
                    <img src={mediaUrl(item.photo_url)} alt="" loading="lazy" decoding="async" />
                  ) : (
                    <div className="admin-list-item__ph" />
                  )}
                  <div>
                    <strong>
                      {item.name}, {item.age}
                    </strong>
                    <span>
                      {statusRu(item.status)} · {item.city}
                    </span>
                    <span>@{item.telegram_username || "—"}</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
          {items.length > 0 ? (
            <div className="admin-list-footer">
              <p className="admin-list-footer__count">
                Показано {items.length} из {profilesTotal}
              </p>
              {profilesHasMore ? (
                <button
                  type="button"
                  className="admin-btn admin-btn--primary admin-btn--block"
                  disabled={profilesLoadingMore || busy}
                  onClick={() => void loadMoreProfiles()}
                >
                  {profilesLoadingMore ? "Загрузка…" : "Показать ещё"}
                </button>
              ) : (
                <p className="admin-list-footer__done">Это все анкеты в разделе</p>
              )}
            </div>
          ) : null}
        </>
      ) : null}

      {selectedAdId == null && tab === "ads" ? (
        <ul className="admin-list">
          {ads.length === 0 ? <li className="admin-empty">Пусто</li> : null}
          {ads.map((ad) => (
            <li key={ad.id}>
              <button type="button" className="admin-list-item" onClick={() => setSelectedAdId(ad.id)}>
                <div className="admin-list-item__ph" />
                <div>
                  <strong>
                    #{ad.id} · {ad.title}
                  </strong>
                  <span>
                    {statusRu(ad.status)} · {adCategoryRu(ad.category)}
                  </span>
                  <span>@{ad.username || ad.user_telegram_id || "—"}</span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      {tab === "complaints" ? (
        <ul className="admin-list">
          {complaints.length === 0 ? <li className="admin-empty">Нет открытых жалоб</li> : null}
          {complaints.map((c) => (
            <li key={c.id} className="admin-payment">
              <strong>
                #{c.id} · {statusRu(c.status)}
              </strong>
              <span>
                от {c.reporter_telegram_id || c.reporter_user_id} → на пользователя {c.reported_user_id || "—"}
                {c.message_request_id ? ` · письмо #${c.message_request_id}` : ""}
              </span>
              <span>{c.reason}</span>
              <span>{formatDt(c.created_at)}</span>
              <div className="admin-row" style={{ marginTop: 8, gap: 8 }}>
                <button
                  type="button"
                  className="admin-btn"
                  disabled={busy}
                  onClick={() =>
                    void run(() => adminResolveComplaint(c.id, "resolved"), "Жалоба закрыта")
                  }
                >
                  Решить
                </button>
                <button
                  type="button"
                  className="admin-btn"
                  disabled={busy}
                  onClick={() =>
                    void run(() => adminResolveComplaint(c.id, "dismissed"), "Жалоба отклонена")
                  }
                >
                  Отклонить
                </button>
                {c.reported_user_id ? (
                  <button
                    type="button"
                    className="admin-btn"
                    disabled={busy}
                    onClick={() =>
                      void run(() => adminBlockUser(c.reported_user_id!), "Пользователь заблокирован")
                    }
                  >
                    Блок
                  </button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      {selectedId == null && tab === "users" ? (
        <>
          <ul className="admin-list">
            {users.length === 0 ? <li className="admin-empty">Пусто</li> : null}
            {users.map((u) => (
              <li key={u.id}>
                <button
                  type="button"
                  className="admin-list-item"
                  onClick={() => (u.profile_id ? setSelectedId(u.profile_id) : undefined)}
                >
                  {u.photo_url ? (
                    <img src={mediaUrl(u.photo_url)} alt="" loading="lazy" decoding="async" />
                  ) : (
                    <div className="admin-list-item__ph" />
                  )}
                  <div>
                    <strong>
                      {u.first_name || "—"} · {u.telegram_id}
                    </strong>
                    <span>
                      @{u.username || "—"} · ★{u.message_credits}
                      {u.is_blocked ? " · заблокирован" : ""}
                    </span>
                    <span>
                      {u.profile_name || "без анкеты"}
                      {u.profile_status ? ` · ${statusRu(u.profile_status)}` : ""}
                    </span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
          {users.length > 0 ? (
            <div className="admin-list-footer">
              <p className="admin-list-footer__count">
                Показано {users.length} из {usersTotal}
              </p>
              {usersHasMore ? (
                <button
                  type="button"
                  className="admin-btn admin-btn--primary admin-btn--block"
                  disabled={usersLoadingMore || busy}
                  onClick={() => void loadMoreUsers()}
                >
                  {usersLoadingMore ? "Загрузка…" : "Показать ещё"}
                </button>
              ) : (
                <p className="admin-list-footer__done">Это все пользователи</p>
              )}
            </div>
          ) : null}
        </>
      ) : null}

      {tab === "payments" ? (
        <ul className="admin-list">
          {payments.map((p) => (
            <li key={p.id} className="admin-payment">
              <strong>
                #{p.id} · {paymentProductRu(p.product)} · {p.stars_amount}★
              </strong>
              <span>
                {paymentStatusRu(p.status)} · @{p.username || p.telegram_id || "—"}
              </span>
              <span>{formatDt(p.completed_at || p.created_at)}</span>
            </li>
          ))}
        </ul>
      ) : null}

      {tab === "stats" && stats ? (
        <div className="admin-stats">
          <div>
            <strong>{stats.profiles_new}</strong>
            <span>анкеты на модерации</span>
          </div>
          <div>
            <strong>{stats.profiles_rejected}</strong>
            <span>анкеты отклонены</span>
          </div>
          <div>
            <strong>{stats.profiles_published}</strong>
            <span>опубликованы</span>
          </div>
          <div>
            <strong>{stats.stars_earned}</strong>
            <span>звёзд заработано</span>
          </div>
          <div>
            <strong>{stats.publish_payments}</strong>
            <span>оплаты публикации</span>
          </div>
          <div>
            <strong>{stats.credit_payments ?? 0}</strong>
            <span>оплаты кредитов</span>
          </div>
          <div>
            <strong>{stats.ad_payments ?? 0}</strong>
            <span>оплаты рекламы</span>
          </div>
          <div>
            <strong>{stats.credits_granted ?? 0}</strong>
            <span>кредиты бонусом</span>
          </div>
          <div>
            <strong>{stats.letters_pending ?? 0}</strong>
            <span>письма ждут ответа</span>
          </div>
          <div>
            <strong>{stats.letters_rejected ?? 0}</strong>
            <span>письма отклонены</span>
          </div>
          <div>
            <strong>{stats.letters_unlocked ?? 0}</strong>
            <span>письма открыты</span>
          </div>
          <div>
            <strong>{stats.ads_pending ?? 0}</strong>
            <span>реклама на модерации</span>
          </div>
          <div>
            <strong>{stats.ads_active ?? 0}</strong>
            <span>реклама в канале</span>
          </div>
          <div>
            <strong>{stats.complaints_open ?? 0}</strong>
            <span>открытые жалобы</span>
          </div>
          <div>
            <strong>{stats.users_total}</strong>
            <span>пользователей</span>
          </div>
          <div>
            <strong>{stats.users_blocked}</strong>
            <span>заблокированы</span>
          </div>
          <div>
            <strong>{stats.users_soft_banned ?? 0}</strong>
            <span>временно ограничены</span>
          </div>
        </div>
      ) : null}
        </>
      )}
    </section>
  );
}
