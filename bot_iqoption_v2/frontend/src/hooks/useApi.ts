import { useState, useEffect, useCallback, useRef } from 'react';
import apiService from '../services/api';

// Generic hook for API calls with smart polling
export function useApi<T>(
  apiCall: () => Promise<T>,
  options?: {
    autoRefresh?: boolean;
    refreshInterval?: number;
    pauseWhenHidden?: boolean;
  }
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isVisible, setIsVisible] = useState(true);
  // Global pause (e.g., while catalog analysis is running) to avoid duplicate polling
  const [externalPause, setExternalPause] = useState(false);
  // Track if initial load completed to avoid page flicker on auto-refresh
  const hasLoadedRef = useRef(false);

  const {
    autoRefresh = false,
    refreshInterval = 30000,
    pauseWhenHidden = true
  } = options || {};

  // Track page visibility to pause polling when tab is not active
  useEffect(() => {
    if (!pauseWhenHidden) return;

    const handleVisibilityChange = () => {
      setIsVisible(!document.hidden);
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [pauseWhenHidden]);

  // Listen to global analysis events to pause polling during heavy background tasks
  useEffect(() => {
    const handleCatalogRunning = () => setExternalPause(true);
    const handleCatalogStopped = () => setExternalPause(false);
    window.addEventListener('catalog-running', handleCatalogRunning);
    window.addEventListener('catalog-stopped', handleCatalogStopped);
    return () => {
      window.removeEventListener('catalog-running', handleCatalogRunning);
      window.removeEventListener('catalog-stopped', handleCatalogStopped);
    };
  }, []);

  const fetchData = useCallback(async () => {
    try {
      // Only show global loading during the very first load
      setLoading(!hasLoadedRef.current);
      setError(null);
      const result = await apiCall();
      setData(result);
      hasLoadedRef.current = true;
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Erro na API';
      setError(errorMessage);
    } finally {
      // Do not force loading=false earlier than necessary; keep it false for subsequent refreshes
      setLoading(false);
    }
  }, [apiCall]);

  useEffect(() => {
    fetchData();
  }, []); // Remove fetchData dependency to prevent infinite loop

  // Auto-refresh with smart pausing
  useEffect(() => {
    if (!autoRefresh || !isVisible || externalPause) return;

    const interval = setInterval(fetchData, refreshInterval);
    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, isVisible, externalPause, fetchData]);

  return { data, loading, error, refetch: fetchData };
}

// Hook for dashboard data - Smart polling enabled with conservative interval
const dashboardApiCall = () => apiService.getDashboardData();
export function useDashboard() {
  return useApi(
    dashboardApiCall,
    { 
      autoRefresh: true, // RE-ENABLED
      refreshInterval: 45000, // Increased to 45s for less frequent polling
      pauseWhenHidden: true 
    }
  );
}

// Hook for trading sessions
export function useTradingSessions() {
  return useApi(() => apiService.getTradingSessions());
}

// Hook for trading configuration
export function useTradingConfig() {
  const [config, setConfig] = useState<import('../types/index').TradingConfiguration | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConfig = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await apiService.getTradingConfig();
      setConfig(result);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Erro ao carregar configuração';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  const updateConfig = useCallback(async (newConfig: Partial<import('../types/index').TradingConfiguration>) => {
    try {
      setLoading(true);
      setError(null);
      const result = await apiService.updateTradingConfig(newConfig);
      setConfig(result);
      return result;
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Erro ao atualizar configuração';
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  return { config, loading, error, updateConfig, refetch: fetchConfig };
}

// Hook for operations - Smart polling enabled with conservative interval
export function useOperations(sessionId?: string | number) {
  const operationsApiCall = useCallback(() => apiService.getOperations(sessionId as any), [sessionId]);
  return useApi(
    operationsApiCall,
    { 
      autoRefresh: true, // RE-ENABLED
      refreshInterval: 60000, // 60s interval for operations
      pauseWhenHidden: true 
    }
  );
}

// Hook for asset catalog
export function useAssetCatalog() {
  const { data, loading, error, refetch } = useApi(() => apiService.getAssetCatalog());

  const runCatalog = useCallback(async () => {
    try {
      await apiService.runAssetCatalog();
      refetch();
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Erro ao executar catalogação';
      throw new Error(errorMessage);
    }
  }, [refetch]);

  return { data, loading, error, refetch, runCatalog };
}

// Hook for trading logs - Smart polling enabled with conservative interval
export function useTradingLogs(sessionId?: number) {
  const logsApiCall = useCallback(() => apiService.getTradingLogs(sessionId), [sessionId]);
  return useApi(
    logsApiCall,
    { 
      autoRefresh: true, // RE-ENABLED
      refreshInterval: 90000, // 90s interval for logs (least frequent)
      pauseWhenHidden: true 
    }
  );
}

// Hook for connection status
export function useConnectionStatus() {
  const [status, setStatus] = useState<import('../types/index').ApiResponse<unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const checkStatus = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await apiService.getConnectionStatus();
      setStatus(result);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Erro ao verificar conexão';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  const testConnection = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await apiService.testConnection();
      setStatus(result);
      return result;
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Erro ao testar conexão';
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { status, loading, error, checkStatus, testConnection };
}

// Hook for trading control
export function useTradingControl() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startTrading = useCallback(async (strategy: string, asset?: string, accountType?: string) => {
    try {
      setLoading(true);
      setError(null);
      
      // Get user profile to determine account type if not provided
      let finalAccountType = accountType;
      if (!finalAccountType) {
        try {
          const user = await apiService.getCurrentUser();
          finalAccountType = user.preferred_account_type || 'PRACTICE';
        } catch {
          finalAccountType = 'PRACTICE';
        }
      }
      
      const result = await apiService.startTrading(strategy, asset || 'EURUSD', finalAccountType);
      return result;
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Erro ao iniciar trading';
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const stopTrading = useCallback(async (sessionId?: string) => {
    try {
      setLoading(true);
      setError(null);
      
      // Get session ID if not provided
      let activeSessionId = sessionId;
      if (!activeSessionId) {
        const dashboardData = await apiService.getDashboardData();
        activeSessionId = dashboardData.current_session?.id?.toString();
      }
      
      if (!activeSessionId) {
        throw new Error('Nenhuma sessão ativa encontrada');
      }
      
      const result = await apiService.stopTrading(activeSessionId);
      return result;
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Erro ao parar trading';
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const pauseTrading = useCallback(async (sessionId?: string) => {
    try {
      setLoading(true);
      setError(null);
      
      // Get session ID if not provided
      let activeSessionId = sessionId;
      if (!activeSessionId) {
        const dashboardData = await apiService.getDashboardData();
        activeSessionId = dashboardData.current_session?.id?.toString();
      }
      
      if (!activeSessionId) {
        throw new Error('Nenhuma sessão ativa encontrada');
      }
      
      const result = await apiService.pauseTrading(activeSessionId);
      return result;
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Erro ao pausar trading';
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const resumeTrading = useCallback(async (sessionId?: string) => {
    try {
      setLoading(true);
      setError(null);
      
      // Get session ID if not provided
      let activeSessionId = sessionId;
      if (!activeSessionId) {
        const dashboardData = await apiService.getDashboardData();
        activeSessionId = dashboardData.current_session?.id?.toString();
      }
      
      if (!activeSessionId) {
        throw new Error('Nenhuma sessão ativa encontrada');
      }
      
      const result = await apiService.resumeTrading(activeSessionId);
      return result;
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Erro ao retomar trading';
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { 
    loading, 
    error, 
    startTrading, 
    stopTrading, 
    pauseTrading, 
    resumeTrading 
  };
}
