import React, { useState } from 'react';
import {
  Box,
  Typography,
  Tabs,
  Tab,
  Paper,
  Grid,
  Card,
  CardContent,
  Button,
  TextField,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  LinearProgress,
  Alert,
  IconButton,
  Tooltip,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
} from '@mui/material';
import {
  HeartPulse,
  Play,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  RefreshCw,
  Search,
  Activity,
  Zap,
  Sliders,
  History,
  Clock,
  Server,
  Layers,
  Flame,
} from 'lucide-react';

interface IncidentItem {
  id: string;
  metric_name: string;
  trigger_value: number;
  threshold: number;
  status: string;
  severity: string;
  assigned_playbook_id: string;
  started_at: string;
  resolved_at?: string;
}

interface PlaybookItem {
  id: string;
  name: string;
  action_type: string;
  target_subsystem: string;
  description: string;
  cooldown_seconds: number;
  max_per_hour: number;
  is_enabled: boolean;
}

interface ExecutionAuditItem {
  id: string;
  incident_id: string;
  action_type: string;
  target_subsystem: string;
  pre_metric_value: number;
  post_metric_value: number;
  outcome: string;
  executed_at: string;
}

const INITIAL_INCIDENTS: IncidentItem[] = [
  {
    id: 'inc-99120',
    metric_name: 'api.request.latency',
    trigger_value: 1850.0,
    threshold: 1500.0,
    status: 'RESOLVED',
    severity: 'WARNING',
    assigned_playbook_id: 'pb-throttle-ingress',
    started_at: '2026-11-01 12:10:00',
    resolved_at: '2026-11-01 12:10:45',
  },
  {
    id: 'inc-99121',
    metric_name: 'model.upstream.error',
    trigger_value: 0.14,
    threshold: 0.05,
    status: 'RESOLVED',
    severity: 'CRITICAL',
    assigned_playbook_id: 'pb-failover-provider',
    started_at: '2026-11-01 12:45:10',
    resolved_at: '2026-11-01 12:45:32',
  },
  {
    id: 'inc-99122',
    metric_name: 'worker.pool.stalled',
    trigger_value: 1.0,
    threshold: 0.0,
    status: 'DETECTED',
    severity: 'WARNING',
    assigned_playbook_id: 'pb-restart-worker',
    started_at: '2026-11-01 13:12:00',
  },
];

const INITIAL_PLAYBOOKS: PlaybookItem[] = [
  {
    id: 'pb-restart-worker',
    name: 'Worker Pool Slot Recycling',
    action_type: 'RESTART_WORKER',
    target_subsystem: 'worker_pool',
    description: 'Recycles stalled worker execution slots without dropping queued tasks.',
    cooldown_seconds: 180,
    max_per_hour: 6,
    is_enabled: true,
  },
  {
    id: 'pb-flush-cache',
    name: 'Redis Transient Key Purge',
    action_type: 'FLUSH_CACHE',
    target_subsystem: 'cache_redis',
    description: 'Evicts volatile cached query responses when memory usage crosses 85%.',
    cooldown_seconds: 300,
    max_per_hour: 4,
    is_enabled: true,
  },
  {
    id: 'pb-failover-provider',
    name: 'Cascading AI Provider Failover',
    action_type: 'FAILOVER_PROVIDER',
    target_subsystem: 'model_router',
    description: 'Reroutes inference requests to secondary fallback AI models during upstream 5xx errors.',
    cooldown_seconds: 120,
    max_per_hour: 10,
    is_enabled: true,
  },
  {
    id: 'pb-throttle-ingress',
    name: 'Adaptive Ingress Concurrency Shedding',
    action_type: 'THROTTLE_INGRESS',
    target_subsystem: 'api_gateway',
    description: 'Temporarily reduces non-critical background traffic during latency spikes.',
    cooldown_seconds: 240,
    max_per_hour: 5,
    is_enabled: true,
  },
  {
    id: 'pb-reset-circuit',
    name: 'Circuit Breaker Probe Reset',
    action_type: 'RESET_CIRCUIT',
    target_subsystem: 'circuit_breaker',
    description: 'Transitions open circuit breakers to HALF_OPEN to test downstream dependency recovery.',
    cooldown_seconds: 120,
    max_per_hour: 8,
    is_enabled: true,
  },
];

