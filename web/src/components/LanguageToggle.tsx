import { type Language, t } from "../i18n/messages";

type Props = {
  language: Language;
  onChange: (language: Language) => void;
};

export function LanguageToggle({ language, onChange }: Props) {
  return (
    <div className="lang-toggle" role="group" aria-label={t(language, "homeSettingsLang")}>
      <button
        type="button"
        className={`lang-toggle__btn${language === "ru" ? " is-active" : ""}`}
        onClick={() => onChange("ru")}
      >
        <span className="lang-toggle__title">Русская версия</span>
        <span className="lang-toggle__sub">Для женщин</span>
      </button>
      <button
        type="button"
        className={`lang-toggle__btn${language === "it" ? " is-active" : ""}`}
        onClick={() => onChange("it")}
      >
        <span className="lang-toggle__title">Versione italiana</span>
        <span className="lang-toggle__sub">Per uomini</span>
      </button>
    </div>
  );
}
