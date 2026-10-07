import { FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { type Language, t, tf } from "../i18n/messages";
import {
  fetchConfig,
  fetchMyAds,
  requestAdInvoice,
  submitAd,
  type AdRequestItem,
  type PublicConfig,
} from "../lib/api";

type Props = { language: Language };

const CATEGORIES = [
  { id: "restaurants", key: "adsCatRestaurants" as const },
  { id: "mens_goods", key: "adsCatMens" as const },
  { id: "language_courses", key: "adsCatLang" as const },
  { id: "other", key: "adsCatOther" as const },
];

function statusLabel(language: Language, status: string): string {
  const map: Record<string, Parameters<typeof t>[1]> = {
    pending: "adsStatusPending",
    awaiting_payment: "adsStatusAwaiting",
    queued: "adsStatusQueued",
    active: "adsStatusActive",
    expired: "adsStatusExpired",
    rejected: "adsStatusRejected",
  };
  const key = map[status];
  return key ? t(language, key) : status;
}

export function AdFormScreen({ language }: Props) {
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [mine, setMine] = useState<AdRequestItem[]>([]);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("other");
  const [body, setBody] = useState("");
  const [contact, setContact] = useState("");
  const [desiredDate, setDesiredDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState<AdRequestItem | null>(null);
  const myRequestsRef = useRef<HTMLDivElement>(null);

  const reload = async () => {
    setMine(await fetchMyAds());
  };

  useEffect(() => {
    void fetchConfig().then(setConfig);
    void reload();
  }, []);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const created = await submitAd({
        title,
        category,
        body,
        contact: contact || undefined,
        desired_date: desiredDate || undefined,
      });
      setSubmitted(created);
      window.scrollTo({ top: 0 });
      setTitle("");
      setBody("");
      setContact("");
      setDesiredDate("");
      await reload();
    } catch {
      setError(t(language, "errorGeneric"));
    } finally {
      setBusy(false);
    }
  };

  const onPay = async (id: number) => {
    setBusy(true);
    setError(null);
    const res = await requestAdInvoice(id);
    setBusy(false);
    if (res?.ok) setInfo(t(language, "adsPaySent"));
    else setError(t(language, "errorGeneric"));
  };

  const showMyRequests = () => {
    setSubmitted(null);
    requestAnimationFrame(() => myRequestsRef.current?.scrollIntoView({ block: "start" }));
  };

  if (submitted) {
    const stars = config?.prices.ad_slot_stars ?? "—";
    return (
      <section className="screen screen--milky">
        <Link to="/" className="work-back">
          ← {t(language, "backHome")}
        </Link>
        <div className="ads-done">
          <div className="ads-done__icon" aria-hidden>
            ✓
          </div>
          <h1 className="work-title">{t(language, "adsDoneTitle")}</h1>
          <p className="work-body">{tf(language, "adsDoneBody", { title: submitted.title })}</p>

          <div className="ads-done__card">
            <h2 className="letter-card__label">{t(language, "adsDoneNext")}</h2>
            <ol className="ads-done__steps">
              <li>{t(language, "adsDoneStep1")}</li>
              <li>{tf(language, "adsDoneStep2", { stars })}</li>
              <li>{t(language, "adsDoneStep3")}</li>
            </ol>
          </div>

          <button type="button" className="btn btn--block btn--dark" onClick={showMyRequests}>
            {t(language, "adsDoneMyRequests")}
          </button>
          <button type="button" className="btn btn--block ads-done__secondary" onClick={() => setSubmitted(null)}>
            {t(language, "adsDoneNew")}
          </button>
          <Link to="/" className="btn btn--block ads-done__secondary">
            {t(language, "toHome")}
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="screen screen--milky">
      <Link to="/" className="work-back">
        ← {t(language, "backHome")}
      </Link>
      <h1 className="work-title">{t(language, "adsTitle")}</h1>
      <p className="work-body">{t(language, "adsHint")}</p>
      <p className="home-meta">
        {tf(language, "adsPrice", { stars: config?.prices.ad_slot_stars ?? "—" })}
      </p>

      <form className="wizard-form" onSubmit={(e) => void onSubmit(e)}>
        <label className="field">
          <span>{t(language, "adsCompany")}</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={120} />
        </label>
        <label className="field">
          <span>{t(language, "adsCategory")}</span>
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map((c) => (
              <option key={c.id} value={c.id}>
                {t(language, c.key)}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{t(language, "adsBody")}</span>
          <textarea rows={5} value={body} onChange={(e) => setBody(e.target.value)} required />
        </label>
        <label className="field">
          <span>{t(language, "adsContact")}</span>
          <input value={contact} onChange={(e) => setContact(e.target.value)} maxLength={255} />
        </label>
        <label className="field">
          <span>{t(language, "adsDesiredDate")}</span>
          <input value={desiredDate} onChange={(e) => setDesiredDate(e.target.value)} maxLength={64} />
        </label>
        <button type="submit" className="btn btn--block btn--dark" disabled={busy}>
          {t(language, "adsSubmit")}
        </button>
      </form>

      {info ? <p className="home-meta">{info}</p> : null}
      {error ? <p className="form-error">{error}</p> : null}

      {mine.length > 0 ? (
        <div className="ads-mine" ref={myRequestsRef}>
          <h2 className="letter-card__label">{t(language, "adsMyRequests")}</h2>
          <ul className="admin-list">
            {mine.map((ad) => (
              <li key={ad.id} className="admin-payment">
                <strong>
                  #{ad.id} · {ad.title}
                </strong>
                <span>{statusLabel(language, ad.status)}</span>
                {ad.moderation_feedback ? <span>{ad.moderation_feedback}</span> : null}
                {ad.can_pay ? (
                  <button
                    type="button"
                    className="btn btn--block btn--champagne"
                    disabled={busy}
                    onClick={() => void onPay(ad.id)}
                  >
                    {t(language, "adsPay")}
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
