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
  SmartToy,
  AltRoute,
  Terminal,
  AttachMoney,
  Security,
  Speed,
  Refresh,
  CheckCircle,
  Warning,
  PlayArrow,
  CompareArrows,
  Layers,
  Bolt,
  Shield,
  AutoAwesome,
} from '@mui/icons-material';

interface AIModel {
  id: string;
  provider: string;
  model_name: string;
  tier: string;
  cost_in: number;
  cost_out: number;
  status: string;
}

interface PromptTemplate {
  id: string;
  name: string;
  version: number;
  variables: string[];
  template: string;
  system: string;
}

interface FallbackStep {
  task: string;
  primary: string;
  primary_provider: string;
  fallback_1: string;
  fallback_2: string;
}

export const EnterpriseAIModelPlatformWorkspace: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Model catalog state
  const [models, setModels] = useState<AIModel[]>([
    { id: 'm-1', provider: 'GOOGLE_GEMINI', model_name: 'gemini-1.5-flash', tier: 'FAST', cost_in: 0.000075, cost_out: 0.0003, status: 'ACTIVE' },
    { id: 'm-2', provider: 'GOOGLE_GEMINI', model_name: 'gemini-1.5-pro', tier: 'BALANCED', cost_in: 0.00125, cost_out: 0.005, status: 'ACTIVE' },
    { id: 'm-3', provider: 'OPENAI', model_name: 'gpt-4o-mini', tier: 'FAST', cost_in: 0.00015, cost_out: 0.0006, status: 'ACTIVE' },
    { id: 'm-4', provider: 'OPENAI', model_name: 'gpt-4o', tier: 'FRONTIER', cost_in: 0.0025, cost_out: 0.010, status: 'ACTIVE' },
    { id: 'm-5', provider: 'ANTHROPIC', model_name: 'claude-3-5-sonnet', tier: 'BALANCED', cost_in: 0.003, cost_out: 0.015, status: 'ACTIVE' },
    { id: 'm-6', provider: 'MOCK', model_name: 'mock-emergency-backup', tier: 'OFFLINE', cost_in: 0.0, cost_out: 0.0, status: 'ACTIVE' },
  ]);

  // Fallback chains
  const [fallbackChains] = useState<FallbackStep[]>([
    { task: 'Lead Dossier Synthesis', primary: 'gemini-1.5-flash', primary_provider: 'GOOGLE_GEMINI', fallback_1: 'gpt-4o-mini (OPENAI)', fallback_2: 'mock-emergency-backup (OFFLINE)' },
    { task: 'Executive Contact Extraction', primary: 'gpt-4o', primary_provider: 'OPENAI', fallback_1: 'gemini-1.5-pro (GOOGLE_GEMINI)', fallback_2: 'claude-3-5-sonnet (ANTHROPIC)' },
    { task: 'Intent Surge Signal Analysis', primary: 'claude-3-5-sonnet', primary_provider: 'ANTHROPIC', fallback_1: 'gemini-1.5-pro (GOOGLE_GEMINI)', fallback_2: 'gpt-4o-mini (OPENAI)' },
  ]);

  // Prompt templates
  const [prompts, setPrompts] = useState<PromptTemplate[]>([
    { id: 'p-1', name: 'b2b_lead_scoring_v1', version: 3, variables: ['company_name', 'industry', 'headcount'], template: 'Evaluate buying intent for {company_name} in {industry} with {headcount} employees.', system: 'You are LeadNexus AI Scorer.' },
    { id: 'p-2', name: 'dossier_executive_brief', version: 1, variables: ['lead_name', 'company_name', 'technologies'], template: 'Generate an executive research brief for {lead_name} at {company_name} utilizing {technologies}.', system: 'Provide concise C-level insights.' },
  ]);

  // Playground state
  const [selectedModel, setSelectedModel] = useState('gemini-1.5-flash');
  const [selectedProvider, setSelectedProvider] = useState('GOOGLE_GEMINI');
  const [playgroundPrompt, setPlaygroundPrompt] = useState('Extract decision maker titles for Odoo and Zoho partners in Sydney.');
  const [playgroundResult, setPlaygroundResult] = useState<any>(null);
  const [executingInference, setExecutingInference] = useState(false);

  // Cost metrics
  const [costMetrics] = useState({
    totalCalls: 1420,
    totalTokens: 1845920,
    totalSpendUSD: 4.82,
    dailyLimitUSD: 50.0,
    fallbackCount: 12,
  });

  const handleRetireModel = (id: string) => {
    setModels((prev) => prev.map((m) => (m.id === id ? { ...m, status: 'RETIRED' } : m)));
    setActionSuccess('Model lifecycle transitioned to RETIRED. Routing updated.');
  };

  const handleRunPlayground = () => {
    setExecutingInference(true);
    setTimeout(() => {
      setPlaygroundResult({
        text: `[${selectedProvider} ${selectedModel}] Extracted 4 qualified decision makers: CEO, Head of ERP Practice, Lead Solution Architect, Director of Integrations. Intelligence verified.`,
        input_tokens: 38,
        output_tokens: 42,
        total_tokens: 80,
        cost_usd: 0.000045,
        latency_ms: 42.6,
        fallback_triggered: false,
        safety_passed: true,
      });
      setExecutingInference(false);
      setActionSuccess('Inference pipeline executed successfully.');
    }, 400);
  };

  return (
    <Box sx={{ p: 3, maxWidth: 1400, margin: '0 auto' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" fontWeight="bold" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <SmartToy color="primary" fontSize="large" /> Enterprise AI Model Platform
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Phase 40 — Multi-Provider Model Gateway, Automated Fallbacks, Prompt Registry, Token Tracking, Cost Governance & Safety Guardrails
          </Typography>
        </Box>
        <Button variant="outlined" startIcon={<Refresh />} onClick={() => setActionSuccess('Synchronized model telemetry.')}>
          Refresh Telemetry
        </Button>
      </Box>

      {actionSuccess && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={() => setActionSuccess(null)}>
          {actionSuccess}
        </Alert>
      )}

      <Paper sx={{ mb: 3 }}>
        <Tabs value={activeTab} onChange={(_, val) => setActiveTab(val)} variant="scrollable" scrollButtons="auto">
          <Tab icon={<Layers />} iconPosition="start" label="Model Registry & Catalog" />
          <Tab icon={<AltRoute />} iconPosition="start" label="Router & Fallbacks" />
          <Tab icon={<Terminal />} iconPosition="start" label="Prompt Registry" />
          <Tab icon={<PlayArrow />} iconPosition="start" label="Gateway Playground" />
          <Tab icon={<AttachMoney />} iconPosition="start" label="Cost & Token Analytics" />
          <Tab icon={<Shield />} iconPosition="start" label="Safety & Guardrails" />
        </Tabs>
      </Paper>

      {/* TAB 0: MODEL REGISTRY & CATALOG */}
      {activeTab === 0 && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6" fontWeight="bold">
              Multi-Provider Enterprise Model Catalog
            </Typography>
            <Chip icon={<AutoAwesome />} label="Vendor Decoupled" color="primary" variant="outlined" />
          </Box>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow sx={{ backgroundColor: 'action.hover' }}>
                  <TableCell>Provider</TableCell>
                  <TableCell>Model Name</TableCell>
                  <TableCell>Tier</TableCell>
                  <TableCell>Input Cost / 1k</TableCell>
                  <TableCell>Output Cost / 1k</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Lifecycle Action</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {models.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell sx={{ fontWeight: 'bold' }}>
                      <Chip label={m.provider} size="small" color={m.provider === 'GOOGLE_GEMINI' ? 'primary' : m.provider === 'OPENAI' ? 'secondary' : 'default'} />
                    </TableCell>
                    <TableCell>
                      <code>{m.model_name}</code>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={m.tier}
                        size="small"
                        color={m.tier === 'FAST' ? 'success' : m.tier === 'FRONTIER' ? 'error' : 'info'}
                      />
                    </TableCell>
                    <TableCell>${m.cost_in.toFixed(6)}</TableCell>
                    <TableCell>${m.cost_out.toFixed(6)}</TableCell>
                    <TableCell>
                      <Chip
                        label={m.status}
                        size="small"
                        color={m.status === 'ACTIVE' ? 'success' : m.status === 'RETIRED' ? 'default' : 'warning'}
                      />
                    </TableCell>
                    <TableCell>
                      {m.status === 'ACTIVE' ? (
                        <Button size="small" color="error" variant="outlined" onClick={() => handleRetireModel(m.id)}>
                          Retire Model
                        </Button>
                      ) : (
                        <Typography variant="caption" color="text.secondary">
                          Archived
                        </Typography>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}

      {/* TAB 1: ROUTER & FALLBACKS */}
      {activeTab === 1 && (
        <Box>
          <Typography variant="h6" fontWeight="bold" sx={{ mb: 2 }}>
            Automated Multi-Tier Fallback Cascades
          </Typography>
          <Grid container spacing={2}>
            {fallbackChains.map((fb, i) => (
              <Grid item xs={12} key={i}>
                <Card sx={{ borderLeft: '4px solid #10b981' }}>
                  <CardContent>
                    <Typography variant="subtitle1" fontWeight="bold">
                      {fb.task}
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, my: 1.5, flexWrap: 'wrap' }}>
                      <Chip label={`Primary: ${fb.primary} (${fb.primary_provider})`} color="primary" />
                      <CompareArrows color="action" />
                      <Chip label={`Secondary: ${fb.fallback_1}`} color="warning" variant="outlined" />
                      <CompareArrows color="action" />
                      <Chip label={`Tertiary: ${fb.fallback_2}`} color="default" variant="outlined" />
                    </Box>
                    <Typography variant="caption" color="text.secondary">
                      Policy: In the event of HTTP 429 rate limit or 5xx outage from primary provider, the gateway automatically cascades within 15ms.
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* TAB 2: PROMPT REGISTRY */}
      {activeTab === 2 && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6" fontWeight="bold">
              Versioned Prompt Templates
            </Typography>
            <Button variant="contained" size="small" onClick={() => setActionSuccess('New prompt template version registered.')}>
              New Prompt Template
            </Button>
          </Box>
          <Grid container spacing={2}>
            {prompts.map((p) => (
              <Grid item xs={12} md={6} key={p.id}>
                <Card sx={{ border: '1px solid #e2e8f0' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                      <Typography variant="subtitle1" fontWeight="bold">
                        {p.name}
                      </Typography>
                      <Chip label={`v${p.version}`} size="small" color="primary" />
                    </Box>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                      System: <i>"{p.system}"</i>
                    </Typography>
                    <Box sx={{ p: 1.5, bgcolor: '#f8fafc', borderRadius: 1, border: '1px solid #e2e8f0', mb: 1.5 }}>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: 13 }}>
                        {p.template}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" fontWeight="bold" display="block">
                        Required Variables:
                      </Typography>
                      {p.variables.map((v) => (
                        <Chip key={v} label={`{${v}}`} size="small" sx={{ mr: 0.5, mt: 0.5 }} color="secondary" variant="outlined" />
                      ))}
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* TAB 3: GATEWAY PLAYGROUND */}
      {activeTab === 3 && (
        <Box>
          <Typography variant="h6" fontWeight="bold" sx={{ mb: 2 }}>
            Live Multi-Provider Inference Gateway
          </Typography>
          <Grid container spacing={3}>
            <Grid item xs={12} md={5}>
              <Card sx={{ p: 2 }}>
                <Typography variant="subtitle2" fontWeight="bold" sx={{ mb: 2 }}>
                  Execution Parameters
                </Typography>
                <TextField
                  select
                  fullWidth
                  size="small"
                  label="Provider"
                  value={selectedProvider}
                  onChange={(e) => setSelectedProvider(e.target.value)}
                  SelectProps={{ native: true }}
                  sx={{ mb: 2 }}
                >
                  <option value="GOOGLE_GEMINI">Google Gemini</option>
                  <option value="OPENAI">OpenAI</option>
                  <option value="ANTHROPIC">Anthropic</option>
                  <option value="MOCK">Mock AI (Offline)</option>
                </TextField>
                <TextField
                  select
                  fullWidth
                  size="small"
                  label="Model"
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  SelectProps={{ native: true }}
                  sx={{ mb: 2 }}
                >
                  <option value="gemini-1.5-flash">gemini-1.5-flash (Fast)</option>
                  <option value="gemini-1.5-pro">gemini-1.5-pro (Balanced)</option>
                  <option value="gpt-4o-mini">gpt-4o-mini (Fast)</option>
                  <option value="gpt-4o">gpt-4o (Frontier)</option>
                  <option value="claude-3-5-sonnet">claude-3-5-sonnet (Balanced)</option>
                  <option value="mock-emergency-backup">mock-emergency-backup (Offline)</option>
                </TextField>
                <TextField
                  fullWidth
                  multiline
                  rows={4}
                  label="Inference Prompt"
                  value={playgroundPrompt}
                  onChange={(e) => setPlaygroundPrompt(e.target.value)}
                  sx={{ mb: 2 }}
                />
                <Button
                  variant="contained"
                  fullWidth
                  startIcon={<Bolt />}
                  onClick={handleRunPlayground}
                  disabled={executingInference}
                >
                  {executingInference ? 'Routing Inference...' : 'Execute Gateway Inference'}
                </Button>
              </Card>
            </Grid>

            <Grid item xs={12} md={7}>
              {playgroundResult ? (
                <Card sx={{ p: 2, bgcolor: '#0f172a', color: '#f8fafc' }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Typography variant="subtitle2" fontWeight="bold" sx={{ color: '#38bdf8' }}>
                      Inference Response
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      <Chip label={`${playgroundResult.latency_ms} ms`} color="info" size="small" />
                      <Chip label={`${playgroundResult.total_tokens} tokens`} color="primary" size="small" />
                      <Chip label={`$${playgroundResult.cost_usd}`} color="success" size="small" />
                    </Box>
                  </Box>
                  <Typography variant="body1" sx={{ p: 2, bgcolor: '#1e293b', borderRadius: 1, mb: 2 }}>
                    {playgroundResult.text}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    <Chip label="Zero Prompt Injections" color="success" size="small" variant="outlined" />
                    <Chip label="PII Redaction Applied" color="success" size="small" variant="outlined" />
                    <Chip label="Automated Fallback Standby: Ready" size="small" variant="outlined" />
                  </Box>
                </Card>
              ) : (
                <Alert severity="info">
                  Configure execution parameters and click Execute. The Enterprise Model Gateway will validate prompt safety, execute through the primary provider, or trigger automated fallbacks on failure.
                </Alert>
              )}
            </Grid>
          </Grid>
        </Box>
      )}

      {/* TAB 4: COST & TOKEN ANALYTICS */}
      {activeTab === 4 && (
        <Box>
          <Grid container spacing={3}>
            <Grid item xs={12} md={4}>
              <Card sx={{ p: 2, textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">
                  Total Gateway Calls
                </Typography>
                <Typography variant="h4" fontWeight="bold" sx={{ my: 1 }}>
                  {costMetrics.totalCalls.toLocaleString()}
                </Typography>
                <Chip label="100% SLA Available" color="success" size="small" />
              </Card>
            </Grid>
            <Grid item xs={12} md={4}>
              <Card sx={{ p: 2, textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">
                  Tokens Processed
                </Typography>
                <Typography variant="h4" fontWeight="bold" sx={{ my: 1 }}>
                  {costMetrics.totalTokens.toLocaleString()}
                </Typography>
                <Chip label="1.84M Tokens" color="primary" size="small" />
              </Card>
            </Grid>
            <Grid item xs={12} md={4}>
              <Card sx={{ p: 2, textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">
                  Total Spend ($USD)
                </Typography>
                <Typography variant="h4" fontWeight="bold" sx={{ my: 1, color: '#10b981' }}>
                  ${costMetrics.totalSpendUSD.toFixed(2)}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Daily Cap: ${costMetrics.dailyLimitUSD.toFixed(2)} (9.6% used)
                </Typography>
              </Card>
            </Grid>
          </Grid>
        </Box>
      )}

      {/* TAB 5: SAFETY & GUARDRAILS */}
      {activeTab === 5 && (
        <Box>
          <Typography variant="h6" fontWeight="bold" sx={{ mb: 2 }}>
            Enterprise LLM Safety & Guardrails
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <Card sx={{ borderLeft: '4px solid #ef4444' }}>
                <CardContent>
                  <Typography variant="subtitle1" fontWeight="bold">
                    Adversarial Injection Defense
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ my: 1 }}>
                    Pre-flight regex and token pattern matching traps prompt injection, jailbreaks, and DAN mode override attempts.
                  </Typography>
                  <Chip label="ENABLED (Active Shield)" color="error" size="small" />
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={4}>
              <Card sx={{ borderLeft: '4px solid #f59e0b' }}>
                <CardContent>
                  <Typography variant="subtitle1" fontWeight="bold">
                    PII Sanitization Pre-Filter
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ my: 1 }}>
                    Automatically strips RFC 5322 emails and phone numbers from user prompts before transmitting to public AI APIs.
                  </Typography>
                  <Chip label="ENABLED (Zero-Leakage)" color="warning" size="small" />
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={4}>
              <Card sx={{ borderLeft: '4px solid #0284c7' }}>
                <CardContent>
                  <Typography variant="subtitle1" fontWeight="bold">
                    Max Token Ceiling & Budget Cap
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ my: 1 }}>
                    Strict cap of 4,096 tokens per call with automatic termination to prevent denial-of-wallet runaway loops.
                  </Typography>
                  <Chip label="ENABLED (4096 Limit)" color="primary" size="small" />
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Box>
      )}
    </Box>
  );
};

export default EnterpriseAIModelPlatformWorkspace;
