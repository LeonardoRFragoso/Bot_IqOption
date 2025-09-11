import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Tabs,
  Tab,
  TextField,
  Button,
  Alert,
  Divider,
  Stack,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormHelperText,
} from '@mui/material';
import type { SelectChangeEvent } from '@mui/material/Select';
import { Save, Security, Settings as SettingsIcon } from '@mui/icons-material';
import ConfigurationForm from '../../components/ConfigurationForm/ConfigurationForm';
import { useAuth } from '../../hooks/useAuth';
import apiService from '../../services/api';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`settings-tabpanel-${index}`}
      aria-labelledby={`settings-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

const Settings: React.FC = () => {
  const [tabValue, setTabValue] = useState(0);
  const [iqCredentials, setIqCredentials] = useState({ email: '', password: '' });
  const [accountType, setAccountType] = useState<'PRACTICE' | 'REAL'>('PRACTICE');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);
  const { user, refreshUser } = useAuth();

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  // Initialize account type from user preference
  useEffect(() => {
    if (user?.preferred_account_type) {
      setAccountType(user.preferred_account_type as 'PRACTICE' | 'REAL');
    }
  }, [user]);

  const handleIqCredentialsChange = (field: 'email' | 'password') => (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    setIqCredentials(prev => ({
      ...prev,
      [field]: event.target.value
    }));
  };

  const handleAccountTypeChange = (event: SelectChangeEvent<string>) => {
    setAccountType(event.target.value as 'PRACTICE' | 'REAL');
  };

  const handleSaveIqCredentials = async () => {
    setLoading(true);
    setMessage(null);

    try {
      // Convert field names to match backend expectations
      const credentials = {
        iq_email: iqCredentials.email,
        iq_password: iqCredentials.password
      };
      await apiService.updateIQCredentials(credentials);
      
      // Update user's preferred account type
      if (user && accountType !== user.preferred_account_type) {
        await apiService.updateUserProfile({ preferred_account_type: accountType });
        await refreshUser(); // Refresh user data to reflect changes
      }
      
      setMessage({ type: 'success', text: 'Credenciais IQ Option e tipo de conta salvos com sucesso!' });
      setIqCredentials({ email: '', password: '' });
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Erro ao salvar credenciais';
      setMessage({ 
        type: 'error', 
        text: errorMessage 
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ width: '100%' }}>
      <Typography variant="h4" gutterBottom>
        Configurações
      </Typography>

      <Card>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={tabValue} onChange={handleTabChange}>
            <Tab 
              label="Trading" 
              icon={<SettingsIcon />} 
              iconPosition="start"
            />
            <Tab 
              label="IQ Option" 
              icon={<Security />} 
              iconPosition="start"
            />
          </Tabs>
        </Box>

        <TabPanel value={tabValue} index={0}>
          <ConfigurationForm />
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Credenciais IQ Option
            </Typography>
            <Typography variant="body2" color="textSecondary" gutterBottom>
              Configure suas credenciais para conectar com a plataforma IQ Option
            </Typography>

            {message && (
              <Alert severity={message.type} sx={{ mb: 3 }}>
                {message.text}
              </Alert>
            )}

            <Stack spacing={3}>
              <TextField
                fullWidth
                label="Email IQ Option"
                type="email"
                value={iqCredentials.email}
                onChange={handleIqCredentialsChange('email')}
                helperText="Email usado para login na IQ Option"
              />

              <TextField
                fullWidth
                label="Senha IQ Option"
                type="password"
                value={iqCredentials.password}
                onChange={handleIqCredentialsChange('password')}
                helperText="Senha da sua conta IQ Option (será criptografada)"
              />

              <FormControl fullWidth>
                <InputLabel>Tipo de Conta</InputLabel>
                <Select
                  value={accountType}
                  label="Tipo de Conta"
                  onChange={handleAccountTypeChange}
                >
                  <MenuItem value="PRACTICE">Demo (Prática)</MenuItem>
                  <MenuItem value="REAL">Real</MenuItem>
                </Select>
                <FormHelperText>
                  {accountType === 'PRACTICE' 
                    ? 'Conta demo para testes sem risco financeiro'
                    : 'Conta real - operações com dinheiro real'}
                </FormHelperText>
              </FormControl>

              <Button
                variant="contained"
                startIcon={<Save />}
                onClick={handleSaveIqCredentials}
                disabled={loading || !iqCredentials.email || !iqCredentials.password}
                sx={{ alignSelf: 'flex-start' }}
              >
                {loading ? 'Salvando...' : 'Salvar Credenciais'}
              </Button>
            </Stack>

            <Divider sx={{ my: 3 }} />

            <Typography variant="h6" gutterBottom>
              Informações da Conta
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2 }}>
              <Typography variant="body2" color="textSecondary">
                <strong>Email:</strong> {user?.email}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                <strong>Nome:</strong> {user?.first_name} {user?.last_name}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                <strong>Tipo de Conta Preferido:</strong> {user?.preferred_account_type}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                <strong>Trader Ativo:</strong> {user?.is_active_trader ? 'Sim' : 'Não'}
              </Typography>
            </Box>
          </CardContent>
        </TabPanel>
      </Card>
    </Box>
  );
};

export default Settings;
