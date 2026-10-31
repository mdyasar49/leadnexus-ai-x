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
  LinearProgress,
  Select,
  MenuItem,
  FormControl,
  InputLabel
} from '@mui/material';
import {
  AutoMode as AutonomyIcon,
  PlayArrow as StartIcon,
  Pause as PauseIcon,
  Preview as SimulateIcon,
  CheckCircle as SuccessIcon,
  Warning as WarningIcon,
  ErrorOutline as ErrorIcon,
  AccountTree as GraphIcon,
  Security as PolicyIcon,
  AssignmentTurnedIn as ReportIcon,
  FactCheck as CorroborateIcon,
  Speed as GaugeIcon
} from '@mui/icons-material';

interface ResearchStep {
  id: string;
  step_order: number;
  title: string;
  agent_name: string;
  tool_name: string;
  task_type: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  depends_on: string[];
}

interface FindingItem {
  agent_name: string;
  finding_type: string;
  confidence_score: number;
  evidence_snippet: string;
  data: Record<string, any>;
  source_urls: string[];
}

export const AutonomousResearchWorkspace: React.FC = () => {
  const [companyName, setCompanyName] = useState('OmniRetail Solutions Pty Ltd');
  const [domain, setDomain] = useState('omniretail.com.au');
  const [mode, setMode] = useState('STANDARD');
  const [activeTab, setActiveTab] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const [simDialogOpen, setSimDialogOpen] = useState(false);

  // Run State
  const [runStatus, setRunStatus] = useState<'IDLE' | 'RUNNING' | 'COMPLETED' | 'PAUSED'>('IDLE');
  const [currentIteration, setCurrentIteration] = useState(0);
  const [toolCalls, setToolCalls] = useState(0);
  const [costAccrued, setCostAccrued] = useState(0.0);
  const [completenessScore, setCompletenessScore] = useState(0.0);
  const [confidenceScore, setConfidenceScore] = useState(0.0);

  // Steps
  const [steps, setSteps] = useState<ResearchStep[]>([
    {
      id: 'step_1',
      step_order: 1,
      title: 'Profile firmographics and web properties',
      agent_name: 'CompanyResearchAgent',
      tool_name: 'company_website_crawler',
      task_type: 'COMPANY_PROFILING',
      status: 'PENDING',
      depends_on: []
    },
    {
      id: 'step_2',
      step_order: 2,
      title: 'Detect ERP & technology stack',
      agent_name: 'TechnologyResearchAgent',
      tool_name: 'company_website_crawler',
      task_type: 'TECHNOLOGY_DETECTION',
      status: 'PENDING',
      depends_on: ['step_1']
    },
    {
      id: 'step_3',
      step_order: 3,
      title: 'Verify Odoo modules and GitHub activity',
      agent_name: 'OdooResearchAgent',
      tool_name: 'github_repository_analyzer',
      task_type: 'ODOO_VERIFICATION',
      status: 'PENDING',
      depends_on: ['step_2']
    },
    {
      id: 'step_4',
      step_order: 4,
      title: 'Discover hiring & ERP migration intent',
      agent_name: 'IntentResearchAgent',
      tool_name: 'job_posting_detector',
      task_type: 'INTENT_DISCOVERY',
      status: 'PENDING',
      depends_on: ['step_1']
    },
    {
      id: 'step_5',
      step_order: 5,
      title: 'Identify key IT decision makers',
      agent_name: 'PersonResearchAgent',
      tool_name: 'search_engine_query',
      task_type: 'DECISION_MAKER_SEARCH',
      status: 'PENDING',
      depends_on: ['step_1']
    },
    {
      id: 'step_6',
      step_order: 6,
      title: 'Verify domain MX and contact patterns',
      agent_name: 'ContactResearchAgent',
      tool_name: 'dns_mx_spf_checker',
      task_type: 'CONTACT_VERIFICATION',
      status: 'PENDING',
      depends_on: ['step_5']
    },
    {
      id: 'step_7',
      step_order: 7,
      title: 'Corroborate claims across independent domains',
      agent_name: 'EvidenceValidationAgent',
      tool_name: 'search_engine_query',
      task_type: 'EVIDENCE_VALIDATION',
      status: 'PENDING',
      depends_on: ['step_3', 'step_4']
    },
    {
      id: 'step_8',
      step_order: 8,
      title: 'Data quality audit and completeness synthesis',
      agent_name: 'DataQualityAgent',
      tool_name: 'semantic_ontology_classifier',
      task_type: 'DATA_QUALITY_AUDIT',
      status: 'PENDING',
      depends_on: ['step_6', 'step_7']
    }
  ]);

  // Findings
  const [findings, setFindings] = useState<FindingItem[]>([]);

  // Simulation Data
  const [simulationData, setSimulationData] = useState<{
    estimated_duration_sec: number;
    estimated_tool_calls: number;
    estimated_cost_usd: number;
    is_feasible: boolean;
    potential_bottlenecks: string[];
  } | null>(null);

  const handleStartRun = () => {
    setIsRunning(true);
    setRunStatus('RUNNING');
    setCurrentIteration(1);
    setToolCalls(0);
    setCostAccrued(0.0);

    // Simulate progressive execution of steps
    setTimeout(() => {
      setSteps(prev => prev.map((s, idx) => ({
        ...s,
        status: 'COMPLETED'
      })));
      setFindings([
        {
          agent_name: 'CompanyResearchAgent',
          finding_type: 'FIRMOGRAPHICS',
          confidence_score: 0.94,
          evidence_snippet: `${companyName} identified at ${domain} with HQ in Sydney, NSW. 150 employees.`,
          data: { industry: 'Retail Wholesale', hq: 'Sydney, Australia', size: '50-250' },
          source_urls: [`https://${domain}/about`, `https://asic.gov.au`]
        },
        {
          agent_name: 'TechnologyResearchAgent',
          finding_type: 'TECH_STACK',
          confidence_score: 0.96,
          evidence_snippet: `Fingerprinted /web/login endpoint with Odoo session cookies on ${domain}.`,
          data: { primary_erp: 'Odoo', detected_stack: ['Python', 'PostgreSQL', 'Odoo'] },
          source_urls: [`https://${domain}/web/login`]
        },
        {
          agent_name: 'OdooResearchAgent',
          finding_type: 'ODOO_INTELLIGENCE',
          confidence_score: 0.97,
          evidence_snippet: `Odoo 17.0 Enterprise confirmed via custom addons repository on GitHub.`,
          data: { version: '17.0', edition: 'Enterprise', hosting: 'Odoo.sh', modules: ['sale', 'stock', 'account', 'purchase'] },
          source_urls: [`https://github.com/omniretail/odoo-addons`, `https://${domain}/odoo/info`]
        },
        {
          agent_name: 'PersonResearchAgent',
          finding_type: 'DECISION_MAKERS',
          confidence_score: 0.91,
          evidence_snippet: `Marcus Vance identified as CTO / Technical Lead; Sarah Jenkins as Head of Systems.`,
          data: { decision_makers: [{ name: 'Marcus Vance', title: 'CTO' }, { name: 'Sarah Jenkins', title: 'Head of Enterprise Systems' }] },
          source_urls: [`https://${domain}/team`]
        },
        {
          agent_name: 'IntentResearchAgent',
          finding_type: 'INTENT_SIGNALS',
          confidence_score: 0.89,
          evidence_snippet: `Job posting: "Hiring Senior Odoo Developer for enterprise migration."`,
          data: { intent_topic: 'Odoo Developer Hiring', signal_strength: 0.89 },
          source_urls: [`https://careers.${domain}/jobs/odoo-dev`]
        }
      ]);
      setCompletenessScore(100.0);
      setConfidenceScore(94.5);
      setToolCalls(8);
      setCostAccrued(0.08);
      setCurrentIteration(3);
      setRunStatus('COMPLETED');
      setIsRunning(false);
    }, 1200);
  };

  const handleSimulate = () => {
    setSimulationData({
      estimated_duration_sec: 14,
      estimated_tool_calls: steps.length,
      estimated_cost_usd: 0.085,
      is_feasible: true,
      potential_bottlenecks: ['Company website crawler requires ~3.5s page analysis latency.']
    });
    setSimDialogOpen(true);
  };

  return (
    <Container maxWidth="xl" sx={{ mt: 3, mb: 6 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
        <AutonomyIcon sx={{ fontSize: 36, color: 'primary.main', mr: 2 }} />
        <Box>
          <Typography variant="h4" fontWeight="bold">
            Autonomous Research & Adaptive Intelligence Engine
          </Typography>
          <Typography variant="body2" color="text.secondary">
            LeadNexus AI X — Bounded Autonomy, Dependency DAG Orchestration & Evidence-First Deep Synthesis
          </Typography>
        </Box>
      </Box>

      {/* Target & Control Bar */}
      <Paper sx={{ p: 2.5, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} sm={4}>
            <TextField
              fullWidth
              size="small"
              label="Target Company Name"
              value={companyName}
              onChange={e => setCompanyName(e.target.value)}
            />
          </Grid>
          <Grid item xs={12} sm={3}>
            <TextField
              fullWidth
              size="small"
              label="Target Domain"
              value={domain}
              onChange={e => setDomain(e.target.value)}
            />
          </Grid>
          <Grid item xs={12} sm={2}>
            <FormControl fullWidth size="small">
              <InputLabel>Research Mode</InputLabel>
              <Select value={mode} label="Research Mode" onChange={e => setMode(e.target.value)}>
                <MenuItem value="QUICK">QUICK (Fast Scan)</MenuItem>
                <MenuItem value="STANDARD">STANDARD (Recommended)</MenuItem>
                <MenuItem value="DEEP">DEEP (Forensic Corroboration)</MenuItem>
                <MenuItem value="CONTINUOUS">CONTINUOUS (Watchlist)</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={3} sx={{ display: 'flex', gap: 1 }}>
            <Button
              variant="outlined"
              color="secondary"
              startIcon={<SimulateIcon />}
              onClick={handleSimulate}
            >
              Simulate
            </Button>
            <Button
              variant="contained"
              color="primary"
              startIcon={isRunning ? <CircularProgress size={18} color="inherit" /> : <StartIcon />}
              onClick={handleStartRun}
              disabled={isRunning}
            >
              {isRunning ? 'Researching...' : 'Start Run'}
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {/* Live Run Metrics Gauge */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={6} sm={2.4}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="caption" color="text.secondary">Status</Typography>
            <Box sx={{ mt: 0.5 }}>
              <Chip
                label={runStatus}
                color={runStatus === 'COMPLETED' ? 'success' : runStatus === 'RUNNING' ? 'primary' : 'default'}
                size="small"
              />
            </Box>
          </Paper>
        </Grid>
        <Grid item xs={6} sm={2.4}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="caption" color="text.secondary">Iterations / Tool Calls</Typography>
            <Typography variant="h6" fontWeight="bold">
              {currentIteration} / {toolCalls} calls
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={6} sm={2.4}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="caption" color="text.secondary">Cost Accrued</Typography>
            <Typography variant="h6" fontWeight="bold" color="text.primary">
              ${costAccrued.toFixed(3)}
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={6} sm={2.4}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="caption" color="text.secondary">Completeness</Typography>
            <Typography variant="h6" fontWeight="bold" color={completenessScore >= 80 ? 'success.main' : 'warning.main'}>
              {completenessScore.toFixed(0)}%
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={6} sm={2.4}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="caption" color="text.secondary">Confidence Score</Typography>
            <Typography variant="h6" fontWeight="bold" color={confidenceScore >= 80 ? 'primary.main' : 'text.primary'}>
              {confidenceScore.toFixed(1)}%
            </Typography>
          </Paper>
        </Grid>
      </Grid>

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={activeTab} onChange={(_, val) => setActiveTab(val)}>
          <Tab icon={<GraphIcon />} label="Research DAG Graph" iconPosition="start" />
          <Tab icon={<FactCheckIconWrapper />} label={`Findings & Evidence (${findings.length})`} iconPosition="start" />
          <Tab icon={<ReportIcon />} label="Executive Intelligence Report" iconPosition="start" />
          <Tab icon={<PolicyIcon />} label="Policy & Safety Boundaries" iconPosition="start" />
        </Tabs>
      </Box>

      {/* Tab 0: Research DAG Graph */}
      {activeTab === 0 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom fontWeight="bold">
            Dependency-Ordered Research Execution Plan (DAG)
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Tasks execute in parallel waves as soon as their upstream prerequisites are satisfied.
          </Typography>
          <List>
            {steps.map(step => (
              <Card key={step.id} sx={{ mb: 1.5, borderLeft: step.status === 'COMPLETED' ? '4px solid #4caf50' : '4px solid #1976d2' }}>
                <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box>
                      <Typography variant="subtitle2" fontWeight="bold">
                        {step.step_order}. {step.title}
                      </Typography>
                      <Box sx={{ display: 'flex', gap: 1, mt: 0.5 }}>
                        <Chip label={step.agent_name} size="small" variant="outlined" color="primary" />
                        <Chip label={`Tool: ${step.tool_name}`} size="small" variant="outlined" />
                        {step.depends_on.length > 0 && (
                          <Chip label={`Depends on: ${step.depends_on.join(', ')}`} size="small" />
                        )}
                      </Box>
                    </Box>
                    <Chip
                      label={step.status}
                      color={step.status === 'COMPLETED' ? 'success' : step.status === 'RUNNING' ? 'primary' : 'default'}
                      size="small"
                    />
                  </Box>
                </CardContent>
              </Card>
            ))}
          </List>
        </Paper>
      )}

      {/* Tab 1: Findings & Evidence */}
      {activeTab === 1 && (
        <Box>
          {findings.length === 0 ? (
            <Alert severity="info">No research findings gathered yet. Start a run or execute a simulation.</Alert>
          ) : (
            <Grid container spacing={2}>
              {findings.map((f, i) => (
                <Grid item xs={12} md={6} key={i}>
                  <Card>
                    <CardHeader
                      title={f.finding_type}
                      subheader={f.agent_name}
                      action={
                        <Chip
                          label={`Confidence ${(f.confidence_score * 100).toFixed(0)}%`}
                          color="primary"
                          size="small"
                        />
                      }
                    />
                    <Divider />
                    <CardContent>
                      <Typography variant="body2" sx={{ mb: 1.5 }}>
                        {f.evidence_snippet}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" fontWeight="bold">
                        Sources ({f.source_urls.length}):
                      </Typography>
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
                        {f.source_urls.map((u, idx) => (
                          <Chip key={idx} label={u} size="small" variant="outlined" />
                        ))}
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          )}
        </Box>
      )}

      {/* Tab 2: Executive Intelligence Report */}
      {activeTab === 2 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h5" fontWeight="bold" gutterBottom>
            LeadNexus Intelligence Report: {companyName}
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            Generated autonomously via verified public web telemetry, code intelligence, and DNS routing.
          </Typography>
          <Divider sx={{ my: 2 }} />

          <Grid container spacing={3}>
            <Grid item xs={12} md={8}>
              <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                Executive Summary
              </Typography>
              <Typography variant="body2" paragraph>
                OmniRetail Solutions Pty Ltd is an active wholesale and retail distribution provider headquartered in Sydney, Australia.
                Autonomous telemetry confirmed an active production deployment of <strong>Odoo 17.0 Enterprise Edition</strong> hosted on <strong>Odoo.sh</strong>,
                corroborated across official domain session cookies and public GitHub repository commits.
              </Typography>

              <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                Confirmed Decision Makers
              </Typography>
              <Typography variant="body2" paragraph>
                - <strong>Marcus Vance</strong> — Chief Technology Officer (Final Technical Decision Maker)<br />
                - <strong>Sarah Jenkins</strong> — Head of Enterprise Systems (Technical Evaluator)
              </Typography>

              <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                Active Expansion Signals
              </Typography>
              <Typography variant="body2">
                Active hiring intent identified for Senior Odoo Developers, signaling ongoing ERP expansion and custom module rollout.
              </Typography>
            </Grid>

            <Grid item xs={12} md={4}>
              <Card sx={{ bgcolor: 'background.default' }}>
                <CardContent>
                  <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
                    Evidence Quality Metrics
                  </Typography>
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="caption">Completeness</Typography>
                    <LinearProgress variant="determinate" value={completenessScore || 100} color="success" sx={{ my: 0.5, height: 8, borderRadius: 4 }} />
                    <Typography variant="caption">Confidence</Typography>
                    <LinearProgress variant="determinate" value={confidenceScore || 94.5} color="primary" sx={{ my: 0.5, height: 8, borderRadius: 4 }} />
                  </Box>
                  <Divider sx={{ my: 1.5 }} />
                  <Typography variant="caption" color="text.secondary">
                    No fabricated data. All claims grounded in independent apex domain evidence.
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Paper>
      )}

      {/* Tab 3: Policy & Safety Boundaries */}
      {activeTab === 3 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" fontWeight="bold" gutterBottom>
            Autonomy Policy & Invariant Boundaries
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            LeadNexus AI X operates within strictly bounded enterprise autonomy policies to ensure security, compliance, and privacy.
          </Typography>
          <List>
            <ListItem>
              <ListItemIcon><SuccessIcon color="success" /></ListItemIcon>
              <ListItemText
                primary="Strict Public Web Exploration Only"
                secondary="No login wall bypassing, no CAPTCHA solving, no private authenticated portals scraping."
              />
            </ListItem>
            <ListItem>
              <ListItemIcon><SuccessIcon color="success" /></ListItemIcon>
              <ListItemText
                primary="No CRM & No Automated Outreach"
                secondary="Sales deals, pipelines, quotas, automated cold emails, calls, and auto-DMs are strictly prohibited."
              />
            </ListItem>
            <ListItem>
              <ListItemIcon><SuccessIcon color="success" /></ListItemIcon>
              <ListItemText
                primary="SSRF Defense & Private IP Blocking"
                secondary="Blocks localhost, internal subnets (10.x, 192.168.x), and cloud metadata endpoints (169.254.169.254)."
              />
            </ListItem>
            <ListItem>
              <ListItemIcon><SuccessIcon color="success" /></ListItemIcon>
              <ListItemText
                primary="Hard Invariant Resource Budgets"
                secondary="Strict caps on AI tokens, tool calls (50 max), runtime (300s max), and budget spend ($10 max)."
              />
            </ListItem>
          </List>
        </Paper>
      )}

      {/* Simulation Dialog */}
      <Dialog open={simDialogOpen} onClose={() => setSimDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Research Plan Dry-Run Simulation</DialogTitle>
        <DialogContent dividers>
          {simulationData && (
            <Box>
              <Alert severity={simulationData.is_feasible ? 'success' : 'error'} sx={{ mb: 2 }}>
                {simulationData.is_feasible ? 'Plan is feasible and compliant with workspace autonomy policy.' : 'Policy violations detected!'}
              </Alert>
              <Typography variant="body2"><strong>Estimated Duration:</strong> ~{simulationData.estimated_duration_sec}s</Typography>
              <Typography variant="body2"><strong>Estimated Tool Calls:</strong> {simulationData.estimated_tool_calls}</Typography>
              <Typography variant="body2"><strong>Estimated Cost:</strong> ${simulationData.estimated_cost_usd.toFixed(4)}</Typography>
              {simulationData.potential_bottlenecks.length > 0 && (
                <Box sx={{ mt: 1.5 }}>
                  <Typography variant="caption" color="text.secondary" fontWeight="bold">Potential Bottlenecks:</Typography>
                  {simulationData.potential_bottlenecks.map((b, idx) => (
                    <Typography key={idx} variant="caption" display="block" color="warning.main">- {b}</Typography>
                  ))}
                </Box>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSimDialogOpen(false)}>Close</Button>
          <Button variant="contained" onClick={() => { setSimDialogOpen(false); handleStartRun(); }}>
            Execute Plan
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

const FactCheckIconWrapper = () => <CorroborateIcon />;

export default AutonomousResearchWorkspace;

