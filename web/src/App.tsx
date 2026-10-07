import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { type Language, loadLanguage, saveLanguage } from "./i18n/messages";
import { claimReferral, fetchMe, patchLanguage, type MeUser } from "./lib/api";
import { AdFormScreen } from "./screens/AdFormScreen";
import { AdminScreen } from "./screens/AdminScreen";
import { ChatScreen } from "./screens/ChatScreen";
import { CreditsScreen } from "./screens/CreditsScreen";
import { HomeScreen } from "./screens/HomeScreen";
import { InboxScreen } from "./screens/InboxScreen";
import { LoadingScreen } from "./screens/LoadingScreen";
import { MessageCardScreen } from "./screens/MessageCardScreen";
import { ProfileWizard } from "./screens/ProfileWizard";
import { ReferralScreen } from "./screens/ReferralScreen";
import { SupportScreen } from "./screens/SupportScreen";
import { WriteLetterScreen } from "./screens/WriteLetterScreen";

const BOOT_MIN_MS = 1200;

function readStartParam(): string | null {
  const tg = window.Telegram?.WebApp;
  const fromTg = (tg?.initDataUnsafe as { start_param?: string } | undefined)?.start_param;
  if (fromTg) return fromTg;
  const q = new URLSearchParams(window.location.search).get("startapp");
  return q;
}

function resolveLanguage(user: MeUser | null, stored: Language | null): Language {
  if (stored) return stored;
  if (user?.language_code === "it" || user?.language_code === "ru") return user.language_code;
  return "ru";
}

function AdminGate({ language, me }: { language: Language; me: MeUser | null }) {
  if (me === null) {
    return (
      <section className="screen screen--work">
        <p className="heading-accent" style={{ color: "var(--color-champagne)" }}>
          Italian Dreamers
        </p>
      </section>
    );
  }
  if (!me.is_admin) {
    return <Navigate to="/" replace />;
  }
  return <AdminScreen language={language} />;
}

function SoftBanGate({
  me,
  language,
  children,
}: {
  me: MeUser | null;
  language: Language;
  children: ReactNode;
}) {
  if (me?.is_soft_banned) {
    return <SupportScreen language={language} me={me} />;
  }
  return <>{children}</>;
}

export default function App() {
  const navigate = useNavigate();
  const initialLanguageRef = useRef(loadLanguage());
  const [language, setLanguage] = useState<Language | null>(() => initialLanguageRef.current);
  const [me, setMe] = useState<MeUser | null>(null);
  const [booting, setBooting] = useState(() => Boolean(initialLanguageRef.current));
  const [deepLinkHandled, setDeepLinkHandled] = useState(false);

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    tg?.ready();
    tg?.expand();
    tg?.setHeaderColor?.("#1A1511");
    tg?.setBackgroundColor?.("#1A1511");
  }, []);

  const refreshMe = useCallback(async () => {
    const user = await fetchMe();
    setMe(user);
    return user;
  }, []);

  // Returning user: show poster splash while profile loads (min duration for polish).
  useEffect(() => {
    const stored = initialLanguageRef.current;
    if (!stored) return;

    let cancelled = false;
    const startedAt = Date.now();

    void (async () => {
      const user = await refreshMe();
      if (cancelled) return;

      const nextLang = resolveLanguage(user, stored);
      setLanguage(nextLang);
      saveLanguage(nextLang);

      if (user && user.language_code !== nextLang) {
        const updated = await patchLanguage(nextLang);
        if (!cancelled && updated) setMe(updated);
      }

      const wait = Math.max(0, BOOT_MIN_MS - (Date.now() - startedAt));
      if (wait > 0) await new Promise((r) => setTimeout(r, wait));
      if (!cancelled) setBooting(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [refreshMe]);

  // First visit after language choice: load profile without splash.
  useEffect(() => {
    if (!language || initialLanguageRef.current) return;
    void (async () => {
      const user = await refreshMe();
      if (user && user.language_code !== language) {
        const updated = await patchLanguage(language);
        if (updated) setMe(updated);
      }
    })();
  }, [language, refreshMe]);

  useEffect(() => {
    if (!language || booting || deepLinkHandled) return;
    const param = readStartParam();
    if (!param) {
      setDeepLinkHandled(true);
      return;
    }
    void (async () => {
      if (param.startsWith("write_")) {
        const profileId = Number(param.slice("write_".length));
        if (Number.isFinite(profileId) && profileId > 0) {
          navigate(`/write/${profileId}`, { replace: true });
        }
      } else if (/^inbox_\d+$/.test(param)) {
        navigate(`/inbox/${param.slice("inbox_".length)}`, { replace: true });
      } else if (/^chat_\d+$/.test(param)) {
        navigate(`/chat/${param.slice("chat_".length)}`, { replace: true });
      } else if (param.startsWith("ref_")) {
        const code = param.slice("ref_".length);
        if (code) {
          try {
            await claimReferral(code);
          } catch {
            /* ignore invalid codes */
          }
        }
      } else if (param === "referral") {
        navigate("/referral", { replace: true });
      } else if (param === "ads") {
        navigate("/ads", { replace: true });
      } else if (param === "admin") {
        navigate("/admin", { replace: true });
      }
      setDeepLinkHandled(true);
    })();
  }, [language, booting, deepLinkHandled, navigate]);

  const handleEnter = (next: Language) => {
    saveLanguage(next);
    setLanguage(next);
    setBooting(false);
  };

  const handleLanguageChange = (next: Language) => {
    saveLanguage(next);
    setLanguage(next);
    void patchLanguage(next).then((updated) => {
      if (updated) setMe(updated);
    });
  };

  const needsLanguageChoice = !language;
  const showSplash = needsLanguageChoice || booting;

  if (showSplash) {
    return (
      <div className="app-shell">
        <LoadingScreen
          mode={needsLanguageChoice ? "choose" : "boot"}
          onEnter={handleEnter}
        />
      </div>
    );
  }

  return (
    <div className="app-shell">
      <Routes>
        <Route
          path="/"
          element={<HomeScreen language={language} me={me} onLanguageChange={handleLanguageChange} />}
        />
        <Route path="/support" element={<SupportScreen language={language} me={me} />} />
        <Route path="/inbox" element={<InboxScreen language={language} />} />
        <Route
          path="/inbox/:id"
          element={
            <MessageCardScreen language={language} onCreditsChange={() => void refreshMe()} />
          }
        />
        <Route
          path="/write/:profileId"
          element={
            <SoftBanGate me={me} language={language}>
              <WriteLetterScreen language={language} />
            </SoftBanGate>
          }
        />
        <Route path="/chat/:id" element={<ChatScreen language={language} />} />
        <Route
          path="/credits"
          element={<CreditsScreen language={language} onCreditsChange={() => void refreshMe()} />}
        />
        <Route path="/referral" element={<ReferralScreen language={language} />} />
        <Route path="/ads" element={<AdFormScreen language={language} />} />
        <Route
          path="/profile/*"
          element={
            <ProfileWizard
              language={language}
              me={me}
              onMeRefresh={async () => {
                await refreshMe();
              }}
            />
          }
        />
        <Route path="/admin/*" element={<AdminGate language={language} me={me} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
