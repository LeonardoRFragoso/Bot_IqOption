import React, { useState } from 'react';
import { Box, Typography, Stack } from '@mui/material';
import TradingControl from '../../components/TradingControl/TradingControl';
import OperationsTable from '../../components/OperationsTable/OperationsTable';
import LogsViewer from '../../components/LogsViewer/LogsViewer';
import BestAssetsSelector from '../../components/BestAssetsSelector/BestAssetsSelector';

const Trading: React.FC = () => {
  const [selectedAsset, setSelectedAsset] = useState<string>('');
  const [selectedStrategy, setSelectedStrategy] = useState<string>('');

  const handleSelectAsset = (asset: string, strategy: string) => {
    setSelectedAsset(asset);
    setSelectedStrategy(strategy);
  };

  return (
    <Box sx={{ flexGrow: 1 }}>
      <Typography variant="h4" gutterBottom>
        Trading
      </Typography>
      <Typography variant="body1" color="textSecondary" gutterBottom>
        Controle e monitore suas operações de trading em tempo real
      </Typography>

      <Stack spacing={3}>
        {/* Melhores Ativos da Catalogação */}
        <BestAssetsSelector
          onSelectAsset={handleSelectAsset}
          selectedAsset={selectedAsset}
          selectedStrategy={selectedStrategy}
          maxResults={5}
        />

        <TradingControl 
          selectedAsset={selectedAsset}
          selectedStrategy={selectedStrategy}
        />
        
        <Box sx={{ display: 'flex', gap: 3, flexDirection: { xs: 'column', lg: 'row' } }}>
          <Box sx={{ flex: { lg: 2 } }}>
            <OperationsTable title="Operações Recentes" maxRows={15} />
          </Box>
          <Box sx={{ flex: { lg: 1 } }}>
            <LogsViewer maxLogs={20} />
          </Box>
        </Box>
      </Stack>
    </Box>
  );
};

export default Trading;
