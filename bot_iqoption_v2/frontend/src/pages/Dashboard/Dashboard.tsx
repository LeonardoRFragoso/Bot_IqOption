import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Alert,
} from '@mui/material';
import {
  TrendingUp,
  AccountBalance,
  Assessment,
  ShowChart,
} from '@mui/icons-material';
import { motion } from 'framer-motion';
import type { TradingSession } from '../../types/index';
import { useDashboard, useOperations } from '../../hooks/useApi';
import TradingControlPanel from '../../components/TradingControlPanel/TradingControlPanel';
import OperationsTable from '../../components/OperationsTable/OperationsTable';
import MarketStatus from '../../components/MarketStatus/MarketStatus';
import StatCard from '../../components/StatCard/StatCard';
import PerformanceChart from '../../components/Charts/PerformanceChart';
import OperationsDistributionChart from '../../components/Charts/OperationsDistributionChart';
import StrategyPerformanceChart from '../../components/Charts/StrategyPerformanceChart';
import AssetAnalysisResults from '../../components/AssetAnalysisResults/AssetAnalysisResults';

const Dashboard: React.FC = () => {
  // Use hooks with optimized polling
  const { data: dashboardData, loading, error } = useDashboard();
  const { data: operations } = useOperations();
  
  // Use operations and logs data to prevent lint warnings
  console.debug('Operations data:', operations?.length || 0, 'items');
  const [currentSession, setCurrentSession] = useState<TradingSession | null>(null);
  const [selectedAsset, setSelectedAsset] = useState<string>('');

  // Update current session when dashboard data changes
  useEffect(() => {
    if (dashboardData && (dashboardData as any).current_session) {
      setCurrentSession((dashboardData as any).current_session);
    } else {
      setCurrentSession(null);
    }
  }, [dashboardData]);

  const handleSessionChange = (session: TradingSession | null) => {
    setCurrentSession(session);
  };

  // Função removida pois não está sendo usada - StatCard já formata valores

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1
      }
    }
  };

  const itemVariants = {
    hidden: { y: 20, opacity: 0 },
    visible: {
      y: 0,
      opacity: 1,
      transition: {
        duration: 0.5
      }
    }
  };


  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
        >
          <ShowChart sx={{ fontSize: 48, color: 'primary.main' }} />
        </motion.div>
        <Typography sx={{ ml: 2, color: 'text.secondary' }}>Carregando dashboard...</Typography>
      </Box>
    );
  }

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      <Box sx={{ flexGrow: 1, p: { xs: 2, md: 3 } }}>
        {error && (
          <motion.div variants={itemVariants}>
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          </motion.div>
        )}

        {/* Market Status */}
        <motion.div variants={itemVariants}>
          <MarketStatus />
        </motion.div>

        {/* Trading Control Panel */}
        <motion.div variants={itemVariants}>
          <Box sx={{ mb: 3 }}>
            <TradingControlPanel onSessionChange={handleSessionChange} />
          </Box>
        </motion.div>

        {/* Statistics Cards */}
        <motion.div variants={itemVariants}>
          <Box sx={{ 
            display: 'grid', 
            gridTemplateColumns: { 
              xs: '1fr', 
              sm: 'repeat(2, 1fr)', 
              lg: 'repeat(4, 1fr)' 
            },
            gap: 3, 
            mb: 3 
          }}>
            <StatCard
              title="Saldo Total"
              value={(dashboardData as any)?.balance || 0}
              icon={AccountBalance}
              color="#00E676"
              prefix="$"
              decimals={2}
              isLoading={loading}
            />
            <StatCard
              title="P&L Hoje"
              value={(dashboardData as any)?.pnl_today || 0}
              icon={TrendingUp}
              color={(dashboardData as any)?.pnl_today >= 0 ? '#00E676' : '#FF1744'}
              prefix="$"
              decimals={2}
              isLoading={loading}
            />
            <StatCard
              title="Total Operações"
              value={(dashboardData as any)?.total_operations || 0}
              icon={Assessment}
              color="#2196F3"
              isLoading={loading}
            />
            <StatCard
              title="Taxa de Acerto"
              value={(dashboardData as any)?.win_rate || 0}
              icon={Assessment}
              color="#FFD700"
              suffix="%"
              decimals={1}
              isLoading={loading}
            />
          </Box>
        </motion.div>

        {/* Asset Analysis Results - Moved to top priority position */}
        <motion.div variants={itemVariants}>
          <AssetAnalysisResults 
            onAssetSelect={setSelectedAsset}
            selectedAsset={selectedAsset}
          />
        </motion.div>

        {/* Charts Section */}
        <motion.div variants={itemVariants}>
          <Box sx={{ 
            display: 'grid', 
            gridTemplateColumns: { xs: '1fr', lg: '2fr 1fr' },
            gap: 3, 
            mb: 3 
          }}>
            <PerformanceChart 
              data={(dashboardData as any)?.performance_data}
              height={350} 
            />
            <OperationsDistributionChart 
              wins={(dashboardData as any)?.wins || 0}
              losses={(dashboardData as any)?.losses || 0}
              height={350}
            />
          </Box>
        </motion.div>

        {/* Operações Recentes e Performance por Estratégia (lado a lado) */}
        <motion.div variants={itemVariants}>
          <Box sx={{ 
            display: 'grid', 
            gridTemplateColumns: { xs: '1fr', lg: '2fr 1fr' },
            gap: 3 
          }}>
            {/* OperationsTable already provides its own Card and header */}
            <OperationsTable sessionId={currentSession?.id} maxRows={10} />

            {/* StrategyPerformanceChart already provides its own Card and header */}
            <StrategyPerformanceChart 
              data={(dashboardData as any)?.strategy_performance}
              height={300}
            />
          </Box>
        </motion.div>
      </Box>
    </motion.div>
  );
};


export default Dashboard;
