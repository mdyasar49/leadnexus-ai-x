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
  Activity,
  BarChart2,
  GitCommit,
  DollarSign,
  AlertOctagon,
  FileCode,
  RefreshCw,
  Search,
  CheckCircle2,
  Clock,
  Layers,
  Cpu,
  ShieldCheck,
  TrendingUp,
  Radio,
  Server,
  Zap,
} from 'lucide-react';

interface MetricItem {
  name: string;
  type: string;
  value: number;
  unit: string;
  change: string;
}

interface SpanItem {
  id: string;
  trace_id: string;
  operation_name: string;
  service_name: string;
  duration_ms: number;
  offset_ms: number;
  status_code: string;
}

interface CostItem {
  category: string;
  micros: number;
  usd: string;
  percentage: number;
}

interface AlertRuleItem {
  id: string;
  name: string;
  metric_name: string;
  condition: string;
  threshold: number;
  severity: string;
}

interface AlertEventItem {
  id: string;
  rule_name: string;
  metric_name: string;
  observed_value: number;
  threshold: number;
  severity: string;
  status: string;
  triggered_at: string;
}

const INITIAL_METRICS: MetricItem[] = [
  { name: 'api.requests.total', type: 'COUNTER', value: 148290, unit: 'reqs', change: '+12.4%' },
  { name: 'api.request.latency.p50', type: 'GAUGE', value: 42.5, unit: 'ms', change: '-4.1%' },
  { name: 'api.request.latency.p95', type: 'GAUGE', value: 185.0, unit: 'ms', change: '+2.0%' },
  { name: 'api.request.latency.p99', type: 'GAUGE', value: 410.2, unit: 'ms', change: '-1.5%' },
  { name: 'worker.pool.utilization', type: 'GAUGE', value: 62.5, unit: '%', change: '+5.0%' },
  { name: 'platform.error_rate', type: 'GAUGE', value: 0.08, unit: '%', change: '-0.02%' },
];

const INITIAL_SPANS: SpanItem[] = [
  {
    id: 'sp-1',
    trace_id: 'tr-8f9210bc91',
    operation_name: 'POST /api/v1/search',
    service_name: 'api-gateway',
    duration_ms: 185.4,
    offset_ms: 0.0,
    status_code: 'OK',
  },
  {
    id: 'sp-2',
    trace_id: 'tr-8f9210bc91',
    operation_name: 'query.database.leads',
    service_name: 'db-postgres',
    duration_ms: 18.2,
    offset_ms: 12.0,
    status_code: 'OK',
  },
  {
    id: 'sp-3',
    trace_id: 'tr-8f9210bc91',
    operation_name: 'model_router.dispatch',
    service_name: 'ai-platform',
    duration_ms: 142.1,
    offset_ms: 32.5,
    status_code: 'OK',
  },
  {
    id: 'sp-4',
    trace_id: 'tr-8f9210bc91',
    operation_name: 'provenance.verify_proof',
    service_name: 'doc-intelligence',
    duration_ms: 8.5,
    offset_ms: 175.0,
    status_code: 'OK',
  },
];

const INITIAL_COSTS: CostItem[] = [
  { category: 'AI Inference (Tokens)', micros: 18450000, usd: '$18.45', percentage: 65 },
  { category: 'Worker Compute Time', micros: 5200000, usd: '$5.20', percentage: 18 },
  { category: 'Document Ingestion & OCR', micros: 3100000, usd: '$3.10', percentage: 11 },
  { category: 'External Data Feeds', micros: 1700000, usd: '$1.70', percentage: 6 },
];

const INITIAL_ALERT_RULES: AlertRuleItem[] = [
  {
    id: 'rule-sla-latency',
    name: 'API Latency SLA Breach',
    metric_name: 'api.request.latency',
    condition: 'GT',
    threshold: 1500.0,
    severity: 'WARNING',
  },
  {
    id: 'rule-error-rate',
    name: 'Critical Error Rate Spike',
    metric_name: 'platform.error_rate',
    condition: 'GT',
    threshold: 0.05,
    severity: 'CRITICAL',
  },
  {
    id: 'rule-budget-cap',
    name: 'Daily Spend Threshold',
    metric_name: 'workspace.daily.cost',
    condition: 'GT',
    threshold: 50.0,
    severity: 'WARNING',
  },
];

