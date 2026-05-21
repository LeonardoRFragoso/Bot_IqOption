import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Button,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  CircularProgress,
} from '@mui/material';
import {
  PlayArrow,
  Stop,
  Pause,
  PlayCircle,
} from '@mui/icons-material';
import { useTradingControl, useConnectionStatus } from '../../hooks/useApi';
import apiService from '../../services/api';

interface TradingControlProps {
  onStatusChange?: (status: 'stopped' | 'running' | 'paused') => void;
  selectedAsset?: string;
  selectedStrategy?: string;
}

const TradingControl: React.FC<TradingControlProps> = ({ 
  onStatusChange, 
  selectedAsset: propAsset,
  selectedStrategy: propStrategy 
}) => {
  const [tradingStatus, setTradingStatus] = useState<'stopped' | 'running' | 'paused'>('stopped');
  const [selectedStrategy, setSelectedStrategy] = useState(propStrategy || 'mhi');
  const [selectedAsset, setSelectedAsset] = useState(propAsset || '');
  const [startError, setStartError] = useState<string | null>(null);
  
  // Map strategy names from catalog to internal format
  const normalizeStrategy = (strategy: string): string => {
    const strategyMap: { [key: string]: string } = {
      'mhi': 'mhi',
      'MHI': 'mhi',
      'torres_gemeas': 'torres_gemeas',
      'TORRES_GEMEAS': 'torres_gemeas',
      'mhi_m5': 'mhi_m5',
      'MHI_M5': 'mhi_m5',
      'rsi': 'rsi',
      'RSI': 'rsi',
      'moving_average': 'moving_average',
      'MOVING_AVERAGE': 'moving_average',
      'bollinger_bands': 'bollinger_bands',
      'BOLLINGER_BANDS': 'bollinger_bands',
      'macd': 'macd',
      'MACD': 'macd',
    };
    return strategyMap[strategy] || strategy.toLowerCase();
  };

  // Sync with props when they change
  useEffect(() => {
    if (propAsset) setSelectedAsset(propAsset);
  }, [propAsset]);
  
  useEffect(() => {
    if (propStrategy) {
      const normalized = normalizeStrategy(propStrategy);
      setSelectedStrategy(normalized);
    }
  }, [propStrategy]);

  // Load active session state on mount
  useEffect(() => {
    (async () => {
      try {
        const active = await apiService.getActiveSession();
        if (active) {
          const status = (active as any).status as string;
          if (status === 'RUNNING') {
            setTradingStatus('running');
          } else if (status === 'PAUSED') {
            setTradingStatus('paused');
          }
          // Restore asset and strategy from active session if not provided via props
          if (!propAsset && (active as any).asset) {
            setSelectedAsset((active as any).asset);
          }
          if (!propStrategy && (active as any).strategy) {
            setSelectedStrategy((active as any).strategy);
          }
        }
      } catch {
        // ignore
      }
    })();
  }, []);
  
  const { 
    loading: tradingLoading, 
    error: tradingError, 
    stopTrading, 
    pauseTrading, 
    resumeTrading 
  } = useTradingControl();
  
  const { 
    status: connectionStatus, 
    loading: connectionLoading, 
    testConnection 
  } = useConnectionStatus();

  const strategies = [
    { value: 'mhi', label: 'MHI (3 Velas)' },
    { value: 'torres_gemeas', label: 'Torres Gêmeas (1 Vela)' },
    { value: 'mhi_m5', label: 'MHI M5 (5 Minutos)' },
    { value: 'rsi', label: 'RSI' },
    { value: 'moving_average', label: 'Médias Móveis' },
    { value: 'bollinger_bands', label: 'Bollinger Bands' },
    { value: 'macd', label: 'MACD' },
  ];

  const handleStart = async () => {
    setStartError(null);
    try {
      // Use the selected asset - REQUIRED for trading
      if (!selectedAsset) {
        setStartError('Selecione um ativo na lista "Melhores Ativos para Operar" antes de iniciar.');
        return;
      }
      await apiService.startTrading(selectedStrategy, selectedAsset);
      setTradingStatus('running');
      onStatusChange?.('running');
    } catch (error) {
      console.error('Erro ao iniciar trading:', error);
      setStartError('Erro ao iniciar trading. Verifique a conexão.');
    }
  };

  const handleStop = async () => {
    try {
      await stopTrading();
      setTradingStatus('stopped');
      onStatusChange?.('stopped');
    } catch (error) {
      console.error('Erro ao parar trading:', error);
    }
  };

  const handlePause = async () => {
    try {
      await pauseTrading();
      setTradingStatus('paused');
      onStatusChange?.('paused');
    } catch (error) {
      console.error('Erro ao pausar trading:', error);
    }
  };

  const handleResume = async () => {
    try {
      await resumeTrading();
      setTradingStatus('running');
      onStatusChange?.('running');
    } catch (error) {
      console.error('Erro ao retomar trading:', error);
    }
  };

  const handleTestConnection = async () => {
    try {
      await testConnection();
    } catch (error) {
      console.error('Erro ao testar conexão:', error);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'success';
      case 'paused': return 'warning';
      case 'stopped': return 'error';
      default: return 'default';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'running': return 'Ativo';
      case 'paused': return 'Pausado';
      case 'stopped': return 'Parado';
      default: return 'Desconhecido';
    }
  };

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">Controle de Trading</Typography>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Chip 
              label={getStatusLabel(tradingStatus)}
              color={getStatusColor(tradingStatus)}
              variant="filled"
            />
            {connectionLoading && <CircularProgress size={20} />}
          </Box>
        </Box>

        {tradingError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {tradingError}
          </Alert>
        )}

        {startError && (
          <Alert severity="warning" sx={{ mb: 2 }} onClose={() => setStartError(null)}>
            {startError}
          </Alert>
        )}

        {connectionStatus && (
          <Alert 
            severity={connectionStatus.success ? 'success' : 'error'} 
            sx={{ mb: 2 }}
          >
            {connectionStatus.message || 'Status da conexão atualizado'}
          </Alert>
        )}

        <Box sx={{ mb: 3 }}>
          <FormControl fullWidth disabled={tradingStatus === 'running'}>
            <InputLabel>Estratégia</InputLabel>
            <Select
              value={selectedStrategy}
              label="Estratégia"
              onChange={(e) => setSelectedStrategy(e.target.value)}
            >
              {strategies.map((strategy) => (
                <MenuItem key={strategy.value} value={strategy.value}>
                  {strategy.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <Button
            variant="contained"
            color="success"
            startIcon={<PlayArrow />}
            onClick={handleStart}
            disabled={tradingStatus === 'running' || tradingLoading}
            sx={{ minWidth: 120 }}
          >
            {tradingLoading ? <CircularProgress size={20} /> : 'Iniciar'}
          </Button>

          {tradingStatus === 'running' && (
            <Button
              variant="contained"
              color="warning"
              startIcon={<Pause />}
              onClick={handlePause}
              disabled={tradingLoading}
              sx={{ minWidth: 120 }}
            >
              {tradingLoading ? <CircularProgress size={20} /> : 'Pausar'}
            </Button>
          )}

          {tradingStatus === 'paused' && (
            <Button
              variant="contained"
              color="info"
              startIcon={<PlayCircle />}
              onClick={handleResume}
              disabled={tradingLoading}
              sx={{ minWidth: 120 }}
            >
              {tradingLoading ? <CircularProgress size={20} /> : 'Retomar'}
            </Button>
          )}

          <Button
            variant="contained"
            color="error"
            startIcon={<Stop />}
            onClick={handleStop}
            disabled={tradingStatus === 'stopped' || tradingLoading}
            sx={{ minWidth: 120 }}
          >
            {tradingLoading ? <CircularProgress size={20} /> : 'Parar'}
          </Button>

          <Button
            variant="outlined"
            onClick={handleTestConnection}
            disabled={connectionLoading}
            sx={{ minWidth: 140 }}
          >
            {connectionLoading ? <CircularProgress size={20} /> : 'Testar Conexão'}
          </Button>
        </Box>

        <Box sx={{ mt: 2 }}>
          {selectedAsset && (
            <Typography variant="body2" color="textSecondary">
              <strong>Ativo Selecionado:</strong> {selectedAsset}
            </Typography>
          )}
          <Typography variant="body2" color="textSecondary">
            <strong>Estratégia Selecionada:</strong> {strategies.find(s => s.value === selectedStrategy)?.label}
          </Typography>
          <Typography variant="body2" color="textSecondary">
            <strong>Status:</strong> {getStatusLabel(tradingStatus)}
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
};

export default TradingControl;
