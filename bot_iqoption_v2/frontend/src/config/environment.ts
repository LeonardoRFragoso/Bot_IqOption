// Configuração de ambiente centralizada
export const config = {
  // API Configuration
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api',
  wsBaseUrl: import.meta.env.VITE_WS_BASE_URL || 'ws://127.0.0.1:8000',
  
  // Environment detection
  isDevelopment: import.meta.env.DEV,
  isProduction: import.meta.env.PROD,
  
  // Debug mode
  debug: import.meta.env.VITE_DEBUG === 'true' || import.meta.env.DEV,
};

// Log configuration on startup (only in development)
if (config.isDevelopment) {
  console.log('🔧 Environment Configuration:', {
    apiBaseUrl: config.apiBaseUrl,
    wsBaseUrl: config.wsBaseUrl,
    isDevelopment: config.isDevelopment,
    isProduction: config.isProduction,
  });
}
