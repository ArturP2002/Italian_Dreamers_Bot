import { useEffect, useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { type Language, type MessageKey, t } from "../i18n/messages";
import { fetchInbox } from "../lib/api";

type Props = { language: Language };

type NavId = "home" | "members" | "messages" | "profile";

const ICON_PROPS = {
  viewBox: "0 0 24 24",
  width: 22,
  height: 22,
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.4,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

const ITEMS: Array<{ id: NavId; to: string; label: MessageKey; icon: ReactNode }> = [
  {
    id: "home",
    to: "/",
    label: "navHome",
    icon: (
      <svg {...ICON_PROPS}>
        <path d="M4 11 12 4l8 7v8.5a.5.5 0 0 1-.5.5H15v-6H9v6H4.5a.5.5 0 0 1-.5-.5V11Z" />
      </svg>
    ),
  },
  {
    id: "members",
    to: "/catalog",
    label: "navMembers",
    icon: (
      <svg {...ICON_PROPS}>
        <circle cx="9" cy="9" r="3.2" />
        <path d="M3.5 19c.4-3 2.6-5 5.5-5s5.1 2 5.5 5" />
        <circle cx="17" cy="9.8" r="2.4" />
        <path d="M16.2 14.2c2.4-.3 4 1.2 4.3 3.8" />
      </svg>
    ),
  },
  {
    id: "messages",
    to: "/inbox",
    label: "navMessages",
    icon: (
      <svg {...ICON_PROPS}>
        <path d="M4 6.5A1.5 1.5 0 0 1 5.5 5h13A1.5 1.5 0 0 1 20 6.5v8a1.5 1.5 0 0 1-1.5 1.5H10l-4 3.5V16h-.5A1.5 1.5 0 0 1 4 14.5v-8Z" />
      </svg>
    ),
  },
  {
    id: "profile",
    to: "/profile",
    label: "navProfile",
    icon: (
      <svg {...ICON_PROPS}>
        <circle cx="12" cy="8.5" r="3.5" />
        <path d="M5 20c.5-3.6 3.2-6 7-6s6.5 2.4 7 6" />
      </svg>
    ),
  },
];

/** Routes on which the bottom menu is shown (main screens of the app). */
export function bottomNavActive(pathname: string): NavId | null {
  if (pathname === "/") return "home";
  if (pathname === "/catalog" || pathname.startsWith("/catalog/") || pathname === "/likes") {
    return "members";
  }
  if (pathname.startsWith("/inbox") || pathname.startsWith("/write/") || pathname.startsWith("/chat/")) {
    return "messages";
  }
  return null;
}

export function BottomNav({ language }: Props) {
  const { pathname } = useLocation();
  const active = bottomNavActive(pathname);
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    const load = () =>
      void fetchInbox().then((data) => {
        if (!cancelled) setUnread(data?.pending_incoming ?? 0);
      });
    load();
    const timer = window.setInterval(load, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [active, pathname]);

  if (!active) return null;

  return (
    <nav className="bottom-nav" aria-label="Dreamers">
      {ITEMS.map((item) => (
        <Link
          key={item.id}
          to={item.to}
          className={`bottom-nav__item${active === item.id ? " is-active" : ""}`}
          aria-current={active === item.id ? "page" : undefined}
        >
          <span className="bottom-nav__icon">
            {item.icon}
            {item.id === "messages" && unread > 0 ? (
              <span className="bottom-nav__badge">{unread > 99 ? "99+" : unread}</span>
            ) : null}
          </span>
          <span className="bottom-nav__label">{t(language, item.label)}</span>
          <span className="bottom-nav__dot" aria-hidden />
        </Link>
      ))}
    </nav>
  );
}
