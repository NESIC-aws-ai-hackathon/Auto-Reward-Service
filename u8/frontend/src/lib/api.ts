const API_BASE = import.meta.env.VITE_API_URL || '';

export class ApiError extends Error {
  constructor(public status: number, public body: unknown) {
    super(`API Error ${status}`);
  }
}

export interface Settings {
  display_name: string;
  diary_time: string;
  notification_enabled: boolean;
  monthly_surplus: number;
}

export class ApiClient {
  private getToken: () => Promise<string>;

  constructor(getToken: () => Promise<string>) {
    this.getToken = getToken;
  }

  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const token = await this.getToken();
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        ...options?.headers,
      },
    });

    if (res.status === 401) {
      throw new ApiError(401, { error: 'unauthorized' });
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new ApiError(res.status, body);
    }
    return res.json();
  }

  getSettings(): Promise<Settings> {
    return this.request<Settings>('/api/settings');
  }

  updateSettings(data: Partial<Settings>): Promise<{ message: string; updated_fields: string[] }> {
    return this.request('/api/settings', {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  getMe(): Promise<{ user_id: string; display_name: string }> {
    return this.request('/api/user/me');
  }

  // ─── Voice Session ───

  endVoiceSession(sessionId: string, summary?: string): Promise<{
    analysis_job_id: string | null;
    duration_sec: number;
    turn_count: number;
  }> {
    return this.request('/api/voice-session/end', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, summary }),
    });
  }

  // ─── Transcript ───

  saveTranscriptTurn(sessionId: string, turn: { role: string; content: string; timestamp: string }): Promise<{ turn_id: string }> {
    return this.request('/api/transcript/turn', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, ...turn }),
    });
  }

  saveTranscriptBulk(sessionId: string, turns: { role: string; content: string; timestamp: string }[]): Promise<{ saved_count: number }> {
    return this.request('/api/transcript/bulk', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, turns }),
    });
  }

  // ─── Push Notifications ───

  pushSubscribe(subscription: PushSubscriptionJSON): Promise<{ message: string }> {
    return this.request('/api/push/subscribe', {
      method: 'POST',
      body: JSON.stringify({ subscription }),
    });
  }

  pushUnsubscribe(): Promise<{ message: string }> {
    return this.request('/api/push/unsubscribe', { method: 'POST' });
  }

  // ─── Recovery ───

  getRecovery(): Promise<{
    stress_level: number | null;
    mood: string | null;
    free_recovery: { id: string; text: string; category: string }[];
    paid_recovery: { id: string; text: string; category: string; budget_hint?: string }[];
    message: string;
  }> {
    return this.request('/api/recovery');
  }

  recordPermit(recoveryId: string, type: string): Promise<{ message: string }> {
    return this.request('/api/recovery/permit', {
      method: 'POST',
      body: JSON.stringify({ recovery_id: recoveryId, type }),
    });
  }

  recordSkip(reason?: string): Promise<{ message: string }> {
    return this.request('/api/recovery/skip', {
      method: 'POST',
      body: JSON.stringify({ reason: reason || '' }),
    });
  }

  // ─── Dashboard ───

  getDashboard(): Promise<{
    surplus: { monthly_budget: number; spent: number; remaining: number; ratio: number };
    stress: { level: number; mood: string; date: string } | null;
    recent_expenses: { description: string; amount: number; date: string }[];
    streak_days: number;
  }> {
    return this.request('/api/dashboard');
  }

  // ─── Diary ───

  getDiaryList(): Promise<{
    entries: { date: string; content: string; life_log_count: number }[];
  }> {
    return this.request('/api/diary');
  }

  getDiaryDetail(date: string): Promise<{
    date: string;
    content: string | null;
    life_log_count: number;
    life_logs: { category: string; content: string }[];
    stress: { level: number; mood: string } | null;
  }> {
    return this.request(`/api/diary/${date}`);
  }

  // ─── Chat Messages ───

  getChatMessages(since?: string, limit?: number): Promise<{
    messages: {
      role: string;
      content: string;
      timestamp: string;
      session_id: string;
      proactive: boolean;
    }[];
  }> {
    const params = new URLSearchParams();
    if (since) params.set('since', since);
    if (limit) params.set('limit', String(limit));
    const qs = params.toString();
    return this.request(`/api/chat/messages${qs ? '?' + qs : ''}`);
  }

  sendChatMessage(content: string): Promise<{ reply: string; timestamp: string }> {
    return this.request('/api/chat/send', {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  }

  // ─── Product Search ───

  searchProducts(keyword: string, category?: string, maxPrice?: number): Promise<{
    products: {
      name: string;
      price: number;
      url: string;
      image: string;
      shop: string;
      review: number;
    }[];
  }> {
    const params = new URLSearchParams();
    if (keyword) params.set('keyword', keyword);
    if (category) params.set('category', category);
    if (maxPrice) params.set('max_price', String(maxPrice));
    return this.request(`/api/search/products?${params.toString()}`);
  }

  searchYoutube(keyword: string): Promise<{
    videos: {
      title: string;
      channel: string;
      url: string;
      thumbnail: string;
      published_at?: string;
    }[];
  }> {
    return this.request(`/api/search/youtube?keyword=${encodeURIComponent(keyword)}`);
  }

  // ─── Health Data ───

  getHealthData(date?: string): Promise<{
    date: string;
    steps: number | null;
    sleep_hours: number | null;
    active_energy: number | null;
    heart_rate_avg: number | null;
    mindful_minutes: number | null;
    mood_history: { time: string; level: number; note?: string }[];
  }> {
    const d = date || new Date().toISOString().slice(0, 10);
    return this.request(`/api/health?date=${d}`);
  }

  submitHealth(data: {
    date?: string;
    steps?: number;
    sleep_hours?: number;
    active_energy?: number;
    heart_rate_avg?: number;
    mindful_minutes?: number;
    mood?: { level: number; note?: string };
  }): Promise<{ message: string }> {
    return this.request('/api/health', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // ─── Onboarding ───

  submitOnboarding(data: {
    monthly_income: number;
    fixed_costs: number;
    reward_budget: number;
    bonus_amount?: number;
    bonus_months?: string;
  }): Promise<{ message: string }> {
    return this.request('/api/onboarding', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  getOnboardingStatus(): Promise<{ completed: boolean; step?: string }> {
    return this.request('/api/onboarding');
  }
}
