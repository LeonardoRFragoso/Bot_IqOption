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
import { useDashboard } from '../../hooks/useApi';
import TradingControlPanel from '../../components/TradingControlPanel/TradingControlPanel';
import OperationsTable from '../../components/OperationsTable/OperationsTable';
import MarketStatus from '../../components/MarketStatus/MarketStatus';
import StatCard from '../../components/StatCard/StatCard';
import PerformanceChart from '../../components/Charts/PerformanceChart';
import OperationsDistributionChart from '../../components/Charts/OperationsDistributionChart';
import StrategyPerformanceChart from '../../components/Charts/StrategyPerformanceChart';
import AssetAnalysisResults from '../../components/AssetAnalysisResults/AssetAnalysisResults';
import { useTradingRealtime } from '../../hooks/useRealtime';
import type { Operation } from '../../types/index';

const Dashboard: React.FC = () => {
  // Use hooks with optimized polling
  const { data: dashboardData, loading, error, refetch: refetchDashboard } = useDashboard();
  const { socket, connected } = useTradingRealtime();
  const [liveOps, setLiveOps] = useState<Map<string, Operation>>(new Map());
  const [opsRefreshSignal, setOpsRefreshSignal] = useState<number>(0);
  
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

  // Helper to convert WS payloads to Operation with safe defaults
  const toOperation = (obj: any): Operation | null => {
    try {
      if (!obj) return null;
      const id = String(obj.id ?? obj.order_id ?? obj.iq_order_id ?? '');
      if (!id) return null;
      const createdAt = obj.created_at || new Date().toISOString();
      const strategy = (currentSession as any)?.strategy || obj.strategy_used || '—';
      return {
        id: id as unknown as any,
        session: Number(obj.session) || (currentSession?.id ?? 0),
        asset: String(obj.asset || obj.symbol || '—'),
        direction: (obj.direction === 'call' || obj.direction === 'put') ? obj.direction : 'call',
        amount: Number(obj.amount ?? obj.value ?? 0),
        expiration_time: Number(obj.expiration_time ?? 0),
        entry_price: Number(obj.entry_price ?? 0),
        exit_price: typeof obj.exit_price === 'number' ? obj.exit_price : undefined,
        result: obj.result === 'win' || obj.result === 'loss' ? obj.result : undefined,
        profit_loss: typeof obj.profit_loss === 'number' ? obj.profit_loss : undefined,
        strategy_used: String(strategy),
        martingale_level: Number(obj.martingale_level ?? 0),
        soros_level: Number(obj.soros_level ?? 0),
        created_at: String(createdAt),
        closed_at: obj.closed_at ? String(obj.closed_at) : undefined,
      };
    } catch {
      return null;
    }
  };

  // Subscribe to WS events to keep KPIs and operations up-to-date
  useEffect(() => {
    const onStatus = (msg: any) => {
      const data = msg?.data || {};
      try {
        const session = data.active_session;
        if (session && typeof session === 'object') {
          setCurrentSession((prev) => ({ ...(prev as any), ...session }));
        }
        if (Array.isArray(data.recent_operations)) {
          setLiveOps((prev) => {
            const map = new Map(prev);
            for (const raw of data.recent_operations) {
              const op = toOperation(raw);
              if (op) map.set(String(op.id), op);
            }
            return map;
          });
        }
        // Ensure KPIs refresh while connected
        try { refetchDashboard(); } catch {}
      } catch {}
    };
    const onOpUpdate = (msg: any) => {
      const raw = msg?.data || msg;
      const op = toOperation(raw);
      if (!op) return;
      setLiveOps((prev) => {
        const map = new Map(prev);
        map.set(String(op.id), op);
        return map;
      });
      // KPI refresh on operation update (especially when finalized)
      try { refetchDashboard(); } catch {}
      setOpsRefreshSignal((s) => s + 1);
    };
    const onSessionUpdate = (msg: any) => {
      const data = msg?.data || {};
      if (data) {
        try { refetchDashboard(); } catch {}
        setOpsRefreshSignal((s) => s + 1);
      }
    };
    const onTradingUpdate = () => {
      try { refetchDashboard(); } catch {}
    };
    const onLogs = () => {
      // no-op for now
    };

    socket.on('status_update', onStatus);
    socket.on('operation_update', onOpUpdate);
    socket.on('session_update', onSessionUpdate);
    socket.on('trading_update', onTradingUpdate);
    socket.on('logs_update', onLogs);
    return () => {
      socket.off('status_update', onStatus);
      socket.off('operation_update', onOpUpdate);
      socket.off('session_update', onSessionUpdate);
      socket.off('trading_update', onTradingUpdate);
      socket.off('logs_update', onLogs);
    };
  }, [socket, refetchDashboard, currentSession]);

  // Fallback: adaptive short polling when WS is disconnected but session is running
  useEffect(() => {
    if (!currentSession || (currentSession as any).status !== 'RUNNING' || connected) return;
    const interval = setInterval(() => {
      try { refetchDashboard(); } catch {}
      setOpsRefreshSignal((s) => s + 1);
    }, 5000);
    return () => clearInterval(interval);
  }, [currentSession, connected, refetchDashboard]);

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
            <OperationsTable 
              sessionId={currentSession?.id} 
              maxRows={10}
              liveOperations={Array.from(liveOps.values())}
              refreshSignal={opsRefreshSignal}
            />

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
