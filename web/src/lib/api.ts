const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export type MeUser = {
  id: number;
  telegram_id: number;
  username: string | null;
  first_name: string | null;
  language_code: string;
  gender: string | null;
  message_credits: number;
  is_admin: boolean;
  is_blocked: boolean;
  soft_ban_until: string | null;
  is_soft_banned: boolean;
  profile_status: string | null;
  profile_id: number | null;
};

export type ProfilePhoto = {
  id: number;
  position: number;
  url: string;
};

export type Profile = {
  id: number;
  status: string;
  name: string;
  age: number;
  age_min: number;
  age_max: number;
  height_cm: number;
  has_children: boolean;
  gender: string | null;
  wants_children: string;
  marital_status: string;
  country: string;
  city: string;
  profession: string;
  hobbies: string;
  about: string;
  desired_partner: string;
  telegram_username: string | null;
  personal_data_agreement: boolean;
  cover_question_id: number | null;
  cover_answer: string | null;
  dream_location: string | null;
  moderation_feedback: string | null;
  scheduled_at?: string | null;
  paid_at?: string | null;
  published_at?: string | null;
  photos: ProfilePhoto[];
  editable: boolean;
  can_pay?: boolean;
  channel_post_url?: string | null;
};

export type AdminProfileListItem = {
  id: number;
  status: string;
  name: string;
  age: number;
  gender: string | null;
  city: string;
  country: string;
  telegram_username: string | null;
  user_telegram_id: number | null;
  user_id: number;
  moderation_feedback: string | null;
  scheduled_at: string | null;
  paid_at: string | null;
  published_at: string | null;
  approved_at: string | null;
  created_at: string;
  photo_url: string | null;
};

export type AdminProfileDetail = AdminProfileListItem & {
  height_cm: number;
  has_children: boolean;
  wants_children: string;
  marital_status: string;
  profession: string;
  hobbies: string;
  about: string;
  desired_partner: string;
  age_min: number;
  age_max: number;
  cover_question_id: number | null;
  cover_answer: string | null;
  dream_location: string | null;
  photos: ProfilePhoto[];
  message_credits: number;
  is_blocked: boolean;
};

export type AdminUser = {
  id: number;
  telegram_id: number;
  username: string | null;
  first_name: string | null;
  language_code: string;
  gender: string | null;
  message_credits: number;
  is_blocked: boolean;
  profile_id: number | null;
  profile_status: string | null;
  profile_name: string | null;
  photo_url?: string | null;
};

export type AdminPayment = {
  id: number;
  user_id: number;
  product: string;
  status: string;
  stars_amount: number;
  related_profile_id: number | null;
  created_at: string;
  completed_at: string | null;
  telegram_id: number | null;
  username: string | null;
};

export type AdminStats = {
  users_total: number;
  users_blocked: number;
  users_soft_banned?: number;
  profiles_new: number;
  profiles_awaiting_payment: number;
  profiles_queued: number;
  profiles_published: number;
  profiles_rejected: number;
  payments_completed: number;
  stars_earned: number;
  publish_payments: number;
  credit_payments?: number;
  ad_payments?: number;
  credits_granted?: number;
  letters_pending?: number;
  letters_rejected?: number;
  letters_unlocked?: number;
  complaints_open?: number;
  ads_pending?: number;
  ads_queued?: number;
  ads_active?: number;
  ads_expired?: number;
};

export type AdRequestItem = {
  id: number;
  status: string;
  title: string;
  category: string;
  body: string;
  contact: string | null;
  desired_date: string | null;
  moderation_feedback: string | null;
  paid_at: string | null;
  scheduled_at: string | null;
  activated_at: string | null;
  expires_at: string | null;
  created_at: string;
  can_pay: boolean;
};

export type AdminAd = {
  id: number;
  status: string;
  title: string;
  category: string;
  body: string;
  contact: string | null;
  desired_date: string | null;
  media_file_id: string | null;
  moderation_feedback: string | null;
  paid_at: string | null;
  scheduled_at: string | null;
  activated_at: string | null;
  expires_at: string | null;
  channel_message_id: number | null;
  created_at: string;
  user_id: number;
  user_telegram_id: number | null;
  username: string | null;
};

