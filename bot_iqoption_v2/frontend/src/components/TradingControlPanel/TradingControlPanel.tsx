import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Box,
  Typography,
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  IconButton,
  Tooltip,
  LinearProgress,
  Divider,
  Alert,
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  Stop,
  Settings,
  Assessment,
  AutoAwesome,
} from '@mui/icons-material';
import apiService from '../../services/api';
import type { TradingSession, Operation, Asset, Strategy } from '../../types/index';
import { useTradingRealtime } from '../../hooks/useRealtime';
import StrategyFiltersConfig from '../StrategyFiltersConfig/StrategyFiltersConfig';
import type { StrategyFilterConfig } from '../StrategyFiltersConfig/StrategyFiltersConfig';

interface TradingControlPanelProps {
  onSessionChange?: (session: TradingSession | null) => void;
}

const TradingControlPanel: React.FC<TradingControlPanelProps> = ({ onSessionChange }) => {
  const [selectedAsset, setSelectedAsset] = useState<string>('');
  const [selectedStrategy, setSelectedStrategy] = useState<string>('');
  const [tradingStatus, setTradingStatus] = useState<'stopped' | 'running' | 'paused'>('stopped');
  const [currentSession, setCurrentSession] = useState<TradingSession | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const { socket } = useTradingRealtime();
  const [liveOps, setLiveOps] = useState<Map<string, Operation>>(new Map());
  const [isStarting, setIsStarting] = useState(false);
  const [strategyFilterConfig, setStrategyFilterConfig] = useState<StrategyFilterConfig>({
    enableFilters: false,
    confirmationFilters: [],
    confirmationThreshold: 0.6,
    filterWeights: {}
  });

  // Trading control functions will use apiService directly

  // Poll for catalog completion
  const waitForCatalogCompletionRef = React.useRef<() => Promise<void>>(undefined);
  waitForCatalogCompletionRef.current = async () => {
    const maxWaitTime = 300000; // 5 minutes max
    const pollInterval = 3000; // 3s for responsive UX
    const start = Date.now();
    while (Date.now() - start < maxWaitTime) {
      try {
        const status = await apiService.getCatalogStatus();
        if (status && status.running === false) {
          setIsAnalyzing(false);
          try { window.dispatchEvent(new CustomEvent('catalog-stopped')); } catch {}
          try { window.dispatchEvent(new CustomEvent('catalog-completed')); } catch {}
          await loadAssetsAndStrategies(true);
          setTimeout(() => { loadAssetsAndStrategies(false).catch(() => {}); }, 500);
          break;
        }
      } catch (e) {
        console.warn('catalog status check failed:', e);
      }
      await new Promise(r => setTimeout(r, pollInterval));
    }
  };

  // Check catalog status on mount and sync with backend
  const checkCatalogStatus = async () => {
    try {
      const status = await apiService.getCatalogStatus();
      if (status && status.running === true) {
        setIsAnalyzing(true);
        // Start polling for completion
        waitForCatalogCompletionRef.current?.();
      }
    } catch {
      // ignore
    }
  };

  // Load real data from API and sync with active session
  useEffect(() => {
    (async () => {
      // First, load assets and strategies
      await loadAssetsAndStrategies();
      checkCatalogStatus();
      
      // Then sync with backend session state (WITHOUT auto-pausing)
      try {
        const active = await apiService.getActiveSession();
        if (active) {
          setCurrentSession(active);
          const status = (active as any).status as string;
          // Just reflect the real status - don't auto-pause
          if (status === 'RUNNING') {
            setTradingStatus('running');
          } else if (status === 'PAUSED') {
            setTradingStatus('paused');
          } else {
            setTradingStatus('stopped');
          }
          
          // Restore the asset and strategy from active session
          const sessionAsset = (active as any).asset;
          const sessionStrategy = (active as any).strategy;
          if (sessionAsset) {
            setSelectedAsset(sessionAsset);
            // Ensure the session asset is in the assets list
            setAssets(prev => {
              if (!prev.find(a => a.id === sessionAsset)) {
                return [...prev, { id: sessionAsset, name: sessionAsset, payout: 80, isOpen: true }];
              }
              return prev;
            });
          }
          if (sessionStrategy) {
            setSelectedStrategy(sessionStrategy);
            // Ensure the session strategy is in the strategies list
            setStrategies(prev => {
              if (!prev.find(s => s.id === sessionStrategy)) {
                return [...prev, { id: sessionStrategy, name: sessionStrategy, description: sessionStrategy }];
              }
              return prev;
            });
          }
        } else {
          setTradingStatus('stopped');
        }
      } catch {
        // ignore
      }
    })();
  }, []);

  // Load last operations for current session and subscribe to WS updates
  useEffect(() => {
    (async () => {
      try {
        if (currentSession?.id) {
          const ops = await apiService.getOperations(currentSession.id as any);
          const map = new Map<string, Operation>();
          (Array.isArray(ops) ? ops : []).slice(0, 10).forEach((op) => map.set(String(op.id), op));
          setLiveOps(map);
        } else {
          setLiveOps(new Map());
        }
      } catch {
        // ignore
      }
    })();
  }, [currentSession?.id]);

  useEffect(() => {
    const onOpUpdate = (msg: any) => {
      const data = msg?.data || msg;
      if (!data) return;
      const sessionMatch = !currentSession?.id || String(data.session) === String(currentSession?.id);
      if (!sessionMatch) return;
      const op: Operation = {
        id: data.id,
        session: data.session,
        asset: String(data.asset),
        direction: (data.direction as any) || 'call',
        amount: Number(data.amount ?? data.entry_price ?? 0),
        expiration_time: Number(data.expiration_time ?? 0),
        entry_price: Number(data.entry_price ?? 0),
        exit_price: typeof data.exit_price === 'number' ? data.exit_price : undefined,
        result: data.result as any,
        profit_loss: typeof data.profit_loss === 'number' ? data.profit_loss : undefined,
        strategy_used: String(data.strategy_used ?? ''),
        martingale_level: Number(data.martingale_level ?? 0),
        soros_level: Number(data.soros_level ?? 0),
        created_at: String(data.created_at ?? new Date().toISOString()),
        closed_at: data.closed_at ? String(data.closed_at) : undefined,
      };
      setLiveOps((prev) => {
        const map = new Map(prev);
        map.set(String(op.id), op);
        return map;
      });
    };
    
    // Listen for session updates (stop win/loss)
    const onSessionUpdate = (msg: any) => {
      const data = msg?.data || {};
      if (data && data.status) {
        const status = String(data.status).toUpperCase();
        if (status === 'STOPPED' || status === 'ERROR') {
          console.log('[TradingControlPanel] Session stopped via WS:', status);
          setTradingStatus('stopped');
          setCurrentSession(null);
          onSessionChange?.(null);
        } else if (status === 'RUNNING') {
          setTradingStatus('running');
        } else if (status === 'PAUSED') {
          setTradingStatus('paused');
        }
      }
    };
    
    socket.on('operation_update', onOpUpdate);
    socket.on('session_update', onSessionUpdate);
    return () => {
      socket.off('operation_update', onOpUpdate);
      socket.off('session_update', onSessionUpdate);
    };
  }, [socket, currentSession?.id, onSessionChange]);

  // Fallback polling: check session status every 5s when running
  // This catches stop win/loss even if WebSocket misses the event
  useEffect(() => {
    if (tradingStatus !== 'running') return;
    
    const checkSessionStatus = async () => {
      try {
        const active = await apiService.getActiveSession();
        if (!active) {
          // Session ended (stop win/loss or manual stop)
          console.log('[TradingControlPanel] Session ended via polling');
          setTradingStatus('stopped');
          setCurrentSession(null);
          onSessionChange?.(null);
        } else {
          const status = String((active as any).status || '').toUpperCase();
          if (status === 'STOPPED' || status === 'ERROR') {
            console.log('[TradingControlPanel] Session stopped via polling:', status);
            setTradingStatus('stopped');
            setCurrentSession(null);
            onSessionChange?.(null);
          }
        }
      } catch {
        // ignore
      }
    };
    
    const interval = setInterval(checkSessionStatus, 5000);
    return () => clearInterval(interval);
  }, [tradingStatus, onSessionChange]);

  const loadAssetsAndStrategies = async (lightMode: boolean = false) => {
    try {
      // Use getBestAssets() for consistency with Trading page
      // This ensures Dashboard and Trading show the same recommended assets
      let realAssets: Asset[] = [];
      
      try {
        const bestAssetsResponse = await apiService.getBestAssets({
          min_win_rate: 55,
          min_gale1_rate: 70,
          max_results: 25,
        });
        
        if (bestAssetsResponse?.assets && Array.isArray(bestAssetsResponse.assets)) {
          realAssets = bestAssetsResponse.assets.map((result: any) => ({
            id: result.asset,
            name: result.asset,
            payout: 80,
            isOpen: true,
            winRate: Math.round(parseFloat(String(result.gale1_rate || result.win_rate || 0))),
            strategy: result.strategy,
            score: parseFloat(String(result.score || 0)),
            isRecommended: result.is_recommended || false,
          }));
        }
      } catch (err) {
        console.warn('Could not fetch best assets, falling back to catalog:', err);
      }
      
      // Fallback to catalog results if getBestAssets() returns empty
      if (realAssets.length === 0) {
        const catalogResults = await apiService.getAssetCatalog();
        
        // Deduplicate by asset symbol: keep the best score per asset
        const bestByAsset = new Map<string, any>();
        for (const r of catalogResults) {
          const key = r.asset;
          const gale2 = parseFloat(String(r.gale2_rate || 0));
          const winRate = parseFloat(String(r.win_rate || 0));
          const score = gale2 || winRate || 0;
          const current = bestByAsset.get(key);
          if (!current) {
            bestByAsset.set(key, { ...r, _score: score });
          } else {
            const curScore = current._score || 0;
            if (score > curScore) bestByAsset.set(key, { ...r, _score: score });
          }
        }
        const uniqueResults = Array.from(bestByAsset.values());

        // Transform to Asset format
        const fxRegex = /^[A-Z]{3,6}(-OTC)?$/;
        realAssets = uniqueResults
          .filter((r: any) => typeof r.asset === 'string' && fxRegex.test(r.asset))
          .map((result: any) => ({
            id: result.asset,
            name: result.asset,
            payout: parseFloat(String(result.payout || 0)) || 80,
            isOpen: true,
            winRate: Math.round(parseFloat(String(result.gale2_rate || result.win_rate || 0)))
          }));
      }

      // Get market status for additional asset info (skip on light mode)
      if (!lightMode) {
        try {
          const marketStatus = await apiService.getMarketStatus();
          if (Array.isArray(marketStatus.open_assets) && marketStatus.open_assets.length > 0) {
            // Update assets only when we have a non-empty list from backend
            realAssets.forEach(asset => {
              const marketAsset = marketStatus.open_assets.find((ma: any) => ma === asset.id);
              asset.isOpen = !!marketAsset;
            });
          }
        } catch (error) {
          console.warn('Could not load market status:', error);
        }
      }

      // Fetch live payouts ONLY if already connected (skip on light mode to liberar UI rápido)
      if (!lightMode) {
        try {
          // Check connection status first
          const conn: any = await apiService.getConnectionStatus();
          const isConnected = !!(conn && (conn as any).connected);
          
          if (isConnected) {
            // Additional payout fetching logic could go here
          }
        } catch (err) {
          console.warn('Could not fetch live payouts:', err);
        }
      }

      // 2) Get real strategy performance data from catalog results
      let strategyPerformance: { [key: string]: number } = {};
      try {
        const catalogResponse = await apiService.getCatalogResults();
        if (catalogResponse && Array.isArray(catalogResponse)) {
          // Calculate average win rate for each strategy across all assets
          const strategyStats: { [key: string]: { total: number, count: number } } = {};
          
          catalogResponse.forEach((result: any) => {
            if (result.strategy) {
              // Parse gale3_rate as float (backend sends Decimal as string)
              const gale3 = parseFloat(String(result.gale3_rate || 0));
              if (gale3 > 0) {
                if (!strategyStats[result.strategy]) {
                  strategyStats[result.strategy] = { total: 0, count: 0 };
                }
                strategyStats[result.strategy].total += gale3;
                strategyStats[result.strategy].count += 1;
              }
            }
          });

          // Calculate averages
          Object.keys(strategyStats).forEach(strategy => {
            const stats = strategyStats[strategy];
            if (stats.count > 0) {
              strategyPerformance[strategy] = Math.round(stats.total / stats.count);
            }
          });
        }
      } catch (err) {
        console.warn('Could not fetch catalog results for strategy performance:', err);
      }

      // Define strategies with real performance data when available (NO fallback values)
      const strategies: Strategy[] = [
        { 
          id: 'mhi', 
          name: 'MHI', 
          description: 'Média Móvel com Indicadores', 
          winRate: strategyPerformance['mhi'] || undefined,
          recommended: (strategyPerformance['mhi'] || 0) >= 70 
        },
        { 
          id: 'torres_gemeas', 
          name: 'Torres Gêmeas', 
          description: 'Estratégia de Reversão', 
          winRate: strategyPerformance['torres_gemeas'] || undefined,
          recommended: (strategyPerformance['torres_gemeas'] || 0) >= 70 
        },
        { 
          id: 'mhi_m5', 
          name: 'MHI M5', 
          description: 'MHI para timeframe de 5 minutos', 
          winRate: strategyPerformance['mhi_m5'] || undefined,
          recommended: (strategyPerformance['mhi_m5'] || 0) >= 70 
        },
        { 
          id: 'rsi', 
          name: 'RSI', 
          description: 'Índice de Força Relativa', 
          winRate: strategyPerformance['rsi'] || undefined,
          recommended: (strategyPerformance['rsi'] || 0) >= 70 
        },
        { 
          id: 'bollinger_bands', 
          name: 'Bollinger Bands', 
          description: 'Bandas de Bollinger', 
          winRate: strategyPerformance['bollinger_bands'] || undefined,
          recommended: (strategyPerformance['bollinger_bands'] || 0) >= 70 
        },
        { 
          id: 'macd', 
          name: 'MACD', 
          description: 'Moving Average Convergence Divergence', 
          winRate: strategyPerformance['macd'] || undefined,
          recommended: (strategyPerformance['macd'] || 0) >= 70 
        },
      ];

      // Use real data if available, otherwise fallback to defaults
      if (realAssets.length > 0) {
        // Cap winRate at 100% (fix any data issues)
        realAssets.forEach(a => {
          if (a.winRate && a.winRate > 100) a.winRate = 100;
        });
        
        // 3) Sort assets: by winRate (best first), then open status, then alphabetical
        realAssets.sort((a, b) => {
          // First: sort by winRate (higher is better)
          const winRateScore = (b.winRate || 0) - (a.winRate || 0);
          if (winRateScore !== 0) return winRateScore;
          // Then: open assets first
          const openScore = (b.isOpen ? 1 : 0) - (a.isOpen ? 1 : 0);
          if (openScore !== 0) return openScore;
          // Finally: alphabetical
          return a.id.localeCompare(b.id);
        });

        // Filter: only show assets with winRate > 0 (cataloged) at the top
        // Keep others at the end for manual selection if needed
        const catalogedAssets = realAssets.filter(a => (a.winRate || 0) > 0);
        const uncatalogedAssets = realAssets.filter(a => (a.winRate || 0) === 0);
        const sortedAssets = [...catalogedAssets, ...uncatalogedAssets];

        setAssets(sortedAssets);
        
        // Prefer the best open asset; if none, pick the overall best by winRate
        let bestAsset = sortedAssets
          .filter(a => a.isOpen && (a.winRate || 0) >= 60)
          .sort((a, b) => (b.winRate || 0) - (a.winRate || 0))[0];

        if (!bestAsset) {
          bestAsset = [...sortedAssets].sort((a, b) => (b.winRate || 0) - (a.winRate || 0))[0];
        }
        
        if (bestAsset) setSelectedAsset(bestAsset.id);
      } else {
        // Fallback to basic assets if no catalog data
        const fallbackAssets: Asset[] = [
          { id: 'EURUSD', name: 'EUR/USD', payout: 80, isOpen: true },
          { id: 'GBPUSD', name: 'GBP/USD', payout: 80, isOpen: true },
          { id: 'USDJPY', name: 'USD/JPY', payout: 80, isOpen: true },
          { id: 'AUDUSD', name: 'AUD/USD', payout: 80, isOpen: true },
          { id: 'USDCAD', name: 'USD/CAD', payout: 80, isOpen: true },
        ];
        setAssets(fallbackAssets);
        setSelectedAsset('EURUSD');
      }

      setStrategies(strategies);
      
      // Set recommended strategy as default
      const recommendedStrategy = strategies.find(s => s.recommended);
      if (recommendedStrategy) setSelectedStrategy(recommendedStrategy.id);
      
    } catch (error) {
      console.error('Failed to load assets and strategies:', error);
      
      // Fallback to basic data on error
      const fallbackAssets: Asset[] = [
        { id: 'EURUSD', name: 'EUR/USD', payout: 80, isOpen: true },
        { id: 'GBPUSD', name: 'GBP/USD', payout: 80, isOpen: true },
        { id: 'USDJPY', name: 'USD/JPY', payout: 80, isOpen: true },
      ];
      
      const fallbackStrategies: Strategy[] = [
        { id: 'mhi', name: 'MHI', description: 'Média Móvel com Indicadores', recommended: false },
        { id: 'torres_gemeas', name: 'Torres Gêmeas', description: 'Estratégia de Reversão', recommended: false },
        { id: 'mhi_m5', name: 'MHI M5', description: 'MHI para timeframe de 5 minutos', recommended: false },
      ];
      
      setAssets(fallbackAssets);
      setStrategies(fallbackStrategies);
      setSelectedAsset('EURUSD');
      setSelectedStrategy('mhi');
    }
  };

  const handleStartTrading = async () => {
    if (!selectedAsset || !selectedStrategy) return;
    
    try {
      setIsStarting(true);
      
      // Save filters to user configuration first
      if (strategyFilterConfig.enableFilters && strategyFilterConfig.confirmationFilters.length > 0) {
        try {
          await apiService.updateTradingConfig({
            filtros_ativos: strategyFilterConfig.confirmationFilters,
            media_movel_threshold: strategyFilterConfig.filterWeights['moving_average'] || 0.15,
            rodrigo_risco_threshold: strategyFilterConfig.confirmationThreshold || 0.75
          });
        } catch (error) {
          console.error('Failed to save filters:', error);
        }
      }
      
      // Prepare strategy configuration with filters
      const strategyConfig = {
        strategy: selectedStrategy,
        ...(strategyFilterConfig.enableFilters && {
          confirmation_filters: strategyFilterConfig.confirmationFilters,
          confirmation_threshold: strategyFilterConfig.confirmationThreshold,
          filter_weights: strategyFilterConfig.filterWeights
        })
      };
      
      // Prevent 400 if there is an active session (RUNNING/PAUSED)
      try {
        const active = await apiService.getActiveSession();
        if (active) {
          alert('Você já possui uma sessão ativa (Rodando ou Pausada). Pare a sessão atual antes de iniciar uma nova.');
          return;
        }
      } catch {
        // ignore
      }

      // Fetch preferred account type and send explicitly (default to REAL)
      let accountType = 'REAL';
      try {
        const user: any = await apiService.getCurrentUser();
        if (user && user.preferred_account_type) {
          accountType = user.preferred_account_type;
        }
        console.log('[Trading] Usando conta:', accountType);
      } catch (err) {
        console.warn('[Trading] Falha ao obter tipo de conta, usando REAL:', err);
        accountType = 'REAL';
      }

      const session = await apiService.startTrading(selectedStrategy, selectedAsset, accountType, strategyConfig);
      setCurrentSession(session);
      setTradingStatus('running');
      onSessionChange?.(session);
    } catch (error) {
      console.error('Failed to start trading:', error);
      // Try to show backend message when available
      const anyErr = error as any;
      const backendMsg = anyErr?.response?.data?.error || anyErr?.message || '';
      alert(`Não foi possível iniciar o trading. ${backendMsg ? 'Detalhes: ' + backendMsg : 'Verifique credenciais da IQ Option, conta (Demo/Real) e o ativo selecionado.'}`);
    } finally {
      setIsStarting(false);
    }
  };

  const handlePauseTrading = async () => {
    if (!currentSession) return;
    
    try {
      await apiService.pauseTrading(currentSession.id.toString());
      setTradingStatus('paused');
    } catch (error) {
      console.error('Failed to pause trading:', error);
    }
  };

  const handleResumeTrading = async () => {
    if (!currentSession) return;
    
    try {
      await apiService.resumeTrading(currentSession.id.toString());
      setTradingStatus('running');
    } catch (error) {
      console.error('Failed to resume trading:', error);
    }
  };

  const handleStopTrading = async () => {
    if (!currentSession) return;
    
    try {
      await apiService.stopTrading(currentSession.id.toString());
      setCurrentSession(null);
      setTradingStatus('stopped');
      onSessionChange?.(null);
    } catch (error) {
      console.error('Failed to stop trading:', error);
    }
  };

  const handleAnalyzeAssets = async () => {
    setIsAnalyzing(true);
    // Broadcast that catalog is running to pause global polling
    try {
      window.dispatchEvent(new CustomEvent('catalog-running'));
    } catch {
      // ignore
    }
    try {
      // Get user's preferred account type
      let accountType = 'REAL';
      try {
        const user: any = await apiService.getCurrentUser();
        accountType = (user && user.preferred_account_type) || 'REAL';
      } catch {
        // Use REAL as default
      }
      // Catalogar apenas estratégias principais (RSI, Bollinger, etc. são filtros de confirmação)
      await apiService.runAssetCatalog(['mhi', 'torres_gemeas', 'mhi_m5'], accountType);
      
      // Poll for completion using the ref
      if (waitForCatalogCompletionRef.current) {
        await waitForCatalogCompletionRef.current();
      }
      
    } catch (error) {
      console.error('Failed to analyze assets:', error);
    } finally {
      // Se por algum motivo não liberamos acima, garanta a liberação aqui
      setIsAnalyzing(prev => {
        if (prev) {
          try { window.dispatchEvent(new CustomEvent('catalog-stopped')); } catch {}
        }
        return false;
      });
    }
  };

  const selectedAssetData = assets.find(a => a.id === selectedAsset);
  const selectedStrategyData = strategies.find(s => s.id === selectedStrategy);

  return (
    <Card sx={{ 
      background: 'linear-gradient(135deg, #1A1A1A 0%, #2A2A2A 100%)',
      border: '1px solid #333333',
      borderRadius: '16px',
      overflow: 'visible'
    }}>
      <CardContent sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <AutoAwesome sx={{ color: 'primary.main', fontSize: 28 }} />
            <Typography variant="h5" sx={{ 
              fontWeight: 600,
              background: 'linear-gradient(135deg, #FFD700 0%, #FFA000 100%)',
              backgroundClip: 'text',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent'
            }}>
              Centro de Controle de Trading
            </Typography>
          </Box>
          
          <Chip 
            label={tradingStatus === 'running' ? 'ATIVO' : tradingStatus === 'paused' ? 'PAUSADO' : 'PARADO'}
            color={tradingStatus === 'running' ? 'success' : tradingStatus === 'paused' ? 'warning' : 'error'}
            sx={{ fontWeight: 'bold' }}
          />
        </Box>

        {tradingStatus === 'running' && (
          <Box sx={{ mb: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
              <Typography variant="body2" sx={{ color: '#B0B0B0' }}>
                Sessão em andamento
              </Typography>
              {/* Placar atual - conta séries (entrada + gales), não operações individuais */}
              {(() => {
                const ops = Array.from(liveOps.values());
                // WIN: qualquer operação WIN na série conta como 1 vitória
                // LOSS: apenas quando a entrada E todos os gales perdem
                
                // Identificar entradas: martingale_level === 0 OU operation_type === 'ENTRY'
                const entries = ops.filter(op => {
                  const opType = (op.operation_type || '').toUpperCase();
                  return opType === 'ENTRY' || op.martingale_level === 0;
                });
                
                let wins = 0;
                let losses = 0;
                const processedEntries = new Set<string>();
                
                entries.forEach(entry => {
                  // Criar chave única para esta entrada
                  const entryKey = `${entry.id}`;
                  
                  // Evitar processar a mesma entrada duas vezes
                  if (processedEntries.has(entryKey)) return;
                  processedEntries.add(entryKey);
                  
                  const entryTime = new Date(entry.created_at).getTime();
                  
                  // Encontrar todas as operações desta série (mesmo ativo, até 5 minutos após)
                  const seriesOps = ops.filter(op => {
                    const opTime = new Date(op.created_at).getTime();
                    return op.asset === entry.asset && opTime >= entryTime && opTime <= entryTime + 300000;
                  });
                  
                  // Se qualquer operação da série ganhou, é WIN
                  const hasWin = seriesOps.some(op => op.result?.toLowerCase() === 'win');
                  // Se todas terminaram e nenhuma ganhou, é LOSS
                  const allClosed = seriesOps.every(op => {
                    const r = op.result?.toLowerCase();
                    return r && r !== 'pending';
                  });
                  const allLost = seriesOps.length > 0 && seriesOps.every(op => {
                    const r = op.result?.toLowerCase();
                    return r === 'loss' || r === 'draw';
                  });
                  
                  if (hasWin) {
                    wins++;
                  } else if (allClosed && allLost) {
                    losses++;
                  }
                });
                
                const diff = wins - losses;
                return (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="body2" sx={{ 
                      color: diff > 0 ? '#4CAF50' : diff < 0 ? '#F44336' : '#B0B0B0',
                      fontWeight: 'bold'
                    }}>
                      Placar: {wins}x{losses}
                    </Typography>
                    {diff !== 0 && (
                      <Chip 
                        label={diff > 0 ? `+${diff}` : `${diff}`}
                        size="small"
                        color={diff > 0 ? 'success' : 'error'}
                        sx={{ minWidth: 40 }}
                      />
                    )}
                  </Box>
                );
              })()}
            </Box>
            <LinearProgress 
              variant="indeterminate" 
              sx={{ 
                height: 4,
                borderRadius: 2,
                backgroundColor: 'rgba(255, 215, 0, 0.1)',
                '& .MuiLinearProgress-bar': {
                  background: 'linear-gradient(135deg, #FFD700 0%, #FFA000 100%)',
                }
              }} 
            />
            {/* Mini feed de operações (últimas 3) */}
            <Box sx={{ mt: 2, display: 'grid', gap: 1 }}>
              {Array.from(liveOps.values())
                .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
                .slice(0, 3)
                .map((op) => {
                  const isPending = !op.result || op.result === 'pending';
                  const isWin = op.result === 'win';
                  const resultLabel = isPending ? 'PENDENTE' : isWin ? 'WIN' : (op.result === 'draw' ? 'DRAW' : 'LOSS');
                  const resultColor: any = isPending ? 'warning' : isWin ? 'success' : (op.result === 'draw' ? 'info' : 'error');
                  const galeLabel = op.martingale_level > 0 ? `Gale ${op.martingale_level}` : 'Entrada';
                  return (
                    <Box key={String(op.id)} sx={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      p: 1,
                      border: '1px solid #333', borderRadius: 1,
                      backgroundColor: 'rgba(255, 255, 255, 0.02)'
                    }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
                        <Chip label={galeLabel} size="small" color="default" variant="outlined" />
                        <Typography variant="body2" sx={{ color: '#E0E0E0' }} noWrap>
                          {op.asset} · {op.direction?.toUpperCase()} · ${op.amount?.toFixed(2)}
                        </Typography>
                      </Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Chip label={resultLabel} size="small" color={resultColor} />
                        {!isPending && typeof op.profit_loss === 'number' && (
                          <Typography variant="body2" sx={{ color: op.profit_loss >= 0 ? 'success.main' : 'error.main', fontWeight: 600 }}>
                            {op.profit_loss >= 0 ? '+' : ''}{op.profit_loss.toFixed(2)}
                          </Typography>
                        )}
                      </Box>
                    </Box>
                  );
                })}
              {Array.from(liveOps.values()).length === 0 && (
                <Typography variant="caption" color="text.secondary">Aguardando operações...</Typography>
              )}
            </Box>
          </Box>
        )}

        <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
          <Box sx={{ flex: '1 1 300px', minWidth: '300px' }}>
            <FormControl fullWidth>
              <InputLabel>Ativo</InputLabel>
              <Select
                value={selectedAsset}
                onChange={(e) => setSelectedAsset(e.target.value)}
                label="Ativo"
                sx={{
                  '& .MuiOutlinedInput-root': {
                    '& fieldset': {
                      borderColor: '#333333',
                    },
                    '&:hover fieldset': {
                      borderColor: '#FFD700',
                    },
                    '&.Mui-focused fieldset': {
                      borderColor: '#FFD700',
                    },
                  },
                }}
              >
                {assets
                  .filter(asset => asset.winRate !== undefined && asset.winRate !== null && asset.winRate > 0) // Only show assets with valid winRate
                  .sort((a, b) => (b.winRate || 0) - (a.winRate || 0)) // Sort by winRate descending
                  .map((asset) => {
                    const rate = asset.winRate || 0;
                    return (
                      <MenuItem key={asset.id} value={asset.id}>
                        <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                          <Typography sx={{ flexGrow: 1 }}>{asset.name}</Typography>
                          <Box sx={{ display: 'flex', gap: 1 }}>
                            {rate > 0 && (
                              <Chip 
                                label={`${rate}%`} 
                                size="small" 
                                color={rate >= 70 ? 'success' : rate >= 60 ? 'warning' : 'error'}
                              />
                            )}
                            {asset.id.endsWith('-OTC') && (
                              <Chip 
                                label="OTC" 
                                size="small" 
                                color="secondary"
                                variant="outlined"
                              />
                            )}
                          </Box>
                        </Box>
                      </MenuItem>
                    );
                  })}
              </Select>
            </FormControl>
          </Box>

          <Box sx={{ flex: '1 1 300px', minWidth: '300px' }}>
            <FormControl fullWidth>
              <InputLabel>Estratégia</InputLabel>
              <Select
                value={selectedStrategy}
                onChange={(e) => setSelectedStrategy(e.target.value)}
                label="Estratégia"
                sx={{
                  '& .MuiOutlinedInput-root': {
                    '& fieldset': {
                      borderColor: '#333333',
                    },
                    '&:hover fieldset': {
                      borderColor: '#FFD700',
                    },
                    '&.Mui-focused fieldset': {
                      borderColor: '#FFD700',
                    },
                  },
                }}
              >
                {strategies.map((strategy) => (
                  <MenuItem key={strategy.id} value={strategy.id}>
                    <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                      <Box sx={{ flexGrow: 1 }}>
                        <Typography>{strategy.name}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          {strategy.description}
                        </Typography>
                      </Box>
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        {strategy.winRate && (
                          <Chip 
                            label={`${strategy.winRate}%`} 
                            size="small" 
                            color={strategy.winRate > 70 ? 'success' : 'warning'}
                          />
                        )}
                        {strategy.recommended && (
                          <Chip 
                            label="Recomendada" 
                            size="small" 
                            color="success"
                            icon={<AutoAwesome />}
                          />
                        )}
                      </Box>
                    </Box>
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>
        </Box>

        {isAnalyzing && (
          <Alert 
            severity="warning"
            sx={{ 
              mt: 2, 
              backgroundColor: 'rgba(255, 193, 7, 0.1)',
              border: '1px solid rgba(255, 193, 7, 0.3)',
              '& .MuiAlert-message': { color: '#FFFFFF' }
            }}
          >
            <Typography variant="body2">
              <strong>Catalogação em andamento...</strong> Aguarde a finalização da análise dos ativos para iniciar o trading com dados atualizados.
            </Typography>
          </Alert>
        )}

        {!isAnalyzing && selectedAssetData && selectedStrategyData && (
          <Alert 
            severity="info"
            sx={{ 
              mt: 2, 
              backgroundColor: 'rgba(0, 176, 255, 0.1)',
              border: '1px solid rgba(0, 176, 255, 0.3)',
              '& .MuiAlert-message': { color: '#FFFFFF' }
            }}
          >
            <Typography variant="body2">
              <strong>{selectedAssetData.name}</strong> com estratégia <strong>{selectedStrategyData.name}</strong>
              {selectedAssetData.winRate ? (
                <span> - Taxa de acerto (catalogação): <strong style={{ color: '#00E676' }}>
                  {selectedAssetData.winRate}%
                </strong></span>
              ) : selectedStrategyData.winRate ? (
                <span> - Taxa média da estratégia: <strong style={{ color: '#00E676' }}>
                  {selectedStrategyData.winRate}%
                </strong></span>
              ) : (
                <span style={{ color: '#FFA000' }}> - Execute a catalogação para ver taxas de acerto</span>
              )}
            </Typography>
          </Alert>
        )}

        <Divider sx={{ my: 3, borderColor: '#333333' }} />

        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          {tradingStatus === 'stopped' && (
            <Button
              variant="contained"
              color="success"
              size="large"
              startIcon={<PlayArrow />}
              onClick={handleStartTrading}
              disabled={!selectedAsset || !selectedStrategy || isAnalyzing || isStarting}
              sx={{ 
                minWidth: 150,
                background: 'linear-gradient(135deg, #00E676 0%, #00C853 100%)',
                '&:hover': {
                  background: 'linear-gradient(135deg, #00C853 0%, #00A152 100%)',
                }
              }}
            >
              {isStarting ? 'INICIANDO...' : 'INICIAR TRADING'}
            </Button>
          )}

          {tradingStatus === 'running' && (
            <>
              <Button
                variant="contained"
                color="warning"
                size="large"
                startIcon={<Pause />}
                onClick={handlePauseTrading}
                sx={{ minWidth: 120 }}
              >
                PAUSAR
              </Button>
              <Button
                variant="contained"
                color="error"
                size="large"
                startIcon={<Stop />}
                onClick={handleStopTrading}
                sx={{ minWidth: 120 }}
              >
                PARAR
              </Button>
            </>
          )}

          {tradingStatus === 'paused' && (
            <>
              <Button
                variant="contained"
                color="success"
                size="large"
                startIcon={<PlayArrow />}
                onClick={handleResumeTrading}
                sx={{ 
                  minWidth: 120,
                  background: 'linear-gradient(135deg, #00E676 0%, #00C853 100%)',
                }}
              >
                RETOMAR
              </Button>
              <Button
                variant="contained"
                color="error"
                size="large"
                startIcon={<Stop />}
                onClick={handleStopTrading}
                sx={{ minWidth: 120 }}
              >
                PARAR
              </Button>
            </>
          )}

          <Tooltip title="Analisar performance dos ativos">
            <Button
              variant="outlined"
              size="large"
              startIcon={<Assessment />}
              onClick={handleAnalyzeAssets}
              disabled={isAnalyzing}
              sx={{ 
                borderColor: 'primary.main',
                color: 'primary.main',
                '&:hover': {
                  borderColor: 'primary.dark',
                  backgroundColor: 'rgba(255, 215, 0, 0.1)',
                }
              }}
            >
              {isAnalyzing ? 'ANALISANDO...' : 'ANALISAR ATIVOS'}
            </Button>
          </Tooltip>

          <Tooltip title="Configurações avançadas">
            <IconButton
              size="large"
              sx={{ 
                border: '1px solid #333333',
                color: '#B0B0B0',
                '&:hover': {
                  borderColor: 'primary.main',
                  color: 'primary.main',
                }
              }}
            >
              <Settings />
            </IconButton>
          </Tooltip>
        </Box>
      </CardContent>
      
      {/* Strategy Filters Configuration */}
      <StrategyFiltersConfig 
        selectedStrategy={selectedStrategy}
        onConfigChange={setStrategyFilterConfig}
      />
    </Card>
  );
};

export default TradingControlPanel;
