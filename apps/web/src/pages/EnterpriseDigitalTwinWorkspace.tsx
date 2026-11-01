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
  Slider,
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
  Divider,
} from '@mui/material';
import {
  Sensors as TwinIcon,
  PlayArrow as RunIcon,
  Speed as SpeedIcon,
  Warning as BottleneckIcon,
  AttachMoney as FinopsIcon,
  Public as RegionIcon,
  Layers as LayersIcon,
  Lightbulb as RecommendIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';

interface SimulationResult {
  run_id: string;
  baseline_snapshot: any;
  simulated_projections: any;
  bottlenecks_detected: string[];
  recommendations: string[];
  duration_ms: number;
}

export const EnterpriseDigitalTwinWorkspace: React.FC = () => {
  const [activeTab, setActiveTab] = useState<number>(0);
  const [leadMult, setLeadMult] = useState<number>(3.0);
  const [aiCostMult, setAiCostMult] = useState<number>(1.5);
  const [sourceDown, setSourceDown] = useState<string>('github');
  const [regionFailed, setRegionFailed] = useState<string>('');
  const [verifSpike, setVerifSpike] = useState<number>(2.0);

  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [history, setHistory] = useState<any[]>([]);

  const fetchRuns = async () => {
    try {
      const res = await fetch('/api/v1/simulation/runs');
      if (res.ok) {
        const data = await res.json();
        setHistory(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleRunSimulation = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/simulation/quick-what-if', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lead_volume_multiplier: leadMult,
          ai_cost_multiplier: aiCostMult,
          source_unavailable: sourceDown || null,
          region_failed: regionFailed || null,
          verification_backlog_multiplier: verifSpike,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setResult(data);
        fetchRuns();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRuns();
    handleRunSimulation();
  }, []);

  return (
    <Box sx={{ p: 4 }}>
      {/* Title */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <TwinIcon color="primary" fontSize="large" />
            Enterprise Digital Twin & Operational Simulation
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Phase 34 (ChatGPT Master Roadmap): What-If Scenarios, Capacity Stress-Testing & Zero Production Mutation
          </Typography>
        </Box>
        <Button variant="outlined" startIcon={<RefreshIcon />} onClick={fetchRuns}>
          Refresh History
        </Button>
      </Box>

      {/* Tabs */}
      <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)} sx={{ mb: 3, borderBottom: 1, borderColor: 'divider' }}>
        <Tab icon={<RunIcon />} iconPosition="start" label="What-If Sandbox" />
        <Tab icon={<BottleneckIcon />} iconPosition="start" label="Bottlenecks & Prescriptions" />
        <Tab icon={<LayersIcon />} iconPosition="start" label="Baseline vs Projected Twin" />
        <Tab icon={<SpeedIcon />} iconPosition="start" label="Simulation History" />
      </Tabs>

      {/* TAB 0: What-If Sandbox */}
      {activeTab === 0 && (
        <Grid container spacing={3}>
          {/* Controls */}
          <Grid item xs={12} md={5}>
            <Card elevation={2}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 3 }}>
                  Simulation Parameters
                </Typography>

                <Box sx={{ mb: 3 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600, mb: 1 }}>
                    Lead Volume Surge: {leadMult}x
                  </Typography>
                  <Slider
                    value={leadMult}
                    min={1.0}
                    max={10.0}
                    step={0.5}
                    valueLabelDisplay="auto"
                    onChange={(_, v) => setLeadMult(v as number)}
                  />
                  <Typography variant="caption" color="text.secondary">
                    Simulates concurrent inbound discovery volume.
                  </Typography>
                </Box>

                <Box sx={{ mb: 3 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600, mb: 1 }}>
                    AI Model Cost Multiplier: {aiCostMult}x
                  </Typography>
                  <Slider
                    value={aiCostMult}
                    min={0.5}
                    max={4.0}
                    step={0.25}
                    valueLabelDisplay="auto"
                    onChange={(_, v) => setAiCostMult(v as number)}
                  />
                  <Typography variant="caption" color="text.secondary">
                    Simulates rate hikes or deep multi-turn prompt expansions.
                  </Typography>
                </Box>

                <Box sx={{ mb: 3 }}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Source Outage Simulation</InputLabel>
                    <Select
                      value={sourceDown}
                      label="Source Outage Simulation"
                      onChange={(e) => setSourceDown(e.target.value)}
                    >
                      <MenuItem value="">None (All Healthy)</MenuItem>
                      <MenuItem value="github">GitHub Public Search (API Quota Exceeded)</MenuItem>
                      <MenuItem value="job_boards">Job Board Collectors (Throttled)</MenuItem>
                      <MenuItem value="web_scraper">Headless Browser Cluster (DDoS / Block)</MenuItem>
                    </Select>
                  </FormControl>
                </Box>

                <Box sx={{ mb: 3 }}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Regional Failure Cascade</InputLabel>
                    <Select
                      value={regionFailed}
                      label="Regional Failure Cascade"
                      onChange={(e) => setRegionFailed(e.target.value)}
                    >
                      <MenuItem value="">None (Multi-Region Healthy)</MenuItem>
                      <MenuItem value="ap-southeast-2">ap-southeast-2 (Sydney Primary Down)</MenuItem>
                      <MenuItem value="ap-southeast-1">ap-southeast-1 (Singapore Secondary Down)</MenuItem>
                    </Select>
                  </FormControl>
                </Box>

                <Box sx={{ mb: 3 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600, mb: 1 }}>
                    Verification Backlog Multiplier: {verifSpike}x
                  </Typography>
                  <Slider
                    value={verifSpike}
                    min={1.0}
                    max={5.0}
                    step={0.5}
                    valueLabelDisplay="auto"
                    onChange={(_, v) => setVerifSpike(v as number)}
                  />
                </Box>

                <Button
                  fullWidth
                  variant="contained"
                  size="large"
                  startIcon={<RunIcon />}
                  onClick={handleRunSimulation}
                  disabled={loading}
                >
                  {loading ? 'Simulating...' : 'Execute Digital Twin Projection'}
                </Button>
              </CardContent>
            </Card>
          </Grid>

          {/* Results Overview */}
          <Grid item xs={12} md={7}>
            {result ? (
              <Grid container spacing={2}>
                <Grid item xs={6} sm={6}>
                  <Card sx={{ bgcolor: 'background.paper', p: 1.5 }}>
                    <Typography variant="caption" color="text.secondary">Projected Leads / Hour</Typography>
                    <Typography variant="h4" sx={{ fontWeight: 700, color: 'primary.main' }}>
                      {result.simulated_projections.projected_leads_hourly}
                    </Typography>
                    <Typography variant="caption">Surge: {result.simulated_projections.lead_volume_multiplier}x</Typography>
                  </Card>
                </Grid>

                <Grid item xs={6} sm={6}>
                  <Card sx={{ bgcolor: 'background.paper', p: 1.5 }}>
                    <Typography variant="caption" color="text.secondary">Worker Pool Utilization</Typography>
                    <Typography variant="h4" sx={{
                      fontWeight: 700,
                      color: result.simulated_projections.projected_worker_utilization_pct > 100 ? 'error.main' : 'success.main'
                    }}>
                      {result.simulated_projections.projected_worker_utilization_pct}%
                    </Typography>
                    <Typography variant="caption">Required: {result.simulated_projections.projected_required_workers} workers</Typography>
                  </Card>
                </Grid>

                <Grid item xs={6} sm={6}>
                  <Card sx={{ bgcolor: 'background.paper', p: 1.5 }}>
                    <Typography variant="caption" color="text.secondary">Projected Monthly Spend</Typography>
                    <Typography variant="h4" sx={{ fontWeight: 700, color: 'warning.main' }}>
                      ${result.simulated_projections.projected_monthly_spend_usd.toLocaleString()}
                    </Typography>
                    <Typography variant="caption">CPL: ${result.simulated_projections.projected_cost_per_lead_usd}</Typography>
                  </Card>
                </Grid>

                <Grid item xs={6} sm={6}>
                  <Card sx={{ bgcolor: 'background.paper', p: 1.5 }}>
                    <Typography variant="caption" color="text.secondary">Verification Latency</Typography>
                    <Typography variant="h4" sx={{ fontWeight: 700 }}>
                      {result.simulated_projections.projected_verification_latency_sec}s
                    </Typography>
                    <Typography variant="caption">Serving: {result.simulated_projections.active_serving_region}</Typography>
                  </Card>
                </Grid>

                {/* Top Bottleneck Alert */}
                <Grid item xs={12}>
                  {result.bottlenecks_detected.length > 0 ? (
                    <Alert severity="error" sx={{ mb: 2 }}>
                      <strong>{result.bottlenecks_detected.length} Bottlenecks Identified:</strong>
                      <Box component="ul" sx={{ pl: 2, mt: 0.5, mb: 0 }}>
                        {result.bottlenecks_detected.map((b, i) => (
                          <li key={i}>{b}</li>
                        ))}
                      </Box>
                    </Alert>
                  ) : (
                    <Alert severity="success" sx={{ mb: 2 }}>
                      No critical bottlenecks detected. Platform capacity is resilient under simulated load.
                    </Alert>
                  )}

                  {result.recommendations.length > 0 && (
                    <Alert severity="info">
                      <strong>Prescriptive Recommendations:</strong>
                      <Box component="ul" sx={{ pl: 2, mt: 0.5, mb: 0 }}>
                        {result.recommendations.map((r, i) => (
                          <li key={i}>{r}</li>
                        ))}
                      </Box>
                    </Alert>
                  )}
                </Grid>
              </Grid>
            ) : (
              <Box sx={{ p: 4, textAlign: 'center', color: 'text.secondary' }}>
                Run a simulation to view projected digital twin metrics.
              </Box>
            )}
          </Grid>
        </Grid>
      )}

      {/* TAB 1: Bottlenecks & Prescriptions */}
      {activeTab === 1 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card elevation={2}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <BottleneckIcon color="error" />
                  Identified Bottlenecks
                </Typography>
                {result && result.bottlenecks_detected.length > 0 ? (
                  result.bottlenecks_detected.map((b, i) => (
                    <Paper key={i} sx={{ p: 2, mb: 1.5, bgcolor: '#fff1f2', borderLeft: '4px solid #f43f5e' }}>
                      <Typography variant="body2" sx={{ fontWeight: 600, color: '#9f1239' }}>
                        Bottleneck #{i + 1}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {b}
                      </Typography>
                    </Paper>
                  ))
                ) : (
                  <Typography variant="body2" color="text.secondary">No active bottlenecks.</Typography>
                )}
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card elevation={2}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <RecommendIcon color="primary" />
                  Prescriptive Recommendations
                </Typography>
                {result && result.recommendations.length > 0 ? (
                  result.recommendations.map((r, i) => (
                    <Paper key={i} sx={{ p: 2, mb: 1.5, bgcolor: '#f0fdf4', borderLeft: '4px solid #22c55e' }}>
                      <Typography variant="body2" sx={{ fontWeight: 600, color: '#166534' }}>
                        Action Plan #{i + 1}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {r}
                      </Typography>
                    </Paper>
                  ))
                ) : (
                  <Typography variant="body2" color="text.secondary">No actions required.</Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* TAB 2: Baseline vs Projected Twin */}
      {activeTab === 2 && result && (
        <TableContainer component={Paper} elevation={1}>
          <Table>
            <TableHead sx={{ backgroundColor: 'action.hover' }}>
              <TableRow>
                <TableCell><strong>Metric Dimension</strong></TableCell>
                <TableCell><strong>Production Reality (Baseline)</strong></TableCell>
                <TableCell><strong>Digital Twin Projection</strong></TableCell>
                <TableCell><strong>Delta / Impact</strong></TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              <TableRow>
                <TableCell>Lead Processing Velocity</TableCell>
                <TableCell>120 leads / hr</TableCell>
                <TableCell>{result.simulated_projections.projected_leads_hourly} leads / hr</TableCell>
                <TableCell sx={{ color: 'primary.main', fontWeight: 600 }}>+{result.simulated_projections.lead_volume_multiplier}x</TableCell>
              </TableRow>
              <TableRow>
                <TableCell>Browser Worker Utilization</TableCell>
                <TableCell>{result.baseline_snapshot.browser_worker_utilization_pct}%</TableCell>
                <TableCell>{result.simulated_projections.projected_worker_utilization_pct}%</TableCell>
                <TableCell sx={{ color: result.simulated_projections.projected_worker_utilization_pct > 100 ? 'error.main' : 'success.main', fontWeight: 600 }}>
                  {result.simulated_projections.projected_worker_utilization_pct > 100 ? 'EXCEEDED' : 'OPTIMAL'}
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>Cost Per Lead (CPL)</TableCell>
                <TableCell>${result.baseline_snapshot.avg_cost_per_lead_usd}</TableCell>
                <TableCell>${result.simulated_projections.projected_cost_per_lead_usd}</TableCell>
                <TableCell sx={{ color: 'warning.main', fontWeight: 600 }}>
                  +${(result.simulated_projections.projected_cost_per_lead_usd - result.baseline_snapshot.avg_cost_per_lead_usd).toFixed(2)}
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>Verification SLA Latency</TableCell>
                <TableCell>{result.baseline_snapshot.avg_verification_latency_sec}s</TableCell>
                <TableCell>{result.simulated_projections.projected_verification_latency_sec}s</TableCell>
                <TableCell>+{round(result.simulated_projections.projected_verification_latency_sec - result.baseline_snapshot.avg_verification_latency_sec, 2)}s</TableCell>
              </TableRow>
              <TableRow>
                <TableCell>Active Region</TableCell>
                <TableCell>{result.baseline_snapshot.primary_region}</TableCell>
                <TableCell>{result.simulated_projections.active_serving_region}</TableCell>
                <TableCell>{result.simulated_projections.active_serving_region.includes('Singapore') ? 'Failover Active' : 'Normal'}</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* TAB 3: Simulation History */}
      {activeTab === 3 && (
        <TableContainer component={Paper} elevation={1}>
          <Table>
            <TableHead sx={{ backgroundColor: 'action.hover' }}>
              <TableRow>
                <TableCell><strong>Run ID</strong></TableCell>
                <TableCell><strong>Type</strong></TableCell>
                <TableCell><strong>Bottlenecks Detected</strong></TableCell>
                <TableCell><strong>Recommendations</strong></TableCell>
                <TableCell><strong>Execution Time</strong></TableCell>
                <TableCell><strong>Timestamp</strong></TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {history.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} align="center" sx={{ py: 3, color: 'text.secondary' }}>
                    No simulation runs recorded yet.
                  </TableCell>
                </TableRow>
              ) : (
                history.map((h) => (
                  <TableRow key={h.id}>
                    <TableCell sx={{ fontFamily: 'monospace' }}>{h.id.slice(0, 8)}...</TableCell>
                    <TableCell><Chip label={h.scenario_type} size="small" /></TableCell>
                    <TableCell>{h.bottlenecks_count}</TableCell>
                    <TableCell>{h.recommendations_count}</TableCell>
                    <TableCell>{h.duration_ms}ms</TableCell>
                    <TableCell>{h.created_at ? new Date(h.created_at).toLocaleTimeString() : '-'}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
};

function round(n: number, d: number) {
  return Number(n.toFixed(d));
}
