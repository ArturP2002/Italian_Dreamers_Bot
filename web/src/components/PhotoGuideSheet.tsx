import { type Language, t } from "../i18n/messages";

type Props = {
  language: Language;
  open: boolean;
  onClose: () => void;
};

/** Bottom tip when a group photo is rejected — visual solo vs group rule. */
export function PhotoGuideSheet({ language, open, onClose }: Props) {
  if (!open) return null;
  return (
    <div className="photo-guide" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="photo-guide__sheet" onClick={(e) => e.stopPropagation()}>
        <div className="photo-guide__examples" aria-hidden>
          <div className="photo-guide__card photo-guide__card--bad">
            <div className="photo-guide__faces">
              <span />
              <span />
              <span />
            </div>
            <span className="photo-guide__mark photo-guide__mark--bad">✕</span>
          </div>
          <div className="photo-guide__card photo-guide__card--good">
            <div className="photo-guide__faces photo-guide__faces--solo">
              <span />
            </div>
            <span className="photo-guide__mark photo-guide__mark--good">✓</span>
          </div>
        </div>
        <h2 className="photo-guide__title">{t(language, "photoGuideTitle")}</h2>
        <p className="photo-guide__body">{t(language, "photoGuideBody")}</p>
        <button type="button" className="btn btn--block btn--dark" onClick={onClose}>
          {t(language, "photoGuideClose")}
        </button>
      </div>
    </div>
  );
}
