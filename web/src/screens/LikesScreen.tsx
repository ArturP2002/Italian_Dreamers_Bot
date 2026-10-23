import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { type Language, t } from "../i18n/messages";
import { fetchLikes, mediaUrl, type CatalogCard } from "../lib/api";

type Props = { language: Language };
type Kind = "sent" | "received";

export function LikesScreen({ language }: Props) {
  const [kind, setKind] = useState<Kind>("sent");
  const [items, setItems] = useState<CatalogCard[]>([]);

  useEffect(() => {
    void fetchLikes(kind).then((data) => setItems(data.items));
  }, [kind]);

  return (
    <section className="screen screen--milky">
      <Link to="/" className="work-back">
        ← {t(language, "backHome")}
      </Link>
      <h1 className="work-title">{t(language, "likesTitle")}</h1>
      <div className="catalog-filters">
        <button
          type="button"
          className={`admin-btn admin-filter${kind === "sent" ? " is-active" : ""}`}
          onClick={() => setKind("sent")}
        >
          {t(language, "likesSent")}
        </button>
        <button
          type="button"
          className={`admin-btn admin-filter${kind === "received" ? " is-active" : ""}`}
          onClick={() => setKind("received")}
        >
          {t(language, "likesReceived")}
        </button>
      </div>
      <div className="catalog-grid">
        {items.map((item, i) =>
          item.id ? (
            <Link key={item.id} to={`/catalog/${item.id}`} className="catalog-card">
              <div className="catalog-card__photos">
                {(item.photo_urls[0] ? [item.photo_urls[0]] : [""]).map((url, idx) =>
                  url ? <img key={url} src={mediaUrl(url)} alt="" /> : <div key={idx} className="catalog-card__ph" />,
                )}
              </div>
              <strong>
                {item.verified ? "✓ " : ""}
                {item.name}
                {item.age ? `, ${item.age}` : ""}
              </strong>
              <span>{item.city}</span>
              {item.matched ? <em>{t(language, "catalogMatch")}</em> : null}
            </Link>
          ) : (
            <div key={`anon-${i}`} className="catalog-card">
              <strong>{item.name}</strong>
              {item.matched ? <em>{t(language, "catalogMatch")}</em> : null}
            </div>
          ),
        )}
      </div>
      {items.length === 0 ? <p className="home-meta">{t(language, "likesEmpty")}</p> : null}
    </section>
  );
}
