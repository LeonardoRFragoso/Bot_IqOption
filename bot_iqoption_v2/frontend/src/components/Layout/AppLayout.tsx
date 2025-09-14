import React, { useState } from 'react';
import {
  AppBar,
  Box,
  CssBaseline,
  IconButton,
  Toolbar,
  Typography,
  Avatar,
  Menu,
  MenuItem,
  Divider,
  Chip,
  ListItemIcon,
} from '@mui/material';
import {
  AccountCircle,
  Logout,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import Sidebar from '../Sidebar/Sidebar';

interface AppLayoutProps {
  children: React.ReactNode;
}

const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [currentPage, setCurrentPage] = useState('dashboard');
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Mapear rotas para IDs de página
  const routeToPageMap: { [key: string]: string } = {
    '/dashboard': 'dashboard',
    '/trading': 'trading',
    '/analysis': 'analytics',
    '/charts': 'charts',
    '/history': 'history',
    '/account': 'account',
    '/notifications': 'notifications',
    '/settings': 'settings',
  };

  // Mapear IDs de página para rotas
  const pageToRouteMap: { [key: string]: string } = {
    'dashboard': '/dashboard',
    'trading': '/trading',
    'analytics': '/analysis',
    'charts': '/charts',
    'history': '/history',
    'account': '/account',
    'notifications': '/notifications',
    'settings': '/settings',
  };

  React.useEffect(() => {
    const pageId = routeToPageMap[location.pathname] || 'dashboard';
    setCurrentPage(pageId);
  }, [location.pathname]);

  const handleSidebarToggle = () => {
    setSidebarOpen(!sidebarOpen);
  };

  const handlePageChange = (pageId: string) => {
    const route = pageToRouteMap[pageId];
    if (route) {
      navigate(route);
    }
  };

  const handleMenuClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
    handleMenuClose();
  };

  const getPageTitle = () => {
    const titles: { [key: string]: string } = {
      'dashboard': 'Dashboard',
      'trading': 'Trading',
      'analytics': 'Analytics',
      'charts': 'Charts',
      'history': 'History',
      'account': 'Account',
      'notifications': 'Notifications',
      'settings': 'Settings',
    };
    return titles[currentPage] || 'Bot IQ Option';
  };

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <CssBaseline />
      
      {/* Sidebar */}
      <Sidebar
        open={sidebarOpen}
        onToggle={handleSidebarToggle}
        currentPage={currentPage}
        onPageChange={handlePageChange}
      />
      
      {/* Main Content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          minHeight: '100vh',
          background: 'linear-gradient(135deg, #0A0A0A 0%, #1A1A1A 100%)',
          ml: sidebarOpen ? { xs: 0, md: '280px' } : { xs: 0, md: '72px' },
          transition: 'margin-left 0.3s ease',
        }}
      >
        {/* Top AppBar */}
        <AppBar
          position="fixed"
          elevation={0}
          sx={{
            ml: sidebarOpen ? { xs: 0, md: '280px' } : { xs: 0, md: '72px' },
            width: sidebarOpen 
              ? { xs: '100%', md: 'calc(100% - 280px)' } 
              : { xs: '100%', md: 'calc(100% - 72px)' },
            background: 'linear-gradient(135deg, #1A1A1A 0%, #2A2A2A 100%)',
            borderBottom: '1px solid #333333',
            backdropFilter: 'blur(10px)',
            transition: 'margin-left 0.3s ease, width 0.3s ease',
            zIndex: 1100,
          }}
        >
          <Toolbar sx={{ minHeight: '70px !important' }}>
            <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography 
                variant="h5" 
                noWrap 
                component="div" 
                sx={{ 
                  fontWeight: 600,
                  background: 'linear-gradient(135deg, #FFFFFF 0%, #FFD700 100%)',
                  backgroundClip: 'text',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent'
                }}
              >
                {getPageTitle()}
              </Typography>
              
              <Chip 
                label="LIVE" 
                size="small" 
                sx={{ 
                  background: 'linear-gradient(135deg, #00E676 0%, #00C853 100%)',
                  color: '#000000',
                  fontWeight: 'bold',
                  animation: 'pulse 2s infinite',
                  '@keyframes pulse': {
                    '0%': { opacity: 1 },
                    '50%': { opacity: 0.7 },
                    '100%': { opacity: 1 }
                  }
                }} 
              />
            </Box>
            
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Box sx={{ 
                display: { xs: 'none', sm: 'flex' }, 
                flexDirection: 'column', 
                alignItems: 'flex-end' 
              }}>
                <Typography variant="body2" sx={{ color: '#FFFFFF', fontWeight: 500 }}>
                  {user?.first_name || user?.email}
                </Typography>
                <Typography variant="caption" sx={{ color: '#B0B0B0' }}>
                  Trader Premium
                </Typography>
              </Box>
              
              <IconButton
                size="large"
                aria-label="account of current user"
                aria-controls="menu-appbar"
                aria-haspopup="true"
                onClick={handleMenuClick}
                sx={{
                  border: '2px solid',
                  borderColor: 'primary.main',
                  '&:hover': {
                    backgroundColor: 'rgba(255, 215, 0, 0.1)',
                  }
                }}
              >
                <Avatar sx={{ 
                  width: 36, 
                  height: 36,
                  background: 'linear-gradient(135deg, #FFD700 0%, #FFA000 100%)',
                  color: '#000000',
                  fontWeight: 'bold'
                }}>
                  {user?.first_name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
                </Avatar>
              </IconButton>
              
              <Menu
                id="menu-appbar"
                anchorEl={anchorEl}
                anchorOrigin={{
                  vertical: 'top',
                  horizontal: 'right',
                }}
                keepMounted
                transformOrigin={{
                  vertical: 'top',
                  horizontal: 'right',
                }}
                open={Boolean(anchorEl)}
                onClose={handleMenuClose}
              >
                <MenuItem onClick={() => { navigate('/profile'); handleMenuClose(); }}>
                  <ListItemIcon>
                    <AccountCircle fontSize="small" />
                  </ListItemIcon>
                  Perfil
                </MenuItem>
                <MenuItem onClick={() => { navigate('/settings'); handleMenuClose(); }}>
                  <ListItemIcon>
                    <SettingsIcon fontSize="small" />
                  </ListItemIcon>
                  Configurações
                </MenuItem>
                <Divider />
                <MenuItem onClick={handleLogout}>
                  <ListItemIcon>
                    <Logout fontSize="small" />
                  </ListItemIcon>
                  Sair
                </MenuItem>
              </Menu>
            </Box>
          </Toolbar>
        </AppBar>
        
        {/* Page Content */}
        <Box sx={{ mt: '70px', p: 3 }}>
          {children}
        </Box>
      </Box>
    </Box>
  );
};

export default AppLayout;
