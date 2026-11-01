import React, { useState } from 'react';
import {
  Box,
  AppBar,
  Toolbar,
  Typography,
  Tabs,
  Tab,
  Chip
} from '@mui/material';
import {
  Shield,
  Search,
  Database,
  Cpu,
  RefreshCw,
  GitMerge,
  BarChart2,
  Workflow,
  Share2,
  Code,
  Radio,
  Zap,
  Activity,
  Globe
} from 'lucide-react';

import AutonomousResearchWorkspace from './pages/AutonomousResearchWorkspace';
import { DeveloperPlatformWorkspace } from './pages/DeveloperPlatformWorkspace';
import { EnterpriseDataLifecycleWorkspace } from './pages/EnterpriseDataLifecycleWorkspace';
import { EnterpriseGovernanceWorkspace } from './pages/EnterpriseGovernanceWorkspace';
import EnterpriseIntegrationsWorkspace from './pages/EnterpriseIntegrationsWorkspace';
import { EnterpriseMigrationWorkspace } from './pages/EnterpriseMigrationWorkspace';
import EnterpriseEventsWorkspace from './pages/EnterpriseEventsWorkspace';
import { EnterpriseWebhooksWorkspace } from './pages/EnterpriseWebhooksWorkspace';
import { EnterpriseDigitalTwinWorkspace } from './pages/EnterpriseDigitalTwinWorkspace';
import { EnterpriseMultiRegionWorkspace } from './pages/EnterpriseMultiRegionWorkspace';
import { EnterprisePerformanceWorkspace } from './pages/EnterprisePerformanceWorkspace';
import { EnterpriseResilienceWorkspace } from './pages/EnterpriseResilienceWorkspace';
import KnowledgeOntologyWorkspace from './pages/KnowledgeOntologyWorkspace';
import KnowledgeRetrievalWorkspace from './pages/KnowledgeRetrievalWorkspace';

export default function App() {
  const [currentTab, setCurrentTab] = useState(0);

  const workspaces = [
    { label: 'Autonomous Research', icon: <Search size={18} />, component: <AutonomousResearchWorkspace /> },
    { label: 'RAG Retrieval', icon: <Cpu size={18} />, component: <KnowledgeRetrievalWorkspace /> },
    { label: 'Semantic Ontology', icon: <Database size={18} />, component: <KnowledgeOntologyWorkspace /> },
    { label: 'Integrations & APIs', icon: <Share2 size={18} />, component: <EnterpriseIntegrationsWorkspace /> },
    { label: 'Developer SDK', icon: <Code size={18} />, component: <DeveloperPlatformWorkspace /> },
    { label: 'Governance & SLA', icon: <Shield size={18} />, component: <EnterpriseGovernanceWorkspace /> },
    { label: 'Resilience & DR', icon: <RefreshCw size={18} />, component: <EnterpriseResilienceWorkspace /> },
    { label: 'Performance & Cost', icon: <BarChart2 size={18} />, component: <EnterprisePerformanceWorkspace /> },
    { label: 'Lifecycle & Archive', icon: <Workflow size={18} />, component: <EnterpriseDataLifecycleWorkspace /> },
    { label: 'Zero-Downtime Migration', icon: <GitMerge size={18} />, component: <EnterpriseMigrationWorkspace /> },
    { label: 'Event Bus & Outbox', icon: <Radio size={18} />, component: <EnterpriseEventsWorkspace /> },
    { label: 'Enterprise Webhooks', icon: <Zap size={18} />, component: <EnterpriseWebhooksWorkspace /> },
    { label: 'Digital Twin Simulation', icon: <Activity size={18} />, component: <EnterpriseDigitalTwinWorkspace /> },
    { label: 'Multi-Region Global', icon: <Globe size={18} />, component: <EnterpriseMultiRegionWorkspace /> },
  ];

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', bgcolor: 'background.default' }}>
      <AppBar position="sticky" sx={{ bgcolor: '#0f172a', borderBottom: '1px solid #1e293b' }} elevation={0}>
        <Toolbar sx={{ justifyContent: 'space-between', px: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Box
              sx={{
                width: 38,
                height: 38,
                borderRadius: 1.5,
                bgcolor: '#0284c7',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 800,
                color: '#fff',
                fontSize: 20
              }}
            >
              LN
            </Box>
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 700, letterSpacing: -0.5, lineHeight: 1.2 }}>
                LeadNexus AI X
              </Typography>
              <Typography variant="caption" sx={{ color: '#94a3b8' }}>
                Hyper-Scale Enterprise Lead Intelligence Platform • Phases 1–33
              </Typography>
            </Box>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Chip label="746 API Endpoints" size="small" color="primary" variant="outlined" />
            <Chip label="PostgreSQL Truth" size="small" sx={{ bgcolor: '#1e293b', color: '#38bdf8' }} />
            <Chip label="Zero CRM" size="small" sx={{ bgcolor: '#334155', color: '#f1f5f9' }} />
            <Chip label="Production Ready" size="small" color="success" />
          </Box>
        </Toolbar>
        <Box sx={{ borderTop: '1px solid #1e293b', px: 2, bgcolor: '#0b1329' }}>
          <Tabs
            value={currentTab}
            onChange={(_, val) => setCurrentTab(val)}
            variant="scrollable"
            scrollButtons="auto"
            sx={{
              '& .MuiTab-root': {
                color: '#94a3b8',
                textTransform: 'none',
                minHeight: 48,
                fontSize: 13,
                fontWeight: 600,
                gap: 1,
                '&.Mui-selected': {
                  color: '#38bdf8',
                },
              },
              '& .MuiTabs-indicator': {
                backgroundColor: '#38bdf8',
              },
            }}
          >
            {workspaces.map((ws, i) => (
              <Tab key={i} icon={ws.icon} iconPosition="start" label={ws.label} />
            ))}
          </Tabs>
        </Box>
      </AppBar>

      <Box sx={{ flexGrow: 1, py: 3 }}>
        {workspaces[currentTab].component}
      </Box>

      <Box
        component="footer"
        sx={{
          py: 2,
          px: 3,
          mt: 'auto',
          borderTop: '1px solid #1e293b',
          bgcolor: '#0b0f19',
          textAlign: 'center',
          color: '#64748b',
          fontSize: 12
        }}
      >
        LeadNexus AI X • Enterprise Intelligence & Autonomous Research System • Built for @mdyasar49
      </Box>
    </Box>
  );
}
