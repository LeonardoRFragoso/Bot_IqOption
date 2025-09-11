import React from 'react';
import { Box, Typography } from '@mui/material';
import AssetCatalog from '../../components/AssetCatalog/AssetCatalog';

const Analysis: React.FC = () => {
  return (
    <Box sx={{ flexGrow: 1 }}>
      <Typography variant="h4" gutterBottom>
        Análise de Ativos
      </Typography>
      <Typography variant="body1" color="textSecondary" gutterBottom>
        Análise de performance dos ativos e estratégias de trading
      </Typography>

      <Box>
        <AssetCatalog />
      </Box>
    </Box>
  );
};

export default Analysis;
