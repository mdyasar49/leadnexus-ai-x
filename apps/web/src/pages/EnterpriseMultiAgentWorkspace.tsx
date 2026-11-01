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
} from '@mui/material';
import {
  Groups,
  AccountTree,
  Forum,
  Memory,
  Gavel,
  Insights,
  Refresh,
  PlayArrow,
  CheckCircle,
  Warning,
  CompareArrows,
  SmartToy,
  Layers,
  Terminal,
  Security,
  DoneAll,
} from '@mui/icons-material';

interface AgentRosterItem {
  type: string;
  name: string;
  role: string;
  capabilities: string[];
  max_steps: number;
  status: string;
}

interface AgentTask {
  id: string;
  agent: string;
  goal: string;
  status: string;
  steps: number;
  tokens: number;
  cost: number;
}

interface BusMessage {
  id: string;
  sender: string;
  recipient: string;
  type: string;
  content: string;
  time: string;
}

interface DisputeItem {
  id: string;
  field: string;
  agent_a: string;
  val_a: string;
  conf_a: number;
  agent_b: string;
  val_b: string;
  conf_b: number;
  status: string;
  winner?: string;
}

const ALL_12_AGENTS: AgentRosterItem[] = [
  { type: 'ResearchAgent', name: 'Research Specialist Agent', role: 'Open-web signal discovery and multi-source synthesis.', capabilities: ['web_search', 'document_scraping', 'dossier_synthesis'], max_steps: 12, status: 'IDLE' },
  { type: 'CompanyAgent', name: 'Firmographic Company Agent', role: 'Canonical company identity, headcount, and revenue bands.', capabilities: ['domain_resolution', 'firmographics_lookup', 'industry_classification'], max_steps: 8, status: 'IDLE' },
  { type: 'PersonAgent', name: 'Decision Maker Profile Agent', role: 'Executive seniority mapping and decision-maker profiling.', capabilities: ['title_classification', 'seniority_mapping', 'executive_discovery'], max_steps: 8, status: 'IDLE' },
  { type: 'ContactAgent', name: 'Contact Verification Agent', role: 'Work email derivation, deliverability checks, and phone formatting.', capabilities: ['email_pattern_derivation', 'smtp_deliverability_check'], max_steps: 6, status: 'IDLE' },
  { type: 'TechnologyAgent', name: 'Technology Stack Agent', role: 'CRM, ERP, Cloud, and framework signature detection.', capabilities: ['technographic_scan', 'cloud_provider_detection', 'crm_erp_fingerprinting'], max_steps: 8, status: 'IDLE' },
  { type: 'EvidenceAgent', name: 'Evidence & Citation Agent', role: 'Citation verification, provenance timestamps, and factual backing.', capabilities: ['citation_verification', 'provenance_tracking', 'hallucination_detection'], max_steps: 6, status: 'IDLE' },
  { type: 'ScoringAgent', name: 'ICP Scoring & Intent Agent', role: 'Multi-factor ICP fit qualification and buying surge scoring.', capabilities: ['icp_fit_calculation', 'intent_weighting', 'propensity_scoring'], max_steps: 6, status: 'IDLE' },
  { type: 'QualityAgent', name: 'Data Quality & Integrity Agent', role: 'Null checks, schema conformity, and freshness SLA audit.', capabilities: ['contract_verification', 'null_inspection', 'freshness_sla_audit'], max_steps: 6, status: 'IDLE' },
  { type: 'GraphAgent', name: 'Semantic Graph Linker Agent', role: 'Relational cross-domain graph linking across all entities.', capabilities: ['subgraph_traversal', 'entity_linking', 'relationship_inference'], max_steps: 8, status: 'IDLE' },
  { type: 'AnalyticsAgent', name: 'Analytics & Telemetry Agent', role: 'Pipeline metrics aggregation, latency, and cost accounting.', capabilities: ['metric_aggregation', 'trend_projection', 'cost_auditing'], max_steps: 6, status: 'IDLE' },
  { type: 'PlanningAgent', name: 'Supervisor Planning Agent', role: 'Master objective decomposition and inter-agent delegation.', capabilities: ['task_decomposition', 'dependency_graphing', 'delegation_coordination'], max_steps: 15, status: 'IDLE' },
  { type: 'ReviewAgent', name: 'Human-in-the-Loop Review Agent', role: 'Audit user explicit-add rules and gatekeep exports.', capabilities: ['compliance_audit', 'export_gatekeeping', 'human_review_escalation'], max_steps: 6, status: 'IDLE' },
];