const INITIAL_EXECUTIONS: ExecutionAuditItem[] = [
  {
    id: 'exec-001',
    incident_id: 'inc-99120',
    action_type: 'THROTTLE_INGRESS',
    target_subsystem: 'api_gateway',
    pre_metric_value: 1850.0,
    post_metric_value: 975.0,
    outcome: 'SUCCESS',
    executed_at: '2026-11-01 12:10:15',
  },
  {
    id: 'exec-002',
    incident_id: 'inc-99121',
    action_type: 'FAILOVER_PROVIDER',
    target_subsystem: 'model_router',
    pre_metric_value: 0.14,
    post_metric_value: 0.01,
    outcome: 'SUCCESS',
    executed_at: '2026-11-01 12:45:20',
  },
];

export const EnterpriseSelfHealingWorkspace: React.FC = () => {
  const [tabIndex, setTabIndex] = useState<number>(0);
  const [incidents, setIncidents] = useState<IncidentItem[]>(INITIAL_INCIDENTS);
  const [playbooks, setPlaybooks] = useState<PlaybookItem[]>(INITIAL_PLAYBOOKS);
  const [executions, setExecutions] = useState<ExecutionAuditItem[]>(INITIAL_EXECUTIONS);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Trigger Action Dialog
  const [selectedPlaybook, setSelectedPlaybook] = useState<PlaybookItem | null>(null);
  const [openTriggerDialog, setOpenTriggerDialog] = useState<boolean>(false);

  const handleExecutePlaybook = (pb: PlaybookItem) => {
    setSelectedPlaybook(pb);
    setOpenTriggerDialog(true);
  };

  const handleConfirmPlaybookExecution = () => {
    if (!selectedPlaybook) return;

    const newExec: ExecutionAuditItem = {
      id: `exec-${Date.now().toString(36)}`,
      incident_id: 'manual-trigger',
      action_type: selectedPlaybook.action_type,
      target_subsystem: selectedPlaybook.target_subsystem,
      pre_metric_value: 120.0,
      post_metric_value: 45.0,
      outcome: 'SUCCESS',
      executed_at: new Date().toISOString().replace('T', ' ').substring(0, 19),
    };

    setExecutions([newExec, ...executions]);
    setOpenTriggerDialog(false);
    setSuccessMsg(`Playbook "${selectedPlaybook.name}" dispatched successfully! Post-metric verified.`);
  };

  const handleResolveIncident = (incId: string) => {
    setIncidents(
      incidents.map((i) =>
        i.id === incId
          ? { ...i, status: 'RESOLVED', resolved_at: new Date().toISOString().replace('T', ' ').substring(0, 19) }
          : i
      )
    );
    setSuccessMsg(`Incident ${incId} resolved and verified.`);
  };

  const handleEscalateIncident = (incId: string) => {
    setIncidents(incidents.map((i) => (i.id === incId ? { ...i, status: 'ESCALATED' } : i)));
    setSuccessMsg(`Incident ${incId} escalated to SRE duty engineer.`);
  };

  return (
    <Box sx={{ p: 4, maxWidth: 1440, margin: '0 auto' }}>
      {/* Header */}
      <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
            <HeartPulse size={28} color="#0284c7" />
            <Typography variant="h4" sx={{ fontWeight: 700, color: '#0f172a' }}>
              Self-Healing, Auto-Remediation & Reliability Engineering
            </Typography>
            <Chip label="Phase 45" color="primary" size="small" sx={{ fontWeight: 600 }} />
          </Box>
          <Typography variant="body1" sx={{ color: '#64748b' }}>
            Automated anomaly incident detection, approved self-healing playbooks, blast radius safety limits,
            and post-remediation verification.
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="outlined"
            startIcon={<RefreshCw size={16} />}
            onClick={() => setSuccessMsg('Reliability metrics and incident queue refreshed.')}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<Flame size={16} />}
            onClick={() => setTabIndex(1)}
            sx={{ bgcolor: '#0284c7', '&:hover': { bgcolor: '#0369a1' } }}
          >
            Playbook Catalog
          </Button>
        </Box>
      </Box>

      {/* Primary Invariant Banner */}
      <Alert severity="info" sx={{ mb: 3, border: '1px solid #bae6fd', bgcolor: '#f0f9ff' }}>
        <strong>Invariant Rule Enforced:</strong> Automated self-healing remediations, worker restarts, and provider failovers
        operate in strictly isolated infrastructure sandboxes and <strong>never</strong> purge, modify, or pollute canonical Saved Leads or Export records.
      </Alert>

      {successMsg && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={() => setSuccessMsg(null)}>
          {successMsg}
        </Alert>
      )}

      {/* Navigation Tabs */}
      <Paper sx={{ mb: 3, borderRadius: 2 }} elevation={1}>
        <Tabs
          value={tabIndex}
          onChange={(_, val) => setTabIndex(val)}
          variant="scrollable"
          scrollButtons="auto"
          textColor="primary"
          indicatorColor="primary"
        >
          <Tab icon={<AlertTriangle size={18} />} iconPosition="start" label={`Incident Queue (${incidents.length})`} />
          <Tab icon={<Sliders size={18} />} iconPosition="start" label="Playbook Catalog" />
          <Tab icon={<ShieldCheck size={18} />} iconPosition="start" label="Safety & Cooldown Guards" />
          <Tab icon={<History size={18} />} iconPosition="start" label="Remediation Audit Trail" />
          <Tab icon={<ShieldAlert size={18} />} iconPosition="start" label="Break-Glass & Escalations" />
          <Tab icon={<Activity size={18} />} iconPosition="start" label="MTTR & Reliability Health" />
        </Tabs>
      </Paper>

      {/* TAB 0: Incident Queue */}
      {tabIndex === 0 && (
        <Card sx={{ borderRadius: 2 }}>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
              <AlertTriangle size={20} color="#0284c7" />
              Active & Resolved Reliability Incidents ({incidents.length})
            </Typography>
            <Typography variant="body2" sx={{ color: '#64748b', mb: 3 }}>
              SLA metric breaches automatically trigger matched remediation playbooks within configured safety cooldowns.
            </Typography>

            <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid #e2e8f0', borderRadius: 2 }}>
              <Table size="small">
                <TableHead sx={{ bgcolor: '#f8fafc' }}>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Incident ID</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Metric</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Observed / Threshold</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Severity</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Status</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Assigned Playbook</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {incidents.map((inc) => (
                    <TableRow key={inc.id} hover>
                      <TableCell sx={{ fontWeight: 600, color: '#0f172a' }}>{inc.id}</TableCell>
                      <TableCell sx={{ color: '#475569', fontSize: '0.85rem' }}>{inc.metric_name}</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>
                        {inc.trigger_value} / {inc.threshold}
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={inc.severity}
                          size="small"
                          color={inc.severity === 'CRITICAL' ? 'error' : 'warning'}
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={inc.status}
                          size="small"
                          color={
                            inc.status === 'RESOLVED'
                              ? 'success'
                              : inc.status === 'REMEDIATING'
                              ? 'primary'
                              : inc.status === 'ESCALATED'
                              ? 'error'
                              : 'warning'
                          }
                        />
                      </TableCell>
                      <TableCell>
                        <Chip label={inc.assigned_playbook_id} size="small" variant="outlined" />
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', gap: 1 }}>
                          {inc.status !== 'RESOLVED' && (
                            <>
                              <Button
                                size="small"
                                variant="contained"
                                color="success"
                                onClick={() => handleResolveIncident(inc.id)}
                              >
                                Resolve
                              </Button>
                              <Button
                                size="small"
                                variant="outlined"
                                color="error"
                                onClick={() => handleEscalateIncident(inc.id)}
                              >
                                Escalate
                              </Button>
                            </>
                          )}
                        </Box>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}

      {/* TAB 1: Playbook Catalog */}
      {tabIndex === 1 && (
        <Card sx={{ borderRadius: 2 }}>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
              <Sliders size={20} color="#0284c7" />
              Approved Remediation Playbook Catalog ({playbooks.length})
            </Typography>
            <Typography variant="body2" sx={{ color: '#64748b', mb: 3 }}>
              Self-healing actions verified for safe automated dispatch across workers, model routers, and caches.
            </Typography>

            <Grid container spacing={2}>
              {playbooks.map((pb) => (
                <Grid item xs={12} md={6} key={pb.id}>
                  <Paper sx={{ p: 2.5, border: '1px solid #e2e8f0', borderRadius: 2, height: '100%' }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                      <Typography variant="subtitle1" sx={{ fontWeight: 700, color: '#0f172a' }}>
                        {pb.name}
                      </Typography>
                      <Chip label={pb.target_subsystem} size="small" color="primary" variant="outlined" />
                    </Box>
                    <Typography variant="body2" sx={{ color: '#64748b', mb: 2, minHeight: 40 }}>
                      {pb.description}
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2 }}>
                      <Chip label={`Cooldown: ${pb.cooldown_seconds}s`} size="small" />
                      <Chip label={`Max: ${pb.max_per_hour}/hr`} size="small" />
                    </Box>
                    <Button
                      fullWidth
                      variant="outlined"
                      startIcon={<Play size={14} />}
                      onClick={() => handleExecutePlaybook(pb)}
                    >
                      Trigger Playbook Action
                    </Button>
                  </Paper>
                </Grid>
              ))}
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* TAB 2: Safety & Cooldown Guards */}
      {tabIndex === 2 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={4}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <ShieldCheck size={18} color="#16a34a" />
                  Blast Radius Cap
                </Typography>
                <Typography variant="h3" sx={{ fontWeight: 700, color: '#16a34a', mb: 1 }}>
                  25%
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  Maximum percentage of worker slots or replica nodes permitted to undergo automated remediation simultaneously.
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Clock size={18} color="#0284c7" />
                  Default Cooldown
                </Typography>
                <Typography variant="h3" sx={{ fontWeight: 700, color: '#0284c7', mb: 1 }}>
                  300s
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  Mandatory settling duration between consecutive remediation executions on the same subsystem.
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <RotateCcw size={18} color="#8b5cf6" />
                  Auto-Rollback Trigger
                </Typography>
                <Typography variant="h3" sx={{ fontWeight: 700, color: '#8b5cf6', mb: 1 }}>
                  Enabled
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  Actions that fail to improve or further degrade the target metric automatically roll back to baseline.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* TAB 3: Remediation Audit Trail */}
      {tabIndex === 3 && (
        <Card sx={{ borderRadius: 2 }}>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
              <History size={20} color="#0284c7" />
              Remediation Action Execution Audit Trail ({executions.length})
            </Typography>
            <Typography variant="body2" sx={{ color: '#64748b', mb: 3 }}>
              Full audit trail recording pre-remediation values, post-remediation observations, and verified outcomes.
            </Typography>

            <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid #e2e8f0', borderRadius: 2 }}>
              <Table size="small">
                <TableHead sx={{ bgcolor: '#f8fafc' }}>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Execution ID</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Action Type</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Subsystem</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Pre-Metric</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Post-Metric</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Outcome</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Executed At</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {executions.map((ex) => (
                    <TableRow key={ex.id} hover>
                      <TableCell sx={{ fontWeight: 600, color: '#0f172a' }}>{ex.id}</TableCell>
                      <TableCell>
                        <Chip label={ex.action_type} size="small" variant="outlined" />
                      </TableCell>
                      <TableCell sx={{ color: '#475569' }}>{ex.target_subsystem}</TableCell>
                      <TableCell sx={{ color: '#ef4444', fontWeight: 600 }}>{ex.pre_metric_value}</TableCell>
                      <TableCell sx={{ color: '#16a34a', fontWeight: 600 }}>{ex.post_metric_value}</TableCell>
                      <TableCell>
                        <Chip
                          label={ex.outcome}
                          size="small"
                          color={ex.outcome === 'SUCCESS' ? 'success' : 'error'}
                        />
                      </TableCell>
                      <TableCell sx={{ color: '#64748b', fontSize: '0.85rem' }}>{ex.executed_at}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}

      {/* TAB 4: Break-Glass & Escalations */}
      {tabIndex === 4 && (
        <Card sx={{ borderRadius: 2 }}>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
              <ShieldAlert size={20} color="#dc2626" />
              SRE Escalation & Break-Glass Console
            </Typography>
            <Typography variant="body2" sx={{ color: '#64748b', mb: 3 }}>
              When automated remediations exhaust retries or trigger safety stops, incidents escalate here for operator review.
            </Typography>

            <Alert severity="warning" sx={{ mb: 3 }}>
              No critical break-glass operations currently active. Platform health within normal operating parameters.
            </Alert>
          </CardContent>
        </Card>
      )}

      {/* TAB 5: MTTR & Reliability Health */}
      {tabIndex === 5 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={4}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Activity size={18} color="#0284c7" />
                  Mean Time to Remediation (MTTR)
                </Typography>
                <Typography variant="h3" sx={{ fontWeight: 700, color: '#0284c7', mb: 1 }}>
                  32.5s
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  Average automated detection to metric verification duration across past 30 days.
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <CheckCircle2 size={18} color="#16a34a" />
                  Automated Resolution Rate
                </Typography>
                <Typography variant="h3" sx={{ fontWeight: 700, color: '#16a34a', mb: 1 }}>
                  96.8%
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  Incidents automatically resolved by self-healing playbooks without human intervention.
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Server size={18} color="#8b5cf6" />
                  Platform Availability SLA
                </Typography>
                <Typography variant="h3" sx={{ fontWeight: 700, color: '#8b5cf6', mb: 1 }}>
                  99.99%
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  Monthly uptime SLA compliance exceeding tier-1 enterprise guarantees.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Trigger Playbook Dialog */}
      <Dialog open={openTriggerDialog} onClose={() => setOpenTriggerDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Dispatch Self-Healing Playbook</DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          {selectedPlaybook && (
            <Box>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, color: '#0f172a', mb: 1 }}>
                {selectedPlaybook.name}
              </Typography>
              <Typography variant="body2" sx={{ color: '#64748b', mb: 2 }}>
                {selectedPlaybook.description}
              </Typography>
              <Paper sx={{ p: 2, bgcolor: '#f8fafc', borderRadius: 1.5, border: '1px solid #e2e8f0', mb: 2 }}>
                <Typography variant="caption" sx={{ color: '#475569', display: 'block', mb: 0.5, fontWeight: 600 }}>
                  Safety Check:
                </Typography>
                <Typography variant="caption" sx={{ color: '#16a34a', display: 'block' }}>
                  ✓ Target subsystem '{selectedPlaybook.target_subsystem}' within blast radius limit.
                </Typography>
                <Typography variant="caption" sx={{ color: '#16a34a', display: 'block' }}>
                  ✓ Cooldown window verified (0s remaining).
                </Typography>
              </Paper>
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setOpenTriggerDialog(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleConfirmPlaybookExecution} sx={{ bgcolor: '#0284c7' }}>
            Confirm & Dispatch Action
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default EnterpriseSelfHealingWorkspace;
