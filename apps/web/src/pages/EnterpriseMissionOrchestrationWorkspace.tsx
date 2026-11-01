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
  GitFork,
  Play,
  Pause,
  RotateCcw,
  Square,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Layers,
  Cpu,
  ShieldCheck,
  UserCheck,
  RefreshCw,
  Plus,
  ArrowRight,
  Database,
  Sliders,
  Activity,
  History,
} from 'lucide-react';

interface MissionSummary {
  id: string;
  name: string;
  goal: string;
  status: string;
  priority: string;
  total_steps: number;
  completed_steps: number;
  failed_steps: number;
  created_at: string;
}

interface StepItem {
  id: string;
  name: string;
  agent_type: string;
  status: string;
  dependencies: string[];
  retry_count: number;
  max_retries: number;
  requires_human_review?: boolean;
}

interface CheckpointItem {
  id: string;
  checkpoint_number: number;
  status: string;
  reason: string;
  state_hash: string;
  created_at: string;
}

interface HumanReviewItem {
  review_id: string;
  step_id: string;
  title: string;
  candidate_data: Record<string, any>;
  created_at: string;
}

const INITIAL_MISSIONS: MissionSummary[] = [
  {
    id: 'm-emea-fintech',
    name: 'EMEA Fintech Executive Intelligence',
    goal: 'Autonomous identification, firmographic extraction, and contact verification for Series B+ Fintechs in London & Berlin.',
    status: 'RUNNING',
    priority: 'HIGH',
    total_steps: 5,
    completed_steps: 3,
    failed_steps: 0,
    created_at: '2026-11-01 11:00:00',
  },
  {
    id: 'm-us-cloud',
    name: 'North America Cloud Scale Audit',
    goal: 'Identify Kubernetes and Snowflake enterprise customers, extract VP Engineering contacts, and ground citations.',
    status: 'AWAITING_HUMAN_REVIEW',
    priority: 'CRITICAL',
    total_steps: 4,
    completed_steps: 2,
    failed_steps: 0,
    created_at: '2026-11-01 12:30:00',
  },
  {
    id: 'm-apac-ai',
    name: 'APAC AI Robotics Deep Research',
    goal: 'Research early-stage robotics manufacturers across Singapore and Japan.',
    status: 'COMPLETED',
    priority: 'NORMAL',
    total_steps: 3,
    completed_steps: 3,
    failed_steps: 0,
    created_at: '2026-11-01 09:15:00',
  },
];

const INITIAL_STEPS: StepItem[] = [
  {
    id: 'step_1',
    name: 'Broad Market Discovery & Entity Search',
    agent_type: 'ResearchAgent',
    status: 'COMPLETED',
    dependencies: [],
    retry_count: 0,
    max_retries: 3,
  },
  {
    id: 'step_2',
    name: 'Firmographic & Revenue Verification',
    agent_type: 'CompanyAgent',
    status: 'COMPLETED',
    dependencies: ['step_1'],
    retry_count: 0,
    max_retries: 3,
  },
  {
    id: 'step_3',
    name: 'Executive Leadership Identification',
    agent_type: 'PersonAgent',
    status: 'COMPLETED',
    dependencies: ['step_2'],
    retry_count: 0,
    max_retries: 3,
  },
  {
    id: 'step_4',
    name: 'Human Verification on High-Priority Accounts',
    agent_type: 'ReviewAgent',
    status: 'RUNNING',
    dependencies: ['step_3'],
    retry_count: 0,
    max_retries: 3,
    requires_human_review: true,
  },
  {
    id: 'step_5',
    name: 'Deliverability & Contact Enrichment',
    agent_type: 'ContactAgent',
    status: 'PENDING',
    dependencies: ['step_4'],
    retry_count: 0,
    max_retries: 3,
  },
];

