import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Chip,
  CircularProgress,
  Alert,
  Tooltip,
} from '@mui/material';
import {
  TrendingUp,
  Schedule,
  Public,
  Assessment,
} from '@mui/icons-material';
import apiService from '../../services/api';

interface MarketStatusData {
  market_info: {
    current_utc: string;
    new_york: string;
    london: string;
    tokyo: string;
    is_weekend: boolean;
    forex_open: boolean;
    us_stocks_open: boolean;
  };
  open_assets_count: number;
  open_assets: string[];
  best_asset: string | null;
  recommendations: {
    forex_trading: boolean;
    stock_trading: boolean;
    weekend_mode: boolean;
  };
}

const MarketStatus: React.FC = () => {
  const [marketData, setMarketData] = useState<MarketStatusData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadMarketStatus();
    const interval = setInterval(loadMarketStatus, 60000); // Update every minute
    return () => clearInterval(interval);
  }, []);

  const loadMarketStatus = async () => {
    try {
      const data = await apiService.getMarketStatus();
      setMarketData(data);
      setError(null);
    } catch (err) {
      setError('Erro ao carregar status do mercado');
      console.error('Market status error:', err);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (isOpen: boolean) => {
    return isOpen ? 'success' : 'error';
  };

  const getStatusText = (isOpen: boolean) => {
    return isOpen ? 'ABERTO' : 'FECHADO';
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" p={2}>
        <CircularProgress size={24} />
        <Typography sx={{ ml: 1 }}>Carregando status...</Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  if (!marketData) return null;

  return (
    <Card sx={{ 
      background: 'linear-gradient(135deg, #1A1A1A 0%, #2A2A2A 100%)',
      border: '1px solid #333333',
      mb: 3
    }}>
      <CardContent>
        <Typography variant="h6" gutterBottom sx={{ color: 'primary.main', display: 'flex', alignItems: 'center' }}>
          <Public sx={{ mr: 1 }} />
          Status dos Mercados
        </Typography>

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {/* Market Hours and Status */}
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
            {/* Market Hours */}
            <Box sx={{ flex: '1 1 300px' }}>
              <Typography variant="subtitle2" sx={{ color: 'text.secondary', mb: 1, display: 'flex', alignItems: 'center' }}>
                <Schedule sx={{ mr: 1, fontSize: 16 }} />
                Horários Globais
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                <Chip 
                  label={`NY: ${marketData.market_info.new_york}`} 
                  size="small" 
                  sx={{ backgroundColor: '#333', color: '#fff' }}
                />
                <Chip 
                  label={`London: ${marketData.market_info.london}`} 
                  size="small" 
                  sx={{ backgroundColor: '#333', color: '#fff' }}
                />
                <Chip 
                  label={`Tokyo: ${marketData.market_info.tokyo}`} 
                  size="small" 
                  sx={{ backgroundColor: '#333', color: '#fff' }}
                />
              </Box>
            </Box>

            {/* Market Status */}
            <Box sx={{ flex: '1 1 300px' }}>
              <Typography variant="subtitle2" sx={{ color: 'text.secondary', mb: 1, display: 'flex', alignItems: 'center' }}>
                <TrendingUp sx={{ mr: 1, fontSize: 16 }} />
                Status dos Mercados
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                <Chip 
                  label={`Forex: ${getStatusText(marketData.recommendations.forex_trading)}`}
                  color={getStatusColor(marketData.recommendations.forex_trading)}
                  size="small"
                />
                <Chip 
                  label={`Ações: ${getStatusText(marketData.recommendations.stock_trading)}`}
                  color={getStatusColor(marketData.recommendations.stock_trading)}
                  size="small"
                />
                {marketData.recommendations.weekend_mode && (
                  <Chip 
                    label="MODO FIM DE SEMANA"
                    color="warning"
                    size="small"
                  />
                )}
              </Box>
            </Box>
          </Box>

          {/* Assets Info */}
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <Assessment sx={{ mr: 1, color: 'info.main' }} />
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                  <strong>{marketData.open_assets_count}</strong> ativos disponíveis
                </Typography>
              </Box>
              
              {marketData.best_asset && (
                <Tooltip title="Melhor ativo recomendado para trading no momento">
                  <Chip 
                    label={`Recomendado: ${marketData.best_asset}`}
                    color="primary"
                    size="small"
                    sx={{ fontWeight: 'bold' }}
                  />
                </Tooltip>
              )}
            </Box>

            {marketData.open_assets.length > 0 && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1 }}>
                  Ativos disponíveis:
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {marketData.open_assets.slice(0, 8).map((asset, index) => (
                    <Chip 
                      key={index}
                      label={asset} 
                      size="small" 
                      variant="outlined"
                      sx={{ fontSize: '0.7rem', height: '24px' }}
                    />
                  ))}
                  {marketData.open_assets.length > 8 && (
                    <Chip 
                      label={`+${marketData.open_assets.length - 8} mais`}
                      size="small" 
                      variant="outlined"
                      sx={{ fontSize: '0.7rem', height: '24px', color: 'text.secondary' }}
                    />
                  )}
                </Box>
              </Box>
            )}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

export default MarketStatus;
