import { getJstDateString } from './datetime';

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

export interface ChatSuggestion {
  type: 'product' | 'video' | 'wishlist' | 'restaurant';
  title: string;
  url: string;
  image?: string;
  price?: number | null;
  reason?: string;
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
    entries: { date: string; content: string; life_log_count: number; chat_count?: number }[];
  }> {
    return this.request('/api/diary');
  }

  getDiaryDetail(date: string): Promise<{
    date: string;
    content: string | null;
    life_log_count: number;
    chat_count?: number;
    life_logs: { category: string; content: string; emotion?: string; timestamp?: string }[];
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

  sendChatMessage(content: string): Promise<{
    reply: string;
    timestamp: string;
    intent?: string;
    expense_saved?: boolean;
    suggestion?: ChatSuggestion;
  }> {
    return this.request('/api/chat/send', {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  }

  // ─── Expenses ───

  getExpenses(limit?: number, month?: string): Promise<{
    expenses: {
      id: string;
      item: string;
      amount: number;
      category: string;
      category_label?: string;
      excuse_tag?: string;
      source: string;
      store: string;
      timestamp: string;
    }[];
  }> {
    const params = new URLSearchParams();
    if (limit) params.set('limit', String(limit));
    if (month) params.set('month', month);
    return this.request(`/api/expenses?${params.toString()}`);
  }

  postExpense(data: { item: string; amount: number; category?: string; store?: string }): Promise<{
    success: boolean;
    id: string;
    excuse_tag: string;
    category: string;
  }> {
    return this.request('/api/expenses', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  updateExpense(id: string, data: { item?: string; amount?: number; category?: string; excuse_tag?: string; store?: string }): Promise<{ success: boolean }> {
    return this.request(`/api/expenses/${encodeURIComponent(id)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  deleteExpense(id: string): Promise<{ success: boolean }> {
    return this.request(`/api/expenses/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    });
  }

  getExpenseSummary(month?: string): Promise<{
    month: string;
    total_spent: number;
    expense_count: number;
    monthly_surplus: number;
    carryover_in?: number;
    balance?: number;
    balance_for_chart?: number;
    remaining: number;
    trend?: {
      month: string;
      total_spent: number;
      expense_count: number;
      monthly_surplus: number;
      carryover_in: number;
      balance: number;
      balance_for_chart: number;
      carryover_out: number;
    }[];
  }> {
    const params = new URLSearchParams();
    if (month) params.set('month', month);
    return this.request(`/api/expenses/summary?${params.toString()}`);
  }

  uploadReceipt(imageBase64: string, mediaType?: string, note?: string): Promise<{
    success: boolean;
    reply: string;
    items: { item: string; amount: number; category: string }[];
    total: number;
    store: string;
    date: string;
  }> {
    return this.request('/api/expenses/receipt', {
      method: 'POST',
      body: JSON.stringify({
        image: imageBase64,
        media_type: mediaType || 'image/jpeg',
        note: note || '',
      }),
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

  // ─── Wishlist (Amazon ほしいものリスト) ───

  getWishlistSources(): Promise<{ sources: { wishlist_source_id: string; wishlist_url: string; display_name?: string; last_sync_at?: string; item_count?: number }[] }> {
    return this.request('/api/wishlist/sources');
  }

  registerWishlist(url: string, displayName?: string): Promise<{ success?: boolean; source_id?: string; error?: string; message?: string }> {
    return this.request('/api/wishlist/register', {
      method: 'POST',
      body: JSON.stringify({ url, display_name: displayName || '' }),
    });
  }

  syncWishlist(sourceId?: string): Promise<{ synced?: number; items?: number; error?: string; message?: string }> {
    return this.request('/api/wishlist/sync', {
      method: 'POST',
      body: JSON.stringify(sourceId ? { source_id: sourceId } : {}),
    });
  }

  getWishlistItems(status?: string): Promise<{
    items: {
      wishlist_item_id: string;
      product_title: string;
      product_url: string;
      product_image_url: string;
      price?: number;
      desire_aging_days?: number;
      status?: string;
    }[];
  }> {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    return this.request(`/api/wishlist/items?${params.toString()}`);
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
    const d = date || getJstDateString();
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

  // ─── API Connection Test ───

  testConnection(service: 'bedrock' | 'rakuten' | 'hotpepper' | 'youtube'): Promise<{
    ok: boolean;
    service: string;
    count?: number;
    sample?: string;
    model?: string;
    error?: string;
  }> {
    return this.request('/api/settings/test-connection', {
      method: 'POST',
      body: JSON.stringify({ service }),
    });
  }
}
