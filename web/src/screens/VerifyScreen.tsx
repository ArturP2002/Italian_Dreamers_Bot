import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { PhotoGuideSheet } from "../components/PhotoGuideSheet";
import { type Language, t } from "../i18n/messages";
import { fetchMe, uploadVerificationSelfie } from "../lib/api";

type Props = { language: Language; onRefresh?: () => void };

export function VerifyScreen({ language, onRefresh }: Props) {
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [photoGuideOpen, setPhotoGuideOpen] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);
  const [cameraError, setCameraError] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setCameraReady(false);
  }, []);

  const startCamera = useCallback(async () => {
    setCameraError(false);
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError(true);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: { ideal: "user" },
          width: { ideal: 720 },
          height: { ideal: 960 },
        },
      });
      streamRef.current = stream;
      const video = videoRef.current;
      if (video) {
        video.srcObject = stream;
        await video.play();
        setCameraReady(true);
      }
    } catch {
      setCameraError(true);
      stopCamera();
    }
  }, [stopCamera]);

  useEffect(() => {
    void fetchMe().then((me) => setStatus(me?.verification_status ?? "none"));
  }, []);

  useEffect(() => {
    if (status === "verified" || status === "pending") {
      stopCamera();
      return;
    }
    void startCamera();
    return () => stopCamera();
  }, [status, startCamera, stopCamera]);

  const uploadBlob = async (blob: Blob, filename: string) => {
    setBusy(true);
    setError(null);
    try {
      const file = new File([blob], filename, { type: blob.type || "image/jpeg" });
      const res = await uploadVerificationSelfie(file);
      setStatus(res.verification_status);
      onRefresh?.();
      if (res.verification_status === "verified" || res.verification_status === "pending") {
        stopCamera();
      }
    } catch (e) {
      const raw = e instanceof Error ? e.message : "";
      if (raw.includes("group_photo")) {
        setPhotoGuideOpen(true);
        setError(t(language, "photoGroupRejected"));
      } else {
        setError(t(language, "writeNoPerson"));
      }
    } finally {
      setBusy(false);
    }
  };

  const capture = async () => {
    const video = videoRef.current;
    if (!video || !cameraReady || busy) return;
    const w = video.videoWidth || 720;
    const h = video.videoHeight || 960;
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    // Mirror to match the preview (user selfie feel).
    ctx.translate(w, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0, w, h);
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob((b) => resolve(b), "image/jpeg", 0.92),
    );
    if (!blob) return;
    await uploadBlob(blob, "selfie.jpg");
  };

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    await uploadBlob(file, file.name || "selfie.jpg");
  };

  const canCapture = status !== "verified" && status !== "pending";

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

      {canCapture ? (
        <>
          <div className="verify-camera">
            <div className="verify-camera__frame">
              <video
                ref={videoRef}
                className="verify-camera__video"
                playsInline
                muted
                autoPlay
              />
              <div className="verify-camera__oval" aria-hidden />
              {!cameraReady && !cameraError ? (
                <p className="verify-camera__hint">{t(language, "verifyCameraStarting")}</p>
              ) : null}
              {cameraError ? (
                <p className="verify-camera__hint">{t(language, "verifyCameraFallback")}</p>
              ) : null}
            </div>
            <p className="verify-camera__caption">{t(language, "verifyOvalHint")}</p>
          </div>

          {cameraReady ? (
            <button
              type="button"
              className="btn btn--block btn--dark"
              disabled={busy}
              onClick={() => void capture()}
            >
              {busy ? t(language, "saving") : t(language, "verifyCapture")}
            </button>
          ) : null}

          <label className="btn btn--block btn--ghost verify-fallback">
            {busy ? t(language, "saving") : t(language, "verifyUpload")}
            <input
              type="file"
              accept="image/*"
              capture="user"
              hidden
              disabled={busy}
              onChange={(e) => void onFile(e.target.files?.[0])}
            />
          </label>
        </>
      ) : null}

      {error ? <p className="form-error">{error}</p> : null}
      <PhotoGuideSheet
        language={language}
        open={photoGuideOpen}
        onClose={() => setPhotoGuideOpen(false)}
      />
    </section>
  );
}
