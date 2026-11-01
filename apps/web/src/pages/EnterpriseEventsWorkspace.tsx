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
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Switch,
  FormControlLabel,
  LinearProgress,
} from '@mui/material';
import {
  Radio,
  CheckCircle,
  AlertCircle,
  Clock,
  RotateCcw,
  Layers,
  Filter,
  Send,
  ArrowRight,
  ShieldAlert,
} from 'lucide-react';

export const EnterpriseEventsWorkspace: React.FC = () => {
  const [tabIndex, setTabIndex] = useState(0);

  // Sample Outbox Events State
  const [outboxEvents, setOutboxEvents] = useState([
    {
      id: 'evt_001',
      event_type: 'company.resolved',
      aggregate_type: 'COMPANY',
      aggregate_id: 'comp_pacific_retail',
      status: 'PUBLISHED',
      retry_count: 0,
      occurred_at: '2026-11-01 10:14:02 UTC',
      checksum: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    },
    {
      id: 'evt_002',
      event_type: 'lead.scored',
      aggregate_type: 'LEAD',
      aggregate_id: 'lead_pacific_odoo',
      status: 'PUBLISHED',
      retry_count: 0,
      occurred_at: '2026-11-01 10:15:20 UTC',
      checksum: '88d4266fd4e6338d13b845fcf289579d209c897823b9217da3e161936f031589',
    },
    {
      id: 'evt_003',
      event_type: 'signal.detected',
      aggregate_type: 'SIGNAL',
      aggregate_id: 'sig_odoo_migration',
      status: 'PENDING',
      retry_count: 0,
      occurred_at: '2026-11-01 10:20:05 UTC',
      checksum: '1e5e6e3f4f1d467886a86c67ef65cf5ef462ae0ebf791556a3e2e283ff1f2421',
    },
  ]);

  // Consumers & Offsets
  const [consumers, setConsumers] = useState([
    {
      name: 'analytics-indexer',
      partition: 'partition-0',
      last_event: 'evt_002',
      processed: 4820,
      lag: 1,
    },
    {
      name: 'knowledge-graph-projector',
      partition: 'partition-0',
      last_event: 'evt_002',
      processed: 4820,
      lag: 1,
    },
    {
      name: 'webhook-dispatcher',
      partition: 'partition-0',
      last_event: 'evt_001',
      processed: 4819,
      lag: 2,
    },
  ]);

  // Replay Form State
  const [replayTarget, setReplayTarget] = useState('analytics-indexer');
  const [replayFrom, setReplayFrom] = useState('2026-11-01T00:00');
  const [replayTo, setReplayTo] = useState('2026-11-01T12:00');
  const [replayDryRun, setReplayDryRun] = useState(true);
  const [replayResult, setReplayResult] = useState<string | null>(null);

  const handleRunReplay = () => {
    setReplayResult(`Replay initiated for consumer '${replayTarget}': 128 events re-dispatched. Dry-run: ${replayDryRun ? 'YES' : 'NO'}`);
  };

  return (
    <Container maxWidth="xl" sx={{ mt: 3, mb: 6 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 700, color: '#f8fafc' }}>
          Enterprise Event-Driven Architecture & Transactional Outbox
        </Typography>
        <Typography variant="body2" sx={{ color: '#94a3b8' }}>
          Phase 34: Transactional Outbox Pattern, Event Bus Pub/Sub, Idempotent Consumers, and Audited Replay
        </Typography>
      </Box>

      <Paper sx={{ bgcolor: '#0f172a', border: '1px solid #1e293b', mb: 3 }}>
        <Tabs
          value={tabIndex}
          onChange={(_, val) => setTabIndex(val)}
          sx={{
            borderBottom: '1px solid #1e293b',
            '& .MuiTab-root': { color: '#94a3b8', textTransform: 'none', fontWeight: 600 },
            '& .Mui-selected': { color: '#38bdf8' },
            '& .MuiTabs-indicator': { backgroundColor: '#38bdf8' },
          }}
        >
          <Tab icon={<Radio size={16} />} iconPosition="start" label="Transactional Outbox Monitor" />
          <Tab icon={<Layers size={16} />} iconPosition="start" label="Consumer Offsets & Lag" />
          <Tab icon={<RotateCcw size={16} />} iconPosition="start" label="Audited Event Replay" />
          <Tab icon={<ShieldAlert size={16} />} iconPosition="start" label="Dead-Letter Queue (DLQ)" />
        </Tabs>

        {/* Tab 0: Outbox Monitor */}
        {tabIndex === 0 && (
          <Box sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6" sx={{ color: '#f8fafc', fontWeight: 600 }}>
                Outbox Events Stream
              </Typography>
              <Chip label="At-Least-Once Delivery Active" color="success" size="small" variant="outlined" />
            </Box>

            <Table sx={{ bgcolor: '#111827', borderRadius: 1 }}>
              <TableHead>
                <TableRow sx={{ '& th': { color: '#94a3b8', borderColor: '#1e293b' } }}>
                  <TableCell>Event ID</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Aggregate</TableCell>
                  <TableCell>Occurred At</TableCell>
                  <TableCell>Checksum (SHA-256)</TableCell>
                  <TableCell>Status</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {outboxEvents.map((evt) => (
                  <TableRow key={evt.id} sx={{ '& td': { color: '#e2e8f0', borderColor: '#1e293b' } }}>
                    <TableCell sx={{ fontFamily: 'monospace', fontSize: 13 }}>{evt.id}</TableCell>
                    <TableCell sx={{ fontWeight: 600, color: '#38bdf8' }}>{evt.event_type}</TableCell>
                    <TableCell>{evt.aggregate_type}:{evt.aggregate_id}</TableCell>
                    <TableCell>{evt.occurred_at}</TableCell>
                    <TableCell sx={{ fontFamily: 'monospace', fontSize: 11, color: '#64748b' }}>
                      {evt.checksum.slice(0, 16)}...
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={evt.status}
                        size="small"
                        color={evt.status === 'PUBLISHED' ? 'success' : evt.status === 'PENDING' ? 'warning' : 'error'}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Box>
        )}

        {/* Tab 1: Consumer Offsets & Lag */}
        {tabIndex === 1 && (
          <Box sx={{ p: 3 }}>
            <Typography variant="h6" sx={{ color: '#f8fafc', fontWeight: 600, mb: 2 }}>
              Active Stream Consumers & Partition Lag
            </Typography>

            <Grid container spacing={3}>
              {consumers.map((c, i) => (
                <Grid item xs={12} md={4} key={i}>
                  <Card sx={{ bgcolor: '#111827', border: '1px solid #1e293b' }}>
                    <CardHeader
                      title={c.name}
                      subheader={`Partition: ${c.partition}`}
                      titleTypographyProps={{ color: '#f8fafc', fontWeight: 600, fontSize: 16 }}
                      subheaderTypographyProps={{ color: '#64748b', fontSize: 13 }}
                    />
                    <CardContent>
                      <Box sx={{ mb: 1, display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="caption" sx={{ color: '#94a3b8' }}>Processed Events</Typography>
                        <Typography variant="caption" sx={{ color: '#38bdf8', fontWeight: 700 }}>{c.processed.toLocaleString()}</Typography>
                      </Box>
                      <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="caption" sx={{ color: '#94a3b8' }}>Consumer Lag</Typography>
                        <Typography variant="caption" sx={{ color: c.lag > 5 ? '#f87171' : '#4ade80', fontWeight: 700 }}>
                          {c.lag} message(s)
                        </Typography>
                      </Box>
                      <LinearProgress variant="determinate" value={100 - (c.lag * 5)} sx={{ height: 6, borderRadius: 1 }} />
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </Box>
        )}

        {/* Tab 2: Audited Event Replay */}
        {tabIndex === 2 && (
          <Box sx={{ p: 3 }}>
            <Typography variant="h6" sx={{ color: '#f8fafc', fontWeight: 600, mb: 2 }}>
              Bounded Historical Event Replay
            </Typography>
            <Alert severity="info" sx={{ mb: 3, bgcolor: '#0c4a6e', color: '#e0f2fe' }}>
              Replay enables re-projecting historical event streams into analytics or graph stores without data corruption. All replay actions are tamper-evident and audited.
            </Alert>

            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Target Consumer"
                  value={replayTarget}
                  onChange={(e) => setReplayTarget(e.target.value)}
                  sx={{ mb: 2 }}
                />
                <TextField
                  fullWidth
                  type="datetime-local"
                  label="From Timestamp"
                  value={replayFrom}
                  onChange={(e) => setReplayFrom(e.target.value)}
                  InputLabelProps={{ shrink: true }}
                  sx={{ mb: 2 }}
                />
                <TextField
                  fullWidth
                  type="datetime-local"
                  label="To Timestamp"
                  value={replayTo}
                  onChange={(e) => setReplayTo(e.target.value)}
                  InputLabelProps={{ shrink: true }}
                  sx={{ mb: 2 }}
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={replayDryRun}
                      onChange={(e) => setReplayDryRun(e.target.checked)}
                      color="primary"
                    />
                  }
                  label="Dry-Run Mode (Simulate without dispatching to consumer)"
                  sx={{ color: '#94a3b8', mb: 2 }}
                />
                <Box>
                  <Button variant="contained" color="primary" startIcon={<RotateCcw size={16} />} onClick={handleRunReplay}>
                    Execute Audited Replay
                  </Button>
                </Box>
              </Grid>

              <Grid item xs={12} md={6}>
                {replayResult && (
                  <Paper sx={{ p: 2, bgcolor: '#111827', border: '1px solid #1e293b' }}>
                    <Typography variant="subtitle2" sx={{ color: '#38bdf8', fontWeight: 600, mb: 1 }}>
                      Replay Execution Log
                    </Typography>
                    <Typography variant="body2" sx={{ color: '#e2e8f0', fontFamily: 'monospace' }}>
                      {replayResult}
                    </Typography>
                  </Paper>
                )}
              </Grid>
            </Grid>
          </Box>
        )}

        {/* Tab 3: DLQ */}
        {tabIndex === 3 && (
          <Box sx={{ p: 3 }}>
            <Typography variant="h6" sx={{ color: '#f8fafc', fontWeight: 600, mb: 2 }}>
              Dead-Letter Queue (DLQ)
            </Typography>
            <Alert severity="success" sx={{ bgcolor: '#064e3b', color: '#a7f3d0' }}>
              DLQ is clear. All published events have been acknowledged by registered stream consumers.
            </Alert>
          </Box>
        )}
      </Paper>
    </Container>
  );
};

export default EnterpriseEventsWorkspace;

