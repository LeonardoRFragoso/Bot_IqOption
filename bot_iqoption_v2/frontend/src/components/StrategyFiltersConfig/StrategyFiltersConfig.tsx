import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Chip,
  Slider,
  Paper,
  Switch,
  FormControlLabel,
  Tooltip,
  IconButton
} from '@mui/material';
import { Info, FilterList } from '@mui/icons-material';
import './StrategyFiltersConfig.css';

interface StrategyFiltersConfigProps {
  selectedStrategy: string;
  onConfigChange: (config: StrategyFilterConfig) => void;
}

export interface StrategyFilterConfig {
  enableFilters: boolean;
  confirmationFilters: string[];
  confirmationThreshold: number;
  filterWeights: { [key: string]: number };
}

const availableFilters = [
  { id: 'macd', name: 'MACD', description: 'Convergência e Divergência de Médias Móveis' },
  { id: 'bollinger_bands', name: 'Bollinger Bands', description: 'Bandas de Bollinger' },
  { id: 'rsi', name: 'RSI', description: 'Índice de Força Relativa' },
  { id: 'moving_average', name: 'Médias Móveis', description: 'Cruzamento de Médias Móveis' },
  { id: 'engulfing', name: 'Engulfing', description: 'Padrão de Engolfo' },
  { id: 'candlestick', name: 'Candlestick', description: 'Padrões de Candlestick' }
];

const defaultWeights = {
  'macd': 0.25,
  'bollinger_bands': 0.25,
  'rsi': 0.20,
  'moving_average': 0.15,
  'engulfing': 0.10,
  'candlestick': 0.05
};

