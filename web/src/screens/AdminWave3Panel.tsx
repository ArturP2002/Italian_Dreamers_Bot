import { useEffect, useState } from "react";
import {
  adminCreateLegacy,
  adminDecideVerification,
  adminFetchComments,
  adminFetchLegacy,
  adminFetchReports,
  adminFetchVerifications,
  adminInviteLegacy,
  adminMarkCommentFp,
  adminSkipLegacy,
  mediaUrl,
  type AdminComment,
  type AdminLegacy,
  type AdminVerification,
  type AdminWeeklyReport,
} from "../lib/api";

type Tab = "verify" | "legacy" | "comments" | "reports";

export function AdminWave3Panel({ tab }: { tab: Tab }) {
  const [verifications, setVerifications] = useState<AdminVerification[]>([]);
  const [legacy, setLegacy] = useState<AdminLegacy[]>([]);
  const [comments, setComments] = useState<AdminComment[]>([]);
  const [reports, setReports] = useState<AdminWeeklyReport[]>([]);
  const [name, setName] = useState("");
  const [nick, setNick] = useState("");
  const [error, setError] = useState<string | null>(null);

  const reload = async () => {
    setError(null);
    try {
      if (tab === "verify") setVerifications(await adminFetchVerifications());
      if (tab === "legacy") setLegacy(await adminFetchLegacy());
      if (tab === "comments") setComments(await adminFetchComments("delete"));
      if (tab === "reports") setReports(await adminFetchReports());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Load failed");
    }
  };

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  return (
    <div>
      {error ? <p className="form-error">{error}</p> : null}

      {tab === "verify" ? (
        <ul className="admin-list">
          {verifications.map((v) => (
            <li key={v.id} className="admin-payment">
              {v.photo_url ? <img src={mediaUrl(v.photo_url)} alt="" style={{ width: 72, height: 96, objectFit: "cover" }} /> : null}
              <strong>
                {v.name}, {v.age} · {v.city}
              </strong>
              <span>@{v.username || v.user_telegram_id || "—"}</span>
              <div className="admin-row-actions">
                <button type="button" className="admin-btn" onClick={() => void adminDecideVerification(v.id, true).then(() => reload())}>
                  Ок
                </button>
                <button type="button" className="admin-btn" onClick={() => void adminDecideVerification(v.id, false).then(() => reload())}>
                  Отклонить
                </button>
              </div>
            </li>
          ))}
          {verifications.length === 0 ? <p className="home-meta">Нет селфи на проверке.</p> : null}
        </ul>
      ) : null}

      {tab === "legacy" ? (
        <div>
          <div className="admin-search-row">
            <input className="admin-input" placeholder="Имя" value={name} onChange={(e) => setName(e.target.value)} />
            <input className="admin-input" placeholder="@ник" value={nick} onChange={(e) => setNick(e.target.value)} />
            <button
              type="button"
              className="admin-btn"
              onClick={() => {
                if (!name.trim()) return;
                void adminCreateLegacy({ name: name.trim(), telegram_username: nick.trim() || undefined }).then(() => {
                  setName("");
                  setNick("");
                  void reload();
                });
              }}
            >
              Добавить
            </button>
          </div>
          <ul className="admin-list">
            {legacy.map((row) => (
              <li key={row.id} className="admin-payment">
                <strong>
                  {row.name} · {row.status}
                </strong>
                <span>
                  @{row.telegram_username || "—"} {row.invite_token ? `· token ${row.invite_token}` : ""}
                </span>
                <div className="admin-row-actions">
                  <button type="button" className="admin-btn" onClick={() => void adminInviteLegacy(row.id).then(() => reload())}>
                    Инвайт
                  </button>
                  <button type="button" className="admin-btn" onClick={() => void adminSkipLegacy(row.id).then(() => reload())}>
                    Пропуск
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {tab === "comments" ? (
        <ul className="admin-list">
          {comments.map((c) => (
            <li key={c.id} className="admin-payment">
              <strong>
                @{c.username || c.telegram_user_id} · {c.decision}
              </strong>
              <span>{c.text}</span>
              <span>{c.reason}</span>
              {c.decision === "delete" ? (
                <button type="button" className="admin-btn" onClick={() => void adminMarkCommentFp(c.id).then(() => reload())}>
                  Ложное
                </button>
              ) : null}
            </li>
          ))}
          {comments.length === 0 ? <p className="home-meta">Удалённых комментариев нет.</p> : null}
        </ul>
      ) : null}

      {tab === "reports" ? (
        <ul className="admin-list">
          {reports.map((r) => (
            <li key={r.id} className="admin-payment">
              <strong>
                {new Date(r.period_start).toLocaleDateString()} – {new Date(r.period_end).toLocaleDateString()}
              </strong>
              <span>
                users {r.payload.users_new ?? 0} · profiles {r.payload.profiles_new ?? 0} · ★ {r.payload.stars_earned ?? 0} · likes{" "}
                {r.payload.likes ?? 0} · matches {r.payload.matches ?? 0} · del {r.payload.comments_deleted ?? 0}
              </span>
            </li>
          ))}
          {reports.length === 0 ? <p className="home-meta">Отчётов пока нет — первый уйдёт в воскресенье в 19:00 по Риму.</p> : null}
        </ul>
      ) : null}
    </div>
  );
}
