import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { profileIntroAssets, profileIntroPhotos } from "../assets/backgrounds";
import { type Language, tf, t } from "../i18n/messages";
import { fetchConfig } from "../lib/api";

type Props = {
  language: Language;
  onStart: () => void;
};

export function ProfileIntroScreen({ language, onStart }: Props) {
  const navigate = useNavigate();
  const [stars, setStars] = useState(3000);
  useEffect(() => {
    void fetchConfig().then((cfg) => {
      if (cfg?.prices.profile_publish_stars) setStars(cfg.prices.profile_publish_stars);
    });
  }, []);

  return (
    <section className="profile-intro screen" aria-label={t(language, "introTitle")}>
      <button type="button" className="profile-intro__back" onClick={() => navigate("/")}>
        ‹
      </button>
      <div className="profile-intro__stack">
        <div className="profile-intro__top">
          <img src={profileIntroPhotos.top} alt="" />
        </div>
        <div className="profile-intro__band">
          <h1 className="profile-intro__title">{t(language, "introTitle")}</h1>
          <p className="profile-intro__accent">{t(language, "introAccent")}</p>
          <p className="profile-intro__body">{t(language, "introBody")}</p>
          <p className="profile-intro__price">{tf(language, "introPrice", { stars })}</p>
          <p className="profile-intro__body" style={{ marginTop: 10 }}>
            {t(language, "introPayNote")}
          </p>
        </div>
        <div className="profile-intro__bottom">
          <img src={profileIntroPhotos.bottom} alt="" />
        </div>
      </div>
      {/* Decorative reference composite kept in public for moodboard parity */}
      <img src={profileIntroAssets[language]} alt="" hidden />
      <div className="profile-intro__actions">
        <button type="button" className="btn btn--cream btn--block" onClick={onStart}>
          {t(language, "start")}
        </button>
      </div>
    </section>
  );
}
