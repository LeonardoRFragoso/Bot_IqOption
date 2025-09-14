import React, { useEffect, useState } from 'react';
import { Box, Card, CardContent, Typography, Alert, Table, TableBody, TableCell, TableHead, TableRow, TextField, Button, Stack, Paper } from '@mui/material';
import apiService from '../../services/api';
import type { AdminUserSubscriptionInfo, PaymentRecord } from '../../types';

const AdminBilling: React.FC = () => {
  const [users, setUsers] = useState<AdminUserSubscriptionInfo[]>([]);
  const [payments, setPayments] = useState<PaymentRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [grantDays, setGrantDays] = useState<number>(30);

  const loadData = async () => {
    setError(null);
    setLoading(true);
    try {
      const [u, p] = await Promise.all([
        apiService.getBillingAdminUsers(),
        apiService.getBillingAdminPayments(),
      ]);
      setUsers(u);
      setPayments(p);
    } catch (err: any) {
      const msg = err?.response?.status === 403 ? 'Não autorizado. Apenas o administrador pode acessar.' : 'Falha ao carregar dados de billing';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  const handleGrant = async (userId: number) => {
    try {
      await apiService.grantSubscriptionDays(userId, grantDays || 30);
      await loadData();
    } catch (err) {
      setError('Falha ao conceder dias de assinatura');
    }
  };

  if (loading) return <Box sx={{ p: 3 }}><Typography>Carregando...</Typography></Box>;

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>Admin • Billing</Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
        <Card sx={{ flex: 1 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>Usuários</Typography>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
              <Typography>Conceder dias:</Typography>
              <TextField type="number" size="small" value={grantDays} onChange={(e) => setGrantDays(parseInt(e.target.value || '0', 10))} sx={{ width: 100 }} />
              <Typography variant="body2" color="text.secondary">Selecione o usuário para aplicar</Typography>
            </Stack>
            <Paper sx={{ width: '100%', overflowX: 'auto' }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>ID</TableCell>
                    <TableCell>Email</TableCell>
                    <TableCell>Nome</TableCell>
                    <TableCell>Assinante</TableCell>
                    <TableCell>Ativo até</TableCell>
                    <TableCell>Ações</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {users.map(u => (
                    <TableRow key={u.id}>
                      <TableCell>{u.id}</TableCell>
                      <TableCell>{u.email}</TableCell>
                      <TableCell>{u.first_name} {u.last_name}</TableCell>
                      <TableCell>{u.is_subscribed ? 'Sim' : 'Não'}</TableCell>
                      <TableCell>{u.active_until ? new Date(u.active_until).toLocaleString() : '-'}</TableCell>
                      <TableCell>
                        <Button variant="outlined" size="small" onClick={() => handleGrant(u.id)}>Conceder</Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Paper>
          </CardContent>
        </Card>

        <Card sx={{ flex: 1 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>Pagamentos Recentes</Typography>
            <Paper sx={{ width: '100%', overflowX: 'auto' }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>ID</TableCell>
                    <TableCell>Usuário</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Valor</TableCell>
                    <TableCell>Moeda</TableCell>
                    <TableCell>Pago em</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {payments.map(p => (
                    <TableRow key={p.id}>
                      <TableCell>{p.id}</TableCell>
                      <TableCell>{p.user_email}</TableCell>
                      <TableCell>{p.status}</TableCell>
                      <TableCell>{p.amount.toFixed(2)}</TableCell>
                      <TableCell>{p.currency}</TableCell>
                      <TableCell>{p.paid_at ? new Date(p.paid_at).toLocaleString() : '-'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Paper>
          </CardContent>
        </Card>
      </Stack>
    </Box>
  );
};

export default AdminBilling;
