import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Tabs,
  Tab,
  Card,
  CardContent,
  Grid,
  Button,
  TextField,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Webhook as WebhookIcon,
  Security as SecurityIcon,
  Replay as ReplayIcon,
  Send as SendIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Refresh as RefreshIcon,
  Delete as DeleteIcon,
  Code as CodeIcon,
} from '@mui/icons-material';

interface WebhookEndpointItem {
  id: string;
  name: string;
  url: string;
  secret_token: string;
  event_patterns: string[];
  is_active: boolean;
  circuit_status: string;
  consecutive_failures: number;
  last_success_at: string | null;
  last_failure_at: string | null;
  created_at: string | null;
}

interface DeliveryItem {
  id: string;
  endpoint_id: string;
  event_id: string;
  event_type: string;
  status: string;
  status_code: number | null;
  execution_duration_ms: number | null;
  attempt_number: number;
  max_retries: number;
  next_retry_at: string | null;
  error_message: string | null;
  created_at: string | null;
}

export const EnterpriseWebhooksWorkspace: React.FC = () => {
  const [activeTab, setActiveTab] = useState<number>(0);
  const [endpoints, setEndpoints] = useState<WebhookEndpointItem[]>([]);
  const [deliveries, setDeliveries] = useState<DeliveryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [alertMsg, setAlertMsg] = useState<{ text: string; severity: 'success' | 'error' | 'info' | 'warning' } | null>(null);

  // New Endpoint Modal
  const [openModal, setOpenModal] = useState<boolean>(false);
  const [newName, setNewName] = useState<string>('ERP Data Receiver');
  const [newUrl, setNewUrl] = useState<string>('https://httpbin.org/post');
  const [newPatterns, setNewPatterns] = useState<string>('company.*, lead.scored');

  // Delivery Detail Modal
  const [selectedDelivery, setSelectedDelivery] = useState<any | null>(null);

  // Verification Tester State
  const [testPayload, setTestPayload] = useState<string>('{\n  "company_id": "comp-123",\n  "name": "Pacific Retails",\n  "technology": "Odoo ERP"\n}');
  const [testSecret, setTestSecret] = useState<string>('whsec_demo_secret_key_1234567890');
  const [testSignature, setTestSignature] = useState<string>('v1=mock_signature_digest');
  const [testTimestamp, setTestTimestamp] = useState<number>(Math.floor(Date.now() / 1000));
  const [testNonce, setTestNonce] = useState<string>('nonce_abc123');
  const [verificationResult, setVerificationResult] = useState<any | null>(null);

  const fetchEndpoints = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/webhooks/endpoints');
      if (res.ok) {
        const data = await res.json();
        setEndpoints(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchDeliveries = async () => {
    try {
      const res = await fetch('/api/v1/webhooks/deliveries?limit=50');
      if (res.ok) {
        const data = await res.json();
        setDeliveries(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchEndpoints();
    fetchDeliveries();
  }, []);

  const handleCreateEndpoint = async () => {
    try {
      const patterns = newPatterns.split(',').map((p) => p.trim()).filter(Boolean);
      const res = await fetch('/api/v1/webhooks/endpoints', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newName,
          url: newUrl,
          event_patterns: patterns,
        }),
      });
      if (res.ok) {
        setAlertMsg({ text: 'Webhook endpoint registered successfully!', severity: 'success' });
        setOpenModal(false);
        fetchEndpoints();
      } else {
        const err = await res.json();
        setAlertMsg({ text: err.detail || 'Failed to create endpoint', severity: 'error' });
      }
    } catch (e: any) {
      setAlertMsg({ text: e.message, severity: 'error' });
    }
  };

  const handlePingEndpoint = async (id: string) => {
    try {
      const res = await fetch(`/api/v1/webhooks/endpoints/${id}/ping`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setAlertMsg({
          text: `Ping dispatched! Status: ${data.status} (HTTP ${data.status_code || 0}) in ${data.execution_duration_ms}ms`,
          severity: data.status === 'SUCCESS' ? 'success' : 'warning',
        });
        fetchDeliveries();
        fetchEndpoints();
      }
    } catch (e: any) {
      setAlertMsg({ text: e.message, severity: 'error' });
    }
  };

  const handleDeleteEndpoint = async (id: string) => {
    try {
      const res = await fetch(`/api/v1/webhooks/endpoints/${id}`, { method: 'DELETE' });
      if (res.ok) {
        setAlertMsg({ text: 'Endpoint deleted.', severity: 'info' });
        fetchEndpoints();
      }
    } catch (e: any) {
      setAlertMsg({ text: e.message, severity: 'error' });
    }
  };

  const handleInspectDelivery = async (id: string) => {
    try {
      const res = await fetch(`/api/v1/webhooks/deliveries/${id}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedDelivery(data);
      }
    } catch (e: any) {
      console.error(e);
    }
  };

  const handleTriggerRedrive = async () => {
    try {
      const res = await fetch('/api/v1/webhooks/redrive', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filter_status: 'DEAD_LETTER', max_attempts: 50 }),
      });
      if (res.ok) {
        const data = await res.json();
        setAlertMsg({
          text: `Redrive job ${data.job_id} launched! Total eligible: ${data.total_eligible}, Succeeded: ${data.success_count}`,
          severity: 'success',
        });
        fetchDeliveries();
        fetchEndpoints();
      }
    } catch (e: any) {
      setAlertMsg({ text: e.message, severity: 'error' });
    }
  };

  const handleVerifyIncoming = async () => {
    try {
      let parsedPayload = {};
      try {
        parsedPayload = JSON.parse(testPayload);
      } catch {
        setAlertMsg({ text: 'Invalid JSON payload format.', severity: 'error' });
        return;
      }

      const res = await fetch('/api/v1/webhooks/verify-incoming', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          payload: parsedPayload,
          secret_token: testSecret,
          signature_header: testSignature,
          timestamp: testTimestamp,
          nonce: testNonce,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setVerificationResult(data);
      }
    } catch (e: any) {
      setAlertMsg({ text: e.message, severity: 'error' });
    }
  };

  return (
    <Box sx={{ p: 4 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <WebhookIcon color="primary" fontSize="large" />
            Enterprise Webhook Delivery Engine
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Phase 35: Cryptographic HMAC-SHA256 Signing, Replay Defense, Circuit Breakers & Dead-Letter Redrive
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button variant="outlined" startIcon={<RefreshIcon />} onClick={() => { fetchEndpoints(); fetchDeliveries(); }}>
            Refresh
          </Button>
          <Button variant="contained" startIcon={<WebhookIcon />} onClick={() => setOpenModal(true)}>
            Register Endpoint
          </Button>
        </Box>
      </Box>

      {alertMsg && (
        <Alert severity={alertMsg.severity} sx={{ mb: 3 }} onClose={() => setAlertMsg(null)}>
          {alertMsg.text}
        </Alert>
      )}

      {/* Tabs */}
      <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)} sx={{ mb: 3, borderBottom: 1, borderColor: 'divider' }}>
        <Tab icon={<WebhookIcon />} iconPosition="start" label="Endpoints & Circuit Status" />
        <Tab icon={<SecurityIcon />} iconPosition="start" label="Signed Delivery Log" />
        <Tab icon={<ReplayIcon />} iconPosition="start" label="Dead-Letter Redrive" />
        <Tab icon={<CodeIcon />} iconPosition="start" label="Signature Tester" />
      </Tabs>

      {/* TAB 0: Endpoints & Circuit Breakers */}
      {activeTab === 0 && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <TableContainer component={Paper} elevation={1}>
              <Table>
                <TableHead sx={{ backgroundColor: 'action.hover' }}>
                  <TableRow>
                    <TableCell><strong>Endpoint Name</strong></TableCell>
                    <TableCell><strong>Destination URL</strong></TableCell>
                    <TableCell><strong>Subscribed Patterns</strong></TableCell>
                    <TableCell><strong>Circuit Status</strong></TableCell>
                    <TableCell><strong>Consecutive Failures</strong></TableCell>
                    <TableCell><strong>Last Success</strong></TableCell>
                    <TableCell align="right"><strong>Actions</strong></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {endpoints.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} align="center" sx={{ py: 3, color: 'text.secondary' }}>
                        No webhook endpoints registered yet. Click "Register Endpoint" to create one.
                      </TableCell>
                    </TableRow>
                  ) : (
                    endpoints.map((ep) => (
                      <TableRow key={ep.id}>
                        <TableCell>
                          <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>{ep.name}</Typography>
                          <Typography variant="caption" color="text.secondary">ID: {ep.id.slice(0, 8)}...</Typography>
                        </TableCell>
                        <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>{ep.url}</TableCell>
                        <TableCell>
                          {ep.event_patterns.map((p) => (
                            <Chip key={p} label={p} size="small" sx={{ mr: 0.5, mb: 0.5 }} />
                          ))}
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={ep.circuit_status}
                            size="small"
                            color={ep.circuit_status === 'CLOSED' ? 'success' : ep.circuit_status === 'HALF_OPEN' ? 'warning' : 'error'}
                          />
                        </TableCell>
                        <TableCell>{ep.consecutive_failures}</TableCell>
                        <TableCell>
                          {ep.last_success_at ? new Date(ep.last_success_at).toLocaleTimeString() : 'Never'}
                        </TableCell>
                        <TableCell align="right">
                          <Tooltip title="Send Signed Ping Event">
                            <IconButton color="primary" onClick={() => handlePingEndpoint(ep.id)}>
                              <SendIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Delete Endpoint">
                            <IconButton color="error" onClick={() => handleDeleteEndpoint(ep.id)}>
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Grid>
        </Grid>
      )}

      {/* TAB 1: Signed Delivery Log */}
      {activeTab === 1 && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <TableContainer component={Paper} elevation={1}>
              <Table>
                <TableHead sx={{ backgroundColor: 'action.hover' }}>
                  <TableRow>
                    <TableCell><strong>Event ID / Type</strong></TableCell>
                    <TableCell><strong>Status</strong></TableCell>
                    <TableCell><strong>HTTP Code</strong></TableCell>
                    <TableCell><strong>Latency</strong></TableCell>
                    <TableCell><strong>Attempt</strong></TableCell>
                    <TableCell><strong>Dispatched At</strong></TableCell>
                    <TableCell align="right"><strong>Inspect Headers</strong></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {deliveries.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} align="center" sx={{ py: 3, color: 'text.secondary' }}>
                        No delivery attempts recorded yet. Dispatched webhooks will stream here.
                      </TableCell>
                    </TableRow>
                  ) : (
                    deliveries.map((d) => (
                      <TableRow key={d.id}>
                        <TableCell>
                          <Typography variant="body2" sx={{ fontWeight: 600 }}>{d.event_type}</Typography>
                          <Typography variant="caption" color="text.secondary">{d.event_id}</Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={d.status}
                            size="small"
                            color={d.status === 'SUCCESS' ? 'success' : d.status === 'RETRYING' ? 'warning' : 'error'}
                          />
                        </TableCell>
                        <TableCell sx={{ fontFamily: 'monospace' }}>{d.status_code || '-'}</TableCell>
                        <TableCell>{d.execution_duration_ms ? `${d.execution_duration_ms}ms` : '-'}</TableCell>
                        <TableCell>{d.attempt_number} / {d.max_retries}</TableCell>
                        <TableCell>{d.created_at ? new Date(d.created_at).toLocaleTimeString() : '-'}</TableCell>
                        <TableCell align="right">
                          <Button size="small" variant="outlined" onClick={() => handleInspectDelivery(d.id)}>
                            Inspect
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Grid>
        </Grid>
      )}

      {/* TAB 2: Dead-Letter Redrive */}
      {activeTab === 2 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card elevation={2}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <ReplayIcon color="primary" />
                  Dead-Letter Queue Redrive
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  Re-dispatches webhooks that exceeded maximum retry attempts back through the delivery engine with fresh HMAC signatures.
                </Typography>
                <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1, mb: 3 }}>
                  <Typography variant="body2"><strong>Filter:</strong> Status = DEAD_LETTER</Typography>
                  <Typography variant="body2"><strong>Max Batch Size:</strong> 50 deliveries</Typography>
                  <Typography variant="body2"><strong>Rate Throttling:</strong> Exponential Backoff with Full Jitter</Typography>
                </Box>
                <Button variant="contained" color="warning" startIcon={<ReplayIcon />} onClick={handleTriggerRedrive}>
                  Execute Batch Redrive
                </Button>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card elevation={2}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <SecurityIcon color="primary" />
                  Replay Attack Defense Architecture
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Every outgoing webhook includes a cryptographic proof consisting of:
                </Typography>
                <Box component="ul" sx={{ pl: 2, fontSize: '0.875rem', color: 'text.secondary' }}>
                  <li><strong>X-LeadNexus-Signature-256:</strong> HMAC-SHA256 digest over timestamp, nonce, and body.</li>
                  <li><strong>X-LeadNexus-Timestamp:</strong> Unix epoch seconds with strict 300s window verification.</li>
                  <li><strong>X-LeadNexus-Nonce:</strong> 128-bit random token cached to reject duplicate delivery replays.</li>
                  <li><strong>Constant-Time Comparison:</strong> Protected against timing oracle attacks via safe equality digest checking.</li>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* TAB 3: Signature Tester */}
      {activeTab === 3 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card elevation={2}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
                  Incoming Webhook Verification Tester
                </Typography>
                <TextField
                  fullWidth
                  label="Payload JSON"
                  multiline
                  rows={4}
                  value={testPayload}
                  onChange={(e) => setTestPayload(e.target.value)}
                  sx={{ mb: 2, fontFamily: 'monospace' }}
                />
                <TextField
                  fullWidth
                  label="Secret Token"
                  value={testSecret}
                  onChange={(e) => setTestSecret(e.target.value)}
                  sx={{ mb: 2 }}
                />
                <TextField
                  fullWidth
                  label="X-LeadNexus-Signature-256 (Header)"
                  value={testSignature}
                  onChange={(e) => setTestSignature(e.target.value)}
                  sx={{ mb: 2 }}
                />
                <Grid container spacing={2} sx={{ mb: 2 }}>
                  <Grid item xs={6}>
                    <TextField
                      fullWidth
                      label="Timestamp (Epoch)"
                      type="number"
                      value={testTimestamp}
                      onChange={(e) => setTestTimestamp(Number(e.target.value))}
                    />
                  </Grid>
                  <Grid item xs={6}>
                    <TextField
                      fullWidth
                      label="Nonce"
                      value={testNonce}
                      onChange={(e) => setTestNonce(e.target.value)}
                    />
                  </Grid>
                </Grid>
                <Button variant="contained" onClick={handleVerifyIncoming}>
                  Verify Signature & Replay Defense
                </Button>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card elevation={2}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
                  Verification Results
                </Typography>
                {verificationResult ? (
                  <Alert severity={verificationResult.is_valid ? 'success' : 'error'} sx={{ mb: 2 }}>
                    {verificationResult.is_valid ? verificationResult.message : verificationResult.error}
                  </Alert>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    Run verification on the left to test signature calculation and nonce cache.
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Modal: Register Endpoint */}
      <Dialog open={openModal} onClose={() => setOpenModal(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Register Enterprise Webhook Endpoint</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Endpoint Name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            sx={{ mt: 2, mb: 2 }}
          />
          <TextField
            fullWidth
            label="Destination URL"
            value={newUrl}
            onChange={(e) => setNewUrl(e.target.value)}
            sx={{ mb: 2 }}
            helperText="Must be an HTTPS endpoint capable of receiving POST payloads."
          />
          <TextField
            fullWidth
            label="Subscribed Event Patterns (comma-separated)"
            value={newPatterns}
            onChange={(e) => setNewPatterns(e.target.value)}
            sx={{ mb: 2 }}
            helperText="Supports wildcards e.g. company.*, lead.scored, evidence.*"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenModal(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleCreateEndpoint}>Register</Button>
        </DialogActions>
      </Dialog>

      {/* Modal: Inspect Delivery */}
      <Dialog open={Boolean(selectedDelivery)} onClose={() => setSelectedDelivery(null)} maxWidth="md" fullWidth>
        <DialogTitle>Webhook Delivery Details</DialogTitle>
        <DialogContent>
          {selectedDelivery && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}><strong>Signed Headers:</strong></Typography>
              <Paper sx={{ p: 2, bgcolor: '#1e1e1e', color: '#4ec9b0', fontFamily: 'monospace', fontSize: '0.8rem', mb: 2 }}>
                <pre style={{ margin: 0 }}>{JSON.stringify(selectedDelivery.headers, null, 2)}</pre>
              </Paper>

              <Typography variant="subtitle2" sx={{ mb: 1 }}><strong>Dispatched Payload:</strong></Typography>
              <Paper sx={{ p: 2, bgcolor: '#1e1e1e', color: '#ce9178', fontFamily: 'monospace', fontSize: '0.8rem', mb: 2 }}>
                <pre style={{ margin: 0 }}>{JSON.stringify(selectedDelivery.payload, null, 2)}</pre>
              </Paper>

              {selectedDelivery.error_message && (
                <Alert severity="warning" sx={{ mt: 1 }}>
                  {selectedDelivery.error_message}
                </Alert>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelectedDelivery(null)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

