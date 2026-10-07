import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { type Language, t, tf } from "../i18n/messages";
import { buyMessageCredits, fetchConfig, fetchMe, type PublicConfig } from "../lib/api";

type Props = { language: Language; onCreditsChange?: () => void };

export function CreditsScreen({ language, onCreditsChange }: Props) {
  const [credits, setCredits] = useState(0);
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchMe().then((me) => setCredits(me?.message_credits ?? 0));
    void fetchConfig().then(setConfig);
  }, []);

  const onBuy = async (pack: boolean) => {
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      await buyMessageCredits({ pack });
      setInfo(t(language, "invoiceSent"));
      onCreditsChange?.();
    } catch {
      setError(t(language, "errorGeneric"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="screen screen--milky">
      <Link to="/" className="work-back">
        ← {t(language, "backHome")}
      </Link>
      <h1 className="work-title">{t(language, "creditsTitle")}</h1>
      <p className="work-body">{tf(language, "creditsBalance", { n: credits })}</p>
      <p className="home-meta">{t(language, "creditsHint")}</p>

      <div className="credits-actions">
        <button
          type="button"
          className="btn btn--block btn--champagne"
          disabled={busy}
          onClick={() => void onBuy(false)}
        >
          {tf(language, "buyOneCredit", {
            stars: config?.prices.message_credit_stars ?? "—",
          })}
        </button>
        <button
          type="button"
          className="btn btn--block btn--dark"
          disabled={busy}
          onClick={() => void onBuy(true)}
        >
          {tf(language, "buyPack", {
            size: config?.prices.message_pack_size ?? 9,
            stars: config?.prices.message_pack_9_stars ?? "—",
          })}
        </button>
      </div>

      {info ? <p className="home-meta">{info}</p> : null}
      {error ? <p className="form-error">{error}</p> : null}
    </section>
  );
}
