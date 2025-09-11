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
  default_strategy: 'mhi' | 'torres_gemeas' | 'mhi_m5';
  created_at: string;
  updated_at: string;
}

export interface TradingSession {
  id: number;
  user: number;
  status: 'STOPPED' | 'RUNNING' | 'PAUSED' | 'ERROR';
  strategy: 'mhi' | 'torres_gemeas' | 'mhi_m5';
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
  id: number;
  session: number;
  asset: string;
  direction: 'call' | 'put';
  amount: number;
  expiration_time: number;
  entry_price: number;
  exit_price?: number;
  result?: 'win' | 'loss';
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