const INITIAL_CHECKPOINTS: CheckpointItem[] = [
  {
    id: 'chk-001',
    checkpoint_number: 1,
    status: 'RUNNING',
    reason: 'STEP_step_1_COMPLETED',
    state_hash: 'a912ff481bca0921fe148012bbecf1109923da8102484a919420bf0124ca9821',
    created_at: '2026-11-01 11:05:12',
  },
  {
    id: 'chk-002',
    checkpoint_number: 2,
    status: 'RUNNING',
    reason: 'STEP_step_2_COMPLETED',
    state_hash: '3bc981249fae0149021eb918cae728019942bf901284a100234ca78901248102',
    created_at: '2026-11-01 11:12:44',
  },
  {
    id: 'chk-003',
    checkpoint_number: 3,
    status: 'RUNNING',
    reason: 'STEP_step_3_COMPLETED',
    state_hash: '77ae81042bca0019283ba89012480129bc8120491a9021bb48019230ca981240',
    created_at: '2026-11-01 11:24:02',
  },
];

const INITIAL_REVIEWS: HumanReviewItem[] = [
  {
    review_id: 'rev-001',
    step_id: 'step_4',
    title: 'Review Required: Apex Robotics Corp ($14M Series A)',
    candidate_data: {
      company: 'Apex Robotics Corp',
      executive: 'Elena Rostova (CTO)',
      email: 'elena@apexrobotics.ai',
      confidence: 0.94,
      source: 'SEC Filing & Tech Brief',
    },
    created_at: '2026-11-01 11:24:10',
  },
];