export type AdminComplaint = {
  id: number;
  status: string;
  reason: string;
  admin_note: string | null;
  reporter_user_id: number;
  reporter_telegram_id: number | null;
  reported_user_id: number | null;
  message_request_id: number | null;
  created_at: string;
  resolved_at: string | null;
};

export type PublicConfig = {
  prices: {
    message_credit_stars: number;
    message_pack_9_stars: number;
    message_pack_size: number;
    profile_publish_stars: number;
    ad_slot_stars: number;
  };
  limits: Record<string, number>;
  timezone: string;
  bot_username?: string | null;
};

export type CoverQuestion = { id: number; ru: string; it: string };

export type MessageRequestItem = {
  id: number;
  status: string;
  direction: "incoming" | "outgoing";
  text: string;
  text_translated: string | null;
  reply_text: string | null;
  reply_text_translated: string | null;
  sender_name: string | null;
  sender_age: number | null;
  sender_photo_url: string | null;
  profile_id: number;
  profile_name: string | null;
  profile_age: number | null;
  profile_photo_url: string | null;
  profile_city: string | null;
  profile_about: string | null;
  profile_dream: string | null;
  counterpart_username: string | null;
  counterpart_telegram_link: string | null;
  unlocked_at: string | null;
  created_at: string;
  responded_at: string | null;
  can_reply: boolean;
  can_reject: boolean;
  can_unlock: boolean;
  can_chat: boolean;
  message_credits: number;
};

export type InboxResponse = {
  items: MessageRequestItem[];
  pending_incoming: number;
  message_credits: number;
};

export type WriteTarget = {
  profile_id: number;
  name: string;
  age: number;
  city: string;
  photo_url: string | null;
  gender: string | null;
  sender: {
    source: "profile" | "saved";
    name: string;
    age: number;
    city: string | null;
    photo_url: string | null;
  } | null;
};

export type ChatMessageItem = {
  id: number;
  sender_user_id: number;
  text: string;
  text_translated: string | null;
  created_at: string;
  is_mine: boolean;
};

export type ChatThread = {
  request_id: number;
  status: string;
  messages: ChatMessageItem[];
  counterpart_name: string | null;
  counterpart_telegram_link: string | null;
  can_send: boolean;
};

export type ReferralInfo = {
  code: string;
  link: string;
  referred_by_user_id: number | null;
  invited_count: number;
  bonus_credits: number;
};

export type ProfileUpdatePayload = Partial<{
  name: string;
  age: number;
  age_min: number;
  age_max: number;
  height_cm: number;
  has_children: boolean;
  gender: "male" | "female";
  wants_children: "yes" | "no" | "unsure";
  marital_status: "single" | "divorced";
  country: string;
  city: string;
  profession: string;
  hobbies: string;
  about: string;
  desired_partner: string;
  telegram_username: string;
  personal_data_agreement: boolean;
  cover_question_id: number;
  cover_answer: string;
  dream_location: string;
}>;

