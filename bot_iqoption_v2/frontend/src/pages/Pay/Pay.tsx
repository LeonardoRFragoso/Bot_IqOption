import React, { useEffect, useState } from 'react';
import { Box, Card, CardContent, Typography, Button, Alert, CircularProgress } from '@mui/material';
import { useNavigate, useLocation } from 'react-router-dom';
import apiService from '../../services/api';
import type { SubscriptionStatus } from '../../types/index';

const MP_SCRIPT_SRC = 'https://www.mercadopago.com.br/integrations/v1/web-payment-checkout.js';

const Pay: React.FC = () => {
  const [status, setStatus] = useState<SubscriptionStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [verifying, setVerifying] = useState<boolean>(false);
  const [verifyMsg, setVerifyMsg] = useState<string>('');
  const navigate = useNavigate();
  const location = useLocation();

  const preferenceId = status?.preference_id;
  const initPoint = status?.init_point;

  const loadStatus = async () => {
    try {
      setLoading(true);
      const s = await apiService.getSubscriptionStatus();
      setStatus(s);
      if (s.is_subscribed) {
        navigate('/dashboard');
      }
    } catch (err) {
      console.error('Failed to load subscription status', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Handle return from Mercado Pago: verify payment if parameters are present
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.size === 0) return;

    const hasRelevant = ['status', 'payment_id', 'collection_id', 'preference_id', 'merchant_order_id']
      .some((k) => params.has(k));
    if (!hasRelevant) return;

    const payload: Record<string, string | null> = {
      status: params.get('status'),
      payment_id: params.get('payment_id'),
      collection_id: params.get('collection_id'),
      preference_id: params.get('preference_id'),
      merchant_order_id: params.get('merchant_order_id'),
    };

    setVerifying(true);
    setVerifyMsg('Verificando pagamento...');
    apiService
      .verifyPaymentReturn(payload)
      .then((res) => {
        if (res.success) {
          if (res.activated) {
            setVerifyMsg('Pagamento aprovado! Assinatura ativada. Redirecionando...');
            // Refresh status and go to dashboard
            void loadStatus();
            setTimeout(() => navigate('/dashboard'), 1200);
          } else {
            setVerifyMsg(`Status do pagamento: ${res.status ?? 'desconhecido'}`);
          }
        } else {
          setVerifyMsg(`Falha na verificação: ${res.error ?? 'erro desconhecido'}`);
        }
      })
      .catch((err) => {
        console.error('verifyPaymentReturn failed', err);
        setVerifyMsg('Falha ao verificar pagamento.');
      })
      .finally(() => setVerifying(false));
  }, [location.search, navigate]);

  // Inject MP script for button when we have a preference id
  useEffect(() => {
    if (!preferenceId) return;

    // Remove any previous script/button
    const prev = document.getElementById('mp-script');
    if (prev && prev.parentElement) prev.parentElement.removeChild(prev);
    const prevBtn = document.getElementById('mp-button');
    if (prevBtn && prevBtn.parentElement) prevBtn.parentElement.removeChild(prevBtn);

    // Create placeholder for the button
    const btn = document.createElement('div');
    btn.id = 'mp-button';
    const container = document.getElementById('mp-button-container');
    if (container) container.appendChild(btn);

    // Load script
    const script = document.createElement('script');
    script.id = 'mp-script';
    script.src = MP_SCRIPT_SRC;
    script.setAttribute('data-preference-id', preferenceId);
    script.setAttribute('data-source', 'button');
    // script.onload = () => {}
    document.body.appendChild(script);
  }, [preferenceId]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', p: 2 }}>
      <Card sx={{ maxWidth: 720, width: '100%' }}>
        <CardContent>
          <Typography variant="h4" gutterBottom>
            Assinatura da Plataforma
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
            Para utilizar o bot e acessar o dashboard, é necessário ter uma assinatura ativa. O pagamento é realizado via botão oficial do Mercado Pago.
          </Typography>

          {status?.is_subscribed ? (
            <Alert severity="success" sx={{ mb: 2 }}>
              Sua assinatura está ativa. Você será redirecionado para o dashboard.
            </Alert>
          ) : (
            <Alert severity="warning" sx={{ mb: 2 }}>
              Assinatura inativa. Conclua o pagamento para liberar o acesso.
            </Alert>
          )}

          {verifying && (
            <Alert severity="info" sx={{ mb: 2 }}>
              {verifyMsg || 'Verificando pagamento...'}
            </Alert>
          )}
          {!verifying && verifyMsg && (
            <Alert severity="info" sx={{ mb: 2 }}>
              {verifyMsg}
            </Alert>
          )}

          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 3 }}>
            {/* Mercado Pago Button */}
            <Box id="mp-button-container" />
            {/* Fallback: abrir checkout diretamente (API-based) */}
            {initPoint && (
              <Button variant="contained" color="primary" href={initPoint} target="_blank" rel="noopener noreferrer">
                Abrir Checkout
              </Button>
            )}
            {preferenceId && (
              <Button
                variant="outlined"
                color="secondary"
                disabled={verifying}
                onClick={() => {
                  setVerifying(true);
                  setVerifyMsg('Verificando pagamento atual...');
                  apiService
                    .verifyPaymentReturn({ preference_id: preferenceId })
                    .then((res) => {
                      if (res.success) {
                        if (res.activated) {
                          setVerifyMsg('Pagamento aprovado! Assinatura ativada. Redirecionando...');
                          void loadStatus();
                          setTimeout(() => navigate('/dashboard'), 1200);
                        } else {
                          setVerifyMsg(`Status do pagamento: ${res.status ?? 'desconhecido'}`);
                        }
                      } else {
                        setVerifyMsg(`Falha na verificação: ${res.error ?? 'erro desconhecido'}`);
                      }
                    })
                    .catch((err) => {
                      console.error('verifyPaymentReturn failed', err);
                      setVerifyMsg('Falha ao verificar pagamento.');
                    })
                    .finally(() => setVerifying(false));
                }}
              >
                Verificar Pagamento
              </Button>
            )}
            {!preferenceId && (
              <Typography variant="body2" color="text.secondary">
                Botão do Mercado Pago indisponível. Verifique se o servidor está com MERCADOPAGO_ACCESS_TOKEN configurado e tente atualizar o status.
              </Typography>
            )}
          </Box>

          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button variant="outlined" onClick={() => loadStatus()} disabled={loading}>
              Atualizar Status
            </Button>
            <Button variant="text" onClick={() => navigate('/dashboard')} disabled={!status?.is_subscribed}>
              Ir para o Dashboard
            </Button>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
};

export default Pay;
