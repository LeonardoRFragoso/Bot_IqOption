import React, { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Alert,
  IconButton,
  Tooltip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  List,
  ListItem,
  ListItemText,
  CircularProgress,
} from '@mui/material';
import { Refresh } from '@mui/icons-material';
import { useTradingLogs } from '../../hooks/useApi';
import type { TradingLog } from '../../types/index';

interface LogsViewerProps {
  sessionId?: number;
  maxLogs?: number;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

const LogsViewer: React.FC<LogsViewerProps> = ({ 
  sessionId, 
  maxLogs = 50,
  autoRefresh = true
}) => {
  // refreshInterval is now handled by the useApi hook internally
  const [levelFilter, setLevelFilter] = useState<string>('ALL');
  const { data: logs, loading, error, refetch } = useTradingLogs(sessionId);

  // Remove manual polling since useApi now handles it automatically
  // useEffect(() => {
  //   if (autoRefresh) {
  //     const interval = setInterval(refetch, refreshInterval);
  //     return () => clearInterval(interval);
  //   }
  // }, [autoRefresh, refreshInterval, refetch]);

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString('pt-BR');
  };

  const getSeverityColor = (level: string) => {
    switch (level.toLowerCase()) {
      case 'error': return 'error';
      case 'warning': return 'warning';
      case 'info': return 'info';
      case 'debug': return 'default';
      default: return 'default';
    }
  };

  const getSeverityIcon = (level: string) => {
    switch (level.toLowerCase()) {
      case 'error': return '🔴';
      case 'warning': return '🟡';
      case 'info': return '🔵';
      case 'debug': return '⚪';
      default: return '⚪';
    }
  };

  const filteredLogs = logs?.filter(log => 
    levelFilter === 'ALL' || log.level === levelFilter
  ).slice(0, maxLogs) || [];

  if (loading && !logs) {
    return (
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', py: 4 }}>
            <CircularProgress />
            <Typography sx={{ ml: 2 }}>Carregando logs...</Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">
            Logs do Sistema
            {sessionId && ` - Sessão ${sessionId}`}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Nível</InputLabel>
              <Select
                value={levelFilter}
                label="Nível"
                onChange={(e) => setLevelFilter(e.target.value)}
              >
                <MenuItem value="ALL">Todos</MenuItem>
                <MenuItem value="ERROR">Error</MenuItem>
                <MenuItem value="WARNING">Warning</MenuItem>
                <MenuItem value="INFO">Info</MenuItem>
                <MenuItem value="DEBUG">Debug</MenuItem>
              </Select>
            </FormControl>
            <Tooltip title="Atualizar">
              <span>
                <IconButton onClick={refetch} disabled={loading}>
                  {loading ? <CircularProgress size={20} /> : <Refresh />}
                </IconButton>
              </span>
            </Tooltip>
          </Box>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Box sx={{ maxHeight: 400, overflow: 'auto' }}>
          {filteredLogs.length === 0 ? (
            <Typography color="textSecondary" align="center" sx={{ py: 4 }}>
              Nenhum log encontrado
            </Typography>
          ) : (
            <List dense>
              {filteredLogs.map((log: TradingLog) => (
                <ListItem 
                  key={log.id} 
                  sx={{ 
                    border: '1px solid',
                    borderColor: 'divider',
                    borderRadius: 1,
                    mb: 1,
                    bgcolor: log.level === 'ERROR' ? 'error.light' : 
                             log.level === 'WARNING' ? 'warning.light' : 
                             'background.paper'
                  }}
                >
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                        <Typography variant="body2" component="span">
                          {getSeverityIcon(log.level)}
                        </Typography>
                        <Chip 
                          label={log.level}
                          color={getSeverityColor(log.level)}
                          size="small"
                        />
                        <Typography variant="caption" color="textSecondary" component="span">
                          {formatDateTime(log.created_at)}
                        </Typography>
                      </Box>
                    }
                    secondary={
                      <Box component="div">
                        <Typography variant="body2" component="div" sx={{ mb: 1 }}>
                          {log.message}
                        </Typography>
                        {log.details && (
                          <Typography
                            component="pre"
                            variant="body2"
                            sx={{ 
                              bgcolor: 'grey.100', 
                              p: 1, 
                              borderRadius: 1,
                              fontSize: '0.75rem',
                              overflow: 'auto',
                              maxHeight: 100,
                              display: 'block',
                              fontFamily: 'monospace',
                              whiteSpace: 'pre-wrap'
                            }}
                          >
                            {String(log.details)}
                          </Typography>
                        )}
                      </Box>
                    }
                    secondaryTypographyProps={{ component: 'div' }}
                  />
                </ListItem>
              ))}
            </List>
          )}
        </Box>

        {logs && logs.length > 0 && (
          <Box sx={{ mt: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="body2" color="textSecondary">
              Mostrando {filteredLogs.length} de {logs.length} logs
            </Typography>
            {autoRefresh && (
              <Chip 
                label="Auto-refresh ativo"
                color="success"
                size="small"
                variant="outlined"
              />
            )}
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default LogsViewer;
