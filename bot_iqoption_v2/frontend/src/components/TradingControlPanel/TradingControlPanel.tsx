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
import type { TradingSession, Operation } from '../../types/index';
import { useTradingRealtime } from '../../hooks/useRealtime';

interface Asset {
  id: string;
  name: string;
  payout: number;
  isOpen: boolean;
  winRate?: number;
}

interface Strategy {
  id: string;
  name: string;
  description: string;
  winRate?: number;
  recommended?: boolean;
}

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

  // Trading control functions will use apiService directly

  // Load real data from API
  useEffect(() => {
    loadAssetsAndStrategies();
    // Sync with backend session state on mount
    (async () => {
      try {
        const active = await apiService.getActiveSession();
        if (active) {
          setCurrentSession(active);
          const status = (active as any).status as string;
          if (status === 'RUNNING') {
            // Safety-first: auto-pause any running session on login/dashboard load
            try {
              await apiService.pauseTrading((active as any).id.toString());
              setTradingStatus('paused');
            } catch {
              // If pause fails, still reflect the real status
              setTradingStatus('running');
            }
          } else if (status === 'PAUSED') {
            setTradingStatus('paused');
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
    socket.on('operation_update', onOpUpdate);
    return () => {
      socket.off('operation_update', onOpUpdate);
    };
  }, [socket, currentSession?.id]);

  const loadAssetsAndStrategies = async (lightMode: boolean = false) => {
    try {
      // Load real asset catalog results
      const catalogResults = await apiService.getAssetCatalog();
      
      // 1) Deduplicate by asset symbol: keep the best score per asset
      const bestByAsset = new Map<string, any>();
      for (const r of catalogResults) {
        const key = r.asset;
        const score = Number(r.gale2_rate ?? r.win_rate ?? 0);
        const current = bestByAsset.get(key);
        if (!current) {
          bestByAsset.set(key, r);
        } else {
          const curScore = Number(current.gale2_rate ?? current.win_rate ?? 0);
          if (score > curScore) bestByAsset.set(key, r);
        }
      }
      const uniqueResults = Array.from(bestByAsset.values());

      // 2) Transform to Asset format (filter to FX-like symbols and their OTC variants)
      const fxRegex = /^[A-Z]{3,6}(-OTC)?$/; // e.g., EURUSD, AUDCAD-OTC
      const realAssets: Asset[] = uniqueResults
        .filter((r: any) => typeof r.asset === 'string' && fxRegex.test(r.asset))
        .map((result: any) => ({
          id: result.asset,
          name: result.asset,
          payout: result.payout || 80, // Default payout if not available
          isOpen: true, // Assume open if in catalog
          // Keep winRate only for internal default selection (hidden in UI to avoid confusion)
          winRate: Math.round(result.gale2_rate || result.win_rate || 0)
        }));

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
            if (result.strategy && result.gale3_rate !== null && result.gale3_rate !== undefined) {
              if (!strategyStats[result.strategy]) {
                strategyStats[result.strategy] = { total: 0, count: 0 };
              }
              strategyStats[result.strategy].total += result.gale3_rate;
              strategyStats[result.strategy].count += 1;
            }
          });

          // Calculate averages
          Object.keys(strategyStats).forEach(strategy => {
            const stats = strategyStats[strategy];
            strategyPerformance[strategy] = Math.round(stats.total / stats.count);
          });
        }
      } catch (err) {
        console.warn('Could not fetch catalog results for strategy performance:', err);
      }

      // Define strategies with real performance data when available
      const strategies: Strategy[] = [
        { 
          id: 'mhi', 
          name: 'MHI', 
          description: 'Média Móvel com Indicadores', 
          winRate: strategyPerformance['mhi'] || 73,
          recommended: true 
        },
        { 
          id: 'torres_gemeas', 
          name: 'Torres Gêmeas', 
          description: 'Estratégia de Reversão', 
          winRate: strategyPerformance['torres_gemeas'] || 68,
          recommended: false 
        },
        { 
          id: 'mhi_m5', 
          name: 'MHI M5', 
          description: 'MHI para timeframe de 5 minutos', 
          winRate: strategyPerformance['mhi_m5'] || 71,
          recommended: true 
        },
        { 
          id: 'rsi', 
          name: 'RSI', 
          description: 'Relative Strength Index', 
          winRate: strategyPerformance['rsi'] || 65,
          recommended: false 
        },
        { 
          id: 'moving_average', 
          name: 'Moving Average', 
          description: 'Média Móvel Simples', 
          winRate: strategyPerformance['moving_average'] || 62,
          recommended: false 
        },
        { 
          id: 'bollinger_bands', 
          name: 'Bollinger Bands', 
          description: 'Bandas de Bollinger', 
          winRate: strategyPerformance['bollinger_bands'] || 67,
          recommended: false 
        },
        { 
          id: 'engulfing', 
          name: 'Engulfing', 
          description: 'Padrão de Engolfo', 
          winRate: strategyPerformance['engulfing'] || 69,
          recommended: false 
        },
        { 
          id: 'candlestick', 
          name: 'Candlestick Patterns', 
          description: 'Padrões de Candlestick', 
          winRate: strategyPerformance['candlestick'] || 64,
          recommended: false 
        },
        { 
          id: 'macd', 
          name: 'MACD', 
          description: 'Moving Average Convergence Divergence', 
          winRate: strategyPerformance['macd'] || 66,
          recommended: false 
        },
      ];

      // Use real data if available, otherwise fallback to defaults
      if (realAssets.length > 0) {
        // 3) Sort assets: open first, then higher payout, then alphabetical
        realAssets.sort((a, b) => {
          const openScore = (b.isOpen ? 1 : 0) - (a.isOpen ? 1 : 0);
          if (openScore !== 0) return openScore;
          const payoutScore = (b.payout || 0) - (a.payout || 0);
          if (payoutScore !== 0) return payoutScore;
          return a.id.localeCompare(b.id);
        });

        setAssets(realAssets);
        
        // Prefer the best open asset; if none, pick the overall best by winRate
        let bestAsset = realAssets
          .filter(a => a.isOpen)
          .sort((a, b) => (b.winRate || 0) - (a.winRate || 0))[0];

        if (!bestAsset) {
          bestAsset = [...realAssets].sort((a, b) => (b.winRate || 0) - (a.winRate || 0))[0];
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
        { id: 'mhi', name: 'MHI', description: 'Média Móvel com Indicadores', recommended: true },
        { id: 'torres_gemeas', name: 'Torres Gêmeas', description: 'Estratégia de Reversão', recommended: false },
        { id: 'mhi_m5', name: 'MHI M5', description: 'MHI para timeframe de 5 minutos', recommended: true },
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

      // Fetch preferred account type and send explicitly
      let accountType = 'PRACTICE';
      try {
        const user: any = await apiService.getCurrentUser();
        accountType = (user && (user as any).preferred_account_type) || 'PRACTICE';
      } catch {
        accountType = 'PRACTICE';
      }

      const session = await apiService.startTrading(selectedStrategy, selectedAsset, accountType);
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
      await apiService.runAssetCatalog(['mhi', 'torres_gemeas', 'mhi_m5', 'rsi', 'moving_average', 'bollinger_bands', 'engulfing', 'candlestick', 'macd']);
      
      // Poll for completion instead of fixed timeout
      await waitForCatalogCompletion();

      // Catalog finished: libera UI imediatamente e faz refresh leve
      setIsAnalyzing(false);
      try { window.dispatchEvent(new CustomEvent('catalog-stopped')); } catch {}
      await loadAssetsAndStrategies(true); // light refresh (sem status/payouts)

      // Agendar refresh completo em background (payouts e status de mercado)
      setTimeout(() => { loadAssetsAndStrategies(false).catch(() => {}); }, 500);
      
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

  const waitForCatalogCompletion = async () => {
    const maxWaitTime = 300000; // 5 minutes max
    const pollInterval = 3000; // 3s for responsive UX
    const start = Date.now();
    while (Date.now() - start < maxWaitTime) {
      try {
        const status = await apiService.getCatalogStatus();
        if (status && status.running === false) {
          try {
            window.dispatchEvent(new CustomEvent('catalog-completed'));
          } catch {}
          break;
        }
      } catch (e) {
        console.warn('catalog status check failed:', e);
        // fall through to wait and retry
      }
      await new Promise(r => setTimeout(r, pollInterval));
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
            <Typography variant="body2" sx={{ color: '#B0B0B0', mb: 1 }}>
              Sessão em andamento
            </Typography>
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
                {assets.map((asset) => (
                  <MenuItem key={asset.id} value={asset.id}>
                    <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                      <Typography sx={{ flexGrow: 1 }}>{asset.name}</Typography>
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        <Chip 
                          label={`${asset.payout}%`} 
                          size="small" 
                          color="info"
                        />
                        {asset.id.endsWith('-OTC') && (
                          <Chip 
                            label="OTC" 
                            size="small" 
                            color="secondary"
                            variant="outlined"
                          />
                        )}
                        {!asset.isOpen && (
                          <Chip 
                            label="Fechado" 
                            size="small" 
                            color="error"
                          />
                        )}
                      </Box>
                    </Box>
                  </MenuItem>
                ))}
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
              {selectedAssetData.winRate && selectedStrategyData.winRate && (
                <span> - Taxa de acerto estimada: <strong style={{ color: '#00E676' }}>
                  {Math.round((selectedAssetData.winRate + selectedStrategyData.winRate) / 2)}%
                </strong></span>
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
    </Card>
  );
};

export default TradingControlPanel;
