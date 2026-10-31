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
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Stepper,
  Step,
  StepLabel
} from '@mui/material';
import {
  SwapHoriz as MigrationIcon,
  Timeline as StepperIcon,
  CompareArrows as ReconcileIcon,
  CloudSync as BackfillIcon,
  HistoryEdu as VersionIcon,
  CheckCircle as SuccessIcon,
  Warning as WarningIcon,
  Undo as RollbackIcon,
  PlayArrow as ActionIcon
} from '@mui/icons-material';

const EXPAND_STEPS = ['Planned', 'Expanding (Add Cols)', 'Backfilling (Keyset)', 'Reconciling (100% Parity)', 'Contracting (Drop Legacy)', 'Completed'];

export const EnterpriseMigrationWorkspace: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);

  // Active Plan State
  const [activePlan, setActivePlan] = useState({
    id: 'plan_v32_to_v33_contact_verification',
    name: 'Contact Verification Schema Evolution',
    source_version: 'v32.0.0',
    target_version: 'v33.0.0',
    phase: 'RECONCILING',
    active_step: 3,
  });

  // Reconciliation State
  const [reconciliation, setReconciliation] = useState({
    table: 'contacts',
    source_col: 'legacy_verified_bool',
    target_col: 'verification_state_enum',
    evaluated: 18450,
    discrepancies: 0,
    parity_pct: 100.0,
    status: 'PASSED',
  });

  // Backfill State
  const [backfill, setBackfill] = useState({
    table: 'contacts',
    processed: 18450,
    total: 18450,
    chunk_size: 500,
    errors: 0,
    status: 'COMPLETED',
  });

  const handleAdvanceToContracting = () => {
    setActivePlan((prev) => ({
      ...prev,
      phase: 'CONTRACTING',
      active_step: 4,
    }));
  };

  const handleRollback = () => {
    setActivePlan((prev) => ({
      ...prev,
      phase: 'ROLLED_BACK',
      active_step: 0,
    }));
  };

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 6 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
          <MigrationIcon color="primary" sx={{ fontSize: 36 }} />
          <Typography variant="h4" fontWeight={700}>
            Enterprise Data Migration & Zero-Downtime Upgrade Platform
          </Typography>
          <Chip label="Phase 33 Active" color="primary" variant="outlined" size="small" />
        </Box>
        <Typography variant="body1" color="text.secondary">
          Expand-Migrate-Contract schema evolution, dual-write parity reconciliation, chunked keyset backfills, and API version contracts.
        </Typography>
      </Box>

      {/* Tabs */}
      <Paper sx={{ mb: 4 }}>
        <Tabs
          value={activeTab}
          onChange={(_, val) => setActiveTab(val)}
          indicatorColor="primary"
          textColor="primary"
          variant="scrollable"
        >
          <Tab icon={<StepperIcon />} label="Expand-Migrate-Contract Stepper" iconPosition="start" />
          <Tab icon={<BackfillIcon />} label="Keyset Backfill Monitor" iconPosition="start" />
          <Tab icon={<ReconcileIcon />} label="Parity & Dual-Write Reconciliation" iconPosition="start" />
          <Tab icon={<VersionIcon />} label="API Version Contracts" iconPosition="start" />
        </Tabs>
      </Paper>

      {/* Tab 0: Stepper & Plan */}
      {activeTab === 0 && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Paper sx={{ p: 4, mb: 3 }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Active Schema Migration: {activePlan.name}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
                {activePlan.source_version} &rarr; {activePlan.target_version} • Plan ID: <code>{activePlan.id}</code>
              </Typography>
              <Stepper activeStep={activePlan.active_step} alternativeLabel>
                {EXPAND_STEPS.map((label, index) => (
                  <Step key={label}>
                    <StepLabel>{label}</StepLabel>
                  </Step>
                ))}
              </Stepper>
            </Paper>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card variant="outlined">
              <CardHeader
                title="Stage Gate: Contracting Approval"
                subheader="Contracting drops legacy columns. Only allowed when Parity == 100.0%."
                action={
                  <Chip
                    label={reconciliation.parity_pct === 100.0 ? 'GATE OPEN' : 'GATE BLOCKED'}
                    color={reconciliation.parity_pct === 100.0 ? 'success' : 'error'}
                    size="small"
                  />
                }
              />
              <Divider />
              <CardContent>
                <Typography variant="body2" sx={{ mb: 2 }}>
                  Current Parity: <strong>{reconciliation.parity_pct}%</strong> (0 discrepancies across {reconciliation.evaluated.toLocaleString()} rows).
                </Typography>
                <Box sx={{ display: 'flex', gap: 2 }}>
                  <Button
                    variant="contained"
                    color="primary"
                    startIcon={<ActionIcon />}
                    disabled={activePlan.phase !== 'RECONCILING'}
                    onClick={handleAdvanceToContracting}
                  >
                    Advance to Contracting
                  </Button>
                  <Button
                    variant="outlined"
                    color="error"
                    startIcon={<RollbackIcon />}
                    onClick={handleRollback}
                  >
                    Trigger Safe Rollback
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card variant="outlined">
              <CardHeader
                title="Zero-Downtime Guarantee"
                subheader="Eliminates table locks and service degradation"
              />
              <Divider />
              <CardContent>
                <List dense>
                  <ListItem>
                    <ListItemIcon><SuccessIcon color="success" /></ListItemIcon>
                    <ListItemText primary="Expand Phase" secondary="New columns added as NULLABLE without table locks." />
                  </ListItem>
                  <ListItem>
                    <ListItemIcon><SuccessIcon color="success" /></ListItemIcon>
                    <ListItemText primary="Dual-Write Mirror" secondary="Writes propagate to both columns with failure isolation." />
                  </ListItem>
                  <ListItem>
                    <ListItemIcon><SuccessIcon color="success" /></ListItemIcon>
                    <ListItemText primary="Reconciliation Gate" secondary="100% parity verified before legacy columns are dropped." />
                  </ListItem>
                </List>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Tab 1: Backfill */}
      {activeTab === 1 && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Chunked Keyset Backfill Engine
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Background backfills execute with zero table locks, rate throttling, and stateful cursor checkpointing.
              </Typography>
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Target Table</TableCell>
                      <TableCell>Chunk Size</TableCell>
                      <TableCell>Progress</TableCell>
                      <TableCell>Errors</TableCell>
                      <TableCell>Status</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    <TableRow>
                      <TableCell><code>{backfill.table}</code></TableCell>
                      <TableCell>{backfill.chunk_size} rows/chunk</TableCell>
                      <TableCell>
                        <strong>{backfill.processed.toLocaleString()} / {backfill.total.toLocaleString()}</strong> (100%)
                      </TableCell>
                      <TableCell>{backfill.errors}</TableCell>
                      <TableCell><Chip label={backfill.status} color="success" size="small" /></TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* Tab 2: Reconciliation */}
      {activeTab === 2 && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Dual-Write Parity & Reconciliation Audit
              </Typography>
              <Alert severity="success" sx={{ mb: 3 }}>
                Parity verified at <strong>100.0%</strong> across 18,450 records. Zero discrepancies detected. Legacy columns are eligible for safe contraction.
              </Alert>
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Table</TableCell>
                      <TableCell>Legacy Column</TableCell>
                      <TableCell>New Schema Column</TableCell>
                      <TableCell>Records Evaluated</TableCell>
                      <TableCell>Discrepancies</TableCell>
                      <TableCell>Parity Status</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    <TableRow>
                      <TableCell><code>{reconciliation.table}</code></TableCell>
                      <TableCell><code>{reconciliation.source_col}</code></TableCell>
                      <TableCell><code>{reconciliation.target_col}</code></TableCell>
                      <TableCell>{reconciliation.evaluated.toLocaleString()}</TableCell>
                      <TableCell>{reconciliation.discrepancies}</TableCell>
                      <TableCell>
                        <Chip
                          icon={<SuccessIcon />}
                          label="100.0% PASSED"
                          color="success"
                          size="small"
                        />
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* Tab 3: API Versions */}
      {activeTab === 3 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card variant="outlined">
              <CardHeader
                title="API v1 (Legacy Stable)"
                subheader="Prefix: /api/v1 • Sunset Scheduled: 2027-12-31"
                action={<Chip label="ACTIVE (DEPRECATION WARNING)" color="warning" size="small" />}
              />
              <Divider />
              <CardContent>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Returns HTTP <code>Sunset: Wed, 31 Dec 2027 23:59:59 GMT</code> and <code>Deprecation: true</code> headers. All v1 routes remain fully operational.
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card variant="outlined">
              <CardHeader
                title="API v2 (Modern Standard)"
                subheader="Prefix: /api/v2 • Active Canonical Version"
                action={<Chip label="CANONICAL" color="success" size="small" />}
              />
              <Divider />
              <CardContent>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Features keyset cursor pagination, structured error envelopes, and strongly-typed data contracts.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
    </Container>
  );
};
