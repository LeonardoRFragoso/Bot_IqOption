// Types based on Django backend models

// API Response type
export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  message?: string;
  errors?: Record<string, string[]>;
}

export interface User {
  id: number;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  preferred_account_type: 'PRACTICE' | 'REAL';
  is_active_trader: boolean;
  phone?: string;
  created_at: string;
  updated_at: string;
}

export interface TradingConfiguration {
  id: number;
  // [AJUSTES] section
  tipo: 'automatico' | 'manual';
  valor_entrada: number;
  stop_win: number;
  stop_loss: number;
  analise_medias: boolean;
  velas_medias: number;
  tipo_par: 'automatico' | 'manual';
  // [MARTINGALE] section
  martingale_usar: boolean;
  martingale_niveis: number;
  martingale_fator: number;
  // [SOROS] section
  soros_usar: boolean;
  soros_niveis: number;
  // Additional fields
  default_strategy: 'mhi' | 'torres_gemeas' | 'mhi_m5' | 'rsi' | 'moving_average' | 'bollinger_bands';
  
  // Torres Gêmeas specific parameters
  torres_event_driven?: boolean;
  torres_event_cooldown_sec?: number;
  torres_timeframe?: number;
  torres_lookback?: number;
  torres_tolerancia_pct?: number;
  torres_break_buffer_pct?: number;
  
  // RSI specific parameters
  rsi_period?: number;
  rsi_oversold?: number;
  rsi_overbought?: number;
  rsi_timeframe?: number;
  
  // Moving Average specific parameters
  ma_fast_period?: number;
  ma_slow_period?: number;
  ma_timeframe?: number;
  
  // Bollinger Bands specific parameters
  bb_period?: number;
  bb_std_dev?: number;
  bb_touch_threshold?: number;
  bb_timeframe?: number;
  
  created_at: string;
  updated_at: string;
}

export interface TradingSession {
  id: string | number;
  user: number;
  status: 'STOPPED' | 'RUNNING' | 'PAUSED' | 'ERROR';
  strategy: 'mhi' | 'torres_gemeas' | 'mhi_m5' | 'rsi' | 'moving_average' | 'bollinger_bands';
  account_type: 'PRACTICE' | 'REAL';
  initial_balance: number;
  current_balance: number;
  total_operations: number;
  successful_operations: number;
  win_rate: number;
  total_profit_loss: number;
  is_active: boolean;
  started_at: string;
  ended_at?: string;
  created_at: string;
  updated_at: string;
}

export interface Operation {
  id: string | number;
  session: string | number;
  asset: string;
  direction: 'call' | 'put';
  amount: number;
  expiration_time: number;
  entry_price: number;
  exit_price?: number;
  result?: 'win' | 'loss' | 'draw' | 'pending';
  profit_loss?: number;
  strategy_used: string;
  martingale_level: number;
  soros_level: number;
  created_at: string;
  closed_at?: string;
}

export interface AssetCatalog {
  asset: string;
  strategy: string;
  win_rate: number;
  gale1_rate: number;
  gale2_rate: number;
  gale3_rate: number;
  total_samples: number;
  analyzed_at: string;
}

export interface TradingLog {
  id: number;
  session?: number;
  level: 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG';
  message: string;
  details?: Record<string, unknown>;
  created_at: string;
}

export interface MarketData {
  id: number;
  asset: string;
  timestamp: string;
  open_price: number;
  close_price: number;
  high_price: number;
  low_price: number;
  volume?: number;
  created_at: string;
}

export interface AssetPerformance {
  asset: string;
  win_rate: number;
  total_operations: number;
  profit_loss: number;
}

export interface DashboardData {
  current_session: TradingSession | null;
  recent_operations: Operation[];
  session_stats: {
    total_sessions: number;
    active_sessions: number;
    total_profit: number;
    win_rate: number;
    best_strategy: string;
    best_asset: string;
  };
  recent_logs: TradingLog[];
  account_balance: number;
  connection_status: boolean;
  total_balance: number;
  today_profit_loss: number;
  win_rate: number;
  total_operations: number;
  asset_performance: AssetPerformance[];
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  username: string;
  password: string;
  password_confirm: string;
  first_name: string;
  last_name: string;
  phone?: string;
}

export interface RegisterResponse {
  user: User;
  tokens: AuthTokens;
}

export interface IQOptionCredentials {
  iq_email: string;
  iq_password: string;
}

// Billing / Subscription types
export interface SubscriptionStatus {
  is_subscribed: boolean;
  active_until?: string | null;
  preference_id?: string;
  init_point?: string;
  public_key?: string;
}

export interface AdminUserSubscriptionInfo {
  id: number;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  is_subscribed: boolean;
  active_until?: string | null;
  date_joined: string;
}

export interface PaymentRecord {
  id: number;
  user: number;
  user_email: string;
  mp_payment_id: string;
  mp_preference_id?: string;
  external_reference?: string;
  status: string;
  amount: number;
  currency: string;
  description: string;
  paid_at?: string;
  created_at: string;
}
