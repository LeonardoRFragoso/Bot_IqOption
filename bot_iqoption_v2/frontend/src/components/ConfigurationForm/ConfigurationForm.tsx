import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  TextField,
  Switch,
  FormControlLabel,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Button,
  Alert,
  Divider,
  Stack,
  CircularProgress,
} from '@mui/material';
import type { SelectChangeEvent } from '@mui/material/Select';
import { Save, Refresh } from '@mui/icons-material';
import { useTradingConfig } from '../../hooks/useApi';
import type { TradingConfiguration } from '../../types/index';

const ConfigurationForm: React.FC = () => {
  const { config, loading, error, updateConfig, refetch } = useTradingConfig();
  const [formData, setFormData] = useState<Partial<TradingConfiguration>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    if (config) {
      setFormData(config);
    }
  }, [config]);

  const handleSelectChange = (field: keyof TradingConfiguration) => (
    event: SelectChangeEvent<string>
  ) => {
    setFormData(prev => ({
      ...prev,
      [field]: event.target.value
    }));
  };

  const handleTextFieldChange = (field: keyof TradingConfiguration) => (
    event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const target = event.target;
    const value = target.type === 'number' ? parseFloat(target.value) || 0 : target.value;
    
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSwitchChange = (field: keyof TradingConfiguration) => (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    setFormData(prev => ({
      ...prev,
      [field]: event.target.checked
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);

    try {
      await updateConfig(formData);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: unknown) {
      setSaveError((err as Error).message || 'Erro ao salvar configuração');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (config) {
      setFormData(config);
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', py: 4 }}>
            <CircularProgress />
            <Typography sx={{ ml: 2 }}>Carregando configurações...</Typography>
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
            <Button color="inherit" size="small" onClick={refetch}>
              Tentar Novamente
            </Button>
          }>
            {error}
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Configurações de Trading
        </Typography>
        <Typography variant="body2" color="textSecondary" gutterBottom>
          Configure os parâmetros baseados no arquivo config.txt do sistema legado
        </Typography>

        {saveSuccess && (
          <Alert severity="success" sx={{ mb: 2 }}>
            Configurações salvas com sucesso!
          </Alert>
        )}

        {saveError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {saveError}
          </Alert>
        )}

        <Box component="form" onSubmit={handleSubmit}>
          {/* Seção [AJUSTES] */}
          <Typography variant="h6" sx={{ mt: 3, mb: 2 }}>
            Ajustes Gerais
          </Typography>
          
          <Stack spacing={3}>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
              <Box sx={{ flex: '1 1 300px', minWidth: '250px' }}>
                <FormControl fullWidth>
                  <InputLabel>Tipo de Operação</InputLabel>
                  <Select
                    value={formData.tipo || 'automatico'}
                    label="Tipo de Operação"
                    onChange={handleSelectChange('tipo')}
                  >
                    <MenuItem value="automatico">Automático</MenuItem>
                    <MenuItem value="manual">Manual</MenuItem>
                  </Select>
                </FormControl>
              </Box>

              <Box sx={{ flex: '1 1 300px', minWidth: '250px' }}>
                <TextField
                  fullWidth
                  label="Valor de Entrada"
                  type="number"
                  value={formData.valor_entrada || 3.0}
                  onChange={handleTextFieldChange('valor_entrada')}
                  inputProps={{ step: 0.1, min: 0.1 }}
                  helperText="Valor em USD para cada operação"
                />
              </Box>
            </Box>

            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
              <Box sx={{ flex: '1 1 300px', minWidth: '250px' }}>
                <TextField
                  fullWidth
                  label="Stop Win"
                  type="number"
                  value={formData.stop_win || 50.0}
                  onChange={handleTextFieldChange('stop_win')}
                  inputProps={{ step: 1, min: 1 }}
                  helperText="Lucro máximo antes de parar"
                />
              </Box>

              <Box sx={{ flex: '1 1 300px', minWidth: '250px' }}>
                <TextField
                  fullWidth
                  label="Stop Loss"
                  type="number"
                  value={formData.stop_loss || 70.0}
                  onChange={handleTextFieldChange('stop_loss')}
                  inputProps={{ step: 1, min: 1 }}
                  helperText="Perda máxima antes de parar"
                />
              </Box>
            </Box>

            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
              <Box sx={{ flex: '1 1 300px', minWidth: '250px' }}>
                <FormControl fullWidth>
                  <InputLabel>Tipo de Par</InputLabel>
                  <Select
                    value={formData.tipo_par || 'automatico'}
                    label="Tipo de Par"
                    onChange={handleSelectChange('tipo_par')}
                  >
                    <MenuItem value="automatico">Automático (Todos os Pares)</MenuItem>
                    <MenuItem value="manual">Manual</MenuItem>
                  </Select>
                </FormControl>
              </Box>

              <Box sx={{ flex: '1 1 300px', minWidth: '250px' }}>
                <FormControl fullWidth>
                  <InputLabel>Estratégia Padrão</InputLabel>
                  <Select
                    value={formData.default_strategy || 'mhi'}
                    label="Estratégia Padrão"
                    onChange={handleSelectChange('default_strategy')}
                  >
                    <MenuItem value="mhi">MHI (3 Velas)</MenuItem>
                    <MenuItem value="torres_gemeas">Torres Gêmeas (1 Vela)</MenuItem>
                    <MenuItem value="mhi_m5">MHI M5 (5 Minutos)</MenuItem>
                  </Select>
                </FormControl>
              </Box>
            </Box>
          </Stack>

          <Divider sx={{ my: 4 }} />

          {/* Análise de Médias */}
          <Typography variant="h6" sx={{ mb: 2 }}>
            Análise de Médias Móveis
          </Typography>
          
          <Stack spacing={3}>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3, alignItems: 'center' }}>
              <Box sx={{ flex: '1 1 300px', minWidth: '250px' }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={formData.analise_medias || false}
                      onChange={handleSwitchChange('analise_medias')}
                    />
                  }
                  label="Usar Análise de Médias"
                />
              </Box>

              <Box sx={{ flex: '1 1 300px', minWidth: '250px' }}>
                <TextField
                  fullWidth
                  label="Número de Velas"
                  type="number"
                  value={formData.velas_medias || 3}
                  onChange={handleTextFieldChange('velas_medias')}
                  inputProps={{ step: 1, min: 1, max: 10 }}
                  disabled={!formData.analise_medias}
                  helperText="Quantidade de velas para análise"
                />
              </Box>
            </Box>
          </Stack>

          <Divider sx={{ my: 4 }} />

          {/* Seção [MARTINGALE] */}
          <Typography variant="h6" sx={{ mb: 2 }}>
            Sistema Martingale
          </Typography>
          
          <Stack spacing={3}>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3, alignItems: 'center' }}>
              <Box sx={{ flex: '1 1 200px', minWidth: '200px' }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={formData.martingale_usar || false}
                      onChange={handleSwitchChange('martingale_usar')}
                    />
                  }
                  label="Usar Martingale"
                />
              </Box>

              <Box sx={{ flex: '1 1 200px', minWidth: '200px' }}>
                <TextField
                  fullWidth
                  label="Níveis do Martingale"
                  type="number"
                  value={formData.martingale_niveis || 1}
                  onChange={handleTextFieldChange('martingale_niveis')}
                  inputProps={{ step: 1, min: 1, max: 5 }}
                  disabled={!formData.martingale_usar}
                  helperText="Quantos níveis usar"
                />
              </Box>

              <Box sx={{ flex: '1 1 200px', minWidth: '200px' }}>
                <TextField
                  fullWidth
                  label="Fator Multiplicador"
                  type="number"
                  value={formData.martingale_fator || 2.0}
                  onChange={handleTextFieldChange('martingale_fator')}
                  inputProps={{ step: 0.1, min: 1.1, max: 5.0 }}
                  disabled={!formData.martingale_usar}
                  helperText="Multiplicador para próximo nível"
                />
              </Box>
            </Box>
          </Stack>

          <Divider sx={{ my: 4 }} />

          {/* Seção [SOROS] */}
          <Typography variant="h6" sx={{ mb: 2 }}>
            Sistema Soros
          </Typography>
          
          <Stack spacing={3}>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3, alignItems: 'center' }}>
              <Box sx={{ flex: '1 1 300px', minWidth: '250px' }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={formData.soros_usar || false}
                      onChange={handleSwitchChange('soros_usar')}
                    />
                  }
                  label="Usar Soros"
                />
              </Box>

              <Box sx={{ flex: '1 1 300px', minWidth: '250px' }}>
                <TextField
                  fullWidth
                  label="Níveis do Soros"
                  type="number"
                  value={formData.soros_niveis || 1}
                  onChange={handleTextFieldChange('soros_niveis')}
                  inputProps={{ step: 1, min: 1, max: 5 }}
                  disabled={!formData.soros_usar}
                  helperText="Quantos níveis usar"
                />
              </Box>
            </Box>
          </Stack>

          {/* Botões de Ação */}
          <Box sx={{ mt: 4, display: 'flex', gap: 2 }}>
            <Button
              type="submit"
              variant="contained"
              startIcon={saving ? <CircularProgress size={20} /> : <Save />}
              disabled={saving}
            >
              {saving ? 'Salvando...' : 'Salvar Configurações'}
            </Button>

            <Button
              variant="outlined"
              startIcon={<Refresh />}
              onClick={handleReset}
              disabled={saving}
            >
              Resetar
            </Button>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

export default ConfigurationForm;
