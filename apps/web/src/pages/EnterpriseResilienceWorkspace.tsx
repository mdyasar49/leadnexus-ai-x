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
  HealthAndSafety as ResilienceIcon,
  Timer as LeaseIcon,
  ReportProblem as DLQIcon,
  FlashOn as CircuitIcon,
  CloudDownload as BackupIcon,
  Healing as HealingIcon,
  CheckCircle as HealthyIcon,
  Error as DegradedIcon,
  Refresh as RefreshIcon,
  PlayArrow as ActionIcon
} from '@mui/icons-material';

export const EnterpriseResilienceWorkspace: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);

  // DLQ State
  const [dlqItems, setDlqItems] = useState([
    {
      id: 'dlq_msg_101',
      queue: 'research_crawler_tasks',
      task_id: 'task_8829',
      category: 'RATE_LIMIT',
      error: 'Upstream returned 429 Too Many Requests (Retry-After: 60s)',
      status: 'QUARANTINED',
    },
    {
      id: 'dlq_msg_102',
      queue: 'enrichment_worker_tasks',
      task_id: 'task_8834',
      category: 'NETWORK_TRANSIENT',
      error: 'Connection timeout after 30000ms connecting to remote endpoint',
      status: 'QUARANTINED',
    },
  ]);

  // Circuit Breakers
  const [circuits, setCircuits] = useState([
    { service: 'github_public_collector', state: 'CLOSED', failures: 0, cooldown: 30 },
    { service: 'google_sheets_sync_api', state: 'CLOSED', failures: 0, cooldown: 30 },
    { service: 'third_party_career_scraper', state: 'OPEN', failures: 5, cooldown: 30 },
  ]);

  // Self-Healing Result
  const [healingLog, setHealingLog] = useState<string[]>([]);

  const handleRedrive = (id: string) => {
    setDlqItems(dlqItems.map((m) => (m.id === id ? { ...m, status: 'REDRIVEN' } : m)));
  };

  const handleDiscard = (id: string) => {
    setDlqItems(dlqItems.filter((m) => m.id !== id));
  };

  const handleResetCircuit = (service: string) => {
    setCircuits(
      circuits.map((c) => (c.service === service ? { ...c, state: 'CLOSED', failures: 0 } : c))
    );
  };

  const handleRunRemediation = () => {
    setHealingLog([
      `[${new Date().toISOString()}] Scanning active worker leases for heartbeat timeouts...`,
      `[${new Date().toISOString()}] Reaped 1 stale lease on task_8810 (worker_node_3 died)`,
      `[${new Date().toISOString()}] Evaluated 3 circuit breakers; 'third_party_career_scraper' probed into HALF_OPEN`,
      `[${new Date().toISOString()}] Cleaned temporary sandbox run buffers. Remediation complete.`,
    ]);
  };

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 6 }}>
      {/* Platform Header */}
      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
          <ResilienceIcon color="primary" sx={{ fontSize: 36 }} />
          <Typography variant="h4" fontWeight={700}>
            Enterprise Reliability, Resilience & Self-Healing Platform
          </Typography>
          <Chip label="Phase 30 Active" color="primary" variant="outlined" size="small" />
        </Box>
        <Typography variant="body1" color="text.secondary">
          Deep readiness probes, distributed task leases, dead letter queue management, circuit breakers, and self-healing automation.
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
          <Tab icon={<HealthyIcon />} label="System Probes & Health" iconPosition="start" />
          <Tab icon={<LeaseIcon />} label="Distributed Task Leases" iconPosition="start" />
          <Tab icon={<DLQIcon />} label="Dead Letter Queue (DLQ)" iconPosition="start" />
          <Tab icon={<CircuitIcon />} label="Circuit Breakers" iconPosition="start" />
          <Tab icon={<BackupIcon />} label="Disaster Recovery (DR)" iconPosition="start" />
          <Tab icon={<HealingIcon />} label="Self-Healing Automation" iconPosition="start" />
        </Tabs>
      </Paper>

      {/* Tab 0: Probes */}
      {activeTab === 0 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={4}>
            <Card variant="outlined">
              <CardHeader
                avatar={<HealthyIcon color="success" />}
                title="PostgreSQL Primary Database"
                subheader="Active connection pool healthy"
              />
              <Divider />
              <CardContent>
                <Typography variant="h5" fontWeight={700} color="success.main">
                  HEALTHY
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  Latency: 1.8ms • Read/Write active
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card variant="outlined">
              <CardHeader
                avatar={<HealthyIcon color="success" />}
                title="Distributed Worker Cluster"
                subheader="Celery & Redis queue broker"
              />
              <Divider />
              <CardContent>
                <Typography variant="h5" fontWeight={700} color="success.main">
                  HEALTHY
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  4 Worker Nodes online • 0 Queue lag
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card variant="outlined">
              <CardHeader
                avatar={<DegradedIcon color="warning" />}
                title="External Provider Circuits"
                subheader="Cascading failure defense"
              />
              <Divider />
              <CardContent>
                <Typography variant="h5" fontWeight={700} color="warning.main">
                  1 TRIPPED (OPEN)
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  2/3 External services normal
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Tab 1: Task Leases */}
      {activeTab === 1 && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6" fontWeight={600}>
                  Active Task Leases & Fencing Tokens
                </Typography>
                <Button variant="outlined" startIcon={<RefreshIcon />}>
                  Reap Stale Leases
                </Button>
              </Box>
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Task ID</TableCell>
                      <TableCell>Worker Node</TableCell>
                      <TableCell>Fencing Token</TableCell>
                      <TableCell>Heartbeats</TableCell>
                      <TableCell>Expires In</TableCell>
                      <TableCell>Status</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    <TableRow>
                      <TableCell>task_autonomy_crawl_49</TableCell>
                      <TableCell>worker_celery_01</TableCell>
                      <TableCell>14</TableCell>
                      <TableCell>42</TableCell>
                      <TableCell>48s</TableCell>
                      <TableCell><Chip label="ACTIVE" color="success" size="small" /></TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>task_kg_inference_92</TableCell>
                      <TableCell>worker_celery_03</TableCell>
                      <TableCell>3</TableCell>
                      <TableCell>8</TableCell>
                      <TableCell>22s</TableCell>
                      <TableCell><Chip label="ACTIVE" color="success" size="small" /></TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* Tab 2: DLQ */}
      {activeTab === 2 && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Quarantined Dead Letter Messages
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Messages quarantined after exhausting exponential retry policies. Inspect, redrive, or discard.
              </Typography>
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Queue</TableCell>
                      <TableCell>Task ID</TableCell>
                      <TableCell>Error Category</TableCell>
                      <TableCell>Error Message</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell align="right">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {dlqItems.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>{item.queue}</TableCell>
                        <TableCell><code>{item.task_id}</code></TableCell>
                        <TableCell>
                          <Chip
                            label={item.category}
                            color={item.category === 'RATE_LIMIT' ? 'warning' : 'error'}
                            size="small"
                          />
                        </TableCell>
                        <TableCell sx={{ maxWidth: 350 }}>
                          <Typography variant="body2" noWrap>{item.error}</Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={item.status}
                            color={item.status === 'QUARANTINED' ? 'default' : 'primary'}
                            size="small"
                          />
                        </TableCell>
                        <TableCell align="right">
                          <Button
                            size="small"
                            variant="outlined"
                            sx={{ mr: 1 }}
                            onClick={() => handleRedrive(item.id)}
                            disabled={item.status === 'REDRIVEN'}
                          >
                            Redrive
                          </Button>
                          <Button
                            size="small"
                            color="error"
                            onClick={() => handleDiscard(item.id)}
                          >
                            Discard
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* Tab 3: Circuit Breakers */}
      {activeTab === 3 && (
        <Grid container spacing={3}>
          {circuits.map((c) => (
            <Grid item xs={12} md={4} key={c.service}>
              <Card variant="outlined">
                <CardHeader
                  avatar={<CircuitIcon color={c.state === 'OPEN' ? 'error' : 'success'} />}
                  title={c.service}
                  subheader={`Cooldown: ${c.cooldown}s`}
                  action={
                    <Chip
                      label={c.state}
                      color={c.state === 'CLOSED' ? 'success' : 'error'}
                      size="small"
                    />
                  }
                />
                <Divider />
                <CardContent>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Consecutive Failures: <strong>{c.failures}</strong>
                  </Typography>
                  <Button
                    variant="outlined"
                    fullWidth
                    disabled={c.state === 'CLOSED'}
                    onClick={() => handleResetCircuit(c.service)}
                  >
                    Reset Circuit to Closed
                  </Button>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Tab 4: Disaster Recovery */}
      {activeTab === 4 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card variant="outlined">
              <CardHeader
                avatar={<BackupIcon color="primary" />}
                title="Latest Verified Backup Manifest"
                subheader="Cryptographically verified via SHA-256"
              />
              <Divider />
              <CardContent>
                <Typography variant="body2" sx={{ mb: 1 }}>
                  Snapshot: <strong>leadnexus_prod_full_20261031.snap</strong>
                </Typography>
                <Typography variant="body2" sx={{ mb: 1 }}>
                  Records Count: <strong>148,290 verified rows</strong>
                </Typography>
                <Typography variant="caption" sx={{ display: 'block', mb: 2, fontFamily: 'monospace' }}>
                  SHA-256: 4f8b9e11a3d902cb48ef89a19c...
                </Typography>
                <Chip icon={<HealthyIcon />} label="VERIFIED INTEGRITY" color="success" size="small" />
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Tab 5: Self-Healing */}
      {activeTab === 5 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={5}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Self-Healing Engine Remediation
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Executes automated remediation scripts to recover from degraded services, zombie task leases, and circuit trip-outs.
              </Typography>
              <Button
                variant="contained"
                startIcon={<ActionIcon />}
                fullWidth
                size="large"
                onClick={handleRunRemediation}
              >
                Trigger Remediation Pass
              </Button>
            </Paper>
          </Grid>

          <Grid item xs={12} md={7}>
            <Paper sx={{ p: 3, bgcolor: '#121212', color: '#00e676', fontFamily: 'monospace', minHeight: 250 }}>
              <Typography variant="subtitle2" sx={{ color: '#fff', mb: 1, fontFamily: 'sans-serif' }}>
                Self-Healing Engine Execution Logs:
              </Typography>
              <Divider sx={{ bgcolor: '#333', mb: 2 }} />
              {healingLog.length === 0 ? (
                <Typography variant="body2" sx={{ color: '#888' }}>
                  Click 'Trigger Remediation Pass' to execute automated platform healing.
                </Typography>
              ) : (
                healingLog.map((line, idx) => (
                  <Box key={idx} sx={{ fontSize: '0.85rem', mb: 0.5 }}>{line}</Box>
                ))
              )}
            </Paper>
          </Grid>
        </Grid>
      )}
    </Container>
  );
};

