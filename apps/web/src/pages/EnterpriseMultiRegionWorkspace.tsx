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
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  Alert,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Switch,
  FormControlLabel,
  Divider,
} from '@mui/material';
import {
  Public as GlobalIcon,
  Shield as ShieldIcon,
  SwapHoriz as FailoverIcon,
  Speed as LatencyIcon,
  CheckCircle as HealthyIcon,
  Warning as WarningIcon,
  Refresh as RefreshIcon,
  Storage as DbIcon,
  Lock as FencingIcon,
} from '@mui/icons-material';

interface RegionNodeItem {
  id: string;
  name: string;
  cloud_provider: string;
  status: string;
  is_primary_write: boolean;
  latency_ms: number;
  replication_lag_seconds: number;
  last_heartbeat: string | null;
}

export const EnterpriseMultiRegionWorkspace: React.FC = () => {
  const [activeTab, setActiveTab] = useState<number>(0);
  const [nodes, setNodes] = useState<RegionNodeItem[]>([]);
  const [affinity, setAffinity] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [alertMsg, setAlertMsg] = useState<{ text: string; severity: 'success' | 'error' | 'info' | 'warning' } | null>(null);

  // Routing Test state
  const [testMethod, setTestMethod] = useState<string>('POST');
  const [testCountry, setTestCountry] = useState<string>('AU');
  const [routeResult, setRouteResult] = useState<any>(null);

  const fetchNodes = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/multi-region/nodes');
      if (res.ok) {
        const data = await res.json();
        setNodes(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const fetchAffinity = async () => {
    try {
      const res = await fetch('/api/v1/multi-region/tenant-affinity');
      if (res.ok) {
        const data = await res.json();
        setAffinity(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchNodes();
    fetchAffinity();
  }, []);

  const handleFailover = async (sourceId: string, targetId: string) => {
    try {
      const res = await fetch('/api/v1/multi-region/failover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_region_id: sourceId,
          target_region_id: targetId,
          job_type: 'PLANNED_FAILOVER',
          max_allowed_lag_s: 1.0,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setAlertMsg({
          text: `Controlled Failover complete! Target '${data.target_region_id}' promoted to Primary Write. Fencing Token: ${data.split_brain_fence_token}`,
          severity: 'success',
        });
        fetchNodes();
      } else {
        const err = await res.json();
        setAlertMsg({ text: err.detail || 'Failover aborted', severity: 'error' });
      }
    } catch (e: any) {
      setAlertMsg({ text: e.message, severity: 'error' });
    }
  };

  const handleUpdateAffinity = async () => {
    if (!affinity) return;
    try {
      const res = await fetch('/api/v1/multi-region/tenant-affinity', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(affinity),
      });
      if (res.ok) {
        setAlertMsg({ text: 'Data Residency & Sovereignty Policy updated!', severity: 'success' });
      }
    } catch (e: any) {
      setAlertMsg({ text: e.message, severity: 'error' });
    }
  };

  const handleTestRouting = async () => {
    try {
      const res = await fetch('/api/v1/multi-region/routing-decision', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ method: testMethod, client_country: testCountry }),
      });
      if (res.ok) {
        const data = await res.json();
        setRouteResult(data);
      }
    } catch (e: any) {
      console.error(e);
    }
  };

  const primaryNode = nodes.find((n) => n.is_primary_write);
  const replicaNode = nodes.find((n) => !n.is_primary_write);

  return (
    <Box sx={{ p: 4 }}>
      {/* Title */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <GlobalIcon color="primary" fontSize="large" />
            Multi-Region Global Architecture & Active-Active Resilience
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Phase 35 (ChatGPT Master Roadmap): Tenant Region Affinity, PostgreSQL Replication & Split-Brain Prevention
          </Typography>
        </Box>
        <Button variant="outlined" startIcon={<RefreshIcon />} onClick={() => { fetchNodes(); fetchAffinity(); }}>
          Refresh
        </Button>
      </Box>

      {alertMsg && (
        <Alert severity={alertMsg.severity} sx={{ mb: 3 }} onClose={() => setAlertMsg(null)}>
          {alertMsg.text}
        </Alert>
      )}

      {/* Tabs */}
      <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)} sx={{ mb: 3, borderBottom: 1, borderColor: 'divider' }}>
        <Tab icon={<DbIcon />} iconPosition="start" label="Global Topology & Primary Write" />
        <Tab icon={<ShieldIcon />} iconPosition="start" label="Data Residency & Sovereignty" />
        <Tab icon={<FailoverIcon />} iconPosition="start" label="Controlled Failover & Failback" />
        <Tab icon={<LatencyIcon />} iconPosition="start" label="Traffic Router Simulator" />
      </Tabs>

      {/* TAB 0: Global Topology */}
      {activeTab === 0 && (
        <Grid container spacing={3}>
          {nodes.map((node) => (
            <Grid item xs={12} md={6} key={node.id}>
              <Card elevation={node.is_primary_write ? 4 : 1} sx={{
                border: node.is_primary_write ? '2px solid #0284c7' : '1px solid #e2e8f0',
                bgcolor: 'background.paper',
              }}>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                    <Box>
                      <Typography variant="h6" sx={{ fontWeight: 700 }}>{node.name}</Typography>
                      <Typography variant="caption" color="text.secondary">Region ID: {node.id}</Typography>
                    </Box>
                    <Chip
                      label={node.is_primary_write ? 'AUTHORIZED WRITE PRIMARY' : 'READ REPLICA'}
                      color={node.is_primary_write ? 'primary' : 'default'}
                      size="small"
                      sx={{ fontWeight: 700 }}
                    />
                  </Box>

                  <Box sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 1, mb: 2 }}>
                    <Typography variant="body2"><strong>Cloud Provider:</strong> {node.cloud_provider}</Typography>
                    <Typography variant="body2">
                      <strong>Replication Lag:</strong> {node.replication_lag_seconds}s ({node.replication_lag_seconds < 0.2 ? 'Sync Optimal' : 'Catching Up'})
                    </Typography>
                    <Typography variant="body2"><strong>p99 Latency:</strong> {node.latency_ms}ms</Typography>
                    <Typography variant="body2"><strong>Status:</strong> {node.status}</Typography>
                  </Box>

                  <Typography variant="caption" color="text.secondary">
                    {node.is_primary_write
                      ? 'Strict Single Primary: All PostgreSQL write transactions (INSERT, UPDATE, DELETE) are serialized here.'
                      : 'Asynchronous streaming replication from primary with automatic failover eligibility.'}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}

          <Grid item xs={12}>
            <Alert severity="info" icon={<FencingIcon />}>
              <strong>Split-Brain Prevention Invariant:</strong> The platform enforces exactly ONE authorized write region at any time. Monotonic cryptographic epoch fencing tokens prevent split-brain dual-primary writes during network partitions.
            </Alert>
          </Grid>
        </Grid>
      )}

      {/* TAB 1: Data Residency & Sovereignty */}
      {activeTab === 1 && affinity && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card elevation={2}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <ShieldIcon color="primary" />
                  Tenant Data Residency Policy
                </Typography>

                <Box sx={{ mb: 3 }}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Data Residency Requirement</InputLabel>
                    <Select
                      value={affinity.data_residency_requirement}
                      label="Data Residency Requirement"
                      onChange={(e) => setAffinity({ ...affinity, data_residency_requirement: e.target.value })}
                    >
                      <MenuItem value="AU_ONLY">AU_ONLY (Strict Australian Privacy Principles compliance)</MenuItem>
                      <MenuItem value="APAC">APAC (Asia-Pacific Region)</MenuItem>
                      <MenuItem value="GLOBAL">GLOBAL (Multi-Region Replication)</MenuItem>
                    </Select>
                  </FormControl>
                </Box>

                <Box sx={{ mb: 3 }}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={affinity.strict_sovereignty_enforced}
                        onChange={(e) => setAffinity({ ...affinity, strict_sovereignty_enforced: e.target.checked })}
                        color="primary"
                      />
                    }
                    label="Strict Sovereignty Enforcement (Reject foreign failover)"
                  />
                  <Typography variant="caption" color="text.secondary" display="block">
                    When active, Australian lead data is strictly prohibited from leaving Australian boundaries (ap-southeast-2 Sydney).
                  </Typography>
                </Box>

                <Button variant="contained" onClick={handleUpdateAffinity}>
                  Save Sovereignty Policy
                </Button>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card elevation={2}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
                  Australian Sovereignty Guarantee
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  LeadNexus AI X is designed to satisfy Australian Privacy Principles (APPs) and Privacy Act 1988 guidelines for enterprise clients:
                </Typography>
                <Box component="ul" sx={{ pl: 2, fontSize: '0.875rem', color: 'text.secondary' }}>
                  <li><strong>Data at Rest:</strong> Pinned to Sydney (ap-southeast-2) with encrypted EBS volumes (AES-256-GCM).</li>
                  <li><strong>Data in Transit:</strong> TLS 1.3 enforced over internal cross-region replication tunnels.</li>
                  <li><strong>Failover Safeguard:</strong> Failover to Singapore or US is hard-blocked if AU_ONLY is locked.</li>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* TAB 2: Controlled Failover */}
      {activeTab === 2 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card elevation={2}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <FailoverIcon color="primary" />
                  Execute Controlled Cutover
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  Promotes the standby read replica into the active write primary while draining in-flight writes on the source.
                </Typography>

                {primaryNode && replicaNode ? (
                  <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1, mb: 3 }}>
                    <Typography variant="body2"><strong>Current Primary:</strong> {primaryNode.name} ({primaryNode.id})</Typography>
                    <Typography variant="body2"><strong>Promote Target:</strong> {replicaNode.name} ({replicaNode.id})</Typography>
                    <Typography variant="body2"><strong>Target Replication Lag:</strong> {replicaNode.replication_lag_seconds}s (Must be &lt; 1.0s)</Typography>
                  </Box>
                ) : null}

                <Button
                  variant="contained"
                  color="warning"
                  startIcon={<FailoverIcon />}
                  onClick={() => {
                    if (primaryNode && replicaNode) {
                      handleFailover(primaryNode.id, replicaNode.id);
                    }
                  }}
                >
                  Initiate Planned Failover (Zero Data Loss)
                </Button>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card elevation={2}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
                  Pre-Flight Safety Gates
                </Typography>
                <Box component="ul" sx={{ pl: 2, fontSize: '0.875rem', color: 'text.secondary' }}>
                  <li><strong>Replication Lag Gate:</strong> Failover is automatically aborted if lag &gt; 1.0s.</li>
                  <li><strong>Source Draining:</strong> Old primary drops write lease and flushes outbox events.</li>
                  <li><strong>Fencing Token Promotion:</strong> Epoch token monotonically increments.</li>
                  <li><strong>DNS / Cloudflare Cutover:</strong> Write traffic re-routed in &lt; 3.0 seconds.</li>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* TAB 3: Traffic Router Simulator */}
      {activeTab === 3 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card elevation={2}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
                  Global Traffic Management (GTM) Simulator
                </Typography>
                <Box sx={{ mb: 2 }}>
                  <FormControl fullWidth size="small">
                    <InputLabel>HTTP Method</InputLabel>
                    <Select value={testMethod} label="HTTP Method" onChange={(e) => setTestMethod(e.target.value)}>
                      <MenuItem value="POST">POST (Write Transaction)</MenuItem>
                      <MenuItem value="PUT">PUT (Write Transaction)</MenuItem>
                      <MenuItem value="GET">GET (Read Query)</MenuItem>
                    </Select>
                  </FormControl>
                </Box>
                <Box sx={{ mb: 2 }}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Client Country Origin</InputLabel>
                    <Select value={testCountry} label="Client Country Origin" onChange={(e) => setTestCountry(e.target.value)}>
                      <MenuItem value="AU">Australia (Sydney Client)</MenuItem>
                      <MenuItem value="NZ">New Zealand</MenuItem>
                      <MenuItem value="SG">Singapore (Asia Client)</MenuItem>
                      <MenuItem value="US">United States</MenuItem>
                    </Select>
                  </FormControl>
                </Box>
                <Button variant="contained" onClick={handleTestRouting}>
                  Evaluate Route Decision
                </Button>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card elevation={2}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
                  Routing Verdict
                </Typography>
                {routeResult ? (
                  <Box>
                    <Alert severity={routeResult.sovereignty_compliant ? 'success' : 'error'} sx={{ mb: 2 }}>
                      {routeResult.sovereignty_compliant
                        ? `Routed to Region: ${routeResult.target_region_id}`
                        : routeResult.error}
                    </Alert>
                    <Typography variant="body2"><strong>Route Type:</strong> {routeResult.route_type}</Typography>
                    <Typography variant="body2"><strong>Write Operation:</strong> {routeResult.is_write ? 'Yes' : 'No'}</Typography>
                    {routeResult.fencing_token && (
                      <Typography variant="body2"><strong>Fencing Token:</strong> {routeResult.fencing_token}</Typography>
                    )}
                  </Box>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    Click "Evaluate Route Decision" to test GTM behavior.
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
    </Box>
  );
};

