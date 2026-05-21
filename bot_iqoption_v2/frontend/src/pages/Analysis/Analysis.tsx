import React, { useState } from 'react';
import { Box, Typography, Tabs, Tab, Card } from '@mui/material';
import { Analytics as AnalyticsIcon, Assessment } from '@mui/icons-material';
import AssetCatalog from '../../components/AssetCatalog/AssetCatalog';
import AdvancedAnalytics from '../../components/AdvancedAnalytics/AdvancedAnalytics';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div role="tabpanel" hidden={value !== index} {...other}>
      {value === index && <Box sx={{ pt: 2 }}>{children}</Box>}
    </div>
  );
}

const Analysis: React.FC = () => {
  const [tabValue, setTabValue] = useState(0);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  return (
    <Box sx={{ flexGrow: 1 }}>
      <Typography variant="h4" gutterBottom>
        Análise de Ativos
      </Typography>
      <Typography variant="body1" color="textSecondary" gutterBottom>
        Análise de performance dos ativos e estratégias de trading
      </Typography>

      <Card sx={{ mb: 2 }}>
        <Tabs value={tabValue} onChange={handleTabChange}>
          <Tab label="Catálogo de Ativos" icon={<Assessment />} iconPosition="start" />
          <Tab label="Análise Avançada" icon={<AnalyticsIcon />} iconPosition="start" />
        </Tabs>
      </Card>

      <TabPanel value={tabValue} index={0}>
        <AssetCatalog />
      </TabPanel>

      <TabPanel value={tabValue} index={1}>
        <AdvancedAnalytics />
      </TabPanel>
    </Box>
  );
};

export default Analysis;
