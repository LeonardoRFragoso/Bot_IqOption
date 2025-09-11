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
import type { TradingSession } from '../../types/index';

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

  // Trading control functions will use apiService directly

  // Load real data from API
  useEffect(() => {
    loadAssetsAndStrategies();
  }, []);

  const loadAssetsAndStrategies = async () => {
    try {
      // Load real asset catalog results
      const catalogResults = await apiService.getAssetCatalog();
      
      // Transform catalog results to Asset format
      const realAssets: Asset[] = catalogResults.map((result: any) => ({
        id: result.asset,
        name: result.asset,
        payout: result.payout || 80, // Default payout if not available
        isOpen: true, // Assume open if in catalog
        winRate: Math.round(result.gale2_rate || result.win_rate || 0) // Use gale2_rate as main indicator
      }));

      // Get market status for additional asset info
      try {
        const marketStatus = await apiService.getMarketStatus();
        if (marketStatus.open_assets) {
          // Update assets with market status
          realAssets.forEach(asset => {
            const marketAsset = marketStatus.open_assets.find((ma: any) => ma === asset.id);
            asset.isOpen = !!marketAsset;
          });
        }
      } catch (error) {
        console.warn('Could not load market status:', error);
      }

      // Define strategies (these are static)
      const strategies: Strategy[] = [
        { 
          id: 'mhi', 
          name: 'MHI', 
          description: 'Média Móvel com Indicadores', 
          winRate: 73,
          recommended: true 
        },
        { 
          id: 'torres_gemeas', 
          name: 'Torres Gêmeas', 
          description: 'Estratégia de Reversão', 
          winRate: 68,
          recommended: false 
        },
        { 
          id: 'mhi_m5', 
          name: 'MHI M5', 
          description: 'MHI para timeframe de 5 minutos', 
          winRate: 71,
          recommended: true 
        },
      ];

      // Use real data if available, otherwise fallback to defaults
      if (realAssets.length > 0) {
        setAssets(realAssets);
        
        // Set best performing asset as default
        const bestAsset = realAssets
          .filter(a => a.isOpen)
          .sort((a, b) => (b.winRate || 0) - (a.winRate || 0))[0];
        
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
      const response = await apiService.startTrading(selectedStrategy);
      const session = response.data as TradingSession;
      setCurrentSession(session);
      setTradingStatus('running');
      onSessionChange?.(session);
    } catch (error) {
      console.error('Failed to start trading:', error);
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
    try {
      await apiService.runAssetCatalog(['mhi', 'torres_gemeas', 'mhi_m5']);
      
      // Wait a moment for analysis to start, then reload data
      setTimeout(() => {
        loadAssetsAndStrategies();
      }, 2000);
      
    } catch (error) {
      console.error('Failed to analyze assets:', error);
    } finally {
      setIsAnalyzing(false);
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
                        {asset.winRate && (
                          <Chip 
                            label={`${asset.winRate}%`} 
                            size="small" 
                            color={asset.winRate > 70 ? 'success' : 'warning'}
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

        {selectedAssetData && selectedStrategyData && (
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
              disabled={!selectedAsset || !selectedStrategy}
              sx={{ 
                minWidth: 150,
                background: 'linear-gradient(135deg, #00E676 0%, #00C853 100%)',
                '&:hover': {
                  background: 'linear-gradient(135deg, #00C853 0%, #00A152 100%)',
                }
              }}
            >
              INICIAR TRADING
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
