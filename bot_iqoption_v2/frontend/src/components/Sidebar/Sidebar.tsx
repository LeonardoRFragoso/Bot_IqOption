import React from 'react';
import {
  Box,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  IconButton,
  Typography,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  TrendingUp as TradingIcon,
  Assessment as AnalyticsIcon,
  Settings as SettingsIcon,
  History as HistoryIcon,
  AccountBalance as AccountIcon,
  Menu as MenuIcon,
  ChevronLeft as ChevronLeftIcon,
  ShowChart as ChartIcon,
  Notifications as NotificationsIcon,
} from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';

interface SidebarProps {
  open: boolean;
  onToggle: () => void;
  currentPage?: string;
  onPageChange?: (page: string) => void;
}

interface MenuItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  path: string;
  badge?: number;
}

const menuItems: MenuItem[] = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    icon: <DashboardIcon />,
    path: '/dashboard',
  },
  {
    id: 'trading',
    label: 'Trading',
    icon: <TradingIcon />,
    path: '/trading',
  },
  {
    id: 'analytics',
    label: 'Analytics',
    icon: <AnalyticsIcon />,
    path: '/analytics',
  },
  {
    id: 'charts',
    label: 'Charts',
    icon: <ChartIcon />,
    path: '/charts',
  },
  {
    id: 'history',
    label: 'History',
    icon: <HistoryIcon />,
    path: '/history',
  },
  {
    id: 'account',
    label: 'Account',
    icon: <AccountIcon />,
    path: '/account',
  },
  {
    id: 'notifications',
    label: 'Notifications',
    icon: <NotificationsIcon />,
    path: '/notifications',
    badge: 3,
  },
  {
    id: 'settings',
    label: 'Settings',
    icon: <SettingsIcon />,
    path: '/settings',
  },
];

const Sidebar: React.FC<SidebarProps> = ({
  open,
  onToggle,
  currentPage = 'dashboard',
  onPageChange,
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const drawerWidth = 280;
  const collapsedWidth = 72;

  const handleItemClick = (item: MenuItem) => {
    if (onPageChange) {
      onPageChange(item.id);
    }
    if (isMobile) {
      onToggle();
    }
  };

  const sidebarVariants = {
    open: {
      width: drawerWidth,
    },
    closed: {
      width: collapsedWidth,
    },
  };

  const itemVariants = {
    hover: {
      backgroundColor: 'rgba(25, 118, 210, 0.08)',
      scale: 1.02,
      transition: {
        duration: 0.2,
      },
    },
    tap: {
      scale: 0.98,
    },
  };

  const drawerContent = (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: 'linear-gradient(180deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
        color: 'white',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          p: 2,
          minHeight: 64,
          borderBottom: '1px solid rgba(255, 255, 255, 0.12)',
        }}
      >
        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.2 }}
            >
              <Typography
                variant="h6"
                sx={{
                  fontWeight: 'bold',
                  background: 'linear-gradient(45deg, #64b5f6, #42a5f5)',
                  backgroundClip: 'text',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                }}
              >
                IQ Bot Pro
              </Typography>
            </motion.div>
          )}
        </AnimatePresence>
        
        <IconButton
          onClick={onToggle}
          sx={{
            color: 'white',
            '&:hover': {
              backgroundColor: 'rgba(255, 255, 255, 0.08)',
            },
          }}
        >
          {open ? <ChevronLeftIcon /> : <MenuIcon />}
        </IconButton>
      </Box>

      {/* Navigation Items */}
      <Box sx={{ flex: 1, py: 1 }}>
        <List sx={{ px: 1 }}>
          {menuItems.map((item) => (
            <ListItem key={item.id} disablePadding sx={{ mb: 0.5 }}>
              <motion.div
                style={{ width: '100%' }}
                variants={itemVariants}
                whileHover="hover"
                whileTap="tap"
              >
                <ListItemButton
                  onClick={() => handleItemClick(item)}
                  selected={currentPage === item.id}
                  sx={{
                    borderRadius: 2,
                    minHeight: 48,
                    px: open ? 2 : 1.5,
                    justifyContent: open ? 'initial' : 'center',
                    '&.Mui-selected': {
                      backgroundColor: 'rgba(25, 118, 210, 0.2)',
                      borderLeft: '3px solid #1976d2',
                      '&:hover': {
                        backgroundColor: 'rgba(25, 118, 210, 0.25)',
                      },
                    },
                    '&:hover': {
                      backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    },
                  }}
                >
                  <ListItemIcon
                    sx={{
                      minWidth: 0,
                      mr: open ? 2 : 'auto',
                      justifyContent: 'center',
                      color: currentPage === item.id ? '#64b5f6' : 'rgba(255, 255, 255, 0.7)',
                      transition: 'color 0.2s ease',
                    }}
                  >
                    {item.icon}
                  </ListItemIcon>
                  
                  <AnimatePresence>
                    {open && (
                      <motion.div
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -10 }}
                        transition={{ duration: 0.2 }}
                        style={{ width: '100%' }}
                      >
                        <ListItemText
                          primary={item.label}
                          sx={{
                            '& .MuiListItemText-primary': {
                              fontSize: '0.9rem',
                              fontWeight: currentPage === item.id ? 600 : 400,
                              color: currentPage === item.id ? 'white' : 'rgba(255, 255, 255, 0.8)',
                            },
                          }}
                        />
                        
                        {item.badge && (
                          <Box
                            sx={{
                              backgroundColor: '#f44336',
                              color: 'white',
                              borderRadius: '50%',
                              minWidth: 20,
                              height: 20,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontSize: '0.75rem',
                              fontWeight: 'bold',
                            }}
                          >
                            {item.badge}
                          </Box>
                        )}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </ListItemButton>
              </motion.div>
            </ListItem>
          ))}
        </List>
      </Box>

      {/* Footer */}
      <Box
        sx={{
          p: 2,
          borderTop: '1px solid rgba(255, 255, 255, 0.12)',
        }}
      >
        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 20 }}
              transition={{ duration: 0.2 }}
            >
              <Typography
                variant="caption"
                sx={{
                  color: 'rgba(255, 255, 255, 0.5)',
                  display: 'block',
                  textAlign: 'center',
                }}
              >
                v2.0.0 - Bot IQ Option
              </Typography>
            </motion.div>
          )}
        </AnimatePresence>
      </Box>
    </Box>
  );

  if (isMobile) {
    return (
      <Drawer
        variant="temporary"
        open={open}
        onClose={onToggle}
        ModalProps={{
          keepMounted: true,
        }}
        sx={{
          '& .MuiDrawer-paper': {
            width: drawerWidth,
            boxSizing: 'border-box',
            border: 'none',
          },
        }}
      >
        {drawerContent}
      </Drawer>
    );
  }

  return (
    <motion.div
      variants={sidebarVariants}
      animate={open ? 'open' : 'closed'}
      style={{
        position: 'fixed',
        left: 0,
        top: 0,
        height: '100vh',
        zIndex: 1200,
      }}
    >
      <Drawer
        variant="permanent"
        open={open}
        sx={{
          width: open ? drawerWidth : collapsedWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: open ? drawerWidth : collapsedWidth,
            boxSizing: 'border-box',
            border: 'none',
            transition: theme.transitions.create('width', {
              easing: theme.transitions.easing.sharp,
              duration: theme.transitions.duration.enteringScreen,
            }),
            overflowX: 'hidden',
          },
        }}
      >
        {drawerContent}
      </Drawer>
    </motion.div>
  );
};

export default Sidebar;
