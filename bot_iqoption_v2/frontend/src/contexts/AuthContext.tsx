import React, { createContext, useState, useEffect, type ReactNode } from 'react';
import type { User, LoginCredentials, RegisterData, SubscriptionStatus } from '../types/index';
import apiService from '../services/api';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (userData: RegisterData) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  isAuthenticated: boolean;
  isSubscribed: boolean;
  refreshSubscriptionStatus: () => Promise<SubscriptionStatus | null>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [isSubscribed, setIsSubscribed] = useState<boolean>(false);

  useEffect(() => {
    const initAuth = async () => {
      if (apiService.isAuthenticated()) {
        try {
          const userData = await apiService.getCurrentUser();
          setUser(userData);
          try {
            const status = await apiService.getSubscriptionStatus();
            setIsSubscribed(!!status?.is_subscribed);
          } catch (err) {
            console.warn('Failed to get subscription status on init:', err);
          }
        } catch (error) {
          console.error('Failed to get current user:', error);
          apiService.logout();
        }
      }
      setLoading(false);
    };

    initAuth();
  }, []);

  const login = async (credentials: LoginCredentials) => {
    try {
      await apiService.login(credentials);
      const userData = await apiService.getCurrentUser();
      setUser(userData);
      try {
        const status = await apiService.getSubscriptionStatus();
        setIsSubscribed(!!status?.is_subscribed);
      } catch (err) {
        console.warn('Failed to get subscription status after login:', err);
      }
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  };

  const register = async (userData: RegisterData) => {
    try {
      const response = await apiService.register(userData);
      setUser(response.user);
      try {
        const status = await apiService.getSubscriptionStatus();
        setIsSubscribed(!!status?.is_subscribed);
      } catch (err) {
        console.warn('Failed to get subscription status after register:', err);
      }
    } catch (error: any) {
      console.error('Registration failed:', error);
      console.error('Error response:', error.response?.data);
      console.error('Error status:', error.response?.status);
      throw error;
    }
  };

  const logout = () => {
    apiService.logout();
    setUser(null);
    setIsSubscribed(false);
  };

  const refreshUser = async () => {
    if (apiService.isAuthenticated()) {
      try {
        const userData = await apiService.getCurrentUser();
        setUser(userData);
      } catch (error) {
        console.error('Failed to refresh user:', error);
      }
    }
  };

  const refreshSubscriptionStatus = async (): Promise<SubscriptionStatus | null> => {
    if (!apiService.isAuthenticated()) return null;
    try {
      const status = await apiService.getSubscriptionStatus();
      setIsSubscribed(!!status?.is_subscribed);
      return status;
    } catch (err) {
      console.error('Failed to refresh subscription status:', err);
      return null;
    }
  };

  const value: AuthContextType = {
    user,
    loading,
    login,
    register,
    logout,
    refreshUser,
    isAuthenticated: !!user,
    isSubscribed,
    refreshSubscriptionStatus,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextType => {
  const context = React.useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export { AuthContext };
