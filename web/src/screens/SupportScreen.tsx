import { Link } from "react-router-dom";
import { type Language, t, tf } from "../i18n/messages";
import type { MeUser } from "../lib/api";

type Props = {
  language: Language;
  me: MeUser | null;
};

export function SupportScreen({ language, me }: Props) {
  const until = me?.soft_ban_until
    ? new Date(me.soft_ban_until).toLocaleString(language === "it" ? "it-IT" : "ru-RU", {
        timeZone: "Europe/Moscow",
      })
    : "—";

  return (
    <section className="screen screen--milky">
      <h1 className="work-title">{t(language, "supportTitle")}</h1>
      <p className="work-body">{t(language, "supportBody")}</p>
      <p className="home-meta">{tf(language, "supportUntil", { when: until })}</p>
      <p className="home-meta">{t(language, "supportHint")}</p>
      <Link to="/" className="btn btn--block btn--dark">
        {t(language, "supportHome")}
      </Link>
    </section>
  );
}
