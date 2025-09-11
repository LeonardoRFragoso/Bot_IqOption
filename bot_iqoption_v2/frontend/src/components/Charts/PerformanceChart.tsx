import React from 'react';
import {
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts';
import { Box, Typography, Card, CardContent } from '@mui/material';
import { TrendingUp } from '@mui/icons-material';

interface PerformanceDataPoint {
  time: string;
  pnl: number;
  balance: number;
  operations: number;
}

interface PerformanceChartProps {
  data?: PerformanceDataPoint[];
  height?: number;
  showBalance?: boolean;
}

const PerformanceChart: React.FC<PerformanceChartProps> = ({ 
  data = [], 
  height = 300,
  showBalance = true 
}) => {
  const chartData = data || [];
  const currentPnL = chartData.length > 0 ? chartData[chartData.length - 1]?.pnl || 0 : 0;
  const isPositive = currentPnL >= 0;

  // Se não há dados, mostrar estado vazio
  if (!chartData || chartData.length === 0) {
    return (
      <Card sx={{ 
        background: 'linear-gradient(135deg, #1A1A1A 0%, #2A2A2A 100%)',
        border: '1px solid #333333',
        borderRadius: '16px',
      }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <TrendingUp sx={{ color: '#666', mr: 1, fontSize: 24 }} />
            <Typography variant="h6" sx={{ color: 'primary.main', fontWeight: 600 }}>
              Performance P&L
            </Typography>
          </Box>
          <Box sx={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center', 
            height: height,
            flexDirection: 'column',
            gap: 2
          }}>
            <Typography variant="h6" sx={{ color: '#666' }}>
              Nenhum dado de performance disponível
            </Typography>
            <Typography variant="body2" sx={{ color: '#888' }}>
              Inicie uma sessão de trading para ver os gráficos
            </Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <Box
          sx={{
            backgroundColor: 'rgba(26, 26, 26, 0.95)',
            border: '1px solid #333',
            borderRadius: 1,
            p: 1.5,
            backdropFilter: 'blur(10px)',
          }}
        >
          <Typography variant="body2" sx={{ color: '#FFD700', fontWeight: 'bold' }}>
            {label}
          </Typography>
          {payload.map((entry: any, index: number) => (
            <Typography
              key={index}
              variant="body2"
              sx={{
                color: entry.dataKey === 'pnl' 
                  ? (entry.value >= 0 ? '#00E676' : '#FF1744')
                  : '#FFFFFF'
              }}
            >
              {entry.dataKey === 'pnl' ? 'P&L: ' : 'Saldo: '}
              ${entry.value.toFixed(2)}
            </Typography>
          ))}
        </Box>
      );
    }
    return null;
  };

  return (
    <Card sx={{ 
      background: 'linear-gradient(135deg, #1A1A1A 0%, #2A2A2A 100%)',
      border: '1px solid #333333',
      borderRadius: '16px',
    }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <TrendingUp sx={{ 
            color: isPositive ? '#00E676' : '#FF1744', 
            mr: 1,
            fontSize: 24 
          }} />
          <Typography variant="h6" sx={{ color: 'primary.main', fontWeight: 600 }}>
            Performance P&L
          </Typography>
          <Box sx={{ ml: 'auto', textAlign: 'right' }}>
            <Typography variant="body2" sx={{ color: '#B0B0B0' }}>
              Hoje
            </Typography>
            <Typography 
              variant="h6" 
              sx={{ 
                color: isPositive ? '#00E676' : '#FF1744',
                fontWeight: 'bold'
              }}
            >
              {isPositive ? '+' : ''}${currentPnL.toFixed(2)}
            </Typography>
          </Box>
        </Box>

        <ResponsiveContainer width="100%" height={height}>
          <AreaChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
            <defs>
              <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
                <stop 
                  offset="5%" 
                  stopColor={isPositive ? '#00E676' : '#FF1744'} 
                  stopOpacity={0.3}
                />
                <stop 
                  offset="95%" 
                  stopColor={isPositive ? '#00E676' : '#FF1744'} 
                  stopOpacity={0.05}
                />
              </linearGradient>
            </defs>
            <CartesianGrid 
              strokeDasharray="3 3" 
              stroke="#333333" 
              horizontal={true}
              vertical={false}
            />
            <XAxis 
              dataKey="time" 
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#B0B0B0', fontSize: 12 }}
            />
            <YAxis 
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#B0B0B0', fontSize: 12 }}
              tickFormatter={(value) => `$${value}`}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="pnl"
              stroke={isPositive ? '#00E676' : '#FF1744'}
              strokeWidth={3}
              fill="url(#pnlGradient)"
              dot={{ 
                fill: isPositive ? '#00E676' : '#FF1744', 
                strokeWidth: 2, 
                stroke: '#1A1A1A',
                r: 4 
              }}
              activeDot={{ 
                r: 6, 
                fill: isPositive ? '#00E676' : '#FF1744',
                stroke: '#1A1A1A',
                strokeWidth: 2
              }}
            />
            {showBalance && (
              <Line
                type="monotone"
                dataKey="balance"
                stroke="#FFD700"
                strokeWidth={2}
                strokeDasharray="5 5"
                dot={false}
                activeDot={{ r: 4, fill: '#FFD700' }}
              />
            )}
          </AreaChart>
        </ResponsiveContainer>

        <Box sx={{ display: 'flex', justifyContent: 'center', gap: 3, mt: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Box sx={{ 
              width: 12, 
              height: 3, 
              backgroundColor: isPositive ? '#00E676' : '#FF1744',
              mr: 1,
              borderRadius: 1
            }} />
            <Typography variant="caption" sx={{ color: '#B0B0B0' }}>
              P&L
            </Typography>
          </Box>
          {showBalance && (
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Box sx={{ 
                width: 12, 
                height: 3, 
                backgroundColor: '#FFD700',
                mr: 1,
                borderRadius: 1,
                backgroundImage: 'repeating-linear-gradient(45deg, transparent, transparent 2px, rgba(0,0,0,0.3) 2px, rgba(0,0,0,0.3) 4px)'
              }} />
              <Typography variant="caption" sx={{ color: '#B0B0B0' }}>
                Saldo
              </Typography>
            </Box>
          )}
        </Box>
      </CardContent>
    </Card>
  );
};

export default PerformanceChart;
