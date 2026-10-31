import React, { useState } from 'react';
import {
  Box,
  Container,
  Typography,
  Paper,
  Grid,
  Card,
  CardHeader,
  CardContent,
  TextField,
  Button,
  Chip,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Alert,
  Tabs,
  Tab,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Select,
  MenuItem,
  FormControl,
  InputLabel
} from '@mui/material';
import {
  Code as DeveloperIcon,
  Apps as AppIcon,
  Store as MarketplaceIcon,
  Science as SandboxIcon,
  Extension as ConnectorIcon,
  AutoAwesome as TemplateIcon,
  Security as SecurityIcon,
  VpnKey as KeyIcon,
  CheckCircle as VerifiedIcon,
  PlayArrow as RunIcon,
  Refresh as ResetIcon,
  ContentCopy as CopyIcon,
  Warning as WarningIcon
} from '@mui/icons-material';

interface DeveloperApp {
  id: string;
  name: string;
  client_id: string;
  status: string;
  application_type: string;
  scopes: { scope_name: string; risk_level: string; is_approved: boolean }[];
}

interface MarketplaceItem {
  connector_id: string;
  title: string;
  category: string;
  author: string;
  trust_level: string;
  rating: number;
  download_count: number;
  is_verified: boolean;
}

export const DeveloperPlatformWorkspace: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);

  // Apps State
  const [apps, setApps] = useState<DeveloperApp[]>([
    {
      id: 'app_01',
      name: 'Custom ERP Signal Ingestion',
      client_id: 'lnx_app_8f9024bc912d09e1',
      status: 'ACTIVE',
      application_type: 'INTERNAL',
      scopes: [
        { scope_name: 'companies:read', risk_level: 'LOW', is_approved: true },
        { scope_name: 'research:run', risk_level: 'MEDIUM', is_approved: true },
      ],
    },
    {
      id: 'app_02',
      name: 'BI Data Warehouse Syncer',
      client_id: 'lnx_app_44e198bca23f8102',
      status: 'ACTIVE',
      application_type: 'PRIVATE',
      scopes: [
        { scope_name: 'companies:read', risk_level: 'LOW', is_approved: true },
        { scope_name: 'exports:create', risk_level: 'HIGH', is_approved: true },
      ],
    },
  ]);

  // App Creation Dialog
  const [openCreateApp, setOpenCreateApp] = useState(false);
  const [newAppName, setNewAppName] = useState('');
  const [newAppType, setNewAppType] = useState('PRIVATE');
  const [issuedSecret, setIssuedSecret] = useState<string | null>(null);

  // Marketplace Catalog
  const [marketplaceItems] = useState<MarketplaceItem[]>([
    {
      connector_id: 'public_job_feed_connector',
      title: 'Public Job Feed Technology Signals',
      category: 'Signal Ingestion',
      author: 'LeadNexus Official',
      trust_level: 'OFFICIAL',
      rating: 4.9,
      download_count: 1420,
      is_verified: true,
    },
    {
      connector_id: 'webhook_intelligence_exporter',
      title: 'Webhook Intelligence Exporter',
      category: 'Intelligence Export',
      author: 'LeadNexus Official',
      trust_level: 'OFFICIAL',
      rating: 4.8,
      download_count: 980,
      is_verified: true,
    },
    {
      connector_id: 'community_domain_reputation_auditor',
      title: 'Domain MX & SPF Health Auditor',
      category: 'Verification',
      author: 'CyberNet Labs',
      trust_level: 'COMMUNITY',
      rating: 4.6,
      download_count: 310,
      is_verified: false,
    },
  ]);

  // Sandboxed Connector Execution
  const [selectedConnector, setSelectedConnector] = useState('public_job_feed_connector');
  const [connectorLog, setConnectorLog] = useState<string[]>([]);
  const [executionResult, setExecutionResult] = useState<any>(null);

  // Sandbox Provider Simulator
  const [simEndpoint, setSimEndpoint] = useState('company_enrichment');
  const [simMode, setSimMode] = useState('SUCCESS');
  const [simResult, setSimResult] = useState<any>(null);

  const handleCreateApp = () => {
    if (!newAppName) return;
    const mockSecret = 'lnx_sec_' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
    const newApp: DeveloperApp = {
      id: `app_${Date.now()}`,
      name: newAppName,
      client_id: 'lnx_app_' + Math.random().toString(16).substring(2, 18),
      status: 'ACTIVE',
      application_type: newAppType,
      scopes: [{ scope_name: 'companies:read', risk_level: 'LOW', is_approved: true }],
    };
    setApps([...apps, newApp]);
    setIssuedSecret(mockSecret);
  };

  const handleRunConnector = () => {
    setConnectorLog([
      `[${new Date().toISOString()}] Validating scopes and security policies for ${selectedConnector}...`,
      `[${new Date().toISOString()}] Permissions approved: ['companies:read', 'research:run']`,
      `[${new Date().toISOString()}] Executing handler in isolated runtime (timeout: 30s)...`,
      `[${new Date().toISOString()}] Fetched 2 verified career posting signals from https://careers.example.com`,
      `[${new Date().toISOString()}] Finished in 34ms with status SUCCESS.`,
    ]);
    setExecutionResult({
      status: 'SUCCESS',
      records_processed: 2,
      records: [
        { job_title: 'Lead Odoo Functional Consultant', company: 'Apex Manufacturing Ltd', confidence: 0.94 },
        { job_title: 'Senior Odoo Developer', company: 'Nexus Logistics Solutions', confidence: 0.91 },
      ],
    });
  };

  const handleSimulateProvider = () => {
    if (simMode === 'RATE_LIMIT') {
      setSimResult({
        status_code: 429,
        error: 'Too Many Requests (Simulated 429)',
        headers: { 'Retry-After': '60' },
      });
    } else if (simMode === 'SERVER_ERROR') {
      setSimResult({
        status_code: 500,
        error: 'Simulated Upstream Server Outage',
      });
    } else {
      setSimResult({
        status_code: 200,
        payload: {
          company_name: 'Apex Manufacturing Ltd [SANDBOX]',
          technologies: ['Odoo 17.0', 'PostgreSQL', 'Nginx'],
          confidence: 0.95,
        },
      });
    }
  };

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 6 }}>
      {/* Platform Header */}
      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
          <DeveloperIcon color="primary" sx={{ fontSize: 36 }} />
          <Typography variant="h4" fontWeight={700}>
            Enterprise Developer Platform & Connector SDK
          </Typography>
          <Chip label="Phase 28 Active" color="primary" variant="outlined" size="small" />
        </Box>
        <Typography variant="body1" color="text.secondary">
          Build, test, sandbox, and package custom data connectors, API applications, and workflow templates.
        </Typography>
      </Box>

      {/* Tabs */}
      <Paper sx={{ mb: 4 }}>
        <Tabs
          value={activeTab}
          onChange={(_, val) => setActiveTab(val)}
          indicatorColor="primary"
          textColor="primary"
          variant="scrollable"
        >
          <Tab icon={<AppIcon />} label="Applications & Credentials" iconPosition="start" />
          <Tab icon={<MarketplaceIcon />} label="Connector Marketplace" iconPosition="start" />
          <Tab icon={<ConnectorIcon />} label="Connector SDK Sandbox" iconPosition="start" />
          <Tab icon={<TemplateIcon />} label="Integration Blueprints" iconPosition="start" />
          <Tab icon={<SandboxIcon />} label="Environment Simulator" iconPosition="start" />
        </Tabs>
      </Paper>

      {/* Tab 0: Applications & Credentials */}
      {activeTab === 0 && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6" fontWeight={600}>
                Registered Applications
              </Typography>
              <Button
                variant="contained"
                startIcon={<AppIcon />}
                onClick={() => {
                  setOpenCreateApp(true);
                  setIssuedSecret(null);
                  setNewAppName('');
                }}
              >
                Create Application
              </Button>
            </Box>
          </Grid>

          {apps.map((app) => (
            <Grid item xs={12} md={6} key={app.id}>
              <Card variant="outlined">
                <CardHeader
                  avatar={<KeyIcon color="primary" />}
                  title={<Typography variant="subtitle1" fontWeight={600}>{app.name}</Typography>}
                  subheader={`Client ID: ${app.client_id}`}
                  action={
                    <Chip
                      label={app.status}
                      color={app.status === 'ACTIVE' ? 'success' : 'default'}
                      size="small"
                    />
                  }
                />
                <Divider />
                <CardContent>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                    Type: <strong>{app.application_type}</strong>
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                    Approved Scopes:
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {app.scopes.map((s) => (
                      <Chip
                        key={s.scope_name}
                        label={`${s.scope_name} (${s.risk_level})`}
                        size="small"
                        color={s.risk_level === 'HIGH' ? 'warning' : 'primary'}
                        variant="outlined"
                      />
                    ))}
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Tab 1: Marketplace */}
      {activeTab === 1 && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Alert severity="info" sx={{ mb: 2 }}>
              Connectors in the LeadNexus Marketplace undergo automated AST static code analysis, SSRF network validation, and permission sandboxing before publishing.
            </Alert>
          </Grid>
          {marketplaceItems.map((item) => (
            <Grid item xs={12} md={4} key={item.connector_id}>
              <Card variant="outlined" sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                <CardHeader
                  avatar={<ConnectorIcon color="secondary" />}
                  title={<Typography variant="subtitle1" fontWeight={600}>{item.title}</Typography>}
                  subheader={`${item.author} • ${item.category}`}
                  action={
                    item.is_verified ? (
                      <Chip icon={<VerifiedIcon />} label="Official" color="success" size="small" />
                    ) : (
                      <Chip label={item.trust_level} size="small" variant="outlined" />
                    )
                  }
                />
                <Divider />
                <CardContent sx={{ flexGrow: 1 }}>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Rating: ★ <strong>{item.rating}</strong> ({item.download_count} installations)
                  </Typography>
                  <Button variant="outlined" fullWidth color="primary">
                    Install to Workspace
                  </Button>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Tab 2: Connector SDK Sandbox */}
      {activeTab === 2 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={5}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Sandboxed Connector Runner
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Test connector code in an isolated execution sandbox under strict resource limits.
              </Typography>
              <FormControl fullWidth sx={{ mb: 3 }}>
                <InputLabel>Select Connector</InputLabel>
                <Select
                  value={selectedConnector}
                  label="Select Connector"
                  onChange={(e) => setSelectedConnector(e.target.value)}
                >
                  <MenuItem value="public_job_feed_connector">Public Job Feed Connector (Signal Ingestion)</MenuItem>
                  <MenuItem value="webhook_intelligence_exporter">Webhook Intelligence Exporter (Outbound Export)</MenuItem>
                </Select>
              </FormControl>
              <Button
                variant="contained"
                startIcon={<RunIcon />}
                fullWidth
                size="large"
                onClick={handleRunConnector}
              >
                Execute in Sandbox
              </Button>
            </Paper>
          </Grid>

          <Grid item xs={12} md={7}>
            <Paper sx={{ p: 3, bgcolor: '#121212', color: '#00e676', fontFamily: 'monospace' }}>
              <Typography variant="subtitle2" sx={{ color: '#fff', mb: 1, fontFamily: 'sans-serif' }}>
                Sandboxed Execution Logs & Result:
              </Typography>
              <Divider sx={{ bgcolor: '#333', mb: 2 }} />
              {connectorLog.length === 0 ? (
                <Typography variant="body2" sx={{ color: '#888' }}>
                  No active execution. Select a connector and click execute.
                </Typography>
              ) : (
                <Box>
                  {connectorLog.map((line, idx) => (
                    <Box key={idx} sx={{ fontSize: '0.85rem', mb: 0.5 }}>{line}</Box>
                  ))}
                  {executionResult && (
                    <Box sx={{ mt: 2, p: 2, bgcolor: '#1e1e1e', borderRadius: 1, color: '#fff' }}>
                      <pre style={{ margin: 0, fontSize: '0.8rem' }}>
                        {JSON.stringify(executionResult, null, 2)}
                      </pre>
                    </Box>
                  )}
                </Box>
              )}
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* Tab 3: Integration Blueprints */}
      {activeTab === 3 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={4}>
            <Card variant="outlined">
              <CardHeader
                avatar={<TemplateIcon color="primary" />}
                title="Google Sheets Lead Intelligence Sync"
                subheader="Productivity & Spreadsheets"
              />
              <Divider />
              <CardContent>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Pre-packaged blueprint for bi-directional Google Sheets sync with lead ID header and formula escaping.
                </Typography>
                <Button variant="contained" fullWidth>
                  Use Template
                </Button>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={4}>
            <Card variant="outlined">
              <CardHeader
                avatar={<TemplateIcon color="secondary" />}
                title="Slack High-Intent Lead Alerts"
                subheader="Alerts & Notifications"
              />
              <Divider />
              <CardContent>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Dispatches authenticated webhooks to Slack when a verified enterprise lead reaches score &gt; 80.
                </Typography>
                <Button variant="contained" fullWidth>
                  Use Template
                </Button>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={4}>
            <Card variant="outlined">
              <CardHeader
                avatar={<TemplateIcon color="success" />}
                title="Public Job Feed Technology Signals"
                subheader="Signal Ingestion"
              />
              <Divider />
              <CardContent>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Crawls public hiring feeds for ERP technology keywords (Odoo, NetSuite) with grounded evidence extraction.
                </Typography>
                <Button variant="contained" fullWidth>
                  Use Template
                </Button>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Tab 4: Environment Simulator */}
      {activeTab === 4 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={5}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Mock External Provider Simulator
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Simulate external upstream provider responses including rate limits and server errors.
              </Typography>
              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel>Endpoint Type</InputLabel>
                <Select
                  value={simEndpoint}
                  label="Endpoint Type"
                  onChange={(e) => setSimEndpoint(e.target.value)}
                >
                  <MenuItem value="company_enrichment">Company Enrichment API</MenuItem>
                  <MenuItem value="contact_verification">Contact Verification API</MenuItem>
                </Select>
              </FormControl>
              <FormControl fullWidth sx={{ mb: 3 }}>
                <InputLabel>Simulation Mode</InputLabel>
                <Select
                  value={simMode}
                  label="Simulation Mode"
                  onChange={(e) => setSimMode(e.target.value)}
                >
                  <MenuItem value="SUCCESS">200 OK (Healthy Response)</MenuItem>
                  <MenuItem value="RATE_LIMIT">429 Rate Limit (Retry-After: 60)</MenuItem>
                  <MenuItem value="SERVER_ERROR">500 External Upstream Error</MenuItem>
                </Select>
              </FormControl>
              <Button
                variant="contained"
                startIcon={<PlayArrowIcon />}
                fullWidth
                size="large"
                onClick={handleSimulateProvider}
              >
                Send Test Request
              </Button>
            </Paper>
          </Grid>

          <Grid item xs={12} md={7}>
            <Paper sx={{ p: 3, bgcolor: '#1a1a2e', color: '#fff', minHeight: 280 }}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Simulated Response Payload:
              </Typography>
              <Divider sx={{ bgcolor: '#333', mb: 2 }} />
              {simResult ? (
                <pre style={{ margin: 0, fontSize: '0.85rem', color: simResult.status_code === 200 ? '#4caf50' : '#f44336' }}>
                  {JSON.stringify(simResult, null, 2)}
                </pre>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No simulation executed yet.
                </Typography>
              )}
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* Create Application Dialog */}
      <Dialog open={openCreateApp} onClose={() => setOpenCreateApp(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create Developer Application</DialogTitle>
        <DialogContent>
          {issuedSecret ? (
            <Box sx={{ mt: 1 }}>
              <Alert severity="success" sx={{ mb: 2 }}>
                Application successfully created!
              </Alert>
              <Alert severity="warning" sx={{ mb: 2 }}>
                Copy and store your client secret now. It will NEVER be shown again!
              </Alert>
              <TextField
                label="Client Secret"
                value={issuedSecret}
                fullWidth
                InputProps={{
                  readOnly: true,
                  endAdornment: (
                    <IconButton onClick={() => navigator.clipboard.writeText(issuedSecret)}>
                      <CopyIcon />
                    </IconButton>
                  ),
                }}
              />
            </Box>
          ) : (
            <Box sx={{ mt: 1 }}>
              <TextField
                label="Application Name"
                fullWidth
                value={newAppName}
                onChange={(e) => setNewAppName(e.target.value)}
                sx={{ mb: 2 }}
              />
              <FormControl fullWidth>
                <InputLabel>Application Type</InputLabel>
                <Select
                  value={newAppType}
                  label="Application Type"
                  onChange={(e) => setNewAppType(e.target.value)}
                >
                  <MenuItem value="PRIVATE">Private (Single Workspace)</MenuItem>
                  <MenuItem value="INTERNAL">Internal Enterprise Service</MenuItem>
                  <MenuItem value="TENANT_APP">Multi-Tenant Application</MenuItem>
                </Select>
              </FormControl>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          {issuedSecret ? (
            <Button onClick={() => setOpenCreateApp(false)} variant="contained">
              Done
            </Button>
          ) : (
            <>
              <Button onClick={() => setOpenCreateApp(false)}>Cancel</Button>
              <Button onClick={handleCreateApp} variant="contained" disabled={!newAppName}>
                Generate Credentials
              </Button>
            </>
          )}
        </DialogActions>
      </Dialog>
    </Container>
  );
};

function PlayArrowIcon() {
  return <RunIcon />;
}

