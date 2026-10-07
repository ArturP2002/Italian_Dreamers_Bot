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
        Русская версия
      </button>
      <button
        type="button"
        className={`lang-toggle__btn${language === "it" ? " is-active" : ""}`}
        onClick={() => onChange("it")}
      >
        Versione italiana
      </button>
    </div>
  );
}