const StrategyFiltersConfig: React.FC<StrategyFiltersConfigProps> = ({
  selectedStrategy,
  onConfigChange
}) => {
  const [enableFilters, setEnableFilters] = useState(false);
  const [confirmationFilters, setConfirmationFilters] = useState<string[]>([]);
  const [confirmationThreshold, setConfirmationThreshold] = useState(0.6);
  const [filterWeights, setFilterWeights] = useState<{ [key: string]: number }>(defaultWeights);

  // Update parent when config changes
  useEffect(() => {
    onConfigChange({
      enableFilters,
      confirmationFilters,
      confirmationThreshold,
      filterWeights
    });
  }, [enableFilters, confirmationFilters, confirmationThreshold, filterWeights, onConfigChange]);

  const handleFilterToggle = (filterId: string) => {
    setConfirmationFilters(prev => {
      if (prev.includes(filterId)) {
        return prev.filter(id => id !== filterId);
      } else {
        return [...prev, filterId];
      }
    });
  };

  const handleWeightChange = (filterId: string, weight: number) => {
    setFilterWeights(prev => ({
      ...prev,
      [filterId]: weight
    }));
  };

  const getThresholdColor = (threshold: number) => {
    if (threshold < 0.4) return '#f44336'; // Red - Muito permissivo
    if (threshold < 0.6) return '#ff9800'; // Orange - Moderado
    if (threshold < 0.8) return '#4caf50'; // Green - Conservador
    return '#2196f3'; // Blue - Muito conservador
  };

  const getThresholdLabel = (threshold: number) => {
    if (threshold < 0.4) return 'Muito Permissivo';
    if (threshold < 0.6) return 'Moderado';
    if (threshold < 0.8) return 'Conservador';
    return 'Muito Conservador';
  };

  if (!selectedStrategy) {
    return (
      <Paper className="strategy-filters-config" elevation={2}>
        <Typography variant="h6" gutterBottom>
          <FilterList /> Filtros de Confirmação
        </Typography>
        <Typography color="textSecondary">
          Selecione uma estratégia para configurar filtros de confirmação
        </Typography>
      </Paper>
    );
  }

  return (
    <Paper className="strategy-filters-config" elevation={2}>
      <Box className="config-header">
        <Typography variant="h6" gutterBottom>
          <FilterList /> Filtros de Confirmação
        </Typography>
        <Tooltip title="Os filtros de confirmação ajudam a validar os sinais da estratégia principal, aumentando a precisão das operações">
          <IconButton size="small">
            <Info />
          </IconButton>
        </Tooltip>
      </Box>

      <FormControlLabel
        control={
          <Switch
            checked={enableFilters}
            onChange={(e) => setEnableFilters(e.target.checked)}
            color="primary"
          />
        }
        label="Ativar Filtros de Confirmação"
        className="enable-filters-switch"
      />

      {enableFilters && (
        <Box className="filters-configuration">
          <Typography variant="subtitle1" gutterBottom className="section-title">
            Estratégia Principal: <strong>{selectedStrategy.toUpperCase()}</strong>
          </Typography>

          <Box className="filters-selection">
            <Typography variant="subtitle2" gutterBottom>
              Filtros de Confirmação:
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {availableFilters.map((filter) => (
                <Tooltip key={filter.id} title={filter.description}>
                  <Chip
                    label={filter.name}
                    clickable
                    color={confirmationFilters.includes(filter.id) ? 'primary' : 'default'}
                    onClick={() => handleFilterToggle(filter.id)}
                    className={`filter-chip ${confirmationFilters.includes(filter.id) ? 'selected' : ''}`}
                  />
                </Tooltip>
              ))}
            </Box>
          </Box>

          {confirmationFilters.length > 0 && (
            <>
              <Box className="threshold-configuration">
                <Typography variant="subtitle2" gutterBottom>
                  Threshold de Confirmação: {confirmationThreshold.toFixed(2)} 
                  <span 
                    className="threshold-label"
                    style={{ color: getThresholdColor(confirmationThreshold) }}
                  >
                    ({getThresholdLabel(confirmationThreshold)})
                  </span>
                </Typography>
                <Slider
                  value={confirmationThreshold}
                  onChange={(_, value) => setConfirmationThreshold(value as number)}
                  min={0.1}
                  max={1.0}
                  step={0.05}
                  marks={[
                    { value: 0.2, label: '0.2' },
                    { value: 0.4, label: '0.4' },
                    { value: 0.6, label: '0.6' },
                    { value: 0.8, label: '0.8' },
                    { value: 1.0, label: '1.0' }
                  ]}
                  className="threshold-slider"
                  style={{ color: getThresholdColor(confirmationThreshold) }}
                />
                <Typography variant="caption" color="textSecondary">
                  Quanto maior o threshold, mais conservadora será a estratégia
                </Typography>
              </Box>

              <Box className="weights-configuration">
                <Typography variant="subtitle2" gutterBottom>
                  Pesos dos Filtros:
                </Typography>
                {confirmationFilters.map((filterId) => {
                  const filter = availableFilters.find(f => f.id === filterId);
                  return (
                    <Box key={filterId} className="weight-control">
                      <Typography variant="body2" className="weight-label">
                        {filter?.name}: {filterWeights[filterId]?.toFixed(2) || '0.00'}
                      </Typography>
                      <Slider
                        value={filterWeights[filterId] || 0}
                        onChange={(_, value) => handleWeightChange(filterId, value as number)}
                        min={0.05}
                        max={0.50}
                        step={0.05}
                        className="weight-slider"
                      />
                    </Box>
                  );
                })}
              </Box>

              <Box className="configuration-summary">
                <Typography variant="subtitle2" gutterBottom>
                  Resumo da Configuração:
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  • Estratégia Principal: <strong>{selectedStrategy.toUpperCase()}</strong> (gatilho de entrada)
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  • Filtros Ativos: <strong>{confirmationFilters.length}</strong> ({confirmationFilters.join(', ')})
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  • Threshold: <strong>{confirmationThreshold.toFixed(2)}</strong> ({getThresholdLabel(confirmationThreshold)})
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  • Operação executada apenas se score de confirmação ≥ {confirmationThreshold.toFixed(2)}
                </Typography>
              </Box>
            </>
          )}
        </Box>
      )}
    </Paper>
  );
};

export default StrategyFiltersConfig;
