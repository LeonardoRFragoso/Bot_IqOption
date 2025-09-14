import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Avatar,
  Divider,
  Alert,
  Switch,
  FormControlLabel,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon
} from '@mui/material';
import {
  Person,
  Email,
  Security,
  Notifications,
  AccountBalance,
  History,
  Settings,
  Save,
  Edit
} from '@mui/icons-material';
import { useAuth } from '../../contexts/AuthContext';

interface UserProfile {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  date_joined: string;
  is_active: boolean;
}

interface AccountSettings {
  notifications_enabled: boolean;
  email_alerts: boolean;
  trading_alerts: boolean;
  auto_trading: boolean;
}

const Account: React.FC = () => {
  const { user } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [settings, setSettings] = useState<AccountSettings>({
    notifications_enabled: true,
    email_alerts: true,
    trading_alerts: true,
    auto_trading: false
  });
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    // Mock user data - in production this would come from the API
    if (user) {
      setProfile({
        id: user.id,
        email: user.email,
        first_name: user.first_name || 'Usuário',
        last_name: user.last_name || 'Bot',
        date_joined: '2024-01-15T10:30:00Z',
        is_active: true
      });
    }
  }, [user]);

  const handleSaveProfile = async () => {
    setLoading(true);
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      setMessage({ type: 'success', text: 'Perfil atualizado com sucesso!' });
      setIsEditing(false);
    } catch (error) {
      setMessage({ type: 'error', text: 'Erro ao atualizar perfil. Tente novamente.' });
    } finally {
      setLoading(false);
    }
  };

  const handleSettingChange = (setting: keyof AccountSettings) => {
    setSettings(prev => ({
      ...prev,
      [setting]: !prev[setting]
    }));
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('pt-BR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  if (!profile) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography>Carregando informações da conta...</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ flexGrow: 1 }}>
      <Typography variant="h4" gutterBottom sx={{ mb: 3, fontWeight: 'bold' }}>
        Minha Conta
      </Typography>

      {message && (
        <Alert 
          severity={message.type} 
          sx={{ mb: 3 }}
          onClose={() => setMessage(null)}
        >
          {message.text}
        </Alert>
      )}

      <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 3 }}>
        {/* Profile Information */}
        <Box sx={{ flex: { xs: 1, md: 2 } }}>
          <Paper sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
              <Avatar
                sx={{ 
                  width: 80, 
                  height: 80, 
                  mr: 3,
                  bgcolor: 'primary.main',
                  fontSize: '2rem'
                }}
              >
                {profile.first_name.charAt(0)}{profile.last_name.charAt(0)}
              </Avatar>
              <Box sx={{ flex: 1 }}>
                <Typography variant="h5" gutterBottom>
                  {profile.first_name} {profile.last_name}
                </Typography>
                <Typography variant="body2" color="textSecondary" gutterBottom>
                  {profile.email}
                </Typography>
                <Chip 
                  label={profile.is_active ? 'Ativo' : 'Inativo'} 
                  color={profile.is_active ? 'success' : 'error'}
                  size="small"
                />
              </Box>
              <Button
                startIcon={<Edit />}
                onClick={() => setIsEditing(!isEditing)}
                variant={isEditing ? 'contained' : 'outlined'}
              >
                {isEditing ? 'Cancelar' : 'Editar'}
              </Button>
            </Box>

            <Divider sx={{ mb: 3 }} />

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Box sx={{ display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, gap: 2 }}>
                <TextField
                  fullWidth
                  label="Nome"
                  value={profile.first_name}
                  disabled={!isEditing}
                  onChange={(e) => setProfile(prev => prev ? {...prev, first_name: e.target.value} : null)}
                />
                <TextField
                  fullWidth
                  label="Sobrenome"
                  value={profile.last_name}
                  disabled={!isEditing}
                  onChange={(e) => setProfile(prev => prev ? {...prev, last_name: e.target.value} : null)}
                />
              </Box>
              <TextField
                fullWidth
                label="Email"
                value={profile.email}
                disabled={!isEditing}
                onChange={(e) => setProfile(prev => prev ? {...prev, email: e.target.value} : null)}
              />

              {isEditing && (
                <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end', mt: 2 }}>
                  <Button
                    variant="contained"
                    startIcon={<Save />}
                    onClick={handleSaveProfile}
                    disabled={loading}
                  >
                    {loading ? 'Salvando...' : 'Salvar Alterações'}
                  </Button>
                </Box>
              )}
            </Box>
          </Paper>
        </Box>

        {/* Account Information & Settings */}
        <Box sx={{ flex: { xs: 1, md: 1 }, display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* Account Info */}
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <AccountBalance />
              Informações da Conta
            </Typography>
            <List dense>
              <ListItem>
                <ListItemIcon>
                  <Person />
                </ListItemIcon>
                <ListItemText 
                  primary="ID da Conta" 
                  secondary={`#${profile.id.toString().padStart(6, '0')}`}
                />
              </ListItem>
              <ListItem>
                <ListItemIcon>
                  <History />
                </ListItemIcon>
                <ListItemText 
                  primary="Membro desde" 
                  secondary={formatDate(profile.date_joined)}
                />
              </ListItem>
              <ListItem>
                <ListItemIcon>
                  <Security />
                </ListItemIcon>
                <ListItemText 
                  primary="Status da Conta" 
                  secondary={profile.is_active ? 'Verificada' : 'Pendente'}
                />
              </ListItem>
            </List>
          </Paper>

          {/* Quick Actions */}
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Ações Rápidas
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Box sx={{ display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, gap: 1 }}>
                <Button
                  fullWidth
                  variant="outlined"
                  startIcon={<Security />}
                  size="small"
                >
                  Alterar Senha
                </Button>
                <Button
                  fullWidth
                  variant="outlined"
                  startIcon={<Email />}
                  size="small"
                >
                  Verificar Email
                </Button>
              </Box>
              <Box sx={{ display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, gap: 1 }}>
                <Button
                  fullWidth
                  variant="outlined"
                  startIcon={<History />}
                  size="small"
                >
                  Histórico
                </Button>
                <Button
                  fullWidth
                  variant="outlined"
                  startIcon={<Settings />}
                  size="small"
                >
                  Configurações
                </Button>
              </Box>
            </Box>
          </Paper>

          {/* Notification Settings */}
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Notifications />
              Configurações de Notificação
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.notifications_enabled}
                    onChange={() => handleSettingChange('notifications_enabled')}
                  />
                }
                label="Notificações Gerais"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.email_alerts}
                    onChange={() => handleSettingChange('email_alerts')}
                  />
                }
                label="Alertas por Email"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.trading_alerts}
                    onChange={() => handleSettingChange('trading_alerts')}
                  />
                }
                label="Alertas de Trading"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.auto_trading}
                    onChange={() => handleSettingChange('auto_trading')}
                  />
                }
                label="Trading Automático"
              />
            </Box>
          </Paper>
        </Box>
      </Box>
    </Box>
  );
};

export default Account;
