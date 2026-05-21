import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Box,
  Button,
  Chip,
  LinearProgress,
  Alert,
  IconButton,
  Tooltip,
  CircularProgress,
} from '@mui/material';
import { PlayArrow, Refresh, TrendingUp, TrendingDown, HourglassEmpty } from '@mui/icons-material';
import { useAssetCatalog } from '../../hooks/useApi';
import apiService from '../../services/api';
// AssetCatalogType imported for potential future use
import type { AssetCatalog as _AssetCatalogType } from '../../types/index';

const AssetCatalog: React.FC = () => {
  const [runningCatalog, setRunningCatalog] = useState(false);
  const [catalogProgress, setCatalogProgress] = useState<string>('');
  const { data: assets, loading, error, refetch, runCatalog } = useAssetCatalog();

  // Check catalog status on mount and poll while running
  const checkCatalogStatus = useCallback(async () => {
    try {
      const status = await apiService.getCatalogStatus();
      if (status.running) {
        setRunningCatalog(true);
        setCatalogProgress('Catalogação em andamento...');
        return true;
      } else {
        setRunningCatalog(false);
        setCatalogProgress('');
        return false;
      }
    } catch (err) {
      console.error('Erro ao verificar status:', err);
      return false;
    }
  }, []);

  useEffect(() => {
    // Check status on mount
    checkCatalogStatus();
  }, [checkCatalogStatus]);

  useEffect(() => {
    // Poll while running
    if (!runningCatalog) return;
    
    // Check status immediately
    checkCatalogStatus();
    
    const interval = setInterval(async () => {
      const stillRunning = await checkCatalogStatus();
      if (!stillRunning) {
        // Cataloging finished, refresh data
        refetch();
      }
    }, 1000); // Poll every 1 second for faster updates
    
    return () => clearInterval(interval);
  }, [runningCatalog, checkCatalogStatus, refetch]);

  const handleRunCatalog = async () => {
    setRunningCatalog(true);
    setCatalogProgress('Iniciando catalogação...');
    try {
      await runCatalog();
      setCatalogProgress('Catalogação em andamento...');
      // Keep polling to monitor status - don't set runningCatalog to false here
      // The polling effect will handle status updates
    } catch (err) {
      console.error('Erro ao executar catalogação:', err);
      setRunningCatalog(false);
      setCatalogProgress('Erro ao iniciar catalogação');
    }
  };

  const formatPercentage = (value: number | string | null | undefined) => {
    const numValue = typeof value === 'number' ? value : parseFloat(String(value || 0));
    return isNaN(numValue) ? '0.00%' : `${numValue.toFixed(2)}%`;
  };

  // formatCurrency available for future use
  const _formatCurrency = (value: number) => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'USD',
    }).format(value);
  };
  void _formatCurrency;

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString('pt-BR');
  };

  const getWinRateColor = (winRate: number) => {
    if (winRate >= 70) return 'success';
    if (winRate >= 50) return 'warning';
    return 'error';
  };

  // getRecommendationIcon available for future use
  const _getRecommendationIcon = (isRecommended: boolean, winRate: number) => {
    if (isRecommended && winRate >= 60) {
      return <TrendingUp color="success" fontSize="small" />;
    }
    return <TrendingDown color="error" fontSize="small" />;
  };
  void _getRecommendationIcon;

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', py: 4 }}>
            <CircularProgress />
            <Typography sx={{ ml: 2 }}>Carregando catálogo de ativos...</Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent>
          <Alert severity="error" action={
            <IconButton color="inherit" size="small" onClick={refetch}>
              <Refresh />
            </IconButton>
          }>
            {error}
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">Catálogo de Ativos</Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              variant="contained"
              startIcon={runningCatalog ? <CircularProgress size={20} /> : <PlayArrow />}
              onClick={handleRunCatalog}
              disabled={runningCatalog}
            >
              {runningCatalog ? 'Executando...' : 'Executar Catalogação'}
            </Button>
            <Tooltip title="Atualizar">
              <IconButton onClick={refetch} disabled={loading}>
                <Refresh />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        <Typography variant="body2" color="textSecondary" gutterBottom>
          Análise de performance dos ativos baseada nas estratégias de trading
        </Typography>

        {runningCatalog && (
          <Box sx={{ mb: 2 }}>
            <Alert 
              severity="info" 
              icon={<HourglassEmpty />}
              sx={{ mb: 1 }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <CircularProgress size={16} />
                <Typography variant="body2">
                  {catalogProgress || 'Catalogação em andamento...'}
                </Typography>
              </Box>
            </Alert>
            <LinearProgress />
          </Box>
        )}

        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Ativo/Estratégia</TableCell>
                <TableCell>Amostras</TableCell>
                <TableCell>Taxa de Vitória</TableCell>
                <TableCell>Taxas Gale</TableCell>
                <TableCell>Recomendado</TableCell>
                <TableCell>Última Análise</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {!assets || assets.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} align="center">
                    <Typography color="textSecondary">
                      Nenhum ativo catalogado. Execute a catalogação para analisar os ativos.
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                assets.map((asset, index) => (
                  <TableRow key={`${asset.asset}-${asset.strategy}-${index}`}>
                    <TableCell>
                      <Box>
                        <Typography variant="body2" fontWeight="medium">
                          {asset.asset}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {asset.strategy}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {asset.total_samples} amostras
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Análise completa
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip 
                        label={formatPercentage(asset.win_rate)}
                        color={getWinRateColor(asset.win_rate)}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>
                      <Box display="flex" flexDirection="column" gap={0.5}>
                        <Typography variant="caption" color="text.secondary">
                          Gale 1: {formatPercentage(asset.gale1_rate)}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Gale 2: {formatPercentage(asset.gale2_rate)}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Gale 3: {formatPercentage(asset.gale3_rate)}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={asset.gale3_rate >= 70 ? 'Recomendado' : 'Não recomendado'}
                        color={asset.gale3_rate >= 70 ? 'success' : 'default'}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {formatDateTime(asset.analyzed_at)}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>

        {assets && assets.length > 0 && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="body2" color="textSecondary">
              <strong>Total de ativos:</strong> {assets.length} | 
              <strong> Recomendados:</strong> {assets.filter(a => a.gale3_rate >= 70).length} |
              <strong> Taxa média:</strong> {formatPercentage(
                assets.reduce((acc, asset) => acc + asset.win_rate, 0) / assets.length
              )}
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default AssetCatalog;
