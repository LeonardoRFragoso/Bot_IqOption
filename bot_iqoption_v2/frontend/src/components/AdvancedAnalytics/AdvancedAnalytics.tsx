import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Chip,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Tooltip,
  Alert,
  Tabs,
  Tab,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Slider,
  Button,
  CircularProgress,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  TrendingFlat,
  Star,
  StarBorder,
  Block,
  Warning,
  Refresh,
  FilterList,
  Schedule,
  ShowChart,
} from '@mui/icons-material';
import apiService from '../../services/api';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div role="tabpanel" hidden={value !== index} {...other}>
      {value === index && <Box sx={{ p: 2 }}>{children}</Box>}
    </div>
  );
}

interface AssetResult {
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
}

interface StrategyPerformance {
  strategy: string;
  total_operations: number;
  wins: number;
  losses: number;
  win_rate: number;
  profit_loss: number;
}

interface DailyStats {
  date: string;
  total_operations: number;
  wins: number;
  losses: number;
  win_rate: number;
  profit_loss: number;
}

const AdvancedAnalytics: React.FC = () => {
  const [tabValue, setTabValue] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Best Assets State
  const [bestAssets, setBestAssets] = useState<AssetResult[]>([]);
  const [minWinRate, setMinWinRate] = useState(60);
  const [minGale1Rate, setMinGale1Rate] = useState(75);

  // Strategy Performance State
  const [strategyPerformance, setStrategyPerformance] = useState<StrategyPerformance[]>([]);
  const [performanceDays, setPerformanceDays] = useState(30);

  // Daily Performance State
  const [dailyStats, setDailyStats] = useState<DailyStats[]>([]);

  // Trading Schedule State
  const [schedule, setSchedule] = useState<any>(null);

  // Loss Tracker State
  const [lossTracker, setLossTracker] = useState<any>(null);

  // Blacklist State
  const [blacklist, setBlacklist] = useState<any>(null);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const fetchBestAssets = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiService.getBestAssets({
        min_win_rate: minWinRate,
        min_gale1_rate: minGale1Rate,
        max_results: 20,
      });
      setBestAssets(data.assets || []);
    } catch (err: any) {
      setError(err.message || 'Erro ao carregar melhores ativos');
    } finally {
      setLoading(false);
    }
  };

  const fetchStrategyPerformance = async () => {
    setLoading(true);
    try {
      const data = await apiService.getStrategyPerformance(performanceDays);
      setStrategyPerformance(data.strategies || []);
    } catch (err: any) {
      setError(err.message || 'Erro ao carregar performance');
    } finally {
      setLoading(false);
    }
  };

  const fetchDailyPerformance = async () => {
    setLoading(true);
    try {
      const data = await apiService.getDailyPerformance(7);
      setDailyStats(data.daily_stats || []);
    } catch (err: any) {
      setError(err.message || 'Erro ao carregar performance diária');
    } finally {
      setLoading(false);
    }
  };

  const fetchSchedule = async () => {
    try {
      const data = await apiService.getTradingSchedule();
      setSchedule(data);
    } catch (err: any) {
      console.error('Erro ao carregar schedule:', err);
    }
  };

  const fetchLossTracker = async () => {
    try {
      const data = await apiService.getLossTrackerStatus();
      setLossTracker(data);
    } catch (err: any) {
      console.error('Erro ao carregar loss tracker:', err);
    }
  };

  const fetchBlacklist = async () => {
    try {
      const data = await apiService.getBlacklist();
      setBlacklist(data);
    } catch (err: any) {
      console.error('Erro ao carregar blacklist:', err);
    }
  };

  const handleResetLossTracker = async () => {
    try {
      await apiService.resetLossTracker();
      fetchLossTracker();
    } catch (err: any) {
      setError(err.message || 'Erro ao resetar contador');
    }
  };

  useEffect(() => {
    fetchBestAssets();
    fetchSchedule();
    fetchLossTracker();
    fetchBlacklist();
  }, []);

  useEffect(() => {
    if (tabValue === 1) {
      fetchStrategyPerformance();
    } else if (tabValue === 2) {
      fetchDailyPerformance();
    }
  }, [tabValue, performanceDays]);

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'UP':
        return <TrendingUp color="success" />;
      case 'DOWN':
        return <TrendingDown color="error" />;
      default:
        return <TrendingFlat color="warning" />;
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'success';
    if (score >= 60) return 'warning';
    return 'error';
  };

  return (
    <Box>
      <Typography variant="h5" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <ShowChart /> Análise Avançada
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Quick Stats Cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {/* Trading Schedule Card */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="textSecondary" gutterBottom>
                <Schedule sx={{ fontSize: 16, mr: 0.5, verticalAlign: 'middle' }} />
                Sessão Atual
              </Typography>
              {schedule ? (
                <>
                  <Typography variant="h6">
                    {schedule.current_sessions?.join(', ') || 'Nenhuma'}
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    {schedule.recommended_assets?.length || 0} ativos recomendados
                  </Typography>
                </>
              ) : (
                <CircularProgress size={20} />
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Loss Tracker Card */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="textSecondary" gutterBottom>
                <Warning sx={{ fontSize: 16, mr: 0.5, verticalAlign: 'middle' }} />
                Perdas Consecutivas
              </Typography>
              {lossTracker ? (
                <>
                  <Typography variant="h6" color={lossTracker.can_continue ? 'success.main' : 'error.main'}>
                    {lossTracker.consecutive_losses} / {lossTracker.max_consecutive_losses}
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="body2" color="textSecondary">
                      Hoje: {lossTracker.total_losses_today} perdas
                    </Typography>
                    <IconButton size="small" onClick={handleResetLossTracker}>
                      <Refresh fontSize="small" />
                    </IconButton>
                  </Box>
                </>
              ) : (
                <CircularProgress size={20} />
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Blacklist Card */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="textSecondary" gutterBottom>
                <Block sx={{ fontSize: 16, mr: 0.5, verticalAlign: 'middle' }} />
                Blacklist
              </Typography>
              {blacklist ? (
                <>
                  <Typography variant="h6">
                    {(blacklist.permanent?.length || 0) + Object.keys(blacklist.temporary || {}).length} ativos
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    {blacklist.permanent?.length || 0} permanentes, {Object.keys(blacklist.temporary || {}).length} temporários
                  </Typography>
                </>
              ) : (
                <CircularProgress size={20} />
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Tabs */}
      <Card>
        <Tabs value={tabValue} onChange={handleTabChange}>
          <Tab label="Melhores Ativos" icon={<Star />} iconPosition="start" />
          <Tab label="Performance por Estratégia" icon={<ShowChart />} iconPosition="start" />
          <Tab label="Performance Diária" icon={<Schedule />} iconPosition="start" />
        </Tabs>

        {/* Best Assets Tab */}
        <TabPanel value={tabValue} index={0}>
          <Box sx={{ mb: 2, display: 'flex', gap: 3, alignItems: 'center', flexWrap: 'wrap' }}>
            <Box sx={{ minWidth: 200 }}>
              <Typography variant="body2" gutterBottom>
                Win Rate Mínimo: {minWinRate}%
              </Typography>
              <Slider
                value={minWinRate}
                onChange={(_, value) => setMinWinRate(value as number)}
                min={0}
                max={100}
                valueLabelDisplay="auto"
              />
            </Box>
            <Box sx={{ minWidth: 200 }}>
              <Typography variant="body2" gutterBottom>
                Gale1 Rate Mínimo: {minGale1Rate}%
              </Typography>
              <Slider
                value={minGale1Rate}
                onChange={(_, value) => setMinGale1Rate(value as number)}
                min={0}
                max={100}
                valueLabelDisplay="auto"
              />
            </Box>
            <Button
              variant="contained"
              startIcon={<FilterList />}
              onClick={fetchBestAssets}
              disabled={loading}
            >
              Filtrar
            </Button>
          </Box>

          {loading ? (
            <LinearProgress />
          ) : (
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Ativo</TableCell>
                    <TableCell>Estratégia</TableCell>
                    <TableCell align="center">Tendência</TableCell>
                    <TableCell align="right">Win Rate</TableCell>
                    <TableCell align="right">Gale1</TableCell>
                    <TableCell align="right">Gale2</TableCell>
                    <TableCell align="right">Amostras</TableCell>
                    <TableCell align="right">Score</TableCell>
                    <TableCell align="center">Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {bestAssets.map((asset, index) => (
                    <TableRow key={`${asset.asset}-${asset.strategy}-${index}`}>
                      <TableCell>
                        <Typography variant="body2" fontWeight="bold">
                          {asset.asset}
                        </Typography>
                      </TableCell>
                      <TableCell>{asset.strategy}</TableCell>
                      <TableCell align="center">
                        {getTrendIcon(asset.trend)}
                      </TableCell>
                      <TableCell align="right">
                        <Chip
                          label={`${asset.win_rate}%`}
                          size="small"
                          color={asset.win_rate >= 60 ? 'success' : 'warning'}
                        />
                      </TableCell>
                      <TableCell align="right">{asset.gale1_rate}%</TableCell>
                      <TableCell align="right">{asset.gale2_rate}%</TableCell>
                      <TableCell align="right">{asset.total_samples}</TableCell>
                      <TableCell align="right">
                        <Chip
                          label={asset.score}
                          size="small"
                          color={getScoreColor(asset.score) as any}
                        />
                      </TableCell>
                      <TableCell align="center">
                        {asset.is_recommended ? (
                          <Tooltip title="Recomendado">
                            <Star color="warning" />
                          </Tooltip>
                        ) : (
                          <StarBorder color="disabled" />
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                  {bestAssets.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={9} align="center">
                        <Typography color="textSecondary">
                          Nenhum ativo encontrado com os filtros selecionados
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </TabPanel>

        {/* Strategy Performance Tab */}
        <TabPanel value={tabValue} index={1}>
          <Box sx={{ mb: 2, display: 'flex', gap: 2, alignItems: 'center' }}>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Período</InputLabel>
              <Select
                value={performanceDays}
                label="Período"
                onChange={(e) => setPerformanceDays(e.target.value as number)}
              >
                <MenuItem value={7}>7 dias</MenuItem>
                <MenuItem value={14}>14 dias</MenuItem>
                <MenuItem value={30}>30 dias</MenuItem>
                <MenuItem value={60}>60 dias</MenuItem>
              </Select>
            </FormControl>
            <Button
              variant="outlined"
              startIcon={<Refresh />}
              onClick={fetchStrategyPerformance}
              disabled={loading}
            >
              Atualizar
            </Button>
          </Box>

          {loading ? (
            <LinearProgress />
          ) : (
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Estratégia</TableCell>
                    <TableCell align="right">Total Ops</TableCell>
                    <TableCell align="right">Wins</TableCell>
                    <TableCell align="right">Losses</TableCell>
                    <TableCell align="right">Win Rate</TableCell>
                    <TableCell align="right">Lucro/Prejuízo</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {strategyPerformance.map((strat) => (
                    <TableRow key={strat.strategy}>
                      <TableCell>
                        <Typography variant="body2" fontWeight="bold">
                          {strat.strategy}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">{strat.total_operations}</TableCell>
                      <TableCell align="right">
                        <Typography color="success.main">{strat.wins}</Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography color="error.main">{strat.losses}</Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Chip
                          label={`${strat.win_rate}%`}
                          size="small"
                          color={strat.win_rate >= 60 ? 'success' : strat.win_rate >= 50 ? 'warning' : 'error'}
                        />
                      </TableCell>
                      <TableCell align="right">
                        <Typography color={strat.profit_loss >= 0 ? 'success.main' : 'error.main'}>
                          R$ {strat.profit_loss.toFixed(2)}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                  {strategyPerformance.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} align="center">
                        <Typography color="textSecondary">
                          Nenhuma operação no período selecionado
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </TabPanel>

        {/* Daily Performance Tab */}
        <TabPanel value={tabValue} index={2}>
          {loading ? (
            <LinearProgress />
          ) : (
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Data</TableCell>
                    <TableCell align="right">Operações</TableCell>
                    <TableCell align="right">Wins</TableCell>
                    <TableCell align="right">Losses</TableCell>
                    <TableCell align="right">Win Rate</TableCell>
                    <TableCell align="right">Resultado</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {dailyStats.map((day) => (
                    <TableRow key={day.date}>
                      <TableCell>
                        <Typography variant="body2" fontWeight="bold">
                          {new Date(day.date).toLocaleDateString('pt-BR')}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">{day.total_operations}</TableCell>
                      <TableCell align="right">
                        <Typography color="success.main">{day.wins}</Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography color="error.main">{day.losses}</Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Chip
                          label={`${day.win_rate}%`}
                          size="small"
                          color={day.win_rate >= 60 ? 'success' : day.win_rate >= 50 ? 'warning' : 'error'}
                        />
                      </TableCell>
                      <TableCell align="right">
                        <Typography color={day.profit_loss >= 0 ? 'success.main' : 'error.main'}>
                          R$ {day.profit_loss.toFixed(2)}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                  {dailyStats.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} align="center">
                        <Typography color="textSecondary">
                          Nenhuma operação nos últimos 7 dias
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </TabPanel>
      </Card>
    </Box>
  );
};

export default AdvancedAnalytics;