const INITIAL_ALERT_EVENTS: AlertEventItem[] = [
  {
    id: 'evt-001',
    rule_name: 'API Latency SLA Breach',
    metric_name: 'api.request.latency',
    observed_value: 1620.0,
    threshold: 1500.0,
    severity: 'WARNING',
    status: 'RESOLVED',
    triggered_at: '2026-11-01 10:45:00',
  },
];

const PROMETHEUS_SAMPLE = `# HELP leadnexus_api_requests_total Monotonic counter of API requests
# TYPE leadnexus_api_requests_total counter
leadnexus_api_requests_total{status="200"} 148202
leadnexus_api_requests_total{status="500"} 88

# HELP leadnexus_request_duration_ms Request latency quantiles
# TYPE leadnexus_request_duration_ms summary
leadnexus_request_duration_ms{quantile="0.5"} 42.5
leadnexus_request_duration_ms{quantile="0.9"} 124.0
leadnexus_request_duration_ms{quantile="0.95"} 185.0
leadnexus_request_duration_ms{quantile="0.99"} 410.2
leadnexus_request_duration_ms_count 148290
leadnexus_request_duration_ms_sum 6302325.0

# HELP leadnexus_worker_pool_utilization Percentage of worker slots active
# TYPE leadnexus_worker_pool_utilization gauge
leadnexus_worker_pool_utilization 0.625

# HELP leadnexus_daily_spend_usd Real-time operational spend in USD
# TYPE leadnexus_daily_spend_usd gauge
leadnexus_daily_spend_usd{workspace="default"} 28.45`;

