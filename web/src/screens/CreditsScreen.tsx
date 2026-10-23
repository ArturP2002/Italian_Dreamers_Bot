import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { type Language, t, tf } from "../i18n/messages";
import {
  buyCatalogTop,
  buyMessageCredits,
  buyUnlimited,
  cancelUnlimited,
  fetchConfig,
  fetchMe,
  type MeUser,
  type PublicConfig,
} from "../lib/api";

type Props = { language: Language; onCreditsChange?: () => void };

export function CreditsScreen({ language, onCreditsChange }: Props) {
  const [credits, setCredits] = useState(0);
  const [me, setMe] = useState<MeUser | null>(null);
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchMe().then((user) => {
      setMe(user);
      setCredits(user?.message_credits ?? 0);
    });
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
            size: config?.prices.message_pack_size ?? 10,
            stars: config?.prices.message_pack_10_stars ?? "—",
          })}
        </button>
        {me?.has_unlimited ? (
          <>
            <p className="home-meta">
              {tf(language, "unlimitedActive", {
                date: me.unlimited_until ? new Date(me.unlimited_until).toLocaleDateString() : "—",
              })}
            </p>
            <button
              type="button"
              className="btn btn--block btn--ghost"
              disabled={busy}
              onClick={() => {
                void cancelUnlimited().then(() => setInfo(t(language, "invoiceSent")));
              }}
            >
              {t(language, "unlimitedCancel")}
            </button>
          </>
        ) : (
          <button
            type="button"
            className="btn btn--block btn--dark"
            disabled={busy}
            onClick={() => {
              setBusy(true);
              void buyUnlimited()
                .then((res) => setInfo(res.already ? tf(language, "unlimitedActive", { date: "—" }) : t(language, "invoiceSent")))
                .catch(() => setError(t(language, "errorGeneric")))
                .finally(() => setBusy(false));
            }}
          >
            {tf(language, "unlimitedBuy", { stars: config?.prices.unlimited_sub_stars ?? 1000 })}
          </button>
        )}
        {!me?.has_unlimited ? (
          <button
            type="button"
            className="btn btn--block btn--ghost"
            disabled={busy}
            onClick={() => {
              setBusy(true);
              void buyCatalogTop()
                .then(() => setInfo(t(language, "invoiceSent")))
                .catch(() => setError(t(language, "errorGeneric")))
                .finally(() => setBusy(false));
            }}
          >
            {tf(language, "catalogTopBuy", { stars: config?.prices.catalog_top_stars ?? 1000 })}
          </button>
        ) : null}
        <p className="home-meta">{t(language, "unlimitedHint")}</p>
      </div>

      {info ? <p className="home-meta">{info}</p> : null}
      {error ? <p className="form-error">{error}</p> : null}
    </section>
  );
}
