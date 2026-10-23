import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { type Language, t } from "../i18n/messages";
import { fetchMe, uploadVerificationSelfie } from "../lib/api";

type Props = { language: Language; onRefresh?: () => void };

export function VerifyScreen({ language, onRefresh }: Props) {
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchMe().then((me) => setStatus(me?.verification_status ?? "none"));
  }, []);

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const res = await uploadVerificationSelfie(file);
      setStatus(res.verification_status);
      onRefresh?.();
    } catch {
      setError(t(language, "writeNoPerson"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="screen screen--milky">
      <Link to="/" className="work-back">
        ← {t(language, "backHome")}
      </Link>
      <h1 className="work-title">{t(language, "verifyTitle")}</h1>
      <p className="work-body">{t(language, "verifyHint")}</p>
      {status === "verified" ? <p className="home-meta">{t(language, "verifyOk")}</p> : null}
      {status === "pending" ? <p className="home-meta">{t(language, "verifyPending")}</p> : null}
      {status === "rejected" ? <p className="form-error">{t(language, "verifyRejected")}</p> : null}
      {status !== "verified" && status !== "pending" ? (
        <label className="btn btn--block btn--dark">
          {busy ? t(language, "saving") : t(language, "verifyUpload")}
          <input
            type="file"
            accept="image/*"
            hidden
            disabled={busy}
            onChange={(e) => void onFile(e.target.files?.[0])}
          />
        </label>
      ) : null}
      {error ? <p className="form-error">{error}</p> : null}
    </section>
  );
}
