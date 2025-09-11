import React from 'react';
import { Card, CardContent, Box, Typography } from '@mui/material';
import type { SvgIconComponent } from '@mui/icons-material';
import CountUp from 'react-countup';
import { motion } from 'framer-motion';

interface StatCardProps {
  title: string;
  value: number;
  icon: SvgIconComponent;
  color: string;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  isLoading?: boolean;
}

const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  icon: Icon,
  color,
  prefix = '',
  suffix = '',
  decimals = 0,
  trend,
  isLoading = false,
}) => {
  // Função removida pois não está sendo usada - CountUp já formata os valores

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      whileHover={{ 
        scale: 1.02,
        transition: { duration: 0.2 }
      }}
    >
      <Card sx={{ 
        background: 'linear-gradient(135deg, #1A1A1A 0%, #2A2A2A 100%)',
        border: '1px solid #333333',
        borderRadius: '16px',
        position: 'relative',
        overflow: 'hidden',
        '&::before': {
          content: '""',
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: '4px',
          background: `linear-gradient(90deg, ${color}, ${color}80)`,
        },
        '&:hover': {
          borderColor: color,
          boxShadow: `0 8px 32px ${color}20`,
        },
        transition: 'all 0.3s ease-in-out',
      }}>
        <CardContent sx={{ p: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
            <Box sx={{ flex: 1 }}>
              <Typography 
                color="text.secondary" 
                gutterBottom 
                variant="body2"
                sx={{ 
                  fontWeight: 500,
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                  fontSize: '0.75rem'
                }}
              >
                {title}
              </Typography>
              
              <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, mb: 1 }}>
                {isLoading ? (
                  <Box sx={{ 
                    width: '80px', 
                    height: '32px', 
                    backgroundColor: '#333',
                    borderRadius: 1,
                    animation: 'pulse 1.5s ease-in-out infinite',
                    '@keyframes pulse': {
                      '0%': { opacity: 1 },
                      '50%': { opacity: 0.5 },
                      '100%': { opacity: 1 },
                    }
                  }} />
                ) : (
                  <Typography 
                    variant="h4" 
                    sx={{ 
                      color: color,
                      fontWeight: 700,
                      lineHeight: 1,
                      fontSize: { xs: '1.5rem', sm: '2rem' }
                    }}
                  >
                    {prefix === '$' ? (
                      <CountUp
                        end={value}
                        duration={2}
                        decimals={decimals}
                        prefix={prefix}
                        preserveValue
                      />
                    ) : (
                      <>
                        {prefix}
                        <CountUp
                          end={value}
                          duration={2}
                          decimals={decimals}
                          preserveValue
                        />
                        {suffix}
                      </>
                    )}
                  </Typography>
                )}
              </Box>

              {trend && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Box
                    component="span"
                    sx={{
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      color: trend.isPositive ? '#00E676' : '#FF1744',
                      display: 'flex',
                      alignItems: 'center',
                    }}
                  >
                    {trend.isPositive ? '↗' : '↘'} {Math.abs(trend.value).toFixed(1)}%
                  </Box>
                  <Typography variant="caption" sx={{ color: '#B0B0B0' }}>
                    vs. período anterior
                  </Typography>
                </Box>
              )}
            </Box>

            <Box sx={{ 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center',
              width: 56,
              height: 56,
              borderRadius: '50%',
              background: `linear-gradient(135deg, ${color}20, ${color}10)`,
              border: `2px solid ${color}30`,
            }}>
              <Icon sx={{ 
                color: color, 
                fontSize: 28,
              }} />
            </Box>
          </Box>
        </CardContent>
      </Card>
    </motion.div>
  );
};

export default StatCard;
