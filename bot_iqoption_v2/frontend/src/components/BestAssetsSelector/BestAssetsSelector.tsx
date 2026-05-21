import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Chip,
  IconButton,
  Tooltip,
  CircularProgress,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Button,
  Collapse,
} from '@mui/material';
import {
  Star,
  TrendingUp,
  TrendingDown,
  TrendingFlat,
  Refresh,
  ExpandMore,
  ExpandLess,
  CheckCircle,
} from '@mui/icons-material';
import apiService from '../../services/api';

interface BestAsset {
  asset: string;
  strategy: string;
  win_rate: number;
  gale1_rate: number;
  gale2_rate: number;
  gale3_rate: number;
  total_samples: number;
  trend: string;
  score: number;
  is_recommended: boolean;
  analyzed_at?: string;
}

interface BestAssetsSelectorProps {
  onSelectAsset?: (asset: string, strategy: string) => void;
  selectedAsset?: string;
  selectedStrategy?: string;
  maxResults?: number;
}

const BestAssetsSelector: React.FC<BestAssetsSelectorProps> = ({
  onSelectAsset,
  selectedAsset,
  selectedStrategy,
  maxResults = 5,
}) => {
  const [assets, setAssets] = useState<BestAsset[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchBestAssets = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiService.getBestAssets({
        min_win_rate: 55,
        min_gale1_rate: 70,
        max_results: maxResults,
      });
      setAssets(data.assets || []);
      setLastUpdate(new Date());
    } catch (err: any) {
      setError(err.message || 'Erro ao carregar melhores ativos');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBestAssets();
    // Atualizar a cada 5 minutos
    const interval = setInterval(fetchBestAssets, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'UP':
        return <TrendingUp fontSize="small" color="success" />;
      case 'DOWN':
        return <TrendingDown fontSize="small" color="error" />;
      default:
        return <TrendingFlat fontSize="small" color="warning" />;
    }
  };

  const handleSelectAsset = (asset: BestAsset) => {
    if (onSelectAsset) {
      onSelectAsset(asset.asset, asset.strategy);
    }
  };

  const isSelected = (asset: BestAsset) => {
    return asset.asset === selectedAsset && asset.strategy === selectedStrategy;
  };

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent sx={{ pb: expanded ? 2 : 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Star color="warning" />
            <Typography variant="subtitle1" fontWeight="bold">
              Melhores Ativos para Operar
            </Typography>
            {assets.length > 0 && (
              <Chip
                label={`${assets.length} encontrados`}
                size="small"
                color="primary"
                variant="outlined"
              />
            )}
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {lastUpdate && (
              <Typography variant="caption" color="textSecondary">
                Atualizado: {lastUpdate.toLocaleTimeString('pt-BR')}
              </Typography>
            )}
            <Tooltip title="Atualizar">
              <IconButton size="small" onClick={fetchBestAssets} disabled={loading}>
                {loading ? <CircularProgress size={18} /> : <Refresh fontSize="small" />}
              </IconButton>
            </Tooltip>
            <IconButton size="small" onClick={() => setExpanded(!expanded)}>
              {expanded ? <ExpandLess /> : <ExpandMore />}
            </IconButton>
          </Box>
        </Box>

        <Collapse in={expanded}>
          {error && (
            <Alert severity="error" sx={{ mt: 2 }} onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          {loading && assets.length === 0 ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
              <CircularProgress />
            </Box>
          ) : assets.length === 0 ? (
            <Alert severity="info" sx={{ mt: 2 }}>
              Nenhum ativo encontrado. Execute uma catalogação primeiro.
            </Alert>
          ) : (
            <TableContainer component={Paper} sx={{ mt: 2 }} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Ativo</TableCell>
                    <TableCell>Estratégia</TableCell>
                    <TableCell align="center">Tendência</TableCell>
                    <TableCell align="right">Win Rate</TableCell>
                    <TableCell align="right">Gale1</TableCell>
                    <TableCell align="right">Score</TableCell>
                    <TableCell align="center">Ação</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {assets.map((asset, index) => (
                    <TableRow
                      key={`${asset.asset}-${asset.strategy}-${index}`}
                      sx={{
                        backgroundColor: isSelected(asset) ? 'action.selected' : 'inherit',
                        '&:hover': { backgroundColor: 'action.hover' },
                        cursor: 'pointer',
                      }}
                      onClick={() => handleSelectAsset(asset)}
                    >
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                          {asset.is_recommended && (
                            <Tooltip title="Recomendado">
                              <Star fontSize="small" color="warning" />
                            </Tooltip>
                          )}
                          <Typography variant="body2" fontWeight="bold">
                            {asset.asset}
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">{asset.strategy}</Typography>
                      </TableCell>
                      <TableCell align="center">
                        <Tooltip title={`Tendência: ${asset.trend}`}>
                          {getTrendIcon(asset.trend)}
                        </Tooltip>
                      </TableCell>
                      <TableCell align="right">
                        <Chip
                          label={`${asset.win_rate}%`}
                          size="small"
                          color={asset.win_rate >= 60 ? 'success' : 'warning'}
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell align="right">
                        <Typography
                          variant="body2"
                          color={asset.gale1_rate >= 80 ? 'success.main' : 'text.secondary'}
                        >
                          {asset.gale1_rate}%
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Chip
                          label={asset.score.toFixed(0)}
                          size="small"
                          color={asset.score >= 70 ? 'success' : asset.score >= 50 ? 'warning' : 'default'}
                        />
                      </TableCell>
                      <TableCell align="center">
                        {isSelected(asset) ? (
                          <CheckCircle color="success" fontSize="small" />
                        ) : (
                          <Button
                            size="small"
                            variant="outlined"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleSelectAsset(asset);
                            }}
                          >
                            Selecionar
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}

          {assets.length > 0 && (
            <Typography variant="caption" color="textSecondary" sx={{ mt: 1, display: 'block' }}>
              Clique em um ativo para selecioná-lo automaticamente para trading
            </Typography>
          )}
        </Collapse>
      </CardContent>
    </Card>
  );
};

export default BestAssetsSelector;
