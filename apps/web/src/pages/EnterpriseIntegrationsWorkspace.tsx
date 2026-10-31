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
  CircularProgress,
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
  Hub as IntegrationIcon,
  Cable as ConnectIcon,
  Transform as MappingIcon,
  TableChart as SheetsIcon,
  Webhook as WebhookIcon,
  VpnKey as KeyIcon,
  Warning as ConflictIcon,
  CheckCircle as SuccessIcon,
  Refresh as SyncIcon,
  PlayArrow as TestIcon,
  Security as SecurityIcon,
  Layers as CatalogIcon
} from '@mui/icons-material';

interface ProviderItem {
  provider_id: string;
  name: string;
  category: string;
  version: string;
  capabilities: string[];
  authentication_type: string;
  is_enabled: boolean;
}

interface ConnectionItem {
  id: string;
  provider_id: string;
  name: string;
  status: 'CONNECTED' | 'DISCONNECTED' | 'ERROR';
  auth_type: string;
  last_health_check?: string;
}

export const EnterpriseIntegrationsWorkspace: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [newKeyDialogOpen, setNewKeyDialogOpen] = useState(false);
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);

  // Providers Catalog
  const providers: ProviderItem[] = [
    {
      provider_id: 'google_sheets',
      name: 'Google Sheets Workbook Sync',
      category: 'PRODUCTIVITY',
      version: '1.2.0',
      capabilities: ['IMPORT', 'EXPORT', 'SYNC'],
      authentication_type: 'OAUTH2',
      is_enabled: true
    },
    {
      provider_id: 'github',
      name: 'GitHub Public Repository & Org Connector',
      category: 'DEVELOPMENT',
      version: '2.0.0',
      capabilities: ['SEARCH', 'IMPORT', 'WEBHOOK'],
      authentication_type: 'API_KEY',
      is_enabled: true
    },
    {
      provider_id: 'slack_notifications',
      name: 'Slack Operational Incident Alerts',
      category: 'COMMUNICATION',
      version: '1.0.0',
      capabilities: ['EXPORT', 'WEBHOOK'],
      authentication_type: 'WEBHOOK_SIGNATURE',
      is_enabled: true
    },
    {
      provider_id: 'teams_notifications',
      name: 'Microsoft Teams Operations Connector',
      category: 'COMMUNICATION',
      version: '1.0.0',
      capabilities: ['EXPORT', 'WEBHOOK'],
      authentication_type: 'WEBHOOK_SIGNATURE',
      is_enabled: true
    },
    {
      provider_id: 'email_verification_provider',
      name: 'Authorized Email Verification Engine',
      category: 'VERIFICATION',
      version: '1.5.0',
      capabilities: ['VERIFY', 'BATCH'],
      authentication_type: 'API_KEY',
      is_enabled: true
    },
    {
      provider_id: 'job_feed_connector',
      name: 'Public Career & Job Feed Connector',
      category: 'DATA_SOURCE',
      version: '1.1.0',
      capabilities: ['IMPORT', 'STREAM'],
      authentication_type: 'NONE',
      is_enabled: true
    }
  ];

  // Active Connections
  const [connections, setConnections] = useState<ConnectionItem[]>([
    {
      id: 'conn_1',
      provider_id: 'google_sheets',
      name: 'Odoo Enterprise Leads Sheet',
      status: 'CONNECTED',
      auth_type: 'OAUTH2',
      last_health_check: 'Just now'
    },
    {
      id: 'conn_2',
      provider_id: 'github',
      name: 'OCA Public Repository Telemetry',
      status: 'CONNECTED',
      auth_type: 'API_KEY',
      last_health_check: '5 mins ago'
    },
    {
      id: 'conn_3',
      provider_id: 'slack_notifications',
      name: 'Security & Operations Alerts Channel',
      status: 'CONNECTED',
      auth_type: 'WEBHOOK_SIGNATURE',
      last_health_check: '12 mins ago'
    }
  ]);

  // Field Mappings Sample
  const [fieldMappings, setFieldMappings] = useState([
    { source: 'Company Legal Name', target: 'name', rule: 'TRIM' },
    { source: 'Corporate Web URL', target: 'domain', rule: 'NORMALIZE_DOMAIN' },
    { source: 'HQ Country Code', target: 'country', rule: 'NORMALIZE_COUNTRY' },
    { source: 'Primary Contact Email', target: 'email', rule: 'NORMALIZE_EMAIL' },
    { source: 'Detected ERP System', target: 'primary_erp', rule: 'UPPERCASE' }
  ]);

  // Conflicts Sample
  const [conflicts, setConflicts] = useState([
    {
      id: 'cnf_101',
      entity: 'Company: OmniRetail Solutions',
      field: 'primary_domain',
      canonical: 'omniretail.com.au',
      external: 'omniretail.com',
      source: 'Google Sheets Row 42',
      resolution: 'KEEP_CANONICAL'
    }
  ]);

  const handleTestConnection = (connName: string) => {
    setTestResult(`Connection test for '${connName}' succeeded. Latency: 14ms (HTTP 200 OK).`);
  };

  const handleGenerateKey = () => {
    setGeneratedKey('lnx_live_8f93ab21e9047b8c2df149b083e911c470dae23');
    setNewKeyDialogOpen(true);
  };

  return (
    <Container maxWidth="xl" sx={{ mt: 3, mb: 6 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
        <IntegrationIcon sx={{ fontSize: 38, color: 'primary.main', mr: 2 }} />
        <Box>
          <Typography variant="h4" fontWeight="bold">
            Enterprise Integrations, API Ecosystem & Connectivity
          </Typography>
          <Typography variant="body2" color="text.secondary">
            LeadNexus AI X — PostgreSQL Canonical Source of Truth | External Adapters | Safe Synchronization & Webhooks
          </Typography>
        </Box>
      </Box>

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs value={activeTab} onChange={(_, val) => setActiveTab(val)}>
          <Tab icon={<ConnectIcon />} label={`Connections (${connections.length})`} iconPosition="start" />
          <Tab icon={<CatalogIcon />} label="Provider Catalog" iconPosition="start" />
          <Tab icon={<MappingIcon />} label="Data Mapping & Transforms" iconPosition="start" />
          <Tab icon={<SheetsIcon />} label="Google Sheets Sync" iconPosition="start" />
          <Tab icon={<ConflictIcon />} label={`Conflicts & Review (${conflicts.length})`} iconPosition="start" />
          <Tab icon={<WebhookIcon />} label="Webhooks & API Keys" iconPosition="start" />
        </Tabs>
      </Box>

      {testResult && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={() => setTestResult(null)}>
          {testResult}
        </Alert>
      )}

      {/* Tab 0: Active Connections */}
      {activeTab === 0 && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6" fontWeight="bold">Configured Workspace Connections</Typography>
            <Button variant="contained" startIcon={<ConnectIcon />}>Add Connection</Button>
          </Box>
          <Grid container spacing={2}>
            {connections.map(c => (
              <Grid item xs={12} md={4} key={c.id}>
                <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                  <CardHeader
                    title={c.name}
                    subheader={`Provider: ${c.provider_id}`}
                    action={
                      <Chip
                        label={c.status}
                        color={c.status === 'CONNECTED' ? 'success' : 'error'}
                        size="small"
                      />
                    }
                  />
                  <Divider />
                  <CardContent>
                    <Typography variant="body2" color="text.secondary">
                      Auth Type: <strong>{c.auth_type}</strong>
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Last Check: {c.last_health_check}
                    </Typography>
                    <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<TestIcon />}
                        onClick={() => handleTestConnection(c.name)}
                      >
                        Health Test
                      </Button>
                      <Button size="small" variant="text" color="primary">Configure</Button>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* Tab 1: Provider Catalog */}
      {activeTab === 1 && (
        <Grid container spacing={2}>
          {providers.map(p => (
            <Grid item xs={12} md={4} key={p.provider_id}>
              <Card sx={{ height: '100%' }}>
                <CardHeader
                  title={p.name}
                  subheader={`Category: ${p.category} | v${p.version}`}
                  action={<Chip label={p.authentication_type} size="small" variant="outlined" />}
                />
                <Divider />
                <CardContent>
                  <Typography variant="caption" color="text.secondary" fontWeight="bold">Capabilities:</Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5, mb: 2 }}>
                    {p.capabilities.map((cap, i) => (
                      <Chip key={i} label={cap} size="small" color="primary" variant="outlined" />
                    ))}
                  </Box>
                  <Button variant="outlined" size="small" fullWidth startIcon={<ConnectIcon />}>
                    Connect Provider
                  </Button>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Tab 2: Schema Mapping & Transformations */}
      {activeTab === 2 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" fontWeight="bold" gutterBottom>
            Schema Mapping & Field Transformations
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            Safely map external system column names to canonical LeadNexus entity attributes. Strict deterministic rules with zero code execution.
          </Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell><strong>External Field Name</strong></TableCell>
                  <TableCell><strong>Canonical Field (LeadNexus)</strong></TableCell>
                  <TableCell><strong>Transformation Rule</strong></TableCell>
                  <TableCell><strong>Action</strong></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {fieldMappings.map((m, idx) => (
                  <TableRow key={idx}>
                    <TableCell>{m.source}</TableCell>
                    <TableCell><Chip label={m.target} size="small" color="primary" variant="outlined" /></TableCell>
                    <TableCell><Chip label={m.rule} size="small" color="secondary" /></TableCell>
                    <TableCell><Button size="small" color="error">Remove</Button></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {/* Tab 3: Google Sheets Sync Preview */}
      {activeTab === 3 && (
        <Paper sx={{ p: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Box>
              <Typography variant="h6" fontWeight="bold">Google Sheets Bidirectional Synchronization</Typography>
              <Typography variant="body2" color="text.secondary">
                Google Sheets is an authorized external adapter. Database values remain the canonical source of truth.
              </Typography>
            </Box>
            <Button variant="contained" color="success" startIcon={<SyncIcon />}>
              Run Sync Preview
            </Button>
          </Box>
          <Alert severity="info" sx={{ mb: 2 }}>
            Row identity is anchored to stable <code>leadnexus_id</code>. Formula injection protection active on all exports.
          </Alert>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>leadnexus_id</TableCell>
                  <TableCell>company_name</TableCell>
                  <TableCell>primary_domain</TableCell>
                  <TableCell>odoo_version</TableCell>
                  <TableCell>decision_maker_name</TableCell>
                  <TableCell>sync_status</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                <TableRow>
                  <TableCell><code>lnx_7194a2b1</code></TableCell>
                  <TableCell>OmniRetail Solutions Pty Ltd</TableCell>
                  <TableCell>omniretail.com.au</TableCell>
                  <TableCell>17.0 Enterprise</TableCell>
                  <TableCell>Marcus Vance (CTO)</TableCell>
                  <TableCell><Chip label="IN_SYNC" color="success" size="small" /></TableCell>
                </TableRow>
                <TableRow>
                  <TableCell><code>lnx_8831ef09</code></TableCell>
                  <TableCell>Pacific Logix Corp</TableCell>
                  <TableCell>pacificlogix.com.au</TableCell>
                  <TableCell>16.0 Community</TableCell>
                  <TableCell>David Miller (Head of IT)</TableCell>
                  <TableCell><Chip label="IN_SYNC" color="success" size="small" /></TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {/* Tab 4: Conflicts & Review */}
      {activeTab === 4 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" fontWeight="bold" gutterBottom>
            Synchronization Conflicts & Resolution
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            External systems cannot silently overwrite canonical data. Default rule: <strong>Database Wins (KEEP_CANONICAL)</strong>.
          </Typography>
          {conflicts.map(c => (
            <Card key={c.id} sx={{ mb: 2, borderLeft: '4px solid #ff9800' }}>
              <CardContent>
                <Typography variant="subtitle1" fontWeight="bold">{c.entity}</Typography>
                <Typography variant="body2">Conflicting Field: <strong>{c.field}</strong> | Source: {c.source}</Typography>
                <Box sx={{ mt: 1, p: 1.5, bgcolor: 'background.default', borderRadius: 1 }}>
                  <Typography variant="body2">Canonical Database: <code>{c.canonical}</code></Typography>
                  <Typography variant="body2">External Source: <code>{c.external}</code></Typography>
                </Box>
                <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
                  <Button size="small" variant="contained" color="primary">Keep Canonical (Default)</Button>
                  <Button size="small" variant="outlined" color="warning">Accept External</Button>
                  <Button size="small" variant="outlined">Merge</Button>
                </Box>
              </CardContent>
            </Card>
          ))}
        </Paper>
      )}

      {/* Tab 5: Webhooks & API Keys */}
      {activeTab === 5 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight="bold" gutterBottom>
                Outbound Webhook Endpoints
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                HMAC-SHA256 signed payloads with 5-minute replay drift protection and automatic retry backoff.
              </Typography>
              <Button variant="outlined" startIcon={<WebhookIcon />} sx={{ mb: 2 }}>
                Register Endpoint
              </Button>
              <Card sx={{ bgcolor: 'background.default' }}>
                <CardContent>
                  <Typography variant="subtitle2" fontWeight="bold">https://ops.omniretail.com.au/webhooks/leadnexus</Typography>
                  <Typography variant="caption" color="text.secondary">Events: RESEARCH_COMPLETED, LEAD_SCORE_CHANGED</Typography>
                  <Box sx={{ mt: 1 }}>
                    <Chip label="ACTIVE" color="success" size="small" />
                    <Chip label="HMAC-SHA256" size="small" sx={{ ml: 1 }} />
                  </Box>
                </CardContent>
              </Card>
            </Paper>
          </Grid>
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight="bold" gutterBottom>
                API Key Management
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                Machine-to-machine scoped keys. Secrets are hashed using SHA-256 and never returned after creation.
              </Typography>
              <Button variant="contained" startIcon={<KeyIcon />} onClick={handleGenerateKey} sx={{ mb: 2 }}>
                Generate API Key
              </Button>
              <Card sx={{ bgcolor: 'background.default' }}>
                <CardContent>
                  <Typography variant="subtitle2" fontWeight="bold">Production BI Reader Key (lnx_live_8f93...)</Typography>
                  <Typography variant="caption" color="text.secondary">Scopes: companies:read, leads:read, research:read</Typography>
                  <Box sx={{ mt: 1 }}>
                    <Chip label="ACTIVE" color="success" size="small" />
                    <Chip label="Expires in 30 days" size="small" sx={{ ml: 1 }} />
                  </Box>
                </CardContent>
              </Card>
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* Key Generation Dialog */}
      <Dialog open={newKeyDialogOpen} onClose={() => setNewKeyDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>API Key Generated</DialogTitle>
        <DialogContent dividers>
          <Alert severity="warning" sx={{ mb: 2 }}>
            Save this key now. It will not be shown again!
          </Alert>
          <Typography variant="caption" color="text.secondary">Plaintext API Key:</Typography>
          <Paper sx={{ p: 1.5, mt: 0.5, bgcolor: 'background.default', fontFamily: 'monospace', wordBreak: 'break-all' }}>
            {generatedKey}
          </Paper>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setNewKeyDialogOpen(false)} variant="contained">Done</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default EnterpriseIntegrationsWorkspace;

