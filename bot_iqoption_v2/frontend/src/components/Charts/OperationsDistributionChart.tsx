import React from 'react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { Box, Typography, Card, CardContent } from '@mui/material';
import { DonutLarge } from '@mui/icons-material';

interface OperationData {
  name: string;
  value: number;
  color: string;
}

interface OperationsDistributionChartProps {
  wins?: number;
  losses?: number;
  height?: number;
}

const OperationsDistributionChart: React.FC<OperationsDistributionChartProps> = ({ 
  wins = 0, 
  losses = 0, 
  height = 250 
}) => {
  const total = wins + losses;
  const winRate = total > 0 ? ((wins / total) * 100) : 0;

  // Se não há dados, mostrar estado vazio
  if (total === 0) {
    return (
      <Card sx={{ 
        background: 'linear-gradient(135deg, #1A1A1A 0%, #2A2A2A 100%)',
        border: '1px solid #333333',
        borderRadius: '16px',
      }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <DonutLarge sx={{ color: '#666', mr: 1, fontSize: 24 }} />
            <Typography variant="h6" sx={{ color: 'primary.main', fontWeight: 600 }}>
              Distribuição de Operações
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
              Nenhuma operação realizada
            </Typography>
            <Typography variant="body2" sx={{ color: '#888' }}>
              Execute operações para ver a distribuição
            </Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  const data: OperationData[] = [
    {
      name: 'Vitórias',
      value: wins,
      color: '#00E676',
    },
    {
      name: 'Derrotas',
      value: losses,
      color: '#FF1744',
    },
  ];

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0];
      const percentage = total > 0 ? ((data.value / total) * 100).toFixed(1) : 0;
      
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
          <Typography variant="body2" sx={{ color: data.payload.color, fontWeight: 'bold' }}>
            {data.name}
          </Typography>
          <Typography variant="body2" sx={{ color: '#FFFFFF' }}>
            {data.value} operações ({percentage}%)
          </Typography>
        </Box>
      );
    }
    return null;
  };

  const CustomLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }: any) => {
    const RADIAN = Math.PI / 180;
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);

    if (percent < 0.05) return null; // Não mostrar label se muito pequeno

    return (
      <text 
        x={x} 
        y={y} 
        fill="white" 
        textAnchor={x > cx ? 'start' : 'end'} 
        dominantBaseline="central"
        fontSize="12"
        fontWeight="bold"
      >
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    );
  };

  return (
    <Card sx={{ 
      background: 'linear-gradient(135deg, #1A1A1A 0%, #2A2A2A 100%)',
      border: '1px solid #333333',
      borderRadius: '16px',
    }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <DonutLarge sx={{ color: 'primary.main', mr: 1, fontSize: 24 }} />
          <Typography variant="h6" sx={{ color: 'primary.main', fontWeight: 600 }}>
            Distribuição de Operações
          </Typography>
        </Box>

        <Box sx={{ position: 'relative' }}>
          <ResponsiveContainer width="100%" height={height}>
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={CustomLabel}
                outerRadius={80}
                innerRadius={40}
                fill="#8884d8"
                dataKey="value"
                strokeWidth={2}
                stroke="#1A1A1A"
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
            </PieChart>
          </ResponsiveContainer>

          {/* Centro do donut com estatísticas */}
          <Box
            sx={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              textAlign: 'center',
              pointerEvents: 'none',
            }}
          >
            <Typography 
              variant="h4" 
              sx={{ 
                color: winRate >= 70 ? '#00E676' : winRate >= 50 ? '#FFD700' : '#FF1744',
                fontWeight: 'bold',
                lineHeight: 1
              }}
            >
              {winRate.toFixed(0)}%
            </Typography>
            <Typography variant="caption" sx={{ color: '#B0B0B0' }}>
              Taxa de Acerto
            </Typography>
          </Box>
        </Box>

        {/* Legenda personalizada */}
        <Box sx={{ display: 'flex', justifyContent: 'center', gap: 3, mt: 2 }}>
          {data.map((entry, index) => (
            <Box key={index} sx={{ display: 'flex', alignItems: 'center' }}>
              <Box sx={{ 
                width: 12, 
                height: 12, 
                backgroundColor: entry.color,
                mr: 1,
                borderRadius: '50%'
              }} />
              <Typography variant="body2" sx={{ color: '#B0B0B0' }}>
                {entry.name}: {entry.value}
              </Typography>
            </Box>
          ))}
        </Box>

        {/* Estatísticas adicionais */}
        <Box sx={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          mt: 2, 
          pt: 2, 
          borderTop: '1px solid #333333' 
        }}>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="h6" sx={{ color: '#00E676', fontWeight: 'bold' }}>
              {wins}
            </Typography>
            <Typography variant="caption" sx={{ color: '#B0B0B0' }}>
              Vitórias
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="h6" sx={{ color: '#FF1744', fontWeight: 'bold' }}>
              {losses}
            </Typography>
            <Typography variant="caption" sx={{ color: '#B0B0B0' }}>
              Derrotas
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="h6" sx={{ color: '#FFFFFF', fontWeight: 'bold' }}>
              {total}
            </Typography>
            <Typography variant="caption" sx={{ color: '#B0B0B0' }}>
              Total
            </Typography>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

export default OperationsDistributionChart;