export const EnterpriseMissionOrchestrationWorkspace: React.FC = () => {
  const [tabIndex, setTabIndex] = useState<number>(0);
  const [missions, setMissions] = useState<MissionSummary[]>(INITIAL_MISSIONS);
  const [selectedMission, setSelectedMission] = useState<MissionSummary>(INITIAL_MISSIONS[0]);
  const [steps, setSteps] = useState<StepItem[]>(INITIAL_STEPS);
  const [checkpoints, setCheckpoints] = useState<CheckpointItem[]>(INITIAL_CHECKPOINTS);
  const [reviews, setReviews] = useState<HumanReviewItem[]>(INITIAL_REVIEWS);

  // New Mission Dialog
  const [openNewDialog, setOpenNewDialog] = useState<boolean>(false);
  const [newMissionName, setNewMissionName] = useState<string>('Enterprise Outreach Mission');
  const [newMissionGoal, setNewMissionGoal] = useState<string>('Autonomous discovery and verification of 50 enterprise leads.');
  const [newPriority, setNewPriority] = useState<string>('HIGH');
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const handleCreateMission = () => {
    const newId = `m-${Date.now().toString(36)}`;
    const newM: MissionSummary = {
      id: newId,
      name: newMissionName,
      goal: newMissionGoal,
      status: 'RUNNING',
      priority: newPriority,
      total_steps: 4,
      completed_steps: 0,
      failed_steps: 0,
      created_at: new Date().toISOString().replace('T', ' ').substring(0, 19),
    };

    setMissions([newM, ...missions]);
    setSelectedMission(newM);
    setOpenNewDialog(false);
    setSuccessMsg(`Mission "${newMissionName}" initiated with validated DAG!`);
  };

  const handlePauseMission = (mId: string) => {
    setMissions(missions.map((m) => (m.id === mId ? { ...m, status: 'PAUSED' } : m)));
    if (selectedMission.id === mId) {
      setSelectedMission({ ...selectedMission, status: 'PAUSED' });
    }
    setSuccessMsg('Mission execution paused. State snapshot checkpoint created.');
  };

  const handleResumeMission = (mId: string) => {
    setMissions(missions.map((m) => (m.id === mId ? { ...m, status: 'RUNNING' } : m)));
    if (selectedMission.id === mId) {
      setSelectedMission({ ...selectedMission, status: 'RUNNING' });
    }
    setSuccessMsg('Mission resumed from last verified checkpoint.');
  };

  const handleReviewDecision = (revId: string, decision: 'APPROVED' | 'REJECTED') => {
    setReviews(reviews.filter((r) => r.review_id !== revId));
    setSteps(
      steps.map((s) =>
        s.id === 'step_4' ? { ...s, status: decision === 'APPROVED' ? 'COMPLETED' : 'FAILED' } : s
      )
    );
    setSuccessMsg(`Human decision "${decision}" applied. DAG workflow advanced.`);
  };

  return (
    <Box sx={{ p: 4, maxWidth: 1440, margin: '0 auto' }}>
      {/* Header */}
      <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
            <GitFork size={28} color="#0284c7" />
            <Typography variant="h4" sx={{ fontWeight: 700, color: '#0f172a' }}>
              Autonomous Orchestration & Long-Running Missions
            </Typography>
            <Chip label="Phase 43" color="primary" size="small" sx={{ fontWeight: 600 }} />
          </Box>
          <Typography variant="body1" sx={{ color: '#64748b' }}>
            Durable DAG execution engine, stateful checkpointing, priority worker pools,
            and human-in-the-loop review governance.
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="outlined"
            startIcon={<RefreshCw size={16} />}
            onClick={() => setSuccessMsg('Orchestration state synchronized with cluster.')}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<Plus size={16} />}
            onClick={() => setOpenNewDialog(true)}
            sx={{ bgcolor: '#0284c7', '&:hover': { bgcolor: '#0369a1' } }}
          >
            New Mission
          </Button>
        </Box>
      </Box>

      {/* Primary Invariant Banner */}
      <Alert severity="info" sx={{ mb: 3, border: '1px solid #bae6fd', bgcolor: '#f0f9ff' }}>
        <strong>Invariant Rule Enforced:</strong> Autonomous missions run in isolated execution sandboxes. Discovered
        companies and contacts are stored in temporary mission ledgers and <strong>never</strong> enter Saved Leads
        or Export streams without explicit operator addition.
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
          <Tab icon={<Sliders size={18} />} iconPosition="start" label="Mission Control Studio" />
          <Tab icon={<GitFork size={18} />} iconPosition="start" label="DAG Task Visualizer" />
          <Tab icon={<Cpu size={18} />} iconPosition="start" label="Worker Pool & Queue" />
          <Tab icon={<History size={18} />} iconPosition="start" label="State Checkpoints" />
          <Tab icon={<UserCheck size={18} />} iconPosition="start" label={`Human Review (${reviews.length})`} />
          <Tab icon={<Activity size={18} />} iconPosition="start" label="Telemetry & Diagnostics" />
        </Tabs>
      </Paper>

      {/* TAB 0: Mission Control Studio */}
      {tabIndex === 0 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={7}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Layers size={20} color="#0284c7" />
                  Active Missions Roster ({missions.length})
                </Typography>
                <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid #e2e8f0', borderRadius: 2 }}>
                  <Table size="small">
                    <TableHead sx={{ bgcolor: '#f8fafc' }}>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 600 }}>Mission Name</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>Priority</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>Status</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>Progress</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {missions.map((m) => {
                        const pct = Math.round((m.completed_steps / Math.max(1, m.total_steps)) * 100);
                        return (
                          <TableRow
                            key={m.id}
                            hover
                            selected={selectedMission.id === m.id}
                            onClick={() => setSelectedMission(m)}
                            sx={{ cursor: 'pointer' }}
                          >
                            <TableCell>
                              <Typography variant="subtitle2" sx={{ fontWeight: 600, color: '#0f172a' }}>
                                {m.name}
                              </Typography>
                              <Typography variant="caption" sx={{ color: '#64748b' }}>
                                {m.id}
                              </Typography>
                            </TableCell>
                            <TableCell>
                              <Chip
                                label={m.priority}
                                size="small"
                                color={m.priority === 'CRITICAL' ? 'error' : m.priority === 'HIGH' ? 'warning' : 'default'}
                              />
                            </TableCell>
                            <TableCell>
                              <Chip
                                label={m.status}
                                size="small"
                                color={
                                  m.status === 'RUNNING'
                                    ? 'primary'
                                    : m.status === 'COMPLETED'
                                    ? 'success'
                                    : m.status === 'PAUSED'
                                    ? 'warning'
                                    : 'secondary'
                                }
                              />
                            </TableCell>
                            <TableCell sx={{ minWidth: 120 }}>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <LinearProgress
                                  variant="determinate"
                                  value={pct}
                                  sx={{ flexGrow: 1, height: 6, borderRadius: 3 }}
                                />
                                <Typography variant="caption" sx={{ color: '#475569', fontWeight: 600 }}>
                                  {pct}%
                                </Typography>
                              </Box>
                            </TableCell>
                            <TableCell>
                              {m.status === 'RUNNING' ? (
                                <Tooltip title="Pause Mission">
                                  <IconButton
                                    size="small"
                                    color="warning"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handlePauseMission(m.id);
                                    }}
                                  >
                                    <Pause size={16} />
                                  </IconButton>
                                </Tooltip>
                              ) : m.status === 'PAUSED' ? (
                                <Tooltip title="Resume Mission">
                                  <IconButton
                                    size="small"
                                    color="primary"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleResumeMission(m.id);
                                    }}
                                  >
                                    <Play size={16} />
                                  </IconButton>
                                </Tooltip>
                              ) : null}
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={5}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Sliders size={20} color="#0284c7" />
                  Mission Overview: {selectedMission.name}
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b', mb: 3 }}>
                  {selectedMission.goal}
                </Typography>

                <Paper sx={{ p: 2, bgcolor: '#f8fafc', borderRadius: 2, mb: 3, border: '1px solid #e2e8f0' }}>
                  <Grid container spacing={2}>
                    <Grid item xs={6}>
                      <Typography variant="caption" sx={{ color: '#64748b' }}>
                        Mission Status
                      </Typography>
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, color: '#0f172a' }}>
                        {selectedMission.status}
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="caption" sx={{ color: '#64748b' }}>
                        Scheduling Priority
                      </Typography>
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, color: '#0f172a' }}>
                        {selectedMission.priority}
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="caption" sx={{ color: '#64748b' }}>
                        Total DAG Steps
                      </Typography>
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, color: '#0f172a' }}>
                        {selectedMission.total_steps} Steps
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="caption" sx={{ color: '#64748b' }}>
                        Checkpoints Saved
                      </Typography>
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, color: '#0f172a' }}>
                        {checkpoints.length} Snapshots
                      </Typography>
                    </Grid>
                  </Grid>
                </Paper>

                <Box sx={{ display: 'flex', gap: 2 }}>
                  {selectedMission.status === 'RUNNING' && (
                    <Button
                      fullWidth
                      variant="outlined"
                      color="warning"
                      startIcon={<Pause size={16} />}
                      onClick={() => handlePauseMission(selectedMission.id)}
                    >
                      Pause Execution
                    </Button>
                  )}
                  {selectedMission.status === 'PAUSED' && (
                    <Button
                      fullWidth
                      variant="contained"
                      color="primary"
                      startIcon={<Play size={16} />}
                      onClick={() => handleResumeMission(selectedMission.id)}
                    >
                      Resume Execution
                    </Button>
                  )}
                  <Button
                    fullWidth
                    variant="outlined"
                    startIcon={<GitFork size={16} />}
                    onClick={() => setTabIndex(1)}
                  >
                    View DAG Graph
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* TAB 1: DAG Task Visualizer */}
      {tabIndex === 1 && (
        <Card sx={{ borderRadius: 2 }}>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Box>
                <Typography variant="h6" sx={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <GitFork size={20} color="#0284c7" />
                  Mission DAG Execution Graph: {selectedMission.name}
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  Topologically ordered task graph with dependency resolution and failure containment.
                </Typography>
              </Box>
              <Chip label="DAG Validated (Acyclic)" color="success" size="small" variant="outlined" />
            </Box>

            <Grid container spacing={2}>
              {steps.map((st, idx) => (
                <Grid item xs={12} key={st.id}>
                  <Paper
                    sx={{
                      p: 2.5,
                      border: '1px solid #e2e8f0',
                      borderRadius: 2,
                      bgcolor: st.status === 'RUNNING' ? '#f0f9ff' : '#ffffff',
                    }}
                  >
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                      <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center' }}>
                        <Typography variant="subtitle1" sx={{ fontWeight: 700, color: '#0f172a' }}>
                          Step {idx + 1}: {st.name}
                        </Typography>
                        <Chip label={st.agent_type} size="small" variant="outlined" />
                        {st.requires_human_review && (
                          <Chip label="Human Gated" size="small" color="secondary" />
                        )}
                      </Box>
                      <Chip
                        label={st.status}
                        size="small"
                        color={
                          st.status === 'COMPLETED'
                            ? 'success'
                            : st.status === 'RUNNING'
                            ? 'primary'
                            : st.status === 'FAILED'
                            ? 'error'
                            : 'default'
                        }
                      />
                    </Box>

                    <Box sx={{ display: 'flex', gap: 3, alignItems: 'center', mt: 1 }}>
                      <Typography variant="caption" sx={{ color: '#64748b' }}>
                        Dependencies: {st.dependencies.length ? st.dependencies.join(', ') : 'None (Root Node)'}
                      </Typography>
                      <Typography variant="caption" sx={{ color: '#64748b' }}>
                        Retries: {st.retry_count} / {st.max_retries}
                      </Typography>
                    </Box>
                  </Paper>
                </Grid>
              ))}
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* TAB 2: Worker Pool & Queue */}
      {tabIndex === 2 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={4}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Cpu size={18} color="#0284c7" />
                  Worker Thread Capacity
                </Typography>
                <Typography variant="h3" sx={{ fontWeight: 700, color: '#0284c7', mb: 1 }}>
                  2 / 8
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  Active worker threads dispatched. 6 available concurrency slots.
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Clock size={18} color="#f59e0b" />
                  Priority Queue Depth
                </Typography>
                <Typography variant="h3" sx={{ fontWeight: 700, color: '#f59e0b', mb: 1 }}>
                  1 Task
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  Queued tasks ordered by CRITICAL &gt; HIGH &gt; NORMAL &gt; LOW priorities.
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <ShieldCheck size={18} color="#16a34a" />
                  Circuit Breaker Health
                </Typography>
                <Typography variant="h3" sx={{ fontWeight: 700, color: '#16a34a', mb: 1 }}>
                  CLOSED
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  Zero trip events. Downstream failure isolation active.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* TAB 3: State Checkpoints */}
      {tabIndex === 3 && (
        <Card sx={{ borderRadius: 2 }}>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
              <History size={20} color="#0284c7" />
              State Checkpoint & Recovery Ledger ({checkpoints.length})
            </Typography>
            <Typography variant="body2" sx={{ color: '#64748b', mb: 3 }}>
              Point-in-time snapshots of DAG progress, variable store, and step outputs enabling zero-loss recovery.
            </Typography>

            <Grid container spacing={2}>
              {checkpoints.map((chk) => (
                <Grid item xs={12} key={chk.id}>
                  <Paper sx={{ p: 2.5, border: '1px solid #e2e8f0', borderRadius: 2 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                      <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center' }}>
                        <Typography variant="subtitle1" sx={{ fontWeight: 700, color: '#0f172a' }}>
                          Snapshot #{chk.checkpoint_number}: {chk.reason}
                        </Typography>
                        <Chip label={chk.status} size="small" color="primary" variant="outlined" />
                      </Box>
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<RotateCcw size={14} />}
                        onClick={() => setSuccessMsg(`State rolled back to snapshot #${chk.checkpoint_number}`)}
                      >
                        Restore State
                      </Button>
                    </Box>
                    <Typography variant="caption" sx={{ color: '#64748b', display: 'block', mb: 1 }}>
                      Timestamp: {chk.created_at}
                    </Typography>
                    <Box sx={{ p: 1, bgcolor: '#f8fafc', borderRadius: 1, border: '1px solid #e2e8f0' }}>
                      <Typography variant="caption" sx={{ color: '#475569', fontWeight: 600, display: 'block' }}>
                        SHA-256 State Hash:
                      </Typography>
                      <Typography variant="caption" sx={{ fontFamily: 'monospace', color: '#0284c7' }}>
                        {chk.state_hash}
                      </Typography>
                    </Box>
                  </Paper>
                </Grid>
              ))}
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* TAB 4: Human Review Queue */}
      {tabIndex === 4 && (
        <Card sx={{ borderRadius: 2 }}>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
              <UserCheck size={20} color="#0284c7" />
              Human-in-the-Loop Review Queue ({reviews.length})
            </Typography>
            <Typography variant="body2" sx={{ color: '#64748b', mb: 3 }}>
              High-uncertainty decision points paused for operator verification prior to outreach or export.
            </Typography>

            {reviews.length === 0 ? (
              <Alert severity="success">All pending human review items have been resolved.</Alert>
            ) : (
              reviews.map((rev) => (
                <Paper key={rev.review_id} sx={{ p: 3, border: '1px solid #fed7aa', bgcolor: '#fffbeb', borderRadius: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Typography variant="subtitle1" sx={{ fontWeight: 700, color: '#9a3412' }}>
                      {rev.title}
                    </Typography>
                    <Chip label="Action Required" size="small" color="warning" />
                  </Box>
                  <Paper sx={{ p: 2, bgcolor: '#ffffff', border: '1px solid #fde68a', borderRadius: 1.5, mb: 3 }}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                      Candidate Data Payload:
                    </Typography>
                    <pre style={{ margin: 0, fontSize: '0.85rem', color: '#334155' }}>
                      {JSON.stringify(rev.candidate_data, null, 2)}
                    </pre>
                  </Paper>
                  <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
                    <Button
                      variant="outlined"
                      color="error"
                      onClick={() => handleReviewDecision(rev.review_id, 'REJECTED')}
                    >
                      Reject Candidate
                    </Button>
                    <Button
                      variant="contained"
                      color="success"
                      onClick={() => handleReviewDecision(rev.review_id, 'APPROVED')}
                    >
                      Approve & Advance Mission
                    </Button>
                  </Box>
                </Paper>
              ))
            )}
          </CardContent>
        </Card>
      )}

      {/* TAB 5: Telemetry & Diagnostics */}
      {tabIndex === 5 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={4}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Activity size={18} color="#0284c7" />
                  Average Step Latency
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 700, color: '#0284c7', mb: 1 }}>
                  1.24s
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  Average execution time per specialized agent task across the active worker pool.
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <RotateCcw size={18} color="#16a34a" />
                  Automatic Retry Success
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 700, color: '#16a34a', mb: 1 }}>
                  99.4%
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  Transient rate limits recovered via exponential backoff without manual intervention.
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Database size={18} color="#8b5cf6" />
                  Storage Isolation
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 700, color: '#8b5cf6', mb: 1 }}>
                  100%
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  Zero candidate lead leakage into canonical SavedLead or export streams.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* New Mission Dialog */}
      <Dialog open={openNewDialog} onClose={() => setOpenNewDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Initiate Autonomous Mission</DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          <TextField
            fullWidth
            label="Mission Name"
            value={newMissionName}
            onChange={(e) => setNewMissionName(e.target.value)}
            sx={{ mb: 2 }}
          />
          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Priority</InputLabel>
            <Select value={newPriority} label="Priority" onChange={(e) => setNewPriority(e.target.value)}>
              <MenuItem value="LOW">Low</MenuItem>
              <MenuItem value="NORMAL">Normal</MenuItem>
              <MenuItem value="HIGH">High</MenuItem>
              <MenuItem value="CRITICAL">Critical</MenuItem>
            </Select>
          </FormControl>
          <TextField
            fullWidth
            multiline
            rows={3}
            label="Autonomous Goal"
            value={newMissionGoal}
            onChange={(e) => setNewMissionGoal(e.target.value)}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setOpenNewDialog(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleCreateMission} sx={{ bgcolor: '#0284c7' }}>
            Validate & Launch
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default EnterpriseMissionOrchestrationWorkspace;

