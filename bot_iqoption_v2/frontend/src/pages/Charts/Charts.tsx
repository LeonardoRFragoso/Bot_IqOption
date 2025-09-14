import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Card,
  CardContent,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Button,
  Chip,
  Alert
} from '@mui/material';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import { TrendingUp, TrendingDown, BarChart, Refresh } from '@mui/icons-material';
import type { SelectChangeEvent } from '@mui/material/Select';

interface ChartData {
  time: string;
  price: number;
  volume?: number;
}

interface AssetInfo {
  symbol: string;
  name: string;
  payout: number;
  isOpen: boolean;
}

const Charts: React.FC = () => {
  const [selectedAsset, setSelectedAsset] = useState<string>('EURUSD');
  const [timeframe, setTimeframe] = useState<string>('1m');
  const [chartData, setChartData] = useState<ChartData[]>([]);
  const [assets, setAssets] = useState<AssetInfo[]>([]);
  const [loading, setLoading] = useState<boolean>(false);

  // Mock data for demonstration
  const mockAssets: AssetInfo[] = [
    { symbol: 'EURUSD', name: 'Euro/US Dollar', payout: 85, isOpen: true },
    { symbol: 'GBPUSD', name: 'British Pound/US Dollar', payout: 83, isOpen: true },
    { symbol: 'USDJPY', name: 'US Dollar/Japanese Yen', payout: 82, isOpen: true },
    { symbol: 'AUDUSD', name: 'Australian Dollar/US Dollar', payout: 84, isOpen: false },
    { symbol: 'USDCAD', name: 'US Dollar/Canadian Dollar', payout: 81, isOpen: true },
  ];

  const generateMockData = (): ChartData[] => {
    const data: ChartData[] = [];
    const now = new Date();
    let basePrice = 1.1000 + Math.random() * 0.1;

    for (let i = 29; i >= 0; i--) {
      const time = new Date(now.getTime() - i * 60000);
      const change = (Math.random() - 0.5) * 0.002;
      basePrice += change;
      
      data.push({
        time: time.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }),
        price: Number(basePrice.toFixed(5)),
        volume: Math.floor(Math.random() * 1000) + 100
      });
    }
    return data;
  };

  useEffect(() => {
    setAssets(mockAssets);
    setChartData(generateMockData());
  }, []);

  useEffect(() => {
    if (selectedAsset) {
      setLoading(true);
      setTimeout(() => {
        setChartData(generateMockData());
        setLoading(false);
      }, 500);
    }
  }, [selectedAsset, timeframe]);

  const handleAssetChange = (event: SelectChangeEvent<string>) => {
    setSelectedAsset(event.target.value);
  };

  const handleTimeframeChange = (event: SelectChangeEvent<string>) => {
    setTimeframe(event.target.value);
  };

  const currentAsset = assets.find(asset => asset.symbol === selectedAsset);
  const currentPrice = chartData.length > 0 ? chartData[chartData.length - 1].price : 0;
  const previousPrice = chartData.length > 1 ? chartData[chartData.length - 2].price : currentPrice;
  const priceChange = currentPrice - previousPrice;
  const isPositive = priceChange >= 0;

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom sx={{ mb: 3, fontWeight: 'bold' }}>
        Gráficos de Trading
      </Typography>

      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} sm={4}>
            <FormControl fullWidth>
              <InputLabel>Ativo</InputLabel>
              <Select
                value={selectedAsset}
                label="Ativo"
                onChange={handleAssetChange}
              >
                {assets.map((asset) => (
                  <MenuItem key={asset.symbol} value={asset.symbol}>
                    {asset.symbol} - {asset.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={3}>
            <FormControl fullWidth>
              <InputLabel>Timeframe</InputLabel>
              <Select
                value={timeframe}
                label="Timeframe"
                onChange={handleTimeframeChange}
              >
                <MenuItem value="1m">1 Minuto</MenuItem>
                <MenuItem value="5m">5 Minutos</MenuItem>
                <MenuItem value="15m">15 Minutos</MenuItem>
                <MenuItem value="1h">1 Hora</MenuItem>
                <MenuItem value="4h">4 Horas</MenuItem>
                <MenuItem value="1d">1 Dia</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={3}>
            <Button
              variant="contained"
              startIcon={<Refresh />}
              onClick={() => setChartData(generateMockData())}
              fullWidth
            >
              Atualizar Dados
            </Button>
          </Grid>
        </Grid>
      </Paper>

      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <BarChart sx={{ color: 'primary.main' }} />
                <Typography variant="h6">Preço Atual</Typography>
              </Box>
              <Typography variant="h4" sx={{ mt: 1, fontWeight: 'bold' }}>
                {currentPrice.toFixed(5)}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
                {isPositive ? (
                  <TrendingUp sx={{ color: 'success.main' }} />
                ) : (
                  <TrendingDown sx={{ color: 'error.main' }} />
                )}
                <Typography 
                  variant="body2" 
                  sx={{ color: isPositive ? 'success.main' : 'error.main' }}
                >
                  {isPositive ? '+' : ''}{(priceChange * 10000).toFixed(1)} pips
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="h6">Payout</Typography>
              <Typography variant="h4" sx={{ mt: 1, fontWeight: 'bold', color: 'primary.main' }}>
                {currentAsset?.payout}%
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Retorno se ganhar
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="h6">Status</Typography>
              <Chip 
                label={currentAsset?.isOpen ? 'Mercado Aberto' : 'Mercado Fechado'}
                color={currentAsset?.isOpen ? 'success' : 'error'}
                sx={{ mt: 1 }}
              />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Disponível para trading
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="h6">Timeframe</Typography>
              <Typography variant="h4" sx={{ mt: 1, fontWeight: 'bold' }}>
                {timeframe}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Intervalo de tempo
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Gráfico de Preços - {currentAsset?.name}
        </Typography>
        
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
            <Typography>Carregando dados...</Typography>
          </Box>
        ) : (
          <ResponsiveContainer width="100%" height={400}>
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="time" 
                tick={{ fontSize: 12 }}
                interval="preserveStartEnd"
              />
              <YAxis 
                domain={['dataMin - 0.001', 'dataMax + 0.001']}
                tick={{ fontSize: 12 }}
                tickFormatter={(value) => value.toFixed(5)}
              />
              <Tooltip 
                formatter={(value: number) => [value.toFixed(5), 'Preço']}
                labelFormatter={(label) => `Horário: ${label}`}
              />
              <Legend />
              <Area
                type="monotone"
                dataKey="price"
                stroke="#1976d2"
                fill="#1976d2"
                fillOpacity={0.1}
                strokeWidth={2}
                name="Preço"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </Paper>

      <Alert severity="info" sx={{ mt: 2 }}>
        <Typography variant="body2">
          <strong>Nota:</strong> Os dados exibidos são simulados para demonstração. 
          Em produção, estes gráficos serão alimentados com dados reais da API do IQ Option.
        </Typography>
      </Alert>
    </Box>
  );
};

export default Charts;
