import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { type Language, t, tf } from "../i18n/messages";
import { fetchCatalogStats, fetchMessage, mediaUrl, type CatalogStats, type MeUser } from "../lib/api";
import { formatCount } from "../lib/writePath";
import { ensureWriteAccess } from "../lib/writeAccess";

type Props = {
  language: Language;
  me: MeUser | null;
  onMeRefresh?: () => void;
};

const STATS_REFRESH_MS = 30_000;

/** TZ screen 3: «Сообщение отправлено» + native requestWriteAccess on top. */
export function WaitingSentScreen({ language, me, onMeRefresh }: Props) {
  const { id } = useParams();
  const navigate = useNavigate();
  const requestId = Number(id);
  const [recipient, setRecipient] = useState<string>("");
  const [stats, setStats] = useState<CatalogStats | null>(null);
  const askedRef = useRef(false);

  useEffect(() => {
    if (!Number.isFinite(requestId)) return;
    void fetchMessage(requestId).then((item) => {
      if (item?.profile_name) setRecipient(item.profile_name);
    });
  }, [requestId]);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      void fetchCatalogStats().then((data) => {
        if (!cancelled && data) setStats(data);
      });
    load();
    const timer = window.setInterval(load, STATS_REFRESH_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  // Ask for write access once, after navigation, only if not granted yet.
  useEffect(() => {
    if (askedRef.current || me === null) return;
    askedRef.current = true;
    if (me.bot_write_access) return;
    void ensureWriteAccess().then(() => onMeRefresh?.());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [me]);

  const teasers = (stats?.teaser_photo_urls ?? []).slice(0, 6);
  const name = recipient || "…";

  return (
    <section className="screen screen--milky waiting-screen">
      <Link to="/" className="work-back work-back--gold">
        ← {t(language, "backHome")}
      </Link>

      <div className="waiting-check" aria-hidden>
        <svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
          <path d="m5 12.5 4.5 4.5L19 7.5" />
        </svg>
      </div>
      <h1 className="waiting-title">{t(language, "waitingSentTitle")}</h1>
      <p className="waiting-body">{tf(language, "waitingSentBody", { name })}</p>

      <article className="waiting-card">
        {teasers.length > 0 ? (
          <div className="waiting-card__grid">
            {teasers.map((url, i) => (
              <img key={`${url}-${i}`} src={mediaUrl(url)} alt="" />
            ))}
            <div className="waiting-card__glass" />
            <div className="waiting-card__fade" />
          </div>
        ) : null}
        <div className="waiting-card__body">
          <h2 className="waiting-card__title">{t(language, "waitingTitle")}</h2>
          {stats ? (
            <p className="waiting-card__count">
              {tf(language, "waitingCount", { count: formatCount(stats.total_count, language) })}
            </p>
          ) : null}
          <button
            type="button"
            className="btn btn--plum btn--block btn--pill"
            onClick={() => navigate("/catalog")}
          >
            {t(language, "waitingCta")}
          </button>
        </div>
      </article>

      <Link to="/" className="waiting-home-link">
        {t(language, "backHome")}
      </Link>
    </section>
  );
}
