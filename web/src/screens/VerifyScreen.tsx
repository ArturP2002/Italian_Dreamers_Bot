import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { PhotoGuideSheet } from "../components/PhotoGuideSheet";
import { type Language, t } from "../i18n/messages";
import { fetchMe, uploadVerificationSelfie } from "../lib/api";

type Props = { language: Language; onRefresh?: () => void };

type CamState = "idle" | "starting" | "live" | "denied";

async function requestCameraStream(): Promise<MediaStream> {
  const media = navigator.mediaDevices;
  if (!media?.getUserMedia) {
    throw new Error("getUserMedia unsupported");
  }
  const attempts: MediaStreamConstraints[] = [
    { audio: false, video: { facingMode: { ideal: "user" }, width: { ideal: 720 }, height: { ideal: 720 } } },
    { audio: false, video: { facingMode: "user" } },
    { audio: false, video: true },
  ];
  let lastError: unknown;
  for (const constraints of attempts) {
    try {
      return await media.getUserMedia(constraints);
    } catch (err) {
      lastError = err;
    }
  }
  throw lastError instanceof Error ? lastError : new Error("camera_denied");
}

function captureSelfieJpeg(video: HTMLVideoElement): Promise<Blob | null> {
  const vw = video.videoWidth;
  const vh = video.videoHeight;
  if (!vw || !vh) return Promise.resolve(null);
  // Keep the full camera frame — the circle is only a framing guide.
  // Aggressive center-crops confused Vision on close-up faces.
  const maxSide = 1280;
  const scale = Math.min(1, maxSide / Math.max(vw, vh));
  const w = Math.max(1, Math.round(vw * scale));
  const h = Math.max(1, Math.round(vh * scale));
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return Promise.resolve(null);
  ctx.translate(w, 0);
  ctx.scale(-1, 1);
  ctx.drawImage(video, 0, 0, w, h);
  return new Promise((resolve) => canvas.toBlob((b) => resolve(b), "image/jpeg", 0.92));
}

export function VerifyScreen({ language, onRefresh }: Props) {
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [photoGuideOpen, setPhotoGuideOpen] = useState(false);
  const [camState, setCamState] = useState<CamState>("idle");
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    const video = videoRef.current;
    if (video) video.srcObject = null;
    setCamState("idle");
  }, []);

  useEffect(() => {
    void fetchMe().then((me) => setStatus(me?.verification_status ?? "none"));
    return () => stopCamera();
  }, [stopCamera]);

  const uploadBlob = async (blob: Blob, filename: string) => {
    setBusy(true);
    setError(null);
    try {
      const file = new File([blob], filename, { type: "image/jpeg" });
      const res = await uploadVerificationSelfie(file);
      setStatus(res.verification_status);
      onRefresh?.();
      if (res.verification_status === "verified" || res.verification_status === "pending") {
        stopCamera();
      } else if (res.verification_status === "rejected") {
        setError(t(language, "verifyRejected"));
      }
    } catch (e) {
      const raw = e instanceof Error ? e.message : "";
      if (raw.includes("group_photo")) {
        setPhotoGuideOpen(true);
        setError(t(language, "photoGroupRejected"));
      } else if (raw.includes("selfie_no_person") || raw.includes("no_person")) {
        setError(t(language, "writeNoPerson"));
      } else if (raw.includes("bad_image_type") || raw.includes("invalid_file")) {
        setError(t(language, "verifyCaptureFailed"));
      } else {
        setError(t(language, "verifyCaptureFailed"));
      }
    } finally {
      setBusy(false);
    }
  };

  const startLivePreview = async () => {
    if (busy || camState === "starting" || camState === "live") return;
    setError(null);
    setCamState("starting");
    try {
      const stream = await requestCameraStream();
      streamRef.current = stream;
      const video = videoRef.current;
      if (!video) {
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        setCamState("denied");
        return;
      }
      video.setAttribute("playsinline", "true");
      video.setAttribute("webkit-playsinline", "true");
      video.muted = true;
      video.srcObject = stream;
      await video.play();
      setCamState("live");
    } catch {
      stopCamera();
      setCamState("denied");
      setError(t(language, "verifyCameraDenied"));
    }
  };

  const captureFromPreview = async () => {
    const video = videoRef.current;
    if (!video || camState !== "live" || busy) return;
    const blob = await captureSelfieJpeg(video);
    if (!blob) {
      setError(t(language, "verifyCaptureFailed"));
      return;
    }
    await uploadBlob(blob, "selfie.jpg");
  };

  const canCapture = status !== "verified" && status !== "pending";
  const isLive = camState === "live";
  const isStarting = camState === "starting";

  return (
    <section className="screen screen--milky verify-screen">
      <Link to="/" className="work-back" onClick={() => stopCamera()}>
        ← {t(language, "backHome")}
      </Link>
      <h1 className="work-title">{t(language, "verifyTitle")}</h1>
      <p className="work-body verify-screen__lead">{t(language, "verifyHint")}</p>

      {status === "verified" ? <p className="home-meta">{t(language, "verifyOk")}</p> : null}
      {status === "pending" ? <p className="home-meta">{t(language, "verifyPending")}</p> : null}
      {status === "rejected" ? <p className="form-error">{t(language, "verifyRejected")}</p> : null}

      {canCapture ? (
        <>
          {!isLive ? (
            <ol className="verify-steps">
              <li>{t(language, "verifyStep1")}</li>
              <li>{t(language, "verifyStep2")}</li>
              <li>{t(language, "verifyStep3")}</li>
            </ol>
          ) : (
            <p className="verify-live-hint">{t(language, "verifyOvalHint")}</p>
          )}

          <div className="verify-camera">
            <div
              className={[
                "verify-camera__frame",
                isLive ? "verify-camera__frame--live" : "",
                isStarting ? "verify-camera__frame--starting" : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <video
                ref={videoRef}
                className="verify-camera__video"
                playsInline
                muted
                autoPlay
              />
              <div className="verify-camera__ring" aria-hidden />
              {isStarting ? <span className="verify-camera__pulse" aria-hidden /> : null}
            </div>
          </div>

          {isLive ? (
            <button
              type="button"
              className="btn btn--block btn--dark"
              disabled={busy}
              onClick={() => void captureFromPreview()}
            >
              {busy ? t(language, "saving") : t(language, "verifyShoot")}
            </button>
          ) : (
            <button
              type="button"
              className="btn btn--block btn--dark"
              disabled={busy || isStarting}
              onClick={() => void startLivePreview()}
            >
              {isStarting ? t(language, "verifyCameraStarting") : t(language, "verifyOpenCamera")}
            </button>
          )}
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
