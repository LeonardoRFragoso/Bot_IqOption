import React from 'react';
import { Box, Typography } from '@mui/material';
import OperationsTable from '../../components/OperationsTable/OperationsTable';

const History: React.FC = () => {

  return (
    <Box sx={{ flexGrow: 1 }}>
      <Typography variant="h4" gutterBottom>
        Histórico de Operações
      </Typography>
      <Typography variant="body1" color="textSecondary" gutterBottom>
        Visualize o histórico completo de suas operações de trading
      </Typography>

      <Box>
        <OperationsTable title="Todas as Operações" />
      </Box>
    </Box>
  );
};

export default History;
