import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { Box, Typography, Card, CardContent } from '@mui/material';
import { BarChart as BarChartIcon } from '@mui/icons-material';

interface StrategyData {
  name: string;
  winRate: number;
  operations: number;
  profit: number;
}

interface StrategyPerformanceChartProps {
  data?: StrategyData[];
  height?: number;
}

const StrategyPerformanceChart: React.FC<StrategyPerformanceChartProps> = ({ 
  data = [], 
  height = 300 
}) => {
  const chartData = data || [];

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
            <BarChartIcon sx={{ color: '#666', mr: 1, fontSize: 24 }} />
            <Typography variant="h6" sx={{ color: 'primary.main', fontWeight: 600 }}>
              Performance por Estratégia
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
              Nenhum dado de estratégia disponível
            </Typography>
            <Typography variant="body2" sx={{ color: '#888' }}>
              Execute operações para ver a performance das estratégias
            </Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  const getBarColor = (winRate: number) => {
    if (winRate >= 70) return '#00E676';
    if (winRate >= 60) return '#FFD700';
    return '#FF1744';
  };

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
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
          <Typography variant="body2" sx={{ color: '#FFFFFF' }}>
            Taxa de Acerto: {data.winRate}%
          </Typography>
          <Typography variant="body2" sx={{ color: '#FFFFFF' }}>
            Operações: {data.operations}
          </Typography>
          <Typography variant="body2" sx={{ color: '#00E676' }}>
            Lucro: ${data.profit.toFixed(2)}
          </Typography>
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
          <BarChartIcon sx={{ color: 'primary.main', mr: 1, fontSize: 24 }} />
          <Typography variant="h6" sx={{ color: 'primary.main', fontWeight: 600 }}>
            Performance por Estratégia
          </Typography>
        </Box>

        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid 
              strokeDasharray="3 3" 
              stroke="#333333" 
              horizontal={true}
              vertical={false}
            />
            <XAxis 
              dataKey="name" 
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#B0B0B0', fontSize: 12 }}
            />
            <YAxis 
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#B0B0B0', fontSize: 12 }}
              tickFormatter={(value) => `${value}%`}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar 
              dataKey="winRate" 
              radius={[4, 4, 0, 0]}
              strokeWidth={2}
              stroke="#1A1A1A"
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={getBarColor(entry.winRate)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>

        {/* Resumo das estratégias */}
        <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid #333333' }}>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
            {chartData.map((strategy, index) => (
              <Box 
                key={index}
                sx={{ 
                  flex: '1 1 150px',
                  textAlign: 'center',
                  p: 1,
                  borderRadius: 1,
                  backgroundColor: 'rgba(255, 255, 255, 0.02)',
                }}
              >
                <Typography variant="body2" sx={{ color: '#B0B0B0', mb: 0.5 }}>
                  {strategy.name}
                </Typography>
                <Typography 
                  variant="h6" 
                  sx={{ 
                    color: getBarColor(strategy.winRate),
                    fontWeight: 'bold',
                    fontSize: '1rem'
                  }}
                >
                  {strategy.winRate}%
                </Typography>
                <Typography variant="caption" sx={{ color: '#888' }}>
                  {strategy.operations} ops
                </Typography>
              </Box>
            ))}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

export default StrategyPerformanceChart;