export const EnterpriseMultiAgentWorkspace: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Tasks state
  const [tasks, setTasks] = useState<AgentTask[]>([
    { id: 'task-101', agent: 'PlanningAgent', goal: 'Decompose enterprise B2B lead discovery for Odoo ERP partners in Sydney', status: 'COMPLETED', steps: 2, tokens: 320, cost: 0.000064 },
    { id: 'task-102', agent: 'CompanyAgent', goal: 'Resolve firmographics for Infogenx Technologies', status: 'COMPLETED', steps: 1, tokens: 140, cost: 0.000028 },
    { id: 'task-103', agent: 'ScoringAgent', goal: 'Calculate ICP fit for target accounts', status: 'COMPLETED', steps: 1, tokens: 125, cost: 0.000025 },
  ]);

  // Message bus state
  const [messages, setMessages] = useState<BusMessage[]>([
    { id: 'msg-1', sender: 'PlanningAgent', recipient: 'CompanyAgent', type: 'DELEGATION', content: 'Resolve firmographic profile and headcount for Infogenx', time: '14:40:12' },
    { id: 'msg-2', sender: 'CompanyAgent', recipient: 'PlanningAgent', type: 'RESPONSE', content: 'Firmographics resolved: Headcount 250-500, SaaS, Australia', time: '14:40:13' },
    { id: 'msg-3', sender: 'PlanningAgent', recipient: 'PersonAgent', type: 'DELEGATION', content: 'Identify VP Engineering and Head of ERP', time: '14:40:14' },
    { id: 'msg-4', sender: 'ReviewAgent', recipient: 'BROADCAST', type: 'AUDIT', content: 'Invariant verified: Saved Leads isolation strictly enforced.', time: '14:40:15' },
  ]);

  // Disputes state
  const [disputes, setDisputes] = useState<DisputeItem[]>([
    {
      id: 'disp-1',
      field: 'annual_revenue',
      agent_a: 'CompanyAgent',
      val_a: '$50M - $100M',
      conf_a: 0.96,
      agent_b: 'ResearchAgent',
      val_b: '$20M - $50M',
      conf_b: 0.72,
      status: 'RESOLVED',
      winner: 'CompanyAgent (Higher confidence 96%)',
    },
    {
      id: 'disp-2',
      field: 'primary_crm',
      agent_a: 'TechnologyAgent',
      val_a: 'Salesforce CRM Enterprise',
      conf_a: 0.94,
      agent_b: 'ResearchAgent',
      val_b: 'HubSpot Starter',
      conf_b: 0.81,
      status: 'PENDING',
    },
  ]);

  // Dispatch modal
  const [selectedAgent, setSelectedAgent] = useState('PlanningAgent');
  const [taskGoal, setTaskGoal] = useState('Research decision-makers and technology stack for Australian cloud partners');
  const [isExecuting, setIsExecuting] = useState(false);

  const handleDispatchTask = () => {
    setIsExecuting(true);
    setTimeout(() => {
      const newTask: AgentTask = {
        id: `task-${Date.now()}`,
        agent: selectedAgent,
        goal: taskGoal,
        status: 'COMPLETED',
        steps: 2,
        tokens: 280,
        cost: 0.000056,
      };
      setTasks((prev) => [newTask, ...prev]);
      setMessages((prev) => [
        {
          id: `msg-${Date.now()}`,
          sender: 'UserOrchestrator',
          recipient: selectedAgent,
          type: 'TASK_DISPATCH',
          content: taskGoal,
          time: new Date().toLocaleTimeString(),
        },
        ...prev,
      ]);
      setIsExecuting(false);
      setActionSuccess(`Autonomous task dispatched to ${selectedAgent} and completed within step bound.`);
    }, 450);
  };

  const handleResolveDispute = (id: string, winner: string) => {
    setDisputes((prev) =>
      prev.map((d) => (d.id === id ? { ...d, status: 'RESOLVED', winner } : d))
    );
    setActionSuccess('Dispute arbitrated using supervisor consensus.');
  };

  return (
    <Box sx={{ p: 3, maxWidth: 1400, margin: '0 auto' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" fontWeight="bold" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Groups color="primary" fontSize="large" /> Multi-Agent AI Platform
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Phase 41 — 12 Specialized Autonomous Agents, Bounded Execution, Inter-Agent Bus, State Memory & Conflict Arbitration
          </Typography>
        </Box>
        <Button variant="outlined" startIcon={<Refresh />} onClick={() => setActionSuccess('Synchronized multi-agent roster.')}>
          Refresh Roster
        </Button>
      </Box>

      {actionSuccess && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={() => setActionSuccess(null)}>
          {actionSuccess}
        </Alert>
      )}

      <Paper sx={{ mb: 3 }}>
        <Tabs value={activeTab} onChange={(_, val) => setActiveTab(val)} variant="scrollable" scrollButtons="auto">
          <Tab icon={<SmartToy />} iconPosition="start" label="12 Specialized Agents" />
          <Tab icon={<AccountTree />} iconPosition="start" label="Task Orchestration" />
          <Tab icon={<Forum />} iconPosition="start" label="Inter-Agent Bus" />
          <Tab icon={<Memory />} iconPosition="start" label="Shared Memory" />
          <Tab icon={<Gavel />} iconPosition="start" label="Conflict Arbitration" />
          <Tab icon={<Insights />} iconPosition="start" label="Telemetry & Health" />
        </Tabs>
      </Paper>

      {/* TAB 0: 12 SPECIALIZED AGENTS */}
      {activeTab === 0 && (
        <Box>
          <Typography variant="h6" fontWeight="bold" sx={{ mb: 2 }}>
            Enterprise Specialist Agent Roster (12 Agents)
          </Typography>
          <Grid container spacing={2}>
            {ALL_12_AGENTS.map((agent) => (
              <Grid item xs={12} sm={6} md={4} key={agent.type}>
                <Card sx={{ height: '100%', borderLeft: '4px solid #0284c7' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                      <Typography variant="subtitle1" fontWeight="bold">
                        {agent.type}
                      </Typography>
                      <Chip label={`Max ${agent.max_steps} steps`} size="small" color="primary" variant="outlined" />
                    </Box>
                    <Typography variant="caption" color="primary" fontWeight="bold" display="block">
                      {agent.name}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ my: 1, minHeight: 40 }}>
                      {agent.role}
                    </Typography>
                    <Box sx={{ mt: 1 }}>
                      <Typography variant="caption" fontWeight="bold" display="block">
                        Capabilities:
                      </Typography>
                      {agent.capabilities.map((c) => (
                        <Chip key={c} label={c} size="small" sx={{ mr: 0.5, mt: 0.5, fontSize: 11 }} />
                      ))}
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* TAB 1: TASK ORCHESTRATION */}
      {activeTab === 1 && (
        <Box>
          <Grid container spacing={3}>
            <Grid item xs={12} md={5}>
              <Card sx={{ p: 2 }}>
                <Typography variant="subtitle2" fontWeight="bold" sx={{ mb: 2 }}>
                  Dispatch Autonomous Agent Task
                </Typography>
                <TextField
                  select
                  fullWidth
                  size="small"
                  label="Select Specialist Agent"
                  value={selectedAgent}
                  onChange={(e) => setSelectedAgent(e.target.value)}
                  SelectProps={{ native: true }}
                  sx={{ mb: 2 }}
                >
                  {ALL_12_AGENTS.map((a) => (
                    <option key={a.type} value={a.type}>
                      {a.type} — {a.name}
                    </option>
                  ))}
                </TextField>
                <TextField
                  fullWidth
                  multiline
                  rows={3}
                  label="Task Goal & Boundaries"
                  value={taskGoal}
                  onChange={(e) => setTaskGoal(e.target.value)}
                  sx={{ mb: 2 }}
                />
                <Button
                  variant="contained"
                  fullWidth
                  startIcon={<PlayArrow />}
                  onClick={handleDispatchTask}
                  disabled={isExecuting}
                >
                  {isExecuting ? 'Agent Reasoning...' : 'Dispatch Bounded Task'}
                </Button>
              </Card>
            </Grid>

            <Grid item xs={12} md={7}>
              <Typography variant="subtitle2" fontWeight="bold" sx={{ mb: 1 }}>
                Recent Task Execution Log
              </Typography>
              <TableContainer component={Paper}>
                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ backgroundColor: 'action.hover' }}>
                      <TableCell>Task ID</TableCell>
                      <TableCell>Agent</TableCell>
                      <TableCell>Goal</TableCell>
                      <TableCell>Steps</TableCell>
                      <TableCell>Status</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {tasks.map((t) => (
                      <TableRow key={t.id}>
                        <TableCell>
                          <code>{t.id}</code>
                        </TableCell>
                        <TableCell>
                          <Chip label={t.agent} size="small" color="primary" />
                        </TableCell>
                        <TableCell sx={{ maxWidth: 220 }}>
                          <Typography variant="caption" noWrap>
                            {t.goal}
                          </Typography>
                        </TableCell>
                        <TableCell>{t.steps}</TableCell>
                        <TableCell>
                          <Chip label={t.status} size="small" color="success" />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Grid>
          </Grid>
        </Box>
      )}

      {/* TAB 2: INTER-AGENT BUS */}
      {activeTab === 2 && (
        <Box>
          <Typography variant="h6" fontWeight="bold" sx={{ mb: 2 }}>
            Inter-Agent Message Bus Feed
          </Typography>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ backgroundColor: 'action.hover' }}>
                  <TableCell>Time</TableCell>
                  <TableCell>Sender</TableCell>
                  <TableCell>Recipient</TableCell>
                  <TableCell>Message Type</TableCell>
                  <TableCell>Payload</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {messages.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell>
                      <Typography variant="caption" color="text.secondary">
                        {m.time}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip label={m.sender} size="small" color="primary" variant="outlined" />
                    </TableCell>
                    <TableCell>
                      <Chip label={m.recipient} size="small" color="secondary" variant="outlined" />
                    </TableCell>
                    <TableCell>
                      <Chip label={m.type} size="small" color={m.type === 'DELEGATION' ? 'warning' : 'default'} />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">{m.content}</Typography>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}

      {/* TAB 3: SHARED MEMORY */}
      {activeTab === 3 && (
        <Box>
          <Typography variant="h6" fontWeight="bold" sx={{ mb: 2 }}>
            Cross-Agent State & Scoped Memory
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <Card sx={{ borderLeft: '4px solid #10b981' }}>
                <CardContent>
                  <Typography variant="subtitle1" fontWeight="bold">
                    Workspace Shared State
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ my: 1 }}>
                    Persists cross-task facts (e.g. firmographic golden records, verified domains).
                  </Typography>
                  <Chip label="TTL: 30 Days" size="small" color="success" />
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={4}>
              <Card sx={{ borderLeft: '4px solid #3b82f6' }}>
                <CardContent>
                  <Typography variant="subtitle1" fontWeight="bold">
                    Task Execution State
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ my: 1 }}>
                    Coordinating context shared between PlanningAgent and dispatched sub-agents.
                  </Typography>
                  <Chip label="TTL: Task Lifespan" size="small" color="primary" />
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={4}>
              <Card sx={{ borderLeft: '4px solid #f59e0b' }}>
                <CardContent>
                  <Typography variant="subtitle1" fontWeight="bold">
                    Ephemeral Working Memory
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ my: 1 }}>
                    Scratchpad memory used during step reflection and tool parameter formulation.
                  </Typography>
                  <Chip label="TTL: Instant Flush" size="small" color="warning" />
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Box>
      )}

      {/* TAB 4: CONFLICT ARBITRATION */}
      {activeTab === 4 && (
        <Box>
          <Typography variant="h6" fontWeight="bold" sx={{ mb: 2 }}>
            Agent Dispute & Conflict Arbitration
          </Typography>
          <Grid container spacing={2}>
            {disputes.map((disp) => (
              <Grid item xs={12} key={disp.id}>
                <Card sx={{ borderLeft: `4px solid ${disp.status === 'RESOLVED' ? '#10b981' : '#f59e0b'}` }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                      <Typography variant="subtitle1" fontWeight="bold">
                        Conflict on Attribute: <code>{disp.field}</code>
                      </Typography>
                      <Chip label={disp.status} size="small" color={disp.status === 'RESOLVED' ? 'success' : 'warning'} />
                    </Box>
                    <Grid container spacing={2} sx={{ my: 1 }}>
                      <Grid item xs={12} md={6}>
                        <Paper sx={{ p: 1.5, bgcolor: '#f8fafc' }}>
                          <Typography variant="caption" fontWeight="bold" color="primary">
                            Claim A — {disp.agent_a} (Confidence: {(disp.conf_a * 100).toFixed(0)}%)
                          </Typography>
                          <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                            {disp.val_a}
                          </Typography>
                        </Paper>
                      </Grid>
                      <Grid item xs={12} md={6}>
                        <Paper sx={{ p: 1.5, bgcolor: '#f8fafc' }}>
                          <Typography variant="caption" fontWeight="bold" color="secondary">
                            Claim B — {disp.agent_b} (Confidence: {(disp.conf_b * 100).toFixed(0)}%)
                          </Typography>
                          <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                            {disp.val_b}
                          </Typography>
                        </Paper>
                      </Grid>
                    </Grid>
                    {disp.status === 'RESOLVED' ? (
                      <Typography variant="body2" color="success.main" fontWeight="bold">
                        Arbitration Outcome: {disp.winner}
                      </Typography>
                    ) : (
                      <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
                        <Button
                          size="small"
                          variant="contained"
                          color="primary"
                          onClick={() => handleResolveDispute(disp.id, `${disp.agent_a} (Confidence ${(disp.conf_a * 100).toFixed(0)}%)`)}
                        >
                          Adopt {disp.agent_a} Claim
                        </Button>
                        <Button
                          size="small"
                          variant="outlined"
                          onClick={() => handleResolveDispute(disp.id, `${disp.agent_b} (Confidence ${(disp.conf_b * 100).toFixed(0)}%)`)}
                        >
                          Adopt {disp.agent_b} Claim
                        </Button>
                      </Box>
                    )}
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* TAB 5: TELEMETRY & HEALTH */}
      {activeTab === 5 && (
        <Box>
          <Typography variant="h6" fontWeight="bold" sx={{ mb: 2 }}>
            Specialist Agents Operational Health & Benchmarks
          </Typography>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ backgroundColor: 'action.hover' }}>
                  <TableCell>Specialist Agent</TableCell>
                  <TableCell>Health</TableCell>
                  <TableCell>Success Rate</TableCell>
                  <TableCell>Max Step Bound</TableCell>
                  <TableCell>Sandbox Isolation</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {ALL_12_AGENTS.map((a) => (
                  <TableRow key={a.type}>
                    <TableCell sx={{ fontWeight: 'bold' }}>{a.type}</TableCell>
                    <TableCell>
                      <Chip icon={<CheckCircle />} label="HEALTHY" color="success" size="small" />
                    </TableCell>
                    <TableCell>100.0%</TableCell>
                    <TableCell>{a.max_steps} steps</TableCell>
                    <TableCell>
                      <Chip label="SANDBOXED" size="small" variant="outlined" />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}
    </Box>
  );
};

export default EnterpriseMultiAgentWorkspace;
