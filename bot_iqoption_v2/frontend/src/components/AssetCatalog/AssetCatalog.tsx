import React, { useState } from 'react';
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
import { PlayArrow, Refresh, TrendingUp, TrendingDown } from '@mui/icons-material';
import { useAssetCatalog } from '../../hooks/useApi';
import type { AssetCatalog as AssetCatalogType } from '../../types/index';

const AssetCatalog: React.FC = () => {
  const [runningCatalog, setRunningCatalog] = useState(false);
  const { data: assets, loading, error, refetch, runCatalog } = useAssetCatalog();

  const handleRunCatalog = async () => {
    setRunningCatalog(true);
    try {
      await runCatalog();
    } catch (err) {
      console.error('Erro ao executar catalogação:', err);
    } finally {
      setRunningCatalog(false);
    }
  };

  const formatPercentage = (value: number) => {
    return `${value.toFixed(2)}%`;
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'USD',
    }).format(value);
  };

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString('pt-BR');
  };

  const getWinRateColor = (winRate: number) => {
    if (winRate >= 70) return 'success';
    if (winRate >= 50) return 'warning';
    return 'error';
  };

  const getRecommendationIcon = (isRecommended: boolean, winRate: number) => {
    if (isRecommended && winRate >= 60) {
      return <TrendingUp color="success" fontSize="small" />;
    }
    return <TrendingDown color="error" fontSize="small" />;
  };

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

        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Ativo</TableCell>
                <TableCell>Estratégia</TableCell>
                <TableCell>Operações</TableCell>
                <TableCell>Taxa de Acerto</TableCell>
                <TableCell>Lucro Médio</TableCell>
                <TableCell>Recomendado</TableCell>
                <TableCell>Última Análise</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {!assets || assets.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} align="center">
                    <Typography color="textSecondary">
                      Nenhum ativo catalogado. Execute a catalogação para analisar os ativos.
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                assets.map((asset: AssetCatalogType) => (
                  <TableRow key={asset.id} hover>
                    <TableCell>
                      <Typography variant="body2" fontWeight="medium">
                        {asset.asset}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip 
                        label={asset.strategy} 
                        size="small"
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>
                      <Box>
                        <Typography variant="body2">
                          {asset.successful_operations}/{asset.total_operations}
                        </Typography>
                        <LinearProgress 
                          variant="determinate" 
                          value={(asset.successful_operations / asset.total_operations) * 100}
                          sx={{ mt: 0.5, height: 4 }}
                        />
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip 
                        label={formatPercentage(asset.win_rate)}
                        color={getWinRateColor(asset.win_rate)}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>
                      <Typography 
                        variant="body2"
                        color={asset.avg_profit >= 0 ? 'success.main' : 'error.main'}
                        fontWeight="medium"
                      >
                        {formatCurrency(asset.avg_profit)}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {getRecommendationIcon(asset.is_recommended, asset.win_rate)}
                        <Chip 
                          label={asset.is_recommended ? 'SIM' : 'NÃO'}
                          color={asset.is_recommended ? 'success' : 'default'}
                          size="small"
                          variant="outlined"
                        />
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="textSecondary">
                        {formatDateTime(asset.last_analysis)}
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
              <strong> Recomendados:</strong> {assets.filter(a => a.is_recommended).length} |
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
