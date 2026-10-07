import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { profileIntroAssets, backgroundAssets } from "../assets/backgrounds";
import { type Language, tf, t } from "../i18n/messages";
import { fetchConfig } from "../lib/api";

type Props = {
  language: Language;
  onStart: () => void;
};

export function ProfileIntroScreen({ language, onStart }: Props) {
  const navigate = useNavigate();
  const [stars, setStars] = useState(3000);
  const topSrc = language === "ru" ? backgroundAssets.bg_spb_winter : backgroundAssets.bg_rome_night;
  const bottomSrc =
    language === "ru" ? backgroundAssets.bg_couple_silhouette : backgroundAssets.bg_positano_run;

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
          <img src={topSrc} alt="" />
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
          <img src={bottomSrc} alt="" />
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
