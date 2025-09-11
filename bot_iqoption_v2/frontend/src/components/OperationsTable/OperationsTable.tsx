import React, { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Chip,
  Box,
  CircularProgress,
  Alert,
  IconButton,
  Tooltip,
} from '@mui/material';
import { Refresh, Visibility } from '@mui/icons-material';
import { useOperations } from '../../hooks/useApi';
import type { Operation } from '../../types/index';

interface OperationsTableProps {
  sessionId?: number;
  title?: string;
  maxRows?: number;
}

const OperationsTable: React.FC<OperationsTableProps> = ({ 
  sessionId, 
  title = 'Operações', 
  maxRows 
}) => {
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(maxRows || 10);
  
  const { data: operations, loading, error, refetch } = useOperations(sessionId);

  const handleChangePage = (_event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'USD',
    }).format(value);
  };

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString('pt-BR');
  };

  const getResultColor = (result?: string) => {
    switch (result) {
      case 'win': return 'success';
      case 'loss': return 'error';
      default: return 'default';
    }
  };

  const getDirectionColor = (direction: string) => {
    return direction === 'call' ? 'success' : 'error';
  };

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', py: 4 }}>
            <CircularProgress />
            <Typography sx={{ ml: 2 }}>Carregando operações...</Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent>
          <Alert severity="error" action={
            <IconButton color="inherit" size="small" onClick={refetch}>
              <Refresh />
            </IconButton>
          }>
            {error}
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const displayOperations = Array.isArray(operations) ? operations : [];
  const paginatedOperations = maxRows 
    ? displayOperations.slice(0, maxRows)
    : displayOperations.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">{title}</Typography>
          <Tooltip title="Atualizar">
            <IconButton onClick={refetch} disabled={loading}>
              <Refresh />
            </IconButton>
          </Tooltip>
        </Box>

        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Ativo</TableCell>
                <TableCell>Direção</TableCell>
                <TableCell>Valor</TableCell>
                <TableCell>Estratégia</TableCell>
                <TableCell>Resultado</TableCell>
                <TableCell>P&L</TableCell>
                <TableCell>Martingale</TableCell>
                <TableCell>Horário</TableCell>
                <TableCell>Ações</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {paginatedOperations.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9} align="center">
                    <Typography color="textSecondary">
                      Nenhuma operação encontrada
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                paginatedOperations.map((operation: Operation) => (
                  <TableRow key={operation.id} hover>
                    <TableCell>
                      <Typography variant="body2" fontWeight="medium">
                        {operation.asset}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip 
                        label={operation.direction.toUpperCase()} 
                        color={getDirectionColor(operation.direction)}
                        size="small"
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {formatCurrency(operation.amount)}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="textSecondary">
                        {operation.strategy_used}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      {operation.result ? (
                        <Chip 
                          label={operation.result === 'win' ? 'WIN' : 'LOSS'} 
                          color={getResultColor(operation.result)}
                          size="small"
                        />
                      ) : (
                        <Chip label="PENDENTE" color="warning" size="small" />
                      )}
                    </TableCell>
                    <TableCell>
                      {operation.profit_loss !== undefined ? (
                        <Typography 
                          variant="body2"
                          color={operation.profit_loss >= 0 ? 'success.main' : 'error.main'}
                          fontWeight="medium"
                        >
                          {formatCurrency(operation.profit_loss)}
                        </Typography>
                      ) : (
                        <Typography variant="body2" color="textSecondary">
                          -
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="body2" color="textSecondary">
                          M{operation.martingale_level}
                        </Typography>
                        {operation.soros_level > 0 && (
                          <Typography variant="body2" color="textSecondary">
                            S{operation.soros_level}
                          </Typography>
                        )}
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="textSecondary">
                        {formatDateTime(operation.created_at)}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Tooltip title="Ver detalhes">
                        <IconButton size="small">
                          <Visibility fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>

        {!maxRows && displayOperations.length > 0 && (
          <TablePagination
            rowsPerPageOptions={[5, 10, 25, 50]}
            component="div"
            count={displayOperations.length}
            rowsPerPage={rowsPerPage}
            page={page}
            onPageChange={handleChangePage}
            onRowsPerPageChange={handleChangeRowsPerPage}
            labelRowsPerPage="Linhas por página:"
            labelDisplayedRows={({ from, to, count }) => 
              `${from}-${to} de ${count !== -1 ? count : `mais de ${to}`}`
            }
          />
        )}
      </CardContent>
    </Card>
  );
};

export default OperationsTable;