function initDataHeader(): HeadersInit {
  const tg = window.Telegram?.WebApp;
  const initData = tg?.initData;
  if (initData) {
    return { "X-Telegram-Init-Data": initData };
  }
  const devId = import.meta.env.VITE_DEV_TELEGRAM_ID;
  if (devId) {
    return { "X-Dev-Telegram-Id": String(devId) };
  }
  return {};
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...initDataHeader(),
        ...(init?.headers ?? {}),
      },
    });
    if (!res.ok) return null;
    if (res.status === 204) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export function mediaUrl(path: string): string {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path}`;
}

export async function fetchMe(): Promise<MeUser | null> {
  return apiFetch<MeUser>("/api/me");
}

export async function patchLanguage(language: "ru" | "it"): Promise<MeUser | null> {
  return apiFetch<MeUser>("/api/me/language", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ language_code: language }),
  });
}

export async function patchGender(gender: "male" | "female"): Promise<MeUser | null> {
  return apiFetch<MeUser>("/api/me/gender", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ gender }),
  });
}

export async function fetchConfig(): Promise<PublicConfig | null> {
  return apiFetch<PublicConfig>("/api/config");
}

export async function fetchProfile(): Promise<Profile | null> {
  return apiFetch<Profile>("/api/me/profile");
}

export async function updateProfile(payload: ProfileUpdatePayload): Promise<Profile | null> {
  return apiFetch<Profile>("/api/me/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function submitProfile(): Promise<Profile | null> {
  return apiFetch<Profile>("/api/me/profile/submit", { method: "POST" });
}

export async function uploadProfilePhoto(file: File): Promise<Profile | null> {
  const body = new FormData();
  body.append("file", file);
  return apiFetch<Profile>("/api/me/profile/photos", { method: "POST", body });
}

export async function deleteProfilePhoto(photoId: number): Promise<Profile | null> {
  return apiFetch<Profile>(`/api/me/profile/photos/${photoId}`, { method: "DELETE" });
}

export async function fetchCoverQuestions(): Promise<CoverQuestion[]> {
  const data = await apiFetch<{ questions: CoverQuestion[] }>("/api/me/profile/cover-questions");
  return data?.questions ?? [];
}

export async function requestPublishInvoice(): Promise<{ ok: boolean; stars?: number } | null> {
  return apiFetch("/api/me/profile/pay", { method: "POST" });
}

async function apiFetchJsonOrThrow<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...initDataHeader(),
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function adminFetchStats(): Promise<AdminStats | null> {
  return apiFetch<AdminStats>("/api/admin/stats");
}

export async function adminFetchProfiles(
  status?: string,
  opts?: { limit?: number; offset?: number },
): Promise<AdminProfileListItem[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (opts?.limit != null) params.set("limit", String(opts.limit));
  if (opts?.offset != null) params.set("offset", String(opts.offset));
  const q = params.toString() ? `?${params}` : "";
  return (await apiFetch<AdminProfileListItem[]>(`/api/admin/profiles${q}`)) ?? [];
}

export async function adminFetchProfile(id: number): Promise<AdminProfileDetail | null> {
  return apiFetch<AdminProfileDetail>(`/api/admin/profiles/${id}`);
}

export async function adminApproveProfile(id: number): Promise<AdminProfileDetail> {
  return apiFetchJsonOrThrow(`/api/admin/profiles/${id}/approve`, { method: "POST" });
}

export async function adminRejectProfile(id: number, feedback: string): Promise<AdminProfileDetail> {
  return apiFetchJsonOrThrow(`/api/admin/profiles/${id}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feedback }),
  });
}

export async function adminScheduleProfile(id: number, scheduledAt: string): Promise<AdminProfileDetail> {
  return apiFetchJsonOrThrow(`/api/admin/profiles/${id}/schedule`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scheduled_at: scheduledAt }),
  });
}

export async function adminMarkPaid(id: number): Promise<AdminProfileDetail> {
  return apiFetchJsonOrThrow(`/api/admin/profiles/${id}/mark-paid`, { method: "POST" });
}

export async function adminPublishNow(id: number): Promise<AdminProfileDetail> {
  return apiFetchJsonOrThrow(`/api/admin/profiles/${id}/publish-now`, { method: "POST" });
}

export async function adminFetchUsers(q: string): Promise<AdminUser[]> {
  const query = q ? `?q=${encodeURIComponent(q)}` : "";
  return (await apiFetch<AdminUser[]>(`/api/admin/users${query}`)) ?? [];
}

export async function adminBlockUser(id: number): Promise<AdminUser> {
  return apiFetchJsonOrThrow(`/api/admin/users/${id}/block`, { method: "POST" });
}

export async function adminUnblockUser(id: number): Promise<AdminUser> {
  return apiFetchJsonOrThrow(`/api/admin/users/${id}/unblock`, { method: "POST" });
}

export async function adminGrantCredits(id: number, delta: number, note?: string): Promise<AdminUser> {
  return apiFetchJsonOrThrow(`/api/admin/users/${id}/credits`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ delta, note }),
  });
}

export async function adminFetchPayments(): Promise<AdminPayment[]> {
  return (await apiFetch<AdminPayment[]>("/api/admin/payments")) ?? [];
}

export async function fetchInbox(): Promise<InboxResponse | null> {
  return apiFetch<InboxResponse>("/api/messages/inbox");
}

export async function fetchWriteTarget(profileId: number): Promise<WriteTarget | null> {
  return apiFetch<WriteTarget>(`/api/messages/write-target/${profileId}`);
}

export async function createLetter(payload: {
  profileId: number;
  text: string;
  senderName?: string;
  senderAge?: number;
  photo?: File | null;
}): Promise<MessageRequestItem> {
  const body = new FormData();
  body.append("profile_id", String(payload.profileId));
  body.append("text", payload.text);
  if (payload.senderName) body.append("sender_name", payload.senderName);
  if (payload.senderAge) body.append("sender_age", String(payload.senderAge));
  if (payload.photo) body.append("photo", payload.photo);
  return apiFetchJsonOrThrow<MessageRequestItem>("/api/messages", { method: "POST", body });
}

