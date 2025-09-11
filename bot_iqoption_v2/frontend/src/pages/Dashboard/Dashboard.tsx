import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Button,
  Chip,
  LinearProgress,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  PlayArrow,
  Stop,
  Pause,
  Refresh,
  AccountBalance,
  Assessment,
  History,
} from '@mui/icons-material';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import type { DashboardData, AssetPerformance } from '../../types/index';
import apiService from '../../services/api';


const Dashboard: React.FC = () => {
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tradingStatus, setTradingStatus] = useState<'stopped' | 'running' | 'paused'>('stopped');


  useEffect(() => {
    loadDashboardData();
    // Set up polling for real-time updates
    const interval = setInterval(loadDashboardData, 5000);
    return () => clearInterval(interval);
  }, []);


  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const data = await apiService.getDashboardData();
      setDashboardData(data);
      
      // Update trading status based on current session
      if (data.current_session) {
        setTradingStatus(data.current_session.status.toLowerCase() as 'stopped' | 'running' | 'paused');
      } else {
        setTradingStatus('stopped');
      }
      
      setError(null);
    } catch (err) {
      setError('Erro ao carregar dados do dashboard');
      console.error('Dashboard error:', err);
    } finally {
      setLoading(false);
    }
  };


  const handleStartTrading = async () => {
    try {
      await apiService.startTrading('mhi');
      setTradingStatus('running');
    } catch {
      setError('Erro ao iniciar trading');
    }
  };


  const handleStopTrading = async () => {
    try {
      if (dashboardData?.current_session?.id) {
        await apiService.stopTrading(dashboardData.current_session.id.toString());
        setTradingStatus('stopped');
      }
    } catch {
      setError('Erro ao parar trading');
    }
  };


  const handlePauseTrading = async () => {
    try {
      if (dashboardData?.current_session?.id) {
        await apiService.pauseTrading(dashboardData.current_session.id.toString());
        setTradingStatus('paused');
      }
    } catch {
      setError('Erro ao pausar trading');
    }
  };


  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'USD',
    }).format(value);
  };


  const formatPercentage = (value: number) => {
    return `${value.toFixed(2)}%`;
  };


  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'success';
      case 'paused': return 'warning';
      case 'stopped': return 'error';
      default: return 'default';
    }
  };


  const pieData = dashboardData?.asset_performance?.slice(0, 5).map((asset: AssetPerformance, index: number) => ({
    name: asset.asset,
    value: asset.win_rate,
    color: `hsl(${index * 72}, 70%, 50%)`,
  })) || [];


  if (loading) {
    return (
      <Box sx={{ width: '100%', mt: 2 }}>
        <LinearProgress />
        <Typography sx={{ mt: 2, textAlign: 'center' }}>Carregando dashboard...</Typography>
      </Box>
    );
  }


  return (
    <Box sx={{ flexGrow: 1 }}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}


      {/* Trading Controls */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">Controle de Trading</Typography>
            <Chip 
              label={tradingStatus === 'running' ? 'Ativo' : tradingStatus === 'paused' ? 'Pausado' : 'Parado'}
              color={getStatusColor(tradingStatus)}
              variant="filled"
            />
          </Box>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              variant="contained"
              color="success"
              startIcon={<PlayArrow />}
              onClick={handleStartTrading}
              disabled={tradingStatus === 'running'}
            >
              Iniciar
            </Button>
            <Button
              variant="contained"
              color="warning"
              startIcon={<Pause />}
              onClick={handlePauseTrading}
              disabled={tradingStatus !== 'running'}
            >
              Pausar
            </Button>
            <Button
              variant="contained"
              color="error"
              startIcon={<Stop />}
              onClick={handleStopTrading}
              disabled={tradingStatus === 'stopped'}
            >
              Parar
            </Button>
            <Button
              variant="outlined"
              startIcon={<Refresh />}
              onClick={loadDashboardData}
            >
              Atualizar
            </Button>
          </Box>
        </CardContent>
      </Card>


      {/* Key Metrics */}
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3, mb: 3 }}>
        <Box sx={{ flex: '1 1 300px', minWidth: '250px' }}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography color="textSecondary" gutterBottom variant="body2">
                    Saldo Total
                  </Typography>
                  <Typography variant="h5">
                    {formatCurrency(dashboardData?.account_balance || 0)}
                  </Typography>
                </Box>
                <AccountBalance color="primary" sx={{ fontSize: 40 }} />
              </Box>
            </CardContent>
          </Card>
        </Box>


        <Box sx={{ flex: '1 1 300px', minWidth: '250px' }}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography color="textSecondary" gutterBottom variant="body2">
                    P&L Hoje
                  </Typography>
                  <Typography variant="h5" color={(dashboardData?.session_stats?.total_profit ?? 0) >= 0 ? 'success.main' : 'error.main'}>
                    {formatCurrency(dashboardData?.session_stats?.total_profit || 0)}
                  </Typography>
                </Box>
                {(dashboardData?.session_stats?.total_profit ?? 0) >= 0 ? 
                  <TrendingUp color="success" sx={{ fontSize: 40 }} /> :
                  <TrendingDown color="error" sx={{ fontSize: 40 }} />
                }
              </Box>
            </CardContent>
          </Card>
        </Box>


        <Box sx={{ flex: '1 1 300px', minWidth: '250px' }}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography color="textSecondary" gutterBottom variant="body2">
                    Taxa de Acerto
                  </Typography>
                  <Typography variant="h5">
                    {formatPercentage(dashboardData?.session_stats?.win_rate || 0)}
                  </Typography>
                </Box>
                <Assessment color="primary" sx={{ fontSize: 40 }} />
              </Box>
            </CardContent>
          </Card>
        </Box>


        <Box sx={{ flex: '1 1 300px', minWidth: '250px' }}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography color="textSecondary" gutterBottom variant="body2">
                    Total Operações
                  </Typography>
                  <Typography variant="h5">
                    {dashboardData?.current_session?.total_operations || 0}
                  </Typography>
                </Box>
                <History color="primary" sx={{ fontSize: 40 }} />
              </Box>
            </CardContent>
          </Card>
        </Box>
      </Box>


      {/* Charts */}
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3, mb: 3 }}>
        <Box sx={{ flex: '2 1 600px', minWidth: '400px' }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Performance dos Ativos
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={dashboardData?.asset_performance || []}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="asset" />
                  <YAxis />
                  <Tooltip formatter={(value) => `${value}%`} />
                  <Line type="monotone" dataKey="win_rate" stroke="#8884d8" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Box>


        <Box sx={{ flex: '1 1 300px', minWidth: '300px' }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Top 5 Ativos
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                    label={({ name, value }) => `${name}: ${value}%`}
                  >
                    {pieData.map((entry: { name: string; value: number; color: string }, index: number) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Box>
      </Box>


      {/* Recent Operations */}
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
        <Box sx={{ flex: '2 1 600px', minWidth: '400px' }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Operações Recentes
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Ativo</TableCell>
                      <TableCell>Direção</TableCell>
                      <TableCell>Valor</TableCell>
                      <TableCell>Resultado</TableCell>
                      <TableCell>P&L</TableCell>
                      <TableCell>Horário</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {dashboardData?.recent_operations?.slice(0, 10).map((operation) => (
                      <TableRow key={operation.id}>
                        <TableCell>{operation.asset}</TableCell>
                        <TableCell>
                          <Chip 
                            label={operation.direction.toUpperCase()} 
                            color={operation.direction === 'call' ? 'success' : 'error'}
                            size="small"
                          />
                        </TableCell>
                        <TableCell>{formatCurrency(operation.amount)}</TableCell>
                        <TableCell>
                          {operation.result && (
                            <Chip 
                              label={operation.result === 'win' ? 'WIN' : 'LOSS'} 
                              color={operation.result === 'win' ? 'success' : 'error'}
                              size="small"
                            />
                          )}
                        </TableCell>
                        <TableCell>
                          {operation.profit_loss && (
                            <Typography color={operation.profit_loss >= 0 ? 'success.main' : 'error.main'}>
                              {formatCurrency(operation.profit_loss)}
                            </Typography>
                          )}
                        </TableCell>
                        <TableCell>
                          {new Date(operation.created_at).toLocaleTimeString('pt-BR')}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        </Box>


        <Box sx={{ flex: '1 1 300px', minWidth: '300px' }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Logs Recentes
              </Typography>
              <Box sx={{ maxHeight: 400, overflow: 'auto' }}>
                {dashboardData?.recent_logs?.map((log) => (
                  <Alert 
                    key={log.id} 
                    severity={log.level.toLowerCase() as 'info' | 'warning' | 'error'}
                    sx={{ mb: 1, fontSize: '0.8rem' }}
                  >
                    <Typography variant="caption" display="block">
                      {new Date(log.created_at).toLocaleTimeString('pt-BR')}
                    </Typography>
                    {log.message}
                  </Alert>
                ))}
              </Box>
            </CardContent>
          </Card>
        </Box>
      </Box>
    </Box>
  );
};


export default Dashboard;
