import React, { useState, useEffect } from 'react';
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
  CircularProgress,
  Alert,
  IconButton,
  Tooltip,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  Switch,
  FormControlLabel
} from '@mui/material';
import {
  Radio,
  Zap,
  Activity,
  Flame,
  Layers,
  Filter,
  Send,
  RefreshCw,
  Sliders,
  CheckCircle,
  AlertTriangle,
  Building,
  Cpu,
  UserCheck,
  TrendingUp,
  Trash2,
  Clock,
  Gauge
} from 'lucide-react';

interface LiveSignal {
  id: string;
  signal_type: string;
  company_name: string;
  entity_key?: string;
  topic: string;
  payload: Record<string, any>;
  confidence: number;
  source: string;
  timestamp: string;
}

interface StreamSubscription {
  id: string;
  topic: string;
  filter_criteria: Record<string, any>;
  is_active: boolean;
  created_at: string;
}

interface AnomalyAlert {
  id: string;
  company_name: string;
  signal_count: number;
  window_seconds: number;
  severity: string;
  description: string;
  timestamp: string;
}

interface StreamStats {
  active_subscriptions: number;
  active_websocket_clients: number;
  buffered_signals: number;
  total_signals_published: number;
  throughput_signals_per_sec: number;
  drop_rate_percent: number;
  active_topics: string[];
}

