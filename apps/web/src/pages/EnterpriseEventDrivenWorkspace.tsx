import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Tabs,
  Tab,
  Button,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  CircularProgress,
  Alert,
  IconButton,
  Tooltip,
  Card,
  CardContent,
  Grid
} from '@mui/material';
import {
  Radio,
  Share2,
  FileCode,
  ShieldCheck,
  AlertTriangle,
  Play,
  RefreshCw,
  RotateCcw,
  Trash2,
  Sliders,
  History,
  Layers,
  CheckCircle,
  Copy,
  Zap
} from 'lucide-react';

interface SchemaItem {
  id: string;
  event_type: string;
  version: string;
  fingerprint: string;
  compatibility: string;
  created_at: string;
  schema_definition: any;
}

interface DLQItem {
  id: string;
  original_event_id: string;
  event_type: string;
  consumer_name: string;
  reason: string;
  error_details: string;
  status: string;
  retry_count: number;
  propagation_depth: number;
  created_at: string;
}

export const EnterpriseEventDrivenWorkspace: React.FC = () => {
  const [currentTab, setCurrentTab] = useState(0);
  const [schemas, setSchemas] = useState<SchemaItem[]>([]);
  const [dlqItems, setDlqItems] = useState<DLQItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(null);

  // CQRS Command State
  const [commandName, setCommandName] = useState('QualifyLeadCommand');
  const [idempotencyKey, setIdempotencyKey] = useState(`cmd_${Date.now()}`);
  const [commandPayload, setCommandPayload] = useState('{\n  "lead_id": "lead-sydney-101",\n  "qualification_tier": "ENTERPRISE_P1",\n  "allocated_budget": 5000\n}');
  const [commandResult, setCommandResult] = useState<any>(null);

  // Event Sourcing State
  const [aggregateType, setAggregateType] = useState('Lead');
  const [aggregateId, setAggregateId] = useState('lead-sample-001');
  const [aggregateHistory, setAggregateHistory] = useState<any>(null);

  // Simulator State
  const [simEventType, setSimEventType] = useState('lead.intent.detected');
  const [simPayload, setSimPayload] = useState('{\n  "intent_score": 94,\n  "technology": "Odoo Enterprise",\n  "region": "Australia"\n}');
  const [simResult, setSimResult] = useState<any>(null);

  const fetchSchemas = async () => {
    try {
      const res = await fetch('/api/v1/events/schemas');
      if (res.ok) {
        const data = await res.json();
        setSchemas(data);
      }
    } catch (err) {
      console.error('Failed to fetch schemas:', err);
    }
  };

  const fetchDLQ = async () => {
    try {
      const res = await fetch('/api/v1/events/dlq/records');
      if (res.ok) {
        const data = await res.json();
        setDlqItems(data);
      }
    } catch (err) {
      console.error('Failed to fetch DLQ:', err);
    }
  };

  useEffect(() => {
    fetchSchemas();
    fetchDLQ();
  }, []);

  const handleDispatchCommand = async () => {
    setIsLoading(true);
    setFeedback(null);
    try {
      let parsedPayload = {};
      try {
        parsedPayload = JSON.parse(commandPayload);
      } catch (e) {
        throw new Error('Invalid JSON format in command payload');
      }

      const res = await fetch('/api/v1/events/commands', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          idempotency_key: idempotencyKey,
          command_name: commandName,
          payload: parsedPayload
        })
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Command dispatch failed');
      }

      const data = await res.json();
      setCommandResult(data);
      setFeedback({
        type: 'success',
        text: data.is_cached
          ? `Idempotent execution: duplicate command recognized (Cached response served).`
          : `Command executed successfully and recorded with idempotency protection.`
      });
    } catch (err: any) {
      setFeedback({ type: 'error', text: err.message });
    } finally {
      setIsLoading(false);
    }
  };

  const handleFetchHistory = async () => {
    setIsLoading(true);
    setFeedback(null);
    try {
      const res = await fetch(`/api/v1/events/aggregates/${aggregateType}/${aggregateId}/history`);
      if (!res.ok) throw new Error('Could not fetch aggregate history');
      const data = await res.json();
      setAggregateHistory(data);
    } catch (err: any) {
      setFeedback({ type: 'error', text: err.message });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSimulate = async () => {
    setIsLoading(true);
    try {
      const res = await fetch('/api/v1/events/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event_type: simEventType,
          payload: JSON.parse(simPayload)
        })
      });
      if (res.ok) {
        const data = await res.json();
        setSimResult(data);
      }
    } catch (err: any) {
      setFeedback({ type: 'error', text: err.message });
    } finally {
      setIsLoading(false);
    }
  };

  const handleRedrive = async (id: string) => {
    try {
      const res = await fetch(`/api/v1/events/dlq/${id}/retry`, { method: 'POST' });
      if (res.ok) {
        setFeedback({ type: 'success', text: `Event ${id} redrived successfully.` });
        fetchDLQ();
      }
    } catch (err: any) {
      setFeedback({ type: 'error', text: err.message });
    }
  };

  return (
    <Box sx={{ maxWidth: 1400, mx: 'auto', p: 3 }}>
      {/* Header */}
      <Paper
        elevation={0}
        sx={{
          p: 3.5,
          mb: 3,
          borderRadius: 3,
          background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
          border: '1px solid #334155'
        }}
      >
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
              <Radio size={26} color="#38bdf8" />
              <Typography variant="h5" sx={{ fontWeight: 800, color: '#f8fafc', letterSpacing: -0.5 }}>
                LeadNexus AI X — Phase 36: Event-Driven Architecture & CQRS Platform
              </Typography>
            </Box>
            <Typography variant="body2" sx={{ color: '#94a3b8' }}>
              Distributed Event Bus, Selective Event Sourcing, Monotonic State Reconstruction, Schema Registry & Loop Defense.
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 1.5 }}>
            <Chip label="CQRS Write/Read Split" size="small" sx={{ bgcolor: '#0284c7', color: '#fff', fontWeight: 700 }} />
            <Chip label="Monotonic Sequence" size="small" sx={{ bgcolor: '#047857', color: '#fff', fontWeight: 700 }} />
            <Chip label="Max Depth 5 Loop Guard" size="small" sx={{ bgcolor: '#7c3aed', color: '#fff', fontWeight: 700 }} />
          </Box>
        </Box>

        <Tabs
          value={currentTab}
          onChange={(_, v) => setCurrentTab(v)}
          sx={{
            borderTop: '1px solid #334155',
            pt: 1,
            '& .MuiTab-root': { color: '#94a3b8', textTransform: 'none', fontWeight: 600 },
            '& .Mui-selected': { color: '#38bdf8' }
          }}
        >
          <Tab icon={<FileCode size={16} />} iconPosition="start" label="Event Schema Registry" />
          <Tab icon={<Zap size={16} />} iconPosition="start" label="CQRS Command Bus" />
          <Tab icon={<History size={16} />} iconPosition="start" label="Event Sourcing & Snapshots" />
          <Tab icon={<AlertTriangle size={16} />} iconPosition="start" label={`Dead Letter Queue (${dlqItems.length})`} />
          <Tab icon={<Sliders size={16} />} iconPosition="start" label="Event Routing Simulator" />
        </Tabs>
      </Paper>

      {feedback && (
        <Alert severity={feedback.type} onClose={() => setFeedback(null)} sx={{ mb: 3 }}>
          {feedback.text}
        </Alert>
      )}

      {/* Tab 0: Schema Registry */}
      {currentTab === 0 && (
        <Paper elevation={0} sx={{ p: 3, bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6" sx={{ color: '#f8fafc', fontWeight: 700 }}>
              Registered Event Schemas ({schemas.length})
            </Typography>
            <IconButton onClick={fetchSchemas} sx={{ color: '#94a3b8' }}>
              <RefreshCw size={18} />
            </IconButton>
          </Box>

          <TableContainer>
            <Table size="small">
              <TableHead sx={{ bgcolor: '#0b1329' }}>
                <TableRow>
                  <TableCell sx={{ color: '#94a3b8', fontWeight: 700 }}>Event Type</TableCell>
                  <TableCell sx={{ color: '#94a3b8', fontWeight: 700 }}>Version</TableCell>
                  <TableCell sx={{ color: '#94a3b8', fontWeight: 700 }}>Compatibility</TableCell>
                  <TableCell sx={{ color: '#94a3b8', fontWeight: 700 }}>SHA-256 Fingerprint</TableCell>
                  <TableCell sx={{ color: '#94a3b8', fontWeight: 700 }}>Created At</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {schemas.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} align="center" sx={{ py: 4, color: '#94a3b8' }}>
                      No schemas registered yet.
                    </TableCell>
                  </TableRow>
                ) : (
                  schemas.map((s) => (
                    <TableRow key={s.id} hover sx={{ borderBottom: '1px solid #1e293b' }}>
                      <TableCell sx={{ color: '#f8fafc', fontWeight: 600 }}>{s.event_type}</TableCell>
                      <TableCell>
                        <Chip label={`v${s.version}`} size="small" sx={{ bgcolor: '#1e293b', color: '#38bdf8' }} />
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={s.compatibility}
                          size="small"
                          sx={{
                            bgcolor: s.compatibility === 'BREAKING' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                            color: s.compatibility === 'BREAKING' ? '#ef4444' : '#10b981',
                            fontWeight: 700
                          }}
                        />
                      </TableCell>
                      <TableCell sx={{ fontFamily: 'monospace', fontSize: 11, color: '#94a3b8' }}>
                        {s.fingerprint.substring(0, 16)}...
                      </TableCell>
                      <TableCell sx={{ color: '#64748b', fontSize: 12 }}>
                        {new Date(s.created_at).toLocaleString()}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {/* Tab 1: CQRS Command Bus */}
      {currentTab === 1 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Paper elevation={0} sx={{ p: 3, bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2 }}>
              <Typography variant="h6" sx={{ color: '#f8fafc', fontWeight: 700, mb: 2 }}>
                Dispatch CQRS Command
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <TextField
                  fullWidth
                  size="small"
                  label="Command Name"
                  value={commandName}
                  onChange={(e) => setCommandName(e.target.value)}
                  InputLabelProps={{ sx: { color: '#94a3b8' } }}
                  InputProps={{ sx: { bgcolor: '#0b1329', color: '#f8fafc' } }}
                />
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Idempotency Key"
                    value={idempotencyKey}
                    onChange={(e) => setIdempotencyKey(e.target.value)}
                    InputLabelProps={{ sx: { color: '#94a3b8' } }}
                    InputProps={{ sx: { bgcolor: '#0b1329', color: '#f8fafc' } }}
                  />
                  <Button
                    variant="outlined"
                    onClick={() => setIdempotencyKey(`cmd_${Date.now()}`)}
                    sx={{ borderColor: '#334155', color: '#94a3b8', textTransform: 'none' }}
                  >
                    New Key
                  </Button>
                </Box>
                <TextField
                  fullWidth
                  multiline
                  rows={6}
                  label="Payload (JSON)"
                  value={commandPayload}
                  onChange={(e) => setCommandPayload(e.target.value)}
                  InputLabelProps={{ sx: { color: '#94a3b8' } }}
                  InputProps={{ sx: { bgcolor: '#0b1329', color: '#38bdf8', fontFamily: 'monospace' } }}
                />
                <Button
                  variant="contained"
                  onClick={handleDispatchCommand}
                  disabled={isLoading}
                  sx={{ bgcolor: '#0284c7', fontWeight: 700, textTransform: 'none' }}
                >
                  {isLoading ? <CircularProgress size={20} color="inherit" /> : 'Dispatch Command'}
                </Button>
              </Box>
            </Paper>
          </Grid>

          <Grid item xs={12} md={6}>
            <Paper elevation={0} sx={{ p: 3, bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2, height: '100%' }}>
              <Typography variant="h6" sx={{ color: '#f8fafc', fontWeight: 700, mb: 2 }}>
                Execution & Idempotency Telemetry
              </Typography>
              {commandResult ? (
                <Box>
                  <Box sx={{ display: 'flex', gap: 1.5, mb: 2 }}>
                    <Chip
                      label={commandResult.is_cached ? 'Idempotent Cache Hit' : 'Initial Execution (Processed)'}
                      color={commandResult.is_cached ? 'warning' : 'success'}
                      sx={{ fontWeight: 700 }}
                    />
                    <Chip label={`Key: ${commandResult.idempotency_key}`} sx={{ bgcolor: '#1e293b', color: '#94a3b8' }} />
                  </Box>
                  <Paper sx={{ p: 2, bgcolor: '#0b1329', border: '1px solid #334155', borderRadius: 1.5 }}>
                    <pre style={{ margin: 0, color: '#38bdf8', fontFamily: 'monospace', fontSize: 13 }}>
                      {JSON.stringify(commandResult.result, null, 2)}
                    </pre>
                  </Paper>
                </Box>
              ) : (
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  Execute a command to inspect execution status, cached duplicate suppression, and transactional response.
                </Typography>
              )}
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* Tab 2: Event Sourcing & Snapshots */}
      {currentTab === 2 && (
        <Paper elevation={0} sx={{ p: 3, bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2 }}>
          <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
            <TextField
              size="small"
              label="Aggregate Type"
              value={aggregateType}
              onChange={(e) => setAggregateType(e.target.value)}
              InputLabelProps={{ sx: { color: '#94a3b8' } }}
              InputProps={{ sx: { bgcolor: '#0b1329', color: '#f8fafc' } }}
            />
            <TextField
              size="small"
              label="Aggregate ID"
              value={aggregateId}
              onChange={(e) => setAggregateId(e.target.value)}
              InputLabelProps={{ sx: { color: '#94a3b8' } }}
              InputProps={{ sx: { bgcolor: '#0b1329', color: '#f8fafc' } }}
            />
            <Button
              variant="contained"
              onClick={handleFetchHistory}
              sx={{ bgcolor: '#0284c7', fontWeight: 700, textTransform: 'none' }}
            >
              Reconstruct State & History
            </Button>
          </Box>

          {aggregateHistory && (
            <Box>
              <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                <Chip label={`Current Sequence: v${aggregateHistory.current_version}`} color="primary" sx={{ fontWeight: 700 }} />
                <Chip label={`Events Count: ${aggregateHistory.events.length}`} sx={{ bgcolor: '#1e293b', color: '#38bdf8' }} />
              </Box>

              <Typography variant="subtitle2" sx={{ color: '#f8fafc', fontWeight: 700, mb: 1 }}>
                Reconstructed Canonical State:
              </Typography>
              <Paper sx={{ p: 2, mb: 3, bgcolor: '#0b1329', border: '1px solid #334155' }}>
                <pre style={{ margin: 0, color: '#34d399', fontFamily: 'monospace', fontSize: 13 }}>
                  {JSON.stringify(aggregateHistory.materialized_state, null, 2)}
                </pre>
              </Paper>

              <Typography variant="subtitle2" sx={{ color: '#f8fafc', fontWeight: 700, mb: 1 }}>
                Event Stream (Monotonic Ordering):
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead sx={{ bgcolor: '#0b1329' }}>
                    <TableRow>
                      <TableCell sx={{ color: '#94a3b8', fontWeight: 700 }}>Seq #</TableCell>
                      <TableCell sx={{ color: '#94a3b8', fontWeight: 700 }}>Event Type</TableCell>
                      <TableCell sx={{ color: '#94a3b8', fontWeight: 700 }}>Correlation ID</TableCell>
                      <TableCell sx={{ color: '#94a3b8', fontWeight: 700 }}>Payload Snapshot</TableCell>
                      <TableCell sx={{ color: '#94a3b8', fontWeight: 700 }}>Occurred At</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {aggregateHistory.events.map((ev: any) => (
                      <TableRow key={ev.id} hover sx={{ borderBottom: '1px solid #1e293b' }}>
                        <TableCell sx={{ color: '#38bdf8', fontWeight: 700 }}>#{ev.sequence_number}</TableCell>
                        <TableCell sx={{ color: '#f8fafc', fontWeight: 600 }}>{ev.event_type}</TableCell>
                        <TableCell sx={{ color: '#94a3b8', fontSize: 11 }}>{ev.correlation_id}</TableCell>
                        <TableCell sx={{ fontFamily: 'monospace', fontSize: 11, color: '#cbd5e1' }}>
                          {JSON.stringify(ev.payload)}
                        </TableCell>
                        <TableCell sx={{ color: '#64748b', fontSize: 12 }}>{new Date(ev.occurred_at).toLocaleTimeString()}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          )}
        </Paper>
      )}

      {/* Tab 3: DLQ */}
      {currentTab === 3 && (
        <Paper elevation={0} sx={{ p: 3, bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6" sx={{ color: '#f8fafc', fontWeight: 700 }}>
              Dead Letter Queue & Poison Pill Isolation ({dlqItems.length})
            </Typography>
            <IconButton onClick={fetchDLQ} sx={{ color: '#94a3b8' }}>
              <RefreshCw size={18} />
            </IconButton>
          </Box>

          <TableContainer>
            <Table size="small">
              <TableHead sx={{ bgcolor: '#0b1329' }}>
                <TableRow>
                  <TableCell sx={{ color: '#94a3b8', fontWeight: 700 }}>Event Type</TableCell>
                  <TableCell sx={{ color: '#94a3b8', fontWeight: 700 }}>Consumer</TableCell>
                  <TableCell sx={{ color: '#94a3b8', fontWeight: 700 }}>Reason</TableCell>
                  <TableCell sx={{ color: '#94a3b8', fontWeight: 700 }}>Error Details</TableCell>
                  <TableCell sx={{ color: '#94a3b8', fontWeight: 700 }}>Status</TableCell>
                  <TableCell align="right" sx={{ color: '#94a3b8', fontWeight: 700 }}>Action</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {dlqItems.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center" sx={{ py: 4, color: '#94a3b8' }}>
                      Dead Letter Queue is clear. No poisoned events in quarantine.
                    </TableCell>
                  </TableRow>
                ) : (
                  dlqItems.map((item) => (
                    <TableRow key={item.id} hover sx={{ borderBottom: '1px solid #1e293b' }}>
                      <TableCell sx={{ color: '#f8fafc', fontWeight: 600 }}>{item.event_type}</TableCell>
                      <TableCell sx={{ color: '#94a3b8' }}>{item.consumer_name}</TableCell>
                      <TableCell>
                        <Chip label={item.reason} size="small" color="error" sx={{ fontWeight: 700 }} />
                      </TableCell>
                      <TableCell sx={{ color: '#f87171', fontSize: 12, maxWidth: 300 }}>
                        {item.error_details}
                      </TableCell>
                      <TableCell>
                        <Chip label={item.status} size="small" sx={{ bgcolor: '#1e293b', color: '#94a3b8' }} />
                      </TableCell>
                      <TableCell align="right">
                        <Button
                          size="small"
                          startIcon={<RotateCcw size={14} />}
                          onClick={() => handleRedrive(item.id)}
                          sx={{ textTransform: 'none', color: '#38bdf8' }}
                        >
                          Redrive
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {/* Tab 4: Simulator */}
      {currentTab === 4 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Paper elevation={0} sx={{ p: 3, bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2 }}>
              <Typography variant="h6" sx={{ color: '#f8fafc', fontWeight: 700, mb: 2 }}>
                Event Routing & Propagation Simulator
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <TextField
                  fullWidth
                  size="small"
                  label="Event Type"
                  value={simEventType}
                  onChange={(e) => setSimEventType(e.target.value)}
                  InputLabelProps={{ sx: { color: '#94a3b8' } }}
                  InputProps={{ sx: { bgcolor: '#0b1329', color: '#f8fafc' } }}
                />
                <TextField
                  fullWidth
                  multiline
                  rows={6}
                  label="Event Payload"
                  value={simPayload}
                  onChange={(e) => setSimPayload(e.target.value)}
                  InputLabelProps={{ sx: { color: '#94a3b8' } }}
                  InputProps={{ sx: { bgcolor: '#0b1329', color: '#38bdf8', fontFamily: 'monospace' } }}
                />
                <Button
                  variant="contained"
                  onClick={handleSimulate}
                  disabled={isLoading}
                  sx={{ bgcolor: '#0284c7', fontWeight: 700, textTransform: 'none' }}
                >
                  Run Simulation
                </Button>
              </Box>
            </Paper>
          </Grid>

          <Grid item xs={12} md={6}>
            <Paper elevation={0} sx={{ p: 3, bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2, height: '100%' }}>
              <Typography variant="h6" sx={{ color: '#f8fafc', fontWeight: 700, mb: 2 }}>
                Predicted Consumers & Projections
              </Typography>
              {simResult ? (
                <Box>
                  <Chip label="Zero Production Mutation" color="success" size="small" sx={{ mb: 2, fontWeight: 700 }} />
                  <Typography variant="subtitle2" sx={{ color: '#94a3b8', mb: 1 }}>Matched Consumer Handlers:</Typography>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
                    {simResult.matched_consumers.map((c: string, i: number) => (
                      <Chip key={i} label={c} size="small" sx={{ bgcolor: '#1e293b', color: '#38bdf8' }} />
                    ))}
                  </Box>
                  <Typography variant="subtitle2" sx={{ color: '#94a3b8', mb: 1 }}>Predicted Side-Effects:</Typography>
                  <ul>
                    {simResult.predicted_side_effects.map((eff: string, i: number) => (
                      <li key={i} style={{ color: '#cbd5e1', fontSize: 13, marginBottom: 4 }}>{eff}</li>
                    ))}
                  </ul>
                </Box>
              ) : (
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  Run a simulation to verify subscriber routing without modifying PostgreSQL database state.
                </Typography>
              )}
            </Paper>
          </Grid>
        </Grid>
      )}
    </Box>
  );
};

export default EnterpriseEventDrivenWorkspace;

