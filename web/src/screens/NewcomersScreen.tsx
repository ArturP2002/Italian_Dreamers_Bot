import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { type Language, t } from "../i18n/messages";
import { fetchNewcomers, mediaUrl, type CatalogCard } from "../lib/api";

type Props = { language: Language };

export function NewcomersScreen({ language }: Props) {
  const [items, setItems] = useState<CatalogCard[]>([]);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    void fetchNewcomers()
      .then((data) => setItems(data.items))
      .finally(() => setBusy(false));
  }, []);

  return (
    <section className="screen screen--milky screen--catalog">
      <Link to="/" className="work-back">
        ← {t(language, "backHome")}
      </Link>
      <h1 className="work-title">{t(language, "newcomersTitle")}</h1>
      <p className="work-body">{t(language, "newcomersHint")}</p>

      <div className="catalog-grid">
        {items.map((item) => {
          const cover = item.photo_urls[0];
          return (
            <div key={item.id} className="catalog-card">
              <div className="catalog-card__media">
                <Link to={`/catalog/${item.id}`} className="catalog-card__photo-link" tabIndex={-1}>
                  {cover ? <img src={mediaUrl(cover)} alt="" /> : <div className="catalog-card__ph" />}
                </Link>
              </div>
              <Link to={`/write/${item.id}`} className="catalog-card__link">
                <strong>
                  {item.name}, {item.age}
                </strong>
                <span>{item.city}</span>
                <em>{t(language, "newcomersWrite")}</em>
              </Link>
            </div>
          );
        })}
      </div>

      {!busy && items.length === 0 ? <p className="home-meta">{t(language, "newcomersEmpty")}</p> : null}
    </section>
  );
}
