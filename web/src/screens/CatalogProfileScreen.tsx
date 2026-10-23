import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { type Language, t } from "../i18n/messages";
import { fetchCatalogProfile, mediaUrl, toggleCatalogLike, type CatalogProfile } from "../lib/api";

type Props = { language: Language };

export function CatalogProfileScreen({ language }: Props) {
  const { id } = useParams();
  const profileId = Number(id);
  const [profile, setProfile] = useState<CatalogProfile | null>(null);

  useEffect(() => {
    if (!Number.isFinite(profileId)) return;
    void fetchCatalogProfile(profileId).then(setProfile);
  }, [profileId]);

  if (!profile) {
    return (
      <section className="screen screen--milky">
        <Link to="/catalog" className="work-back">
          ← {t(language, "catalogTitle")}
        </Link>
        <p className="home-meta">{t(language, "saving")}</p>
      </section>
    );
  }

  return (
    <section className="screen screen--milky">
      <Link to="/catalog" className="work-back">
        ← {t(language, "catalogTitle")}
      </Link>
      <div className="catalog-detail-photos">
        {profile.photo_urls.map((url) => (
          <img key={url} src={mediaUrl(url)} alt="" />
        ))}
      </div>
      <h1 className="work-title">
        {profile.is_top ? "↑ " : ""}
        {profile.verified ? "✓ " : ""}
        {profile.name}, {profile.age}
      </h1>
      <p className="home-meta">
        {profile.city}
        {profile.country ? `, ${profile.country}` : ""}
        {profile.profession ? ` · ${profile.profession}` : ""}
        {profile.height_cm ? ` · ${profile.height_cm} см` : ""}
      </p>
      {profile.status === "queued" ? <p className="home-meta">{t(language, "catalogQueued")}</p> : null}

      <h2 className="admin-section-label">{t(language, "catalogAbout")}</h2>
      <p className="work-body">{profile.about}</p>
      {profile.hobbies ? <p className="work-body">{profile.hobbies}</p> : null}

      <h2 className="admin-section-label">
        {t(language, "catalogLooking")} · {profile.age_min}–{profile.age_max}
      </h2>
      <p className="work-body">{profile.desired_partner}</p>

      {!profile.is_mine ? (
        <button
          type="button"
          className={`btn btn--block ${profile.liked ? "btn--champagne" : "btn--ghost"}`}
          onClick={() => {
            void toggleCatalogLike(profile.id).then((res) => {
              setProfile({ ...profile, liked: res.liked, matched: res.matched });
            });
          }}
        >
          {profile.matched
            ? t(language, "catalogMatch")
            : profile.liked
              ? t(language, "catalogLiked")
              : t(language, "catalogLike")}
        </button>
      ) : null}

      {profile.is_mine ? (
        <p className="home-meta">{t(language, "catalogMine")}</p>
      ) : profile.already_written && profile.active_request_id ? (
        <Link to={`/inbox/${profile.active_request_id}`} className="btn btn--block btn--dark">
          {t(language, "catalogOpenLetter")}
        </Link>
      ) : profile.already_written ? (
        <p className="home-meta">{t(language, "catalogAlreadyWritten")}</p>
      ) : (
        <Link to={`/write/${profile.id}`} className="btn btn--block btn--dark">
          {t(language, "catalogWrite")}
        </Link>
      )}
    </section>
  );
}
