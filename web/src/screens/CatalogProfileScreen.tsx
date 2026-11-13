import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { LikeHeart, MatchBanner } from "../components/LikeHeart";
import { PhotoLightbox } from "../components/PhotoLightbox";
import { type Language, t } from "../i18n/messages";
import {
  fetchCatalogProfile,
  mediaUrl,
  toggleCatalogLike,
  type CatalogProfile,
  type MeUser,
} from "../lib/api";

type Props = { language: Language; me?: MeUser | null };

export function CatalogProfileScreen({ language, me = null }: Props) {
  const navigate = useNavigate();
  const guest = me?.is_registered === false;
  const { id } = useParams();
  const profileId = Number(id);
  const [profile, setProfile] = useState<CatalogProfile | null>(null);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

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

  const photos = profile.photo_urls.map((url) => mediaUrl(url)).filter(Boolean) as string[];
  const heightUnit = language === "it" ? "cm" : "см";

  return (
    <section className="screen screen--milky">
      <Link to="/catalog" className="work-back">
        ← {t(language, "catalogTitle")}
      </Link>
      <div className="catalog-detail-photos">
        {profile.photo_urls.map((url, index) => (
          <div key={url} className="catalog-detail-photos__item">
            <button
              type="button"
              className="catalog-detail-photos__open"
              onClick={() => setLightboxIndex(index)}
              aria-label={`${profile.name} ${index + 1}`}
            >
              <img src={mediaUrl(url)} alt="" />
            </button>
            {index === 0 && !profile.is_mine && !guest ? (
              <LikeHeart
                liked={profile.liked}
                matched={profile.matched}
                className="like-heart--on-photo"
                aria-label={t(language, "catalogLike")}
                onClick={() => {
                  void toggleCatalogLike(profile.id)
                    .then((res) => {
                      setProfile({ ...profile, liked: res.liked, matched: res.matched });
                    })
                    .catch((e: unknown) => {
                      if (e instanceof Error && e.message.includes("registration_required")) {
                        navigate("/profile");
                      }
                    });
                }}
              />
            ) : null}
          </div>
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
        {profile.height_cm ? ` · ${profile.height_cm} ${heightUnit}` : ""}
      </p>
      {profile.status === "queued" ? <p className="home-meta">{t(language, "catalogQueued")}</p> : null}

      {profile.matched ? (
        <MatchBanner title={t(language, "catalogMatchTitle")} hint={t(language, "catalogMatchHint")} />
      ) : null}

      <h2 className="admin-section-label">{t(language, "catalogAbout")}</h2>
      <p className="work-body">{profile.about}</p>
      {profile.hobbies ? <p className="work-body">{profile.hobbies}</p> : null}

      <h2 className="admin-section-label">
        {t(language, "catalogLooking")} · {profile.age_min}–{profile.age_max}
      </h2>
      <p className="work-body">{profile.desired_partner}</p>

      <div className="catalog-detail-actions">
        {!profile.is_mine && !profile.matched && !guest ? (
          <button
            type="button"
            className={`btn btn--block ${profile.liked ? "btn--champagne" : "btn--outline"}`}
            onClick={() => {
              void toggleCatalogLike(profile.id)
                .then((res) => {
                  setProfile({ ...profile, liked: res.liked, matched: res.matched });
                })
                .catch((e: unknown) => {
                  if (e instanceof Error && e.message.includes("registration_required")) {
                    navigate("/profile");
                  }
                });
            }}
          >
            {profile.liked ? t(language, "catalogLiked") : t(language, "catalogLike")}
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
      </div>

      {lightboxIndex != null ? (
        <PhotoLightbox
          urls={photos}
          index={lightboxIndex}
          onClose={() => setLightboxIndex(null)}
          onIndexChange={setLightboxIndex}
          closeLabel="×"
        />
      ) : null}
    </section>
  );
}
