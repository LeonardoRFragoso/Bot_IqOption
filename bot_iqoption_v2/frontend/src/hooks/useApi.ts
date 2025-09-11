import { useState, useEffect, useCallback } from 'react';
import apiService from '../services/api';

// Generic hook for API calls
export function useApi<T>(
  apiCall: () => Promise<T>
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await apiCall();
      setData(result);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Erro na API';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [apiCall]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}

// Hook for dashboard data
export function useDashboard() {
  return useApi(() => apiService.getDashboardData());
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

// Hook for operations
export function useOperations(sessionId?: number) {
  return useApi(() => apiService.getOperations(sessionId));
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

// Hook for trading logs
export function useTradingLogs(sessionId?: number) {
  return useApi(() => apiService.getTradingLogs(sessionId));
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
