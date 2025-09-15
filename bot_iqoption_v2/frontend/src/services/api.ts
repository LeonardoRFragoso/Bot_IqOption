import axios from 'axios';
import type { AxiosInstance, AxiosResponse } from 'axios';
import type { 
  User, 
  LoginCredentials, 
  RegisterData, 
  RegisterResponse,
  AuthTokens, 
  IQOptionCredentials, 
  TradingConfiguration,
  TradingSession,
  Operation,
  TradingLog,
  ApiResponse,
  AssetCatalog,
  DashboardData,
  SubscriptionStatus,
  AdminUserSubscriptionInfo,
  PaymentRecord
} from '../types/index';

class ApiService {
  private api: AxiosInstance;
  private baseURL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api';

  constructor() {
    this.api = axios.create({
      baseURL: this.baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add request interceptor to include auth token
    this.api.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Add response interceptor to handle token refresh
    this.api.interceptors.response.use(
      (response) => response,
      async (error) => {
        if (error.response?.status === 401) {
          const refreshToken = localStorage.getItem('refresh_token');
          if (refreshToken) {
            try {
              const response = await axios.post(`${this.baseURL}/auth/token/refresh/`, {
                refresh: refreshToken,
              });
              const { access } = response.data;
              localStorage.setItem('access_token', access);
              error.config.headers.Authorization = `Bearer ${access}`;
              return axios.request(error.config);
            } catch {
              this.logout();
              window.location.href = '/login';
            }
          } else {
            this.logout();
            window.location.href = '/login';
          }
        }
        return Promise.reject(error);
      }
    );
  }

  // Authentication methods
  async login(credentials: LoginCredentials): Promise<AuthTokens> {
    const response: AxiosResponse<{user: User, access: string, refresh: string}> = await this.api.post('/auth/login/', credentials);
    const { access, refresh } = response.data;
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
    return { access, refresh };
  }

  async register(userData: RegisterData): Promise<RegisterResponse> {
    const response: AxiosResponse<{user: User, access: string, refresh: string}> = await this.api.post('/auth/register/', userData);
    const { user, access, refresh } = response.data;
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
    return { user, tokens: { access, refresh } };
  }

  logout(): void {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  }

  async getCurrentUser(): Promise<User> {
    const response: AxiosResponse<User> = await this.api.get('/auth/profile/');
    return response.data;
  }

  async updateUserProfile(userData: Partial<User>): Promise<User> {
    const response: AxiosResponse<User> = await this.api.put('/auth/profile/', userData);
    return response.data;
  }

  async updateIQCredentials(credentials: IQOptionCredentials): Promise<ApiResponse<unknown>> {
    const response: AxiosResponse<ApiResponse<unknown>> = await this.api.post('/auth/iq-credentials/', credentials);
    return response.data;
  }

  // Trading Configuration methods
  async getTradingConfig(): Promise<TradingConfiguration> {
    const response: AxiosResponse<TradingConfiguration> = await this.api.get('/auth/trading-config/');
    return response.data;
  }

  async updateTradingConfig(config: Partial<TradingConfiguration>): Promise<TradingConfiguration> {
    const response: AxiosResponse<TradingConfiguration> = await this.api.put('/auth/trading-config/', config);
    return response.data;
  }

  // Trading Session methods
  async getTradingSessions(): Promise<TradingSession[]> {
    const response: AxiosResponse<TradingSession[]> = await this.api.get('/trading/sessions/');
    return response.data;
  }

  async createTradingSession(sessionData: Partial<TradingSession>): Promise<TradingSession> {
    const response: AxiosResponse<TradingSession> = await this.api.post('/trading/sessions/', sessionData);
    return response.data;
  }

  async getTradingSession(id: number): Promise<TradingSession> {
    const response: AxiosResponse<TradingSession> = await this.api.get(`/trading/sessions/${id}/`);
    return response.data;
  }

  async getActiveSession(): Promise<TradingSession | null> {
    const response: AxiosResponse<any> = await this.api.get('/trading/sessions/active/');
    const data = response.data;
    // Backend may return the session directly (serialized TradingSession) or wrapped as { session }
    if (data && typeof data === 'object') {
      if ('id' in data && ('status' in data || 'strategy' in data)) {
        return data as TradingSession;
      }
      if ('session' in data) {
        return (data as { session: TradingSession | null }).session ?? null;
      }
    }
    return null;
  }

  async updateTradingSession(id: number, sessionData: Partial<TradingSession>): Promise<TradingSession> {
    const response: AxiosResponse<TradingSession> = await this.api.put(`/trading/sessions/${id}/`, sessionData);
    return response.data;
  }

  // Trading Control methods
  async startTrading(strategy: string, asset: string = 'EURUSD', account_type: string = 'PRACTICE', strategyConfig?: any): Promise<TradingSession> {
    const response: AxiosResponse<TradingSession> = await this.api.post('/trading/start/', { 
      strategy, 
      asset,
      strategy_config: strategyConfig, 
      account_type 
    });
    return response.data;
  }

  async stopTrading(sessionId: string): Promise<ApiResponse<unknown>> {
    const response: AxiosResponse<ApiResponse<unknown>> = await this.api.post('/trading/stop/', {
      session_id: sessionId
    });
    return response.data;
  }

  async pauseTrading(sessionId: string): Promise<ApiResponse<unknown>> {
    const response: AxiosResponse<ApiResponse<unknown>> = await this.api.post('/trading/pause/', {
      session_id: sessionId
    });
    return response.data;
  }

  async resumeTrading(sessionId: string): Promise<ApiResponse<unknown>> {
    const response: AxiosResponse<ApiResponse<unknown>> = await this.api.post('/trading/resume/', {
      session_id: sessionId
    });
    return response.data;
  }

  // Asset Catalog methods
  async getAssetCatalog(): Promise<AssetCatalog[]> {
    const response: AxiosResponse<AssetCatalog[]> = await this.api.get('/trading/catalog/results/');
    return response.data;
  }

  async getCatalogResults(): Promise<AssetCatalog[]> {
    return this.getAssetCatalog();
  }

  async runAssetCatalog(strategies: string[] = ['mhi', 'torres_gemeas', 'mhi_m5', 'rsi', 'moving_average', 'bollinger_bands', 'engulfing', 'candlestick', 'macd']): Promise<ApiResponse<unknown>> {
    const response: AxiosResponse<ApiResponse<unknown>> = await this.api.post('/trading/catalog/', { strategies });
    return response.data;
  }

  async getCatalogStatus(): Promise<{ running: boolean; last_started?: string; last_completed?: string }> {
    const response: AxiosResponse<{ running: boolean; last_started?: string; last_completed?: string }>
      = await this.api.get('/trading/catalog/status/');
    return response.data;
  }

  // Operations methods
  async getOperations(sessionId?: string | number): Promise<Operation[]> {
    const url = sessionId ? `/trading/operations/?session=${sessionId}` : '/trading/operations/';
    const response: AxiosResponse<Operation[]> = await this.api.get(url);
    return response.data;
  }

  async getOperation(id: number): Promise<Operation> {
    const response: AxiosResponse<Operation> = await this.api.get(`/trading/operations/${id}/`);
    return response.data;
  }

  // Logs methods
  async getTradingLogs(sessionId?: string | number): Promise<TradingLog[]> {
    const url = sessionId ? `/trading/logs/?session_id=${sessionId}` : '/trading/logs/';
    const response: AxiosResponse<TradingLog[]> = await this.api.get(url);
    return response.data;
  }

  // Dashboard methods
  async getDashboardData(): Promise<DashboardData> {
    const response: AxiosResponse<DashboardData> = await this.api.get('/trading/dashboard/');
    return response.data;
  }

  // Connection methods
  async getConnectionStatus(): Promise<ApiResponse<unknown>> {
    const response: AxiosResponse<ApiResponse<unknown>> = await this.api.get('/trading/connection/status/');
    return response.data;
  }

  async testConnection(): Promise<ApiResponse<unknown>> {
    const response: AxiosResponse<ApiResponse<unknown>> = await this.api.post('/trading/connection/test/');
    return response.data;
  }

  // Market status methods
  async getMarketStatus(): Promise<any> {
    const response: AxiosResponse<any> = await this.api.get('/trading/market/status/');
    return response.data;
  }

  // Payouts methods
  async getPayouts(assets: string[], account_type: string = 'PRACTICE'):
    Promise<Array<{ asset: string; binary: number; turbo: number; digital: number }>> {
    const response: AxiosResponse<{ payouts: Array<{ asset: string; binary: number; turbo: number; digital: number }> }> =
      await this.api.post('/trading/payouts/', { assets, account_type });
    return response.data.payouts;
  }

  // Billing methods
  async getSubscriptionStatus(): Promise<SubscriptionStatus> {
    const response: AxiosResponse<SubscriptionStatus> = await this.api.get('/billing/status/');
    return response.data;
  }

  async verifyPaymentReturn(params: Record<string, string | null | undefined>): Promise<{ success: boolean; activated?: boolean; status?: string; active_until?: string; error?: string }> {
    // Build query string from params
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v != null) query.append(k, String(v));
    });
    const url = `/billing/verify-return/?${query.toString()}`;
    const response: AxiosResponse<{ success: boolean; activated?: boolean; status?: string; active_until?: string; error?: string }> = await this.api.get(url);
    return response.data;
  }

  async getBillingAdminUsers(): Promise<AdminUserSubscriptionInfo[]> {
    const response: AxiosResponse<AdminUserSubscriptionInfo[]> = await this.api.get('/billing/admin/users/');
    return response.data;
  }

  async getBillingAdminPayments(): Promise<PaymentRecord[]> {
    const response: AxiosResponse<PaymentRecord[]> = await this.api.get('/billing/admin/payments/');
    return response.data;
  }

  async grantSubscriptionDays(user_id: number, days: number = 30): Promise<{ success: boolean; active_until?: string; error?: string }> {
    const response: AxiosResponse<{ success: boolean; active_until?: string; error?: string }> = await this.api.post('/billing/admin/grant/', { user_id, days });
    return response.data;
  }

  // Notification methods
  async getNotifications(): Promise<any[]> {
    const response: AxiosResponse<any[]> = await this.api.get('/auth/notifications/');
    return response.data;
  }

  async getNotificationCount(): Promise<{ total: number; unread: number }> {
    const response: AxiosResponse<{ total: number; unread: number }> = await this.api.get('/auth/notifications/count/');
    return response.data;
  }

  async markNotificationRead(notificationId: string): Promise<any> {
    const response: AxiosResponse<any> = await this.api.put(`/auth/notifications/${notificationId}/read/`);
    return response.data;
  }

  async markAllNotificationsRead(): Promise<any> {
    const response: AxiosResponse<any> = await this.api.post('/auth/notifications/mark-all-read/');
    return response.data;
  }

  async deleteNotification(notificationId: string): Promise<any> {
    const response: AxiosResponse<any> = await this.api.delete(`/auth/notifications/${notificationId}/delete/`);
    return response.data;
  }

  async clearAllNotifications(): Promise<any> {
    const response: AxiosResponse<any> = await this.api.delete('/auth/notifications/clear-all/');
    return response.data;
  }

  // Utility methods
  isAuthenticated(): boolean {
    return !!localStorage.getItem('access_token');
  }

  getAuthToken(): string | null {
    return localStorage.getItem('access_token');
  }
}

export const apiService = new ApiService();
export default apiService;
