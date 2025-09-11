import { createTheme } from '@mui/material/styles';

export const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#FFD700', // Gold
      dark: '#FFA000',
      light: '#FFECB3',
      contrastText: '#000000',
    },
    secondary: {
      main: '#FFFFFF', // White
      dark: '#F5F5F5',
      light: '#FFFFFF',
      contrastText: '#000000',
    },
    background: {
      default: '#0A0A0A', // Deep black
      paper: '#1A1A1A', // Slightly lighter black for cards
    },
    surface: {
      main: '#2A2A2A', // For elevated surfaces
    },
    text: {
      primary: '#FFFFFF',
      secondary: '#B0B0B0',
    },
    divider: '#333333',
    success: {
      main: '#00E676',
      dark: '#00C853',
      light: '#69F0AE',
    },
    error: {
      main: '#FF1744',
      dark: '#D50000',
      light: '#FF5983',
    },
    warning: {
      main: '#FFD700',
      dark: '#FFA000',
      light: '#FFECB3',
    },
    info: {
      main: '#00B0FF',
      dark: '#0091EA',
      light: '#40C4FF',
    },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontWeight: 700,
      fontSize: '2.5rem',
      color: '#FFFFFF',
    },
    h2: {
      fontWeight: 600,
      fontSize: '2rem',
      color: '#FFFFFF',
    },
    h3: {
      fontWeight: 600,
      fontSize: '1.75rem',
      color: '#FFFFFF',
    },
    h4: {
      fontWeight: 600,
      fontSize: '1.5rem',
      color: '#FFFFFF',
    },
    h5: {
      fontWeight: 600,
      fontSize: '1.25rem',
      color: '#FFFFFF',
    },
    h6: {
      fontWeight: 600,
      fontSize: '1.125rem',
      color: '#FFFFFF',
    },
    body1: {
      fontSize: '1rem',
      color: '#FFFFFF',
    },
    body2: {
      fontSize: '0.875rem',
      color: '#B0B0B0',
    },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: '#0A0A0A',
          backgroundImage: 'linear-gradient(135deg, #0A0A0A 0%, #1A1A1A 100%)',
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundColor: '#1A1A1A',
          border: '1px solid #333333',
          borderRadius: '12px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
          backdropFilter: 'blur(10px)',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: '8px',
          textTransform: 'none',
          fontWeight: 600,
          padding: '10px 24px',
          boxShadow: 'none',
          '&:hover': {
            boxShadow: '0 4px 16px rgba(255, 215, 0, 0.3)',
          },
        },
        contained: {
          '&.MuiButton-containedPrimary': {
            background: 'linear-gradient(135deg, #FFD700 0%, #FFA000 100%)',
            color: '#000000',
            '&:hover': {
              background: 'linear-gradient(135deg, #FFA000 0%, #FF8F00 100%)',
            },
          },
          '&.MuiButton-containedSuccess': {
            background: 'linear-gradient(135deg, #00E676 0%, #00C853 100%)',
            '&:hover': {
              background: 'linear-gradient(135deg, #00C853 0%, #00A152 100%)',
            },
          },
          '&.MuiButton-containedError': {
            background: 'linear-gradient(135deg, #FF1744 0%, #D50000 100%)',
            '&:hover': {
              background: 'linear-gradient(135deg, #D50000 0%, #B71C1C 100%)',
            },
          },
          '&.MuiButton-containedWarning': {
            background: 'linear-gradient(135deg, #FFD700 0%, #FFA000 100%)',
            color: '#000000',
            '&:hover': {
              background: 'linear-gradient(135deg, #FFA000 0%, #FF8F00 100%)',
            },
          },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            backgroundColor: '#2A2A2A',
            borderRadius: '8px',
            '& fieldset': {
              borderColor: '#333333',
            },
            '&:hover fieldset': {
              borderColor: '#FFD700',
            },
            '&.Mui-focused fieldset': {
              borderColor: '#FFD700',
            },
          },
        },
      },
    },
    MuiSelect: {
      styleOverrides: {
        root: {
          backgroundColor: '#2A2A2A',
          borderRadius: '8px',
          '& .MuiOutlinedInput-notchedOutline': {
            borderColor: '#333333',
          },
          '&:hover .MuiOutlinedInput-notchedOutline': {
            borderColor: '#FFD700',
          },
          '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
            borderColor: '#FFD700',
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: '6px',
          fontWeight: 500,
        },
        colorSuccess: {
          backgroundColor: '#00E676',
          color: '#000000',
        },
        colorError: {
          backgroundColor: '#FF1744',
          color: '#FFFFFF',
        },
        colorWarning: {
          backgroundColor: '#FFD700',
          color: '#000000',
        },
      },
    },
    MuiTableContainer: {
      styleOverrides: {
        root: {
          backgroundColor: '#1A1A1A',
          borderRadius: '12px',
          border: '1px solid #333333',
        },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          backgroundColor: '#2A2A2A',
          '& .MuiTableCell-head': {
            color: '#FFD700',
            fontWeight: 600,
            borderBottom: '2px solid #333333',
          },
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          '&:hover': {
            backgroundColor: '#2A2A2A',
          },
          '&:last-child td': {
            borderBottom: 0,
          },
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: '#1A1A1A',
          borderRight: '1px solid #333333',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#1A1A1A',
          borderBottom: '1px solid #333333',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.2)',
        },
      },
    },
  },
});

// Extend the theme interface to include custom colors
declare module '@mui/material/styles' {
  interface Palette {
    surface: Palette['primary'];
  }

  interface PaletteOptions {
    surface?: PaletteOptions['primary'];
  }
}
