import React, { useState } from 'react';
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

interface TradingControlProps {
  onStatusChange?: (status: 'stopped' | 'running' | 'paused') => void;
}

const TradingControl: React.FC<TradingControlProps> = ({ onStatusChange }) => {
  const [tradingStatus, setTradingStatus] = useState<'stopped' | 'running' | 'paused'>('stopped');
  const [selectedStrategy, setSelectedStrategy] = useState('mhi');
  
  const { 
    loading: tradingLoading, 
    error: tradingError, 
    startTrading, 
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
  ];

  const handleStart = async () => {
    try {
      await startTrading(selectedStrategy);
      setTradingStatus('running');
      onStatusChange?.('running');
    } catch (error) {
      console.error('Erro ao iniciar trading:', error);
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
