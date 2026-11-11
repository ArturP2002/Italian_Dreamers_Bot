import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { LikeHeart } from "../components/LikeHeart";
import { type Language, t } from "../i18n/messages";
import { fetchCatalog, mediaUrl, toggleCatalogLike, type CatalogCard } from "../lib/api";

type Props = { language: Language };

type GenderFilter = "all" | "female" | "male";

export function CatalogScreen({ language }: Props) {
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

  return (
    <section className="screen screen--milky">
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
          className={`admin-btn admin-filter${verifiedOnly ? " is-active" : ""}`}
          onClick={() => {
            const next = !verifiedOnly;
            setVerifiedOnly(next);
            void load(true, null, gender, next);
          }}
        >
          {t(language, "catalogVerifiedOnly")}
        </button>
      </div>

      {error ? <p className="home-meta">{error}</p> : null}

      <div className="catalog-grid">
        {items.map((item) => {
          const cover = item.photo_urls[0];
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
                ) : null}
                {item.verified ? (
                  <span className="catalog-card__badge catalog-card__badge--verified" aria-hidden>
                    ✓
                  </span>
                ) : null}
                <LikeHeart
                  liked={item.liked}
                  matched={item.matched}
                  className="like-heart--card-br"
                  aria-label={t(language, "catalogLike")}
                  onClick={() => {
                    void toggleCatalogLike(item.id).then((res) => {
                      setItems((prev) =>
                        prev.map((p) =>
                          p.id === item.id ? { ...p, liked: res.liked, matched: res.matched } : p,
                        ),
                      );
                    });
                  }}
                />
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

      {items.length === 0 && !busy ? <p className="home-meta">{t(language, "catalogEmpty")}</p> : null}

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
    </section>
  );
}