export async function fetchMessage(id: number): Promise<MessageRequestItem | null> {
  return apiFetch<MessageRequestItem>(`/api/messages/${id}`);
}

export async function rejectMessage(id: number): Promise<MessageRequestItem> {
  return apiFetchJsonOrThrow(`/api/messages/${id}/reject`, { method: "POST" });
}

export async function replyMessage(id: number, text: string): Promise<MessageRequestItem> {
  return apiFetchJsonOrThrow(`/api/messages/${id}/reply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}

export async function unlockMessage(id: number): Promise<MessageRequestItem> {
  return apiFetchJsonOrThrow(`/api/messages/${id}/unlock`, { method: "POST" });
}

export async function buyMessageCredits(opts: {
  pack: boolean;
  messageRequestId?: number | null;
}): Promise<{ ok: boolean; stars?: number }> {
  return apiFetchJsonOrThrow("/api/messages/buy-credits", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      pack: opts.pack,
      message_request_id: opts.messageRequestId ?? null,
    }),
  });
}

export async function fetchChat(id: number): Promise<ChatThread | null> {
  return apiFetch<ChatThread>(`/api/messages/${id}/chat`);
}

export async function sendChatMessage(id: number, text: string): Promise<ChatMessageItem> {
  return apiFetchJsonOrThrow(`/api/messages/${id}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}

export async function fetchReferral(): Promise<ReferralInfo | null> {
  return apiFetch<ReferralInfo>("/api/me/referral");
}

export async function claimReferral(code: string): Promise<ReferralInfo> {
  return apiFetchJsonOrThrow("/api/me/referral/claim", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
}

export async function submitAd(payload: {
  title: string;
  category: string;
  body: string;
  contact?: string;
  desired_date?: string;
}): Promise<AdRequestItem> {
  return apiFetchJsonOrThrow("/api/ads", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fetchMyAds(): Promise<AdRequestItem[]> {
  return (await apiFetch<AdRequestItem[]>("/api/ads/mine")) ?? [];
}

export async function requestAdInvoice(adId: number): Promise<{ ok: boolean; stars?: number } | null> {
  return apiFetch(`/api/ads/${adId}/pay`, { method: "POST" });
}

export async function fileComplaint(payload: {
  reason: string;
  message_request_id?: number;
  reported_user_id?: number;
}): Promise<{ ok: boolean; id: number }> {
  return apiFetchJsonOrThrow("/api/complaints", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function adminFetchAds(status?: string): Promise<AdminAd[]> {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return (await apiFetch<AdminAd[]>(`/api/admin/ads${q}`)) ?? [];
}

export async function adminFetchAd(id: number): Promise<AdminAd | null> {
  return apiFetch<AdminAd>(`/api/admin/ads/${id}`);
}

export async function adminApproveAd(id: number): Promise<AdminAd> {
  return apiFetchJsonOrThrow(`/api/admin/ads/${id}/approve`, { method: "POST" });
}

export async function adminRejectAd(id: number, feedback: string): Promise<AdminAd> {
  return apiFetchJsonOrThrow(`/api/admin/ads/${id}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feedback }),
  });
}

export async function adminMarkAdPaid(id: number): Promise<AdminAd> {
  return apiFetchJsonOrThrow(`/api/admin/ads/${id}/mark-paid`, { method: "POST" });
}

export async function adminActivateAdNow(id: number): Promise<AdminAd> {
  return apiFetchJsonOrThrow(`/api/admin/ads/${id}/activate-now`, { method: "POST" });
}

export async function adminFetchComplaints(status = "open"): Promise<AdminComplaint[]> {
  const q = `?status=${encodeURIComponent(status)}`;
  return (await apiFetch<AdminComplaint[]>(`/api/admin/complaints${q}`)) ?? [];
}

export async function adminResolveComplaint(
  id: number,
  status: "reviewed" | "resolved" | "dismissed",
  adminNote?: string,
): Promise<AdminComplaint> {
  return apiFetchJsonOrThrow(`/api/admin/complaints/${id}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, admin_note: adminNote }),
  });
}
