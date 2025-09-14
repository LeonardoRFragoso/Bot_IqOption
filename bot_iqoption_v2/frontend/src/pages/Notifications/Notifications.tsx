import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Badge,
  Chip,
  Button,
  Divider,
  Alert,
  Switch,
  FormControlLabel,
  CircularProgress
} from '@mui/material';
import {
  Notifications as NotificationsIcon,
  TrendingUp,
  Warning,
  Info,
  CheckCircle,
  Delete,
  MarkEmailRead,
  Settings,
  Clear
} from '@mui/icons-material';
import { apiService } from '../../services/api';

interface Notification {
  id: string;
  type: 'success' | 'warning' | 'error' | 'info';
  title: string;
  message: string;
  created_at: string;
  read: boolean;
  category: 'trading' | 'system' | 'account';
}

const Notifications: React.FC = () => {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [showOnlyUnread, setShowOnlyUnread] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadNotifications = async () => {
    try {
      setLoading(true);
      const data = await apiService.getNotifications();
      setNotifications(data);
    } catch (error) {
      console.error('Erro ao carregar notificações:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadNotifications();
  }, []);

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'success':
        return <CheckCircle color="success" />;
      case 'warning':
        return <Warning color="warning" />;
      case 'error':
        return <Warning color="error" />;
      case 'info':
      default:
        return <Info color="info" />;
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'trading':
        return <TrendingUp />;
      case 'system':
        return <Settings />;
      case 'account':
      default:
        return <NotificationsIcon />;
    }
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const handleMarkAsRead = async (id: string) => {
    try {
      await apiService.markNotificationRead(id);
      setNotifications(prev =>
        prev.map(notification =>
          notification.id === id
            ? { ...notification, read: true }
            : notification
        )
      );
    } catch (error) {
      console.error('Erro ao marcar notificação como lida:', error);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await apiService.deleteNotification(id);
      setNotifications(prev =>
        prev.filter(notification => notification.id !== id)
      );
    } catch (error) {
      console.error('Erro ao excluir notificação:', error);
    }
  };

  const handleMarkAllAsRead = async () => {
    try {
      await apiService.markAllNotificationsRead();
      setNotifications(prev =>
        prev.map(notification => ({ ...notification, read: true }))
      );
    } catch (error) {
      console.error('Erro ao marcar todas como lidas:', error);
    }
  };

  const handleClearAll = async () => {
    try {
      await apiService.clearAllNotifications();
      setNotifications([]);
    } catch (error) {
      console.error('Erro ao limpar notificações:', error);
    }
  };

  const filteredNotifications = showOnlyUnread
    ? notifications.filter(n => !n.read)
    : notifications;

  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <Box sx={{ flexGrow: 1 }}>
      <Typography variant="h4" gutterBottom>
        Notificações
        {unreadCount > 0 && (
          <Badge badgeContent={unreadCount} color="primary" sx={{ ml: 2 }}>
            <NotificationsIcon />
          </Badge>
        )}
      </Typography>

      <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
        <Button
          variant="outlined"
          startIcon={<MarkEmailRead />}
          onClick={handleMarkAllAsRead}
          disabled={unreadCount === 0}
        >
          Marcar Todas como Lidas
        </Button>
        
        <Button
          variant="outlined"
          color="error"
          startIcon={<Clear />}
          onClick={handleClearAll}
          disabled={notifications.length === 0}
        >
          Limpar Todas
        </Button>

        <FormControlLabel
          control={
            <Switch
              checked={showOnlyUnread}
              onChange={(e) => setShowOnlyUnread(e.target.checked)}
            />
          }
          label="Mostrar apenas não lidas"
        />
      </Box>

      <Typography variant="body1" color="textSecondary" gutterBottom>
        Acompanhe todas as notificações do sistema, trading e conta
      </Typography>

      {loading ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <CircularProgress />
          <Typography variant="body2" color="textSecondary" sx={{ mt: 2 }}>
            Carregando notificações...
          </Typography>
        </Paper>
      ) : filteredNotifications.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <NotificationsIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" color="textSecondary" gutterBottom>
            {showOnlyUnread ? 'Nenhuma notificação não lida' : 'Nenhuma notificação'}
          </Typography>
          <Typography variant="body2" color="textSecondary">
            {showOnlyUnread ? 'Todas as suas notificações foram lidas' : 'Você não tem notificações no momento'}
          </Typography>
        </Paper>
      ) : (
        <Paper>
          <List sx={{ width: '100%' }}>
            {filteredNotifications.map((notification, index) => (
              <React.Fragment key={notification.id}>
                <ListItem
                  sx={{
                    bgcolor: notification.read ? 'transparent' : 'action.hover',
                    '&:hover': {
                      bgcolor: 'action.selected'
                    }
                  }}
                >
                  <ListItemIcon>
                    <Box sx={{ position: 'relative' }}>
                      {getCategoryIcon(notification.category)}
                      <Box
                        sx={{
                          position: 'absolute',
                          bottom: -4,
                          right: -4,
                          transform: 'scale(0.7)'
                        }}
                      >
                        {getNotificationIcon(notification.type)}
                      </Box>
                    </Box>
                  </ListItemIcon>
                  
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                        <Typography
                          variant="subtitle1"
                          sx={{
                            fontWeight: notification.read ? 'normal' : 'bold'
                          }}
                        >
                          {notification.title}
                        </Typography>
                        <Chip
                          label={notification.category}
                          size="small"
                          variant="outlined"
                          sx={{ fontSize: '0.7rem', height: 20 }}
                        />
                        {!notification.read && (
                          <Box
                            sx={{
                              width: 8,
                              height: 8,
                              borderRadius: '50%',
                              bgcolor: 'primary.main'
                            }}
                          />
                        )}
                      </Box>
                    }
                    secondary={
                      <Box>
                        <Typography variant="body2" color="textSecondary" sx={{ mb: 0.5 }}>
                          {notification.message}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {formatTimestamp(notification.created_at)}
                        </Typography>
                      </Box>
                    }
                  />
                  
                  <ListItemSecondaryAction>
                    <Box sx={{ display: 'flex', gap: 0.5 }}>
                      {!notification.read && (
                        <IconButton
                          edge="end"
                          onClick={() => handleMarkAsRead(notification.id)}
                          size="small"
                          title="Marcar como lida"
                        >
                          <MarkEmailRead />
                        </IconButton>
                      )}
                      <IconButton
                        edge="end"
                        onClick={() => handleDelete(notification.id)}
                        size="small"
                        title="Excluir notificação"
                      >
                        <Delete />
                      </IconButton>
                    </Box>
                  </ListItemSecondaryAction>
                </ListItem>
                
                {index < filteredNotifications.length - 1 && <Divider />}
              </React.Fragment>
            ))}
          </List>
        </Paper>
      )}

      {notifications.length > 0 && (
        <Alert severity="info" sx={{ mt: 3 }}>
          <Typography variant="body2">
            <strong>Dica:</strong> As notificações são atualizadas automaticamente. 
            Você pode configurar suas preferências de notificação na página de Conta.
          </Typography>
        </Alert>
      )}
    </Box>
  );
};

export default Notifications;