export const EnterpriseTelemetryWorkspace: React.FC = () => {
  const [tabIndex, setTabIndex] = useState<number>(0);
  const [metrics, setMetrics] = useState<MetricItem[]>(INITIAL_METRICS);
  const [spans, setSpans] = useState<SpanItem[]>(INITIAL_SPANS);
  const [costs, setCosts] = useState<CostItem[]>(INITIAL_COSTS);
  const [rules, setRules] = useState<AlertRuleItem[]>(INITIAL_ALERT_RULES);
  const [events, setEvents] = useState<AlertEventItem[]>(INITIAL_ALERT_EVENTS);
  const [traceSearch, setTraceSearch] = useState<string>('tr-8f9210bc91');
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // New Alert Rule Dialog
  const [openNewRuleDialog, setOpenNewRuleDialog] = useState<boolean>(false);
  const [newRuleName, setNewRuleName] = useState<string>('Worker Queue Depth Alert');
  const [newRuleMetric, setNewRuleMetric] = useState<string>('worker.queue.depth');
  const [newRuleThreshold, setNewRuleThreshold] = useState<number>(20);
  const [newRuleSeverity, setNewRuleSeverity] = useState<string>('WARNING');

  const handleCreateRule = () => {
    const newR: AlertRuleItem = {
      id: `rule-${Date.now().toString(36)}`,
      name: newRuleName,
      metric_name: newRuleMetric,
      condition: 'GT',
      threshold: newRuleThreshold,
      severity: newRuleSeverity,
    };
    setRules([...rules, newR]);
    setOpenNewRuleDialog(false);
    setSuccessMsg(`SLA Alert Rule "${newRuleName}" created and active.`);
  };

  const handleResolveEvent = (evId: string) => {
    setEvents(events.map((e) => (e.id === evId ? { ...e, status: 'RESOLVED' } : e)));
    setSuccessMsg('Alert event marked as RESOLVED.');
  };

  return (
    <Box sx={{ p: 4, maxWidth: 1440, margin: '0 auto' }}>
      {/* Header */}
      <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
            <Activity size={28} color="#0284c7" />
            <Typography variant="h4" sx={{ fontWeight: 700, color: '#0f172a' }}>
              Enterprise Analytics, Observability & Platform Telemetry
            </Typography>
            <Chip label="Phase 44" color="primary" size="small" sx={{ fontWeight: 600 }} />
          </Box>
          <Typography variant="body1" sx={{ color: '#64748b' }}>
            Time-series metric quantiles, OpenTelemetry distributed tracing, multi-dimensional cost attribution,
            and dynamic SLA anomaly alerting.
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="outlined"
            startIcon={<RefreshCw size={16} />}
            onClick={() => setSuccessMsg('Telemetry metrics and traces refreshed.')}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<AlertOctagon size={16} />}
            onClick={() => setOpenNewRuleDialog(true)}
            sx={{ bgcolor: '#0284c7', '&:hover': { bgcolor: '#0369a1' } }}
          >
            Add Alert Rule
          </Button>
        </Box>
      </Box>

      {/* Primary Invariant Banner */}
      <Alert severity="info" sx={{ mb: 3, border: '1px solid #bae6fd', bgcolor: '#f0f9ff' }}>
        <strong>Invariant Rule Enforced:</strong> Platform telemetry, tracing spans, and cost attribution instrumentation
        are strictly read-only observation layers and <strong>never</strong> mutate or pollute Saved Leads or Export datasets.
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
          <Tab icon={<BarChart2 size={18} />} iconPosition="start" label="Real-Time Metrics" />
          <Tab icon={<GitCommit size={18} />} iconPosition="start" label="Distributed Tracing" />
          <Tab icon={<DollarSign size={18} />} iconPosition="start" label="Cost Attribution" />
          <Tab icon={<AlertOctagon size={18} />} iconPosition="start" label={`SLA Alerts (${rules.length})`} />
          <Tab icon={<FileCode size={18} />} iconPosition="start" label="Prometheus Exporter" />
          <Tab icon={<Cpu size={18} />} iconPosition="start" label="Subsystem Health" />
        </Tabs>
      </Paper>

      {/* TAB 0: Real-Time Metrics */}
      {tabIndex === 0 && (
        <Grid container spacing={3}>
          {metrics.map((m) => (
            <Grid item xs={12} sm={6} md={4} key={m.name}>
              <Card sx={{ borderRadius: 2, height: '100%' }}>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                    <Typography variant="caption" sx={{ color: '#64748b', fontWeight: 600 }}>
                      {m.type}
                    </Typography>
                    <Chip
                      label={m.change}
                      size="small"
                      color={m.change.startsWith('+') ? 'success' : 'default'}
                      variant="outlined"
                    />
                  </Box>
                  <Typography variant="h4" sx={{ fontWeight: 700, color: '#0f172a', mb: 0.5 }}>
                    {m.value.toLocaleString()} {m.unit}
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#475569', fontFamily: 'monospace', fontSize: '0.85rem' }}>
                    {m.name}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* TAB 1: Distributed Tracing */}
      {tabIndex === 1 && (
        <Card sx={{ borderRadius: 2 }}>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
              <Box>
                <Typography variant="h6" sx={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <GitCommit size={20} color="#0284c7" />
                  Distributed Trace Waterfall Explorer
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  OpenTelemetry-compatible span execution timelines across API, database, AI inference, and document OCR.
                </Typography>
              </Box>
              <TextField
                size="small"
                value={traceSearch}
                onChange={(e) => setTraceSearch(e.target.value)}
                placeholder="Trace ID..."
                InputProps={{
                  startAdornment: <Search size={16} style={{ marginRight: 8, color: '#94a3b8' }} />,
                }}
              />
            </Box>

            <Paper sx={{ p: 2, bgcolor: '#f8fafc', borderRadius: 2, mb: 3, border: '1px solid #e2e8f0' }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, color: '#0f172a' }}>
                  Trace: {traceSearch} · Total Duration: 185.4ms · 4 Spans
                </Typography>
                <Chip label="Status: OK" color="success" size="small" />
              </Box>
            </Paper>

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {spans.map((sp) => {
                const leftPct = (sp.offset_ms / 185.4) * 100;
                const widthPct = Math.max(5, (sp.duration_ms / 185.4) * 100);

                return (
                  <Paper key={sp.id} sx={{ p: 2, border: '1px solid #e2e8f0', borderRadius: 2 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                      <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center' }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 600, color: '#0f172a' }}>
                          {sp.operation_name}
                        </Typography>
                        <Chip label={sp.service_name} size="small" variant="outlined" />
                      </Box>
                      <Typography variant="caption" sx={{ fontWeight: 700, color: '#0284c7' }}>
                        {sp.duration_ms} ms
                      </Typography>
                    </Box>

                    {/* Waterfall bar */}
                    <Box sx={{ width: '100%', height: 10, bgcolor: '#f1f5f9', borderRadius: 5, position: 'relative' }}>
                      <Box
                        sx={{
                          position: 'absolute',
                          left: `${leftPct}%`,
                          width: `${widthPct}%`,
                          height: '100%',
                          bgcolor: '#0284c7',
                          borderRadius: 5,
                        }}
                      />
                    </Box>
                  </Paper>
                );
              })}
            </Box>
          </CardContent>
        </Card>
      )}

      {/* TAB 2: Cost Attribution */}
      {tabIndex === 2 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={7}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <DollarSign size={20} color="#0284c7" />
                  Operational Cost Attribution Breakdown
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b', mb: 3 }}>
                  Granular micro-USD accounting tracking exact token usage, worker compute time, and external APIs.
                </Typography>

                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
                  {costs.map((c) => (
                    <Box key={c.category}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 600, color: '#0f172a' }}>
                          {c.category}
                        </Typography>
                        <Typography variant="subtitle2" sx={{ fontWeight: 700, color: '#0284c7' }}>
                          {c.usd} ({c.percentage}%)
                        </Typography>
                      </Box>
                      <LinearProgress
                        variant="determinate"
                        value={c.percentage}
                        sx={{ height: 8, borderRadius: 4, bgcolor: '#f1f5f9' }}
                      />
                    </Box>
                  ))}
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={5}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <TrendingUp size={20} color="#0284c7" />
                  Monthly Spend & Budget Ceiling
                </Typography>

                <Paper sx={{ p: 2.5, bgcolor: '#f8fafc', borderRadius: 2, mb: 3, border: '1px solid #e2e8f0' }}>
                  <Typography variant="caption" sx={{ color: '#64748b', display: 'block' }}>
                    Current Monthly Operational Spend
                  </Typography>
                  <Typography variant="h3" sx={{ fontWeight: 700, color: '#0f172a', mb: 1 }}>
                    $28.45
                  </Typography>
                  <Typography variant="caption" sx={{ color: '#16a34a', fontWeight: 600 }}>
                    56.9% of $50.00 monthly soft budget cap
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={56.9}
                    sx={{ height: 8, borderRadius: 4, mt: 1.5, bgcolor: '#e2e8f0' }}
                  />
                </Paper>

                <Typography variant="caption" sx={{ color: '#64748b', display: 'block', lineHeight: 1.5 }}>
                  Billing unit rates: AI Pro Input at $3.00/1M, Flash Input at $0.35/1M, Compute at $0.005/sec, Document OCR at $0.0015/page.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* TAB 3: SLA Alerts */}
      {tabIndex === 3 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <AlertOctagon size={20} color="#0284c7" />
                  Configured Alert Rules ({rules.length})
                </Typography>
                <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid #e2e8f0', borderRadius: 2 }}>
                  <Table size="small">
                    <TableHead sx={{ bgcolor: '#f8fafc' }}>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 600 }}>Rule Name</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>Metric</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>Condition</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>Severity</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {rules.map((r) => (
                        <TableRow key={r.id} hover>
                          <TableCell sx={{ fontWeight: 600, color: '#0f172a' }}>{r.name}</TableCell>
                          <TableCell sx={{ color: '#475569', fontSize: '0.85rem' }}>{r.metric_name}</TableCell>
                          <TableCell>
                            {r.condition} {r.threshold}
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={r.severity}
                              size="small"
                              color={r.severity === 'CRITICAL' ? 'error' : 'warning'}
                              variant="outlined"
                            />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <ShieldCheck size={20} color="#0284c7" />
                  Alert History & Incidents ({events.length})
                </Typography>

                {events.map((ev) => (
                  <Paper key={ev.id} sx={{ p: 2.5, border: '1px solid #e2e8f0', borderRadius: 2, mb: 2 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, color: '#0f172a' }}>
                        {ev.rule_name}
                      </Typography>
                      <Chip
                        label={ev.status}
                        size="small"
                        color={ev.status === 'RESOLVED' ? 'success' : 'error'}
                      />
                    </Box>
                    <Typography variant="body2" sx={{ color: '#475569', mb: 1.5 }}>
                      Observed {ev.observed_value} against threshold of {ev.threshold} on {ev.metric_name}.
                    </Typography>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Typography variant="caption" sx={{ color: '#64748b' }}>
                        Triggered at: {ev.triggered_at}
                      </Typography>
                      {ev.status === 'TRIGGERED' && (
                        <Button
                          size="small"
                          variant="outlined"
                          color="success"
                          onClick={() => handleResolveEvent(ev.id)}
                        >
                          Resolve Alert
                        </Button>
                      )}
                    </Box>
                  </Paper>
                ))}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* TAB 4: Prometheus Exporter */}
      {tabIndex === 4 && (
        <Card sx={{ borderRadius: 2 }}>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Box>
                <Typography variant="h6" sx={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <FileCode size={20} color="#0284c7" />
                  Prometheus / OpenMetrics Standard Scrapable Output
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  Live endpoint active at <code>/api/v1/telemetry/metrics/prometheus</code> for Datadog, Prometheus, or Grafana Agent scraping.
                </Typography>
              </Box>
              <Button
                variant="outlined"
                size="small"
                onClick={() => setSuccessMsg('Prometheus endpoint URL copied to clipboard.')}
              >
                Copy Endpoint URL
              </Button>
            </Box>

            <Paper sx={{ p: 2.5, bgcolor: '#0f172a', borderRadius: 2 }}>
              <pre style={{ margin: 0, color: '#38bdf8', fontFamily: 'monospace', fontSize: '0.85rem', lineHeight: 1.6 }}>
                {PROMETHEUS_SAMPLE}
              </pre>
            </Paper>
          </CardContent>
        </Card>
      )}

      {/* TAB 5: Subsystem Health */}
      {tabIndex === 5 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={4}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Server size={18} color="#0284c7" />
                  API Throughput Velocity
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 700, color: '#0284c7', mb: 1 }}>
                  245 req/sec
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  Sustained API ingress with automatic keep-alive connection pooling.
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Zap size={18} color="#16a34a" />
                  AI Token Generation Rate
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 700, color: '#16a34a', mb: 1 }}>
                  1,840 tok/sec
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  Combined streaming inference velocity across active specialized agents.
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Radio size={18} color="#8b5cf6" />
                  Circuit Breakers & DR
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 700, color: '#8b5cf6', mb: 1 }}>
                  Healthy (Closed)
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  All 12 agent circuits and cross-region replica endpoints operational.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Add Alert Rule Dialog */}
      <Dialog open={openNewRuleDialog} onClose={() => setOpenNewRuleDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Add SLA Anomaly Alert Rule</DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          <TextField
            fullWidth
            label="Rule Name"
            value={newRuleName}
            onChange={(e) => setNewRuleName(e.target.value)}
            sx={{ mb: 2 }}
          />
          <TextField
            fullWidth
            label="Target Metric Name"
            value={newRuleMetric}
            onChange={(e) => setNewRuleMetric(e.target.value)}
            sx={{ mb: 2 }}
          />
          <TextField
            fullWidth
            type="number"
            label="Threshold Value"
            value={newRuleThreshold}
            onChange={(e) => setNewRuleThreshold(Number(e.target.value))}
            sx={{ mb: 2 }}
          />
          <FormControl fullWidth>
            <InputLabel>Severity Level</InputLabel>
            <Select
              value={newRuleSeverity}
              label="Severity Level"
              onChange={(e) => setNewRuleSeverity(e.target.value)}
            >
              <MenuItem value="INFO">Info</MenuItem>
              <MenuItem value="WARNING">Warning</MenuItem>
              <MenuItem value="CRITICAL">Critical</MenuItem>
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setOpenNewRuleDialog(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleCreateRule} sx={{ bgcolor: '#0284c7' }}>
            Register Alert Rule
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default EnterpriseTelemetryWorkspace;
