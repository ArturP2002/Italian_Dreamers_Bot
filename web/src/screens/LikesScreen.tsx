import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { LikeHeart } from "../components/LikeHeart";
import { type Language, t } from "../i18n/messages";
import { fetchLikes, mediaUrl, toggleCatalogLike, type CatalogCard } from "../lib/api";

type Props = { language: Language };
type Kind = "sent" | "received";

export function LikesScreen({ language }: Props) {
  const [kind, setKind] = useState<Kind>("received");
  const [items, setItems] = useState<CatalogCard[]>([]);

  useEffect(() => {
    void fetchLikes(kind).then((data) => setItems(data.items));
  }, [kind]);

  return (
    <section className="screen screen--milky">
      <Link to="/" className="work-back work-back--sticky">
        ← {t(language, "backHome")}
      </Link>
      <h1 className="work-title">{t(language, "likesTitle")}</h1>
      <div className="catalog-filters">
        <button
          type="button"
          className={`admin-btn admin-filter${kind === "received" ? " is-active" : ""}`}
          onClick={() => setKind("received")}
        >
          {t(language, "likesReceived")}
        </button>
        <button
          type="button"
          className={`admin-btn admin-filter${kind === "sent" ? " is-active" : ""}`}
          onClick={() => setKind("sent")}
        >
          {t(language, "likesSent")}
        </button>
      </div>
      <div className="catalog-grid">
        {items.map((item, i) =>
          item.id ? (
            <div key={item.id} className="catalog-card">
              <div className="catalog-card__media">
                <Link to={`/catalog/${item.id}`} className="catalog-card__photo-link" tabIndex={-1}>
                  {item.photo_urls[0] ? (
                    <img src={mediaUrl(item.photo_urls[0])} alt="" />
                  ) : (
                    <div className="catalog-card__ph" />
                  )}
                </Link>
                <LikeHeart
                  liked={item.liked || kind === "sent"}
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
                  {item.name}
                  {item.age ? `, ${item.age}` : ""}
                </strong>
                <span>{item.city}</span>
                {item.matched ? <em className="catalog-card__match">{t(language, "catalogMatchTitle")}</em> : null}
              </Link>
            </div>
          ) : (
            <div key={`anon-${i}`} className="catalog-card">
              <div className="catalog-card__media">
                <div className="catalog-card__ph" />
              </div>
              <div className="catalog-card__link">
                <strong>{item.name}</strong>
                {item.matched ? <em className="catalog-card__match">{t(language, "catalogMatchTitle")}</em> : null}
              </div>
            </div>
          ),
        )}
      </div>
      {items.length === 0 ? (
        <div className="likes-empty">
          <span className="likes-empty__icon" aria-hidden>
            ♡
          </span>
          <strong>{t(language, "likesEmpty")}</strong>
          <p>{t(language, "likesEmptyHint")}</p>
        </div>
      ) : null}
    </section>
  );
}
