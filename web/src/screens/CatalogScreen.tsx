import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { LikeHeart } from "../components/LikeHeart";
import { type Language, t } from "../i18n/messages";
import { fetchCatalog, mediaUrl, toggleCatalogLike, type CatalogCard, type MeUser } from "../lib/api";
import { formatCount } from "../lib/writePath";

type Props = { language: Language; me?: MeUser | null };

type GenderFilter = "all" | "female" | "male";

export function CatalogScreen({ language, me = null }: Props) {
  const navigate = useNavigate();
  const [isRegistered, setIsRegistered] = useState<boolean>(me?.is_registered !== false);
  const [totalCount, setTotalCount] = useState<number | null>(null);
  const [gateReached, setGateReached] = useState(false);
  const [items, setItems] = useState<CatalogCard[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [gender, setGender] = useState<GenderFilter | null>(null);
  const [ageMin, setAgeMin] = useState("");
  const [ageMax, setAgeMax] = useState("");
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (
      reset: boolean,
      nextCursor?: string | null,
      nextGender?: GenderFilter | null,
      nextVerified?: boolean,
    ) => {
      setBusy(true);
      setError(null);
      try {
        const g = nextGender ?? gender;
        const page = await fetchCatalog({
          gender: g === "all" ? "all" : g,
          ageMin: ageMin ? Number(ageMin) : null,
          ageMax: ageMax ? Number(ageMax) : null,
          verified: nextVerified ?? verifiedOnly,
          cursor: reset ? null : nextCursor,
        });
        if (!page) {
          setError(t(language, "errorGeneric"));
          return;
        }
        if (g == null && (page.gender === "male" || page.gender === "female")) {
          setGender(page.gender);
        } else if (g == null) {
          setGender("all");
        }
        setIsRegistered(page.is_registered !== false);
        setTotalCount(page.total_count ?? null);
        setGateReached(Boolean(page.gate_reached));
        setItems((prev) => (reset ? page.items : [...prev, ...page.items]));
        setCursor(page.next_cursor);
      } catch {
        setError(t(language, "errorGeneric"));
      } finally {
        setBusy(false);
      }
    },
    [ageMax, ageMin, gender, language, verifiedOnly],
  );

  useEffect(() => {
    void load(true, null, gender);
    // initial + when gender chosen from API
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const applyFilters = (next?: GenderFilter) => {
    const g = next ?? gender ?? "all";
    if (next) setGender(next);
    void load(true, null, g);
  };

  const guest = !isRegistered;
  const showGate = guest && (gateReached || items.some((i) => i.blurred));
  const goCreateProfile = () => navigate("/profile");

  return (
    <section
      className={`screen screen--milky screen--catalog${showGate ? " screen--with-sheet" : ""}`}
    >
      <Link to="/" className="work-back">
        ← {t(language, "backHome")}
      </Link>
      <h1 className="work-title">{t(language, "catalogTitle")}</h1>

      <div className="catalog-filters" role="group" aria-label={t(language, "catalogFilters")}>
        {(
          [
            ["all", "catalogGenderAll"],
            ["female", "catalogGenderWomen"],
            ["male", "catalogGenderMen"],
          ] as const
        ).map(([id, key]) => (
          <button
            key={id}
            type="button"
            className={`admin-btn admin-filter${gender === id ? " is-active" : ""}`}
            onClick={() => applyFilters(id)}
          >
            {t(language, key)}
          </button>
        ))}
      </div>
      <div className="catalog-age">
        <label>
          {t(language, "catalogAge")}
          <input
            className="admin-input"
            inputMode="numeric"
            placeholder="18"
            value={ageMin}
            onChange={(e) => setAgeMin(e.target.value.replace(/\D/g, "").slice(0, 2))}
          />
        </label>
        <span>—</span>
        <input
          className="admin-input"
          inputMode="numeric"
          placeholder="99"
          value={ageMax}
          onChange={(e) => setAgeMax(e.target.value.replace(/\D/g, "").slice(0, 2))}
        />
        <button type="button" className="admin-btn" onClick={() => applyFilters()}>
          OK
        </button>
        <button
          type="button"
          className={`admin-btn admin-filter catalog-verified-filter${verifiedOnly ? " is-active" : ""}`}
          onClick={() => {
            const next = !verifiedOnly;
            setVerifiedOnly(next);
            void load(true, null, gender, next);
          }}
        >
          <span className="catalog-verified-filter__icon" aria-hidden>
            ✓
          </span>
          {t(language, "catalogVerifiedOnly")}
        </button>
      </div>

      {error ? <p className="home-meta">{error}</p> : null}

      <div className="catalog-grid">
        {items.map((item) => {
          const cover = item.photo_urls[0];
          if (item.blurred) {
            return (
              <div key={item.id} className="catalog-card catalog-card--blurred" aria-hidden>
                <div className="catalog-card__media">
                  {cover ? <img src={mediaUrl(cover)} alt="" /> : <div className="catalog-card__ph" />}
                </div>
                <div className="catalog-card__link catalog-card__link--bars">
                  <i />
                  <i />
                </div>
              </div>
            );
          }
          return (
            <div key={item.id} className="catalog-card">
              <div className="catalog-card__media">
                <Link to={`/catalog/${item.id}`} className="catalog-card__photo-link" tabIndex={-1}>
                  {cover ? (
                    <img src={mediaUrl(cover)} alt="" />
                  ) : (
                    <div className="catalog-card__ph" />
                  )}
                </Link>
                {item.is_top ? (
                  <span className="catalog-card__badge catalog-card__badge--top" aria-hidden>
                    ↑
                  </span>
                ) : item.is_new ? (
                  <span className="catalog-card__badge catalog-card__badge--new" aria-hidden>
                    NEW
                  </span>
                ) : null}
                {item.verified && !item.is_top && !item.is_new ? (
                  <span className="catalog-card__badge catalog-card__badge--verified" aria-hidden>
                    ✓
                  </span>
                ) : item.verified ? (
                  <span
                    className="catalog-card__badge catalog-card__badge--verified catalog-card__badge--offset"
                    aria-hidden
                  >
                    ✓
                  </span>
                ) : null}
                {!guest ? (
                  <LikeHeart
                    liked={item.liked}
                    matched={item.matched}
                    className="like-heart--card-br"
                    aria-label={t(language, "catalogLike")}
                    onClick={() => {
                      void toggleCatalogLike(item.id)
                        .then((res) => {
                          setItems((prev) =>
                            prev.map((p) =>
                              p.id === item.id ? { ...p, liked: res.liked, matched: res.matched } : p,
                            ),
                          );
                        })
                        .catch((e: unknown) => {
                          if (e instanceof Error && e.message.includes("registration_required")) {
                            goCreateProfile();
                          }
                        });
                    }}
                  />
                ) : null}
              </div>
              <Link to={`/catalog/${item.id}`} className="catalog-card__link">
                <strong>
                  {item.name}, {item.age}
                </strong>
                <span>{item.city}</span>
                {item.matched ? (
                  <em className="catalog-card__match">{t(language, "catalogMatchTitle")}</em>
                ) : item.already_written ? (
                  <em>{t(language, "catalogAlreadyWritten")}</em>
                ) : item.status === "queued" ? (
                  <em>{t(language, "catalogQueued")}</em>
                ) : null}
              </Link>
            </div>
          );
        })}
      </div>

      {items.length === 0 && !busy ? (
        <p className="home-meta">
          {t(language, guest ? "catalogGateTomorrow" : "catalogEmpty")}
        </p>
      ) : null}

      {cursor ? (
        <button
          type="button"
          className="btn btn--block btn--dark"
          disabled={busy}
          onClick={() => void load(false, cursor)}
        >
          {busy ? t(language, "saving") : t(language, "catalogLoadMore")}
        </button>
      ) : null}

      {showGate ? (
        <aside className="catalog-gate" role="dialog" aria-label={t(language, "catalogGateTitle")}>
          <h2 className="catalog-gate__title">{t(language, "catalogGateTitle")}</h2>
          <p className="catalog-gate__body">
            <strong>{t(language, "catalogGateBodyA")}</strong>
            {t(language, "catalogGateBodyB")}
            <strong>{formatCount(totalCount ?? 0, language)}</strong>
            {t(language, "catalogGateBodyC")}
          </p>
          <button
            type="button"
            className="btn btn--plum btn--block btn--pill"
            onClick={goCreateProfile}
          >
            {t(language, "catalogGateCta")}
          </button>
          <p className="catalog-gate__foot">{t(language, "catalogGateFoot")}</p>
        </aside>
      ) : null}
    </section>
  );
}