export default function EnterpriseSignalStreamingWorkspace() {
  const [activeTab, setActiveTab] = useState(0);
  const [signals, setSignals] = useState<LiveSignal[]>([]);
  const [subscriptions, setSubscriptions] = useState<StreamSubscription[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyAlert[]>([]);
  const [stats, setStats] = useState<StreamStats | null>(null);

  // Filters & State
  const [selectedTopic, setSelectedTopic] = useState<string>('ALL');
  const [isLiveStreaming, setIsLiveStreaming] = useState(true);
  const [loading, setLoading] = useState(false);
  const [alertMsg, setAlertMsg] = useState<{ type: 'success' | 'info' | 'error'; text: string } | null>(null);

  // New Subscription Form
  const [newSubTopic, setNewSubTopic] = useState('signals.intent');
  const [newSubKey, setNewSubKey] = useState('country');
  const [newSubVal, setNewSubVal] = useState('Australia');

  // Publisher Form
  const [pubCompany, setPubCompany] = useState('Nexus Cloud Solutions');
  const [pubType, setPubType] = useState('TECH_ADOPTION');
  const [pubTopic, setPubTopic] = useState('signals.technology');
  const [pubPayload, setPubPayload] = useState('{"technology": "Odoo 17", "country": "Australia", "employees": 200}');
  const [pubConfidence, setPubConfidence] = useState('0.98');

  // Fetch recent signals
  const fetchRecentSignals = async () => {
    try {
      const topicParam = selectedTopic !== 'ALL' ? `?topic=${selectedTopic}&limit=30` : '?limit=30';
      const res = await fetch(`/api/v1/stream/signals/recent${topicParam}`);
      if (res.ok) {
        const data = await res.json();
        setSignals(data);
      }
    } catch (e) {
      console.warn('Failed to fetch stream signals', e);
    }
  };

  // Fetch subscriptions
  const fetchSubscriptions = async () => {
    try {
      const res = await fetch('/api/v1/stream/subscriptions');
      if (res.ok) {
        const data = await res.json();
        setSubscriptions(data);
      }
    } catch (e) {
      console.warn('Failed to fetch subscriptions', e);
    }
  };

  // Fetch anomalies
  const fetchAnomalies = async () => {
    try {
      const res = await fetch('/api/v1/stream/anomalies?limit=20');
      if (res.ok) {
        const data = await res.json();
        setAnomalies(data);
      }
    } catch (e) {
      console.warn('Failed to fetch anomalies', e);
    }
  };

  // Fetch stats
  const fetchStats = async () => {
    try {
      const res = await fetch('/api/v1/stream/stats');
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (e) {
      console.warn('Failed to fetch stream stats', e);
    }
  };

  // Initial load and live polling
  useEffect(() => {
    fetchRecentSignals();
    fetchSubscriptions();
    fetchAnomalies();
    fetchStats();

    const interval = setInterval(() => {
      if (isLiveStreaming) {
        fetchRecentSignals();
        fetchAnomalies();
        fetchStats();
      }
    }, 4000);

    return () => clearInterval(interval);
  }, [selectedTopic, isLiveStreaming]);

  // Create subscription
  const handleCreateSubscription = async () => {
    try {
      const criteria = newSubKey && newSubVal ? { [newSubKey]: newSubVal } : {};
      const res = await fetch('/api/v1/stream/subscriptions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: newSubTopic, filter_criteria: criteria })
      });
      if (res.ok) {
        setAlertMsg({ type: 'success', text: `Subscription created for topic ${newSubTopic}` });
        fetchSubscriptions();
      }
    } catch (e) {
      setAlertMsg({ type: 'error', text: 'Failed to create subscription' });
    }
  };

  // Delete subscription
  const handleDeleteSubscription = async (id: string) => {
    try {
      const res = await fetch(`/api/v1/stream/subscriptions/${id}`, { method: 'DELETE' });
      if (res.ok) {
        setAlertMsg({ type: 'info', text: 'Subscription removed' });
        fetchSubscriptions();
      }
    } catch (e) {
      setAlertMsg({ type: 'error', text: 'Failed to delete subscription' });
    }
  };

  // Publish manual signal
  const handlePublishSignal = async () => {
    try {
      let parsedPayload = {};
      try {
        parsedPayload = JSON.parse(pubPayload);
      } catch (err) {
        setAlertMsg({ type: 'error', text: 'Invalid JSON payload' });
        return;
      }

      const res = await fetch('/api/v1/stream/signals/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          signal_type: pubType,
          company_name: pubCompany,
          topic: pubTopic,
          payload: parsedPayload,
          confidence: parseFloat(pubConfidence) || 0.95,
          source: 'CONSOLE_INJECTOR'
        })
      });
      if (res.ok) {
        const data = await res.json();
        setAlertMsg({ type: 'success', text: `Signal published! Status: ${data.status}, ID: ${data.signal_id}` });
        fetchRecentSignals();
        fetchStats();
      }
    } catch (e) {
      setAlertMsg({ type: 'error', text: 'Failed to publish signal' });
    }
  };

  // Trigger surge simulation
  const handleSimulateSurge = async () => {
    try {
      const res = await fetch('/api/v1/stream/simulate-surge?company_name=Canva%20Inc&surge_count=4', { method: 'POST' });
      if (res.ok) {
        setAlertMsg({ type: 'success', text: 'Burst of 4 high-velocity intent signals simulated for Canva Inc!' });
        fetchRecentSignals();
        fetchAnomalies();
        fetchStats();
      }
    } catch (e) {
      setAlertMsg({ type: 'error', text: 'Simulation failed' });
    }
  };

  const getSignalBadgeColor = (type: string) => {
    switch (type) {
      case 'TECH_ADOPTION': return '#8b5cf6';
      case 'HIRING_SURGE': return '#0284c7';
      case 'BUYING_INTENT': return '#10b981';
      case 'LEADERSHIP_CHANGE': return '#f59e0b';
      case 'FUNDING_ROUND': return '#ec4899';
      default: return '#64748b';
    }
  };

  return (
    <Box sx={{ p: 3, maxWidth: 1600, mx: 'auto' }}>
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Radio size={28} color="#0284c7" />
            <Typography variant="h5" sx={{ fontWeight: 700, color: '#f8fafc' }}>
              Real-Time Streaming Intelligence & Signal Feeds
            </Typography>
            <Chip label="Phase 47" size="small" sx={{ bgcolor: '#0284c7', color: '#fff', fontWeight: 600 }} />
          </Box>
          <Typography variant="body2" sx={{ color: '#94a3b8', mt: 0.5 }}>
            Sub-second B2B signal ingestion, sliding-window deduplication, intent spike anomaly detection, and backpressure ring buffers.
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <FormControlLabel
            control={
              <Switch
                checked={isLiveStreaming}
                onChange={(e) => setIsLiveStreaming(e.target.checked)}
                color="primary"
              />
            }
            label={<Typography variant="body2" sx={{ color: '#cbd5e1' }}>Live Stream Active</Typography>}
          />
          <Button
            variant="contained"
            color="secondary"
            startIcon={<Flame size={16} />}
            onClick={handleSimulateSurge}
            sx={{ bgcolor: '#d97706', '&:hover': { bgcolor: '#b45309' } }}
          >
            Simulate Intent Surge
          </Button>
          <Button
            variant="outlined"
            startIcon={<RefreshCw size={16} />}
            onClick={() => { fetchRecentSignals(); fetchStats(); fetchAnomalies(); }}
            sx={{ borderColor: '#334155', color: '#cbd5e1' }}
          >
            Refresh Feed
          </Button>
        </Box>
      </Box>

      {alertMsg && (
        <Alert severity={alertMsg.type} sx={{ mb: 3 }} onClose={() => setAlertMsg(null)}>
          {alertMsg.text}
        </Alert>
      )}

      {/* Tabs */}
      <Paper sx={{ bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2, mb: 3 }}>
        <Tabs
          value={activeTab}
          onChange={(_, val) => setActiveTab(val)}
          variant="scrollable"
          scrollButtons="auto"
          sx={{
            '& .MuiTab-root': { color: '#94a3b8', textTransform: 'none', fontWeight: 600, minHeight: 48 },
            '& .Mui-selected': { color: '#38bdf8' },
            '& .MuiTabs-indicator': { bgcolor: '#38bdf8' },
          }}
        >
          <Tab icon={<Radio size={18} />} iconPosition="start" label="Live Signal Stream & Feed" />
          <Tab icon={<Filter size={18} />} iconPosition="start" label="Subscriptions & Predicates" />
          <Tab icon={<Flame size={18} />} iconPosition="start" label="Intent Spikes & Anomalies" />
          <Tab icon={<Gauge size={18} />} iconPosition="start" label="Backpressure & Ring Buffer" />
          <Tab icon={<Send size={18} />} iconPosition="start" label="Signal Publisher Console" />
          <Tab icon={<Activity size={18} />} iconPosition="start" label="Throughput & Topics" />
        </Tabs>
      </Paper>

      {/* Tab 1: Live Signal Stream */}
      {activeTab === 0 && (
        <Paper sx={{ p: 3, bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2 }}>
          {/* Filter Bar */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="subtitle2" sx={{ color: '#94a3b8', mr: 1 }}>
                Topic Channel:
              </Typography>
              {['ALL', 'signals.technology', 'signals.hiring', 'signals.intent', 'signals.leadership'].map((t) => (
                <Chip
                  key={t}
                  label={t}
                  clickable
                  onClick={() => setSelectedTopic(t)}
                  sx={{
                    bgcolor: selectedTopic === t ? '#0284c7' : '#1e293b',
                    color: selectedTopic === t ? '#fff' : '#94a3b8',
                    fontWeight: 600,
                    fontSize: 12
                  }}
                />
              ))}
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Clock size={16} color="#38bdf8" />
              <Typography variant="caption" sx={{ color: '#38bdf8', fontWeight: 600 }}>
                {isLiveStreaming ? 'LIVE POLLING (4s)' : 'STREAM PAUSED'}
              </Typography>
            </Box>
          </Box>

          {/* Signals Table */}
          <TableContainer component={Paper} sx={{ bgcolor: '#090d16', border: '1px solid #1e293b' }}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ '& th': { color: '#94a3b8', fontWeight: 600 } }}>
                  <TableCell>Signal Type</TableCell>
                  <TableCell>Company</TableCell>
                  <TableCell>Topic</TableCell>
                  <TableCell>Intelligence Payload</TableCell>
                  <TableCell>Confidence</TableCell>
                  <TableCell>Source</TableCell>
                  <TableCell>Timestamp</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {signals.map((sig) => (
                  <TableRow key={sig.id} sx={{ '& td': { color: '#cbd5e1' } }}>
                    <TableCell>
                      <Chip
                        label={sig.signal_type}
                        size="small"
                        sx={{ bgcolor: getSignalBadgeColor(sig.signal_type), color: '#fff', fontSize: 10, height: 20 }}
                      />
                    </TableCell>
                    <TableCell sx={{ fontWeight: 600, color: '#f8fafc' }}>
                      {sig.company_name}
                    </TableCell>
                    <TableCell sx={{ fontFamily: 'monospace', color: '#38bdf8', fontSize: 12 }}>
                      {sig.topic}
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption" sx={{ color: '#cbd5e1', fontFamily: 'monospace' }}>
                        {JSON.stringify(sig.payload)}
                      </Typography>
                    </TableCell>
                    <TableCell sx={{ color: '#10b981', fontWeight: 600 }}>
                      {(sig.confidence * 100).toFixed(0)}%
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={sig.source}
                        size="small"
                        variant="outlined"
                        sx={{ borderColor: '#334155', color: '#94a3b8', fontSize: 10 }}
                      />
                    </TableCell>
                    <TableCell sx={{ color: '#64748b', fontSize: 11 }}>
                      {new Date(sig.timestamp).toLocaleTimeString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {/* Tab 2: Subscriptions & Predicates */}
      {activeTab === 1 && (
        <Paper sx={{ p: 3, bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, color: '#f8fafc', mb: 1 }}>
            Stream Subscription Rules & Predicate Routing
          </Typography>
          <Typography variant="body2" sx={{ color: '#94a3b8', mb: 3 }}>
            Configure real-time topic subscribers with JSON predicate criteria to match live business opportunities.
          </Typography>

          {/* New subscription form */}
          <Grid container spacing={2} sx={{ mb: 4, alignItems: 'center' }}>
            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                size="small"
                label="Topic Channel (e.g. signals.intent)"
                value={newSubTopic}
                onChange={(e) => setNewSubTopic(e.target.value)}
                sx={{ bgcolor: '#090d16', input: { color: '#f8fafc' }, label: { color: '#94a3b8' } }}
              />
            </Grid>
            <Grid item xs={12} sm={3}>
              <TextField
                fullWidth
                size="small"
                label="Filter Attribute"
                value={newSubKey}
                onChange={(e) => setNewSubKey(e.target.value)}
                sx={{ bgcolor: '#090d16', input: { color: '#f8fafc' }, label: { color: '#94a3b8' } }}
              />
            </Grid>
            <Grid item xs={12} sm={3}>
              <TextField
                fullWidth
                size="small"
                label="Match Value"
                value={newSubVal}
                onChange={(e) => setNewSubVal(e.target.value)}
                sx={{ bgcolor: '#090d16', input: { color: '#f8fafc' }, label: { color: '#94a3b8' } }}
              />
            </Grid>
            <Grid item xs={12} sm={2}>
              <Button
                fullWidth
                variant="contained"
                onClick={handleCreateSubscription}
                sx={{ bgcolor: '#0284c7', '&:hover': { bgcolor: '#0369a1' }, height: 40 }}
              >
                Subscribe
              </Button>
            </Grid>
          </Grid>

          {/* Active Subscriptions List */}
          <Typography variant="subtitle2" sx={{ fontWeight: 600, color: '#cbd5e1', mb: 1.5 }}>
            Active Subscription Registrations ({subscriptions.length})
          </Typography>
          <TableContainer component={Paper} sx={{ bgcolor: '#090d16', border: '1px solid #1e293b' }}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ '& th': { color: '#94a3b8', fontWeight: 600 } }}>
                  <TableCell>Subscription ID</TableCell>
                  <TableCell>Topic Pattern</TableCell>
                  <TableCell>Predicate Criteria</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Created At</TableCell>
                  <TableCell>Action</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {subscriptions.map((sub) => (
                  <TableRow key={sub.id} sx={{ '& td': { color: '#cbd5e1' } }}>
                    <TableCell sx={{ fontFamily: 'monospace', color: '#f8fafc' }}>{sub.id}</TableCell>
                    <TableCell sx={{ color: '#38bdf8', fontWeight: 600 }}>{sub.topic}</TableCell>
                    <TableCell>
                      <Typography variant="caption" sx={{ color: '#94a3b8' }}>
                        {JSON.stringify(sub.filter_criteria)}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={sub.is_active ? 'ACTIVE' : 'INACTIVE'}
                        size="small"
                        sx={{ bgcolor: sub.is_active ? '#065f46' : '#991b1b', color: '#fff', fontSize: 10 }}
                      />
                    </TableCell>
                    <TableCell sx={{ color: '#64748b', fontSize: 11 }}>
                      {new Date(sub.created_at).toLocaleTimeString()}
                    </TableCell>
                    <TableCell>
                      <IconButton size="small" onClick={() => handleDeleteSubscription(sub.id)} sx={{ color: '#ef4444' }}>
                        <Trash2 size={16} />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {/* Tab 3: Intent Spikes & Anomalies */}
      {activeTab === 2 && (
        <Paper sx={{ p: 3, bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 700, color: '#f8fafc' }}>
                Intent Velocity Spikes & Anomaly Alerts
              </Typography>
              <Typography variant="body2" sx={{ color: '#94a3b8' }}>
                Companies experiencing unusual clusters of hiring, technology adoption, and buying signals within 5-minute sliding windows.
              </Typography>
            </Box>
            <Button
              variant="contained"
              color="secondary"
              startIcon={<Flame size={16} />}
              onClick={handleSimulateSurge}
              sx={{ bgcolor: '#d97706', '&:hover': { bgcolor: '#b45309' } }}
            >
              Simulate Surge Event
            </Button>
          </Box>

          <TableContainer component={Paper} sx={{ bgcolor: '#090d16', border: '1px solid #1e293b' }}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ '& th': { color: '#94a3b8', fontWeight: 600 } }}>
                  <TableCell>Alert ID</TableCell>
                  <TableCell>Company</TableCell>
                  <TableCell>Severity</TableCell>
                  <TableCell>Burst Frequency</TableCell>
                  <TableCell>Sliding Window</TableCell>
                  <TableCell>Description</TableCell>
                  <TableCell>Timestamp</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {anomalies.map((anom) => (
                  <TableRow key={anom.id} sx={{ '& td': { color: '#cbd5e1' } }}>
                    <TableCell sx={{ fontFamily: 'monospace', color: '#f8fafc' }}>{anom.id}</TableCell>
                    <TableCell sx={{ fontWeight: 600, color: '#38bdf8' }}>{anom.company_name}</TableCell>
                    <TableCell>
                      <Chip
                        label={anom.severity}
                        size="small"
                        sx={{
                          bgcolor: anom.severity === 'CRITICAL' ? '#b91c1c' : '#d97706',
                          color: '#fff',
                          fontWeight: 700,
                          fontSize: 10
                        }}
                      />
                    </TableCell>
                    <TableCell sx={{ fontWeight: 700, color: '#f8fafc' }}>
                      {anom.signal_count} signals
                    </TableCell>
                    <TableCell>{anom.window_seconds}s</TableCell>
                    <TableCell sx={{ color: '#cbd5e1', fontSize: 12 }}>{anom.description}</TableCell>
                    <TableCell sx={{ color: '#64748b', fontSize: 11 }}>
                      {new Date(anom.timestamp).toLocaleTimeString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {/* Tab 4: Backpressure & Buffer */}
      {activeTab === 3 && (
        <Paper sx={{ p: 3, bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, color: '#f8fafc', mb: 2 }}>
            Stream Backpressure & Bounded Ring Buffer Health
          </Typography>

          <Grid container spacing={3} sx={{ mb: 4 }}>
            <Grid item xs={12} sm={3}>
              <Card sx={{ bgcolor: '#090d16', border: '1px solid #1e293b' }}>
                <CardContent>
                  <Typography variant="caption" sx={{ color: '#94a3b8' }}>Buffer Capacity</Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, color: '#38bdf8' }}>
                    1,000
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Card sx={{ bgcolor: '#090d16', border: '1px solid #1e293b' }}>
                <CardContent>
                  <Typography variant="caption" sx={{ color: '#94a3b8' }}>Buffered Signals</Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, color: '#10b981' }}>
                    {stats?.buffered_signals || 0}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Card sx={{ bgcolor: '#090d16', border: '1px solid #1e293b' }}>
                <CardContent>
                  <Typography variant="caption" sx={{ color: '#94a3b8' }}>Overflow Drop Rate</Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, color: '#f59e0b' }}>
                    {stats?.drop_rate_percent || 0}%
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Card sx={{ bgcolor: '#090d16', border: '1px solid #1e293b' }}>
                <CardContent>
                  <Typography variant="caption" sx={{ color: '#94a3b8' }}>Total Ingested</Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, color: '#8b5cf6' }}>
                    {stats?.total_signals_published || 0}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          <Box sx={{ p: 2.5, bgcolor: '#090d16', borderRadius: 1.5, border: '1px solid #1e293b' }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, color: '#cbd5e1', mb: 1 }}>
              Backpressure Policy: Drop Oldest (Ring Buffer Strategy)
            </Typography>
            <Typography variant="body2" sx={{ color: '#94a3b8' }}>
              When subscriber downstream consumers experience processing lag, the stream hub retains a fixed 1,000 signal sliding window. Older frames are gracefully evicted, preventing memory starvation and ensuring real-time zero-lag propagation for newly arrived signals.
            </Typography>
          </Box>
        </Paper>
      )}

      {/* Tab 5: Publisher Console */}
      {activeTab === 4 && (
        <Paper sx={{ p: 3, bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, color: '#f8fafc', mb: 1 }}>
            Signal Publisher & Test Injection Console
          </Typography>
          <Typography variant="body2" sx={{ color: '#94a3b8', mb: 3 }}>
            Manually inject synthetic or verified B2B intelligence signals to test live subscriber delivery and pipeline throughput.
          </Typography>

          <Grid container spacing={2} sx={{ mb: 3 }}>
            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                label="Target Company"
                value={pubCompany}
                onChange={(e) => setPubCompany(e.target.value)}
                sx={{ bgcolor: '#090d16', input: { color: '#f8fafc' }, label: { color: '#94a3b8' } }}
              />
            </Grid>
            <Grid item xs={12} sm={4}>
              <FormControl fullWidth>
                <InputLabel sx={{ color: '#94a3b8' }}>Signal Type</InputLabel>
                <Select
                  value={pubType}
                  onChange={(e) => setPubType(e.target.value)}
                  label="Signal Type"
                  sx={{ color: '#f8fafc', bgcolor: '#090d16', '& .MuiOutlinedInput-notchedOutline': { borderColor: '#334155' } }}
                >
                  <MenuItem value="TECH_ADOPTION">TECH_ADOPTION</MenuItem>
                  <MenuItem value="HIRING_SURGE">HIRING_SURGE</MenuItem>
                  <MenuItem value="BUYING_INTENT">BUYING_INTENT</MenuItem>
                  <MenuItem value="LEADERSHIP_CHANGE">LEADERSHIP_CHANGE</MenuItem>
                  <MenuItem value="FUNDING_ROUND">FUNDING_ROUND</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                label="Topic Channel"
                value={pubTopic}
                onChange={(e) => setPubTopic(e.target.value)}
                sx={{ bgcolor: '#090d16', input: { color: '#f8fafc' }, label: { color: '#94a3b8' } }}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                multiline
                rows={3}
                label="JSON Payload"
                value={pubPayload}
                onChange={(e) => setPubPayload(e.target.value)}
                sx={{ bgcolor: '#090d16', textarea: { color: '#f8fafc', fontFamily: 'monospace' }, label: { color: '#94a3b8' } }}
              />
            </Grid>
          </Grid>

          <Button
            variant="contained"
            onClick={handlePublishSignal}
            startIcon={<Send size={16} />}
            sx={{ bgcolor: '#0284c7', '&:hover': { bgcolor: '#0369a1' }, px: 3, height: 42 }}
          >
            Publish Live Signal
          </Button>
        </Paper>
      )}

      {/* Tab 6: Throughput & Channel Metrics */}
      {activeTab === 5 && (
        <Paper sx={{ p: 3, bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, color: '#f8fafc', mb: 2 }}>
            Real-Time Streaming Throughput & Channel Metrics
          </Typography>

          <Grid container spacing={3} sx={{ mb: 4 }}>
            <Grid item xs={12} sm={4}>
              <Card sx={{ bgcolor: '#090d16', border: '1px solid #1e293b' }}>
                <CardContent>
                  <Typography variant="caption" sx={{ color: '#94a3b8' }}>Ingestion Throughput</Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, color: '#38bdf8' }}>
                    {stats?.throughput_signals_per_sec || 0} <span style={{ fontSize: 16 }}>sig/sec</span>
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={4}>
              <Card sx={{ bgcolor: '#090d16', border: '1px solid #1e293b' }}>
                <CardContent>
                  <Typography variant="caption" sx={{ color: '#94a3b8' }}>Active Subscriptions</Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, color: '#10b981' }}>
                    {stats?.active_subscriptions || 0}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={4}>
              <Card sx={{ bgcolor: '#090d16', border: '1px solid #1e293b' }}>
                <CardContent>
                  <Typography variant="caption" sx={{ color: '#94a3b8' }}>Active Topics</Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, color: '#f59e0b' }}>
                    {stats?.active_topics.length || 0}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {stats && (
            <Box>
              <Typography variant="subtitle2" sx={{ fontWeight: 600, color: '#cbd5e1', mb: 1 }}>
                Registered Topic Broadcast Channels
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5 }}>
                {stats.active_topics.map((topic) => (
                  <Chip
                    key={topic}
                    label={topic}
                    variant="outlined"
                    sx={{ borderColor: '#0284c7', color: '#38bdf8', fontWeight: 600 }}
                  />
                ))}
              </Box>
            </Box>
          )}
        </Paper>
      )}
    </Box>
  );
}
