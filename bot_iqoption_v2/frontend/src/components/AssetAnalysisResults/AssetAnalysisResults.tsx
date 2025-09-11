import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  CircularProgress,
  Alert,
  List,
  ListItem,
  ListItemText,
  Avatar,
  Divider
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  BarChart,
  Assessment
} from '@mui/icons-material';
import apiService from '../../services/api';
import type { AssetCatalog } from '../../types/index';


interface AssetAnalysisResultsProps {
  refreshTrigger?: number;
}

export const AssetAnalysisResults: React.FC<AssetAnalysisResultsProps> = ({ refreshTrigger }) => {
  const [results, setResults] = useState<AssetCatalog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchResults = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiService.getAssetCatalog();
      setResults(response);
    } catch (err: any) {
      setError('Erro ao carregar resultados da análise');
      console.error('Error fetching catalog results:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchResults();
  }, [refreshTrigger]);

  const getStrategyDisplayName = (strategy: string) => {
    const strategyNames: { [key: string]: string } = {
      'mhi': 'MHI',
      'torres_gemeas': 'Torres Gêmeas',
      'mhi_m5': 'MHI M5'
    };
    return strategyNames[strategy] || strategy.toUpperCase();
  };

  const getSuccessRateColor = (rate: number): 'success' | 'warning' | 'error' => {
    if (rate >= 80) return 'success';
    if (rate >= 70) return 'warning';
    return 'error';
  };

  const getSuccessRateIcon = (rate: number) => {
    if (rate >= 70) return <TrendingUp sx={{ fontSize: 16 }} />;
    return <TrendingDown sx={{ fontSize: 16 }} />;
  };

  // Group results by asset and get best strategy for each
  const groupedResults = results.reduce((acc, result) => {
    if (!acc[result.asset] || acc[result.asset].gale3_rate < result.gale3_rate) {
      acc[result.asset] = result;
    }
    return acc;
  }, {} as { [key: string]: AssetCatalog });

  // Get top 10 assets sorted by gale3_rate
  const topAssets = Object.values(groupedResults)
    .sort((a, b) => b.gale3_rate - a.gale3_rate)
    .slice(0, 10);

  if (loading) {
    return (
      <Card sx={{ 
        background: 'linear-gradient(135deg, #1A1A1A 0%, #2A2A2A 100%)',
        border: '1px solid #333333',
        borderRadius: '16px'
      }}>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ 
            color: 'primary.main',
            display: 'flex',
            alignItems: 'center',
            gap: 1
          }}>
            <BarChart />
            Resultados da Análise de Ativos
          </Typography>
          <Box display="flex" justifyContent="center" alignItems="center" py={4}>
            <CircularProgress size={32} />
            <Typography sx={{ ml: 2, color: 'text.secondary' }}>
              Carregando resultados...
            </Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card sx={{ 
        background: 'linear-gradient(135deg, #1A1A1A 0%, #2A2A2A 100%)',
        border: '1px solid #333333',
        borderRadius: '16px'
      }}>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ 
            color: 'primary.main',
            display: 'flex',
            alignItems: 'center',
            gap: 1
          }}>
            <BarChart />
            Resultados da Análise de Ativos
          </Typography>
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        </CardContent>
      </Card>
    );
  }

  if (topAssets.length === 0) {
    return (
      <Card sx={{ 
        background: 'linear-gradient(135deg, #1A1A1A 0%, #2A2A2A 100%)',
        border: '1px solid #333333',
        borderRadius: '16px'
      }}>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ 
            color: 'primary.main',
            display: 'flex',
            alignItems: 'center',
            gap: 1
          }}>
            <BarChart />
            Resultados da Análise de Ativos
          </Typography>
          <Box textAlign="center" py={4}>
            <Assessment sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
            <Typography color="text.secondary">
              Nenhuma análise encontrada
            </Typography>
            <Typography variant="body2" color="text.disabled">
              Execute a catalogação de ativos para ver os resultados
            </Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card sx={{ 
      background: 'linear-gradient(135deg, #1A1A1A 0%, #2A2A2A 100%)',
      border: '1px solid #333333',
      borderRadius: '16px'
    }}>
      <CardContent>
        <Typography variant="h6" gutterBottom sx={{ 
          color: 'primary.main',
          display: 'flex',
          alignItems: 'center',
          gap: 1
        }}>
          <BarChart />
          Top 10 Ativos - Melhores Resultados
        </Typography>
        
        <List>
          {topAssets.map((result: AssetCatalog, index: number) => (
            <React.Fragment key={`${result.asset}-${result.strategy}`}>
              <ListItem>
                <Avatar sx={{ 
                  bgcolor: 'primary.main', 
                  mr: 2,
                  width: 32,
                  height: 32,
                  fontSize: '0.875rem'
                }}>
                  {index + 1}
                </Avatar>
                <ListItemText
                  primary={
                    <Box display="flex" justifyContent="space-between" alignItems="center">
                      <Box>
                        <Typography variant="h6" component="span" sx={{ color: 'text.primary' }}>
                          {result.asset}
                        </Typography>
                        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                          {getStrategyDisplayName(result.strategy)} • {result.total_samples} amostras
                        </Typography>
                      </Box>
                      <Box display="flex" gap={3} alignItems="center">
                        <Box textAlign="center">
                          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                            Entrada
                          </Typography>
                          <Typography variant="body2" fontWeight="bold">
                            {Math.round(result.win_rate)}%
                          </Typography>
                        </Box>
                        <Box textAlign="center">
                          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                            Até Gale 1
                          </Typography>
                          <Typography variant="body2" fontWeight="bold">
                            {Math.round(result.gale1_rate)}%
                          </Typography>
                        </Box>
                        <Box textAlign="center">
                          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                            Até Gale 2
                          </Typography>
                          <Chip
                            icon={getSuccessRateIcon(result.gale2_rate)}
                            label={`${Math.round(result.gale2_rate)}%`}
                            color={getSuccessRateColor(result.gale2_rate)}
                            size="small"
                            variant="outlined"
                          />
                        </Box>
                        <Box textAlign="center">
                          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                            Até Gale 3
                          </Typography>
                          <Chip
                            icon={getSuccessRateIcon(result.gale3_rate)}
                            label={`${Math.round(result.gale3_rate)}%`}
                            color={getSuccessRateColor(result.gale3_rate)}
                            size="small"
                            variant="outlined"
                          />
                        </Box>
                      </Box>
                    </Box>
                  }
                />
              </ListItem>
              {index < topAssets.length - 1 && <Divider />}
            </React.Fragment>
          ))}
        </List>

        <Alert severity="info" sx={{ mt: 3 }}>
          <Typography variant="body2" fontWeight="bold" gutterBottom>
            Como interpretar os resultados:
          </Typography>
          <Box component="ul" sx={{ pl: 2, m: 0 }}>
            <Typography component="li" variant="caption">
              <strong>Entrada:</strong> Taxa de acerto na primeira tentativa
            </Typography>
            <Typography component="li" variant="caption">
              <strong>Até Gale 1:</strong> Taxa de acerto considerando até o primeiro Gale
            </Typography>
            <Typography component="li" variant="caption">
              <strong>Até Gale 2:</strong> Taxa de acerto considerando até o segundo Gale
            </Typography>
            <Typography component="li" variant="caption">
              <strong>Recomendado:</strong> Ativos com taxa ≥ 70% até Gale 2
            </Typography>
          </Box>
        </Alert>
      </CardContent>
    </Card>
  );
};

export default AssetAnalysisResults;
