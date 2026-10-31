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
  InputLabel
} from '@mui/material';
import {
  Gavel as PolicyIcon,
  VisibilityOff as MaskIcon,
  Description as ContractIcon,
  Block as SuppressionIcon,
  Lock as LegalHoldIcon,
  Speed as QuotaIcon,
  Security as SecurityIcon,
  CheckCircle as ValidIcon,
  Warning as ViolationIcon,
  PlayArrow as EvaluateIcon
} from '@mui/icons-material';

export const EnterpriseGovernanceWorkspace: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);

  // Policy Evaluation State
  const [evalAction, setEvalAction] = useState('companies:export');
  const [evalRole, setEvalRole] = useState('ANALYST');
  const [evalResult, setEvalResult] = useState<any>(null);

  // Masking State
  const [rawEmail, setRawEmail] = useState('sarah.jenkins@targetacme.com');
  const [rawPhone, setRawPhone] = useState('+1-415-555-8921');
  const [maskedOutput, setMaskedOutput] = useState<any>(null);

  // Data Contract State
  const [contractPayload, setContractPayload] = useState(
    JSON.stringify(
      {
        name: 'Apex Manufacturing Ltd',
        domain: 'apexmanufacturing.com',
        technologies: ['Odoo 17.0', 'PostgreSQL'],
        observed_at: new Date().toISOString(),
      },
      null,
      2
    )
  );
  const [contractValidation, setContractValidation] = useState<any>(null);

  // Suppression State
  const [checkTarget, setCheckTarget] = useState('competitor-corp.com');
  const [suppressionResult, setSuppressionResult] = useState<any>(null);

  const handleEvaluatePolicy = () => {
    if (evalRole === 'ANALYST' && evalAction === 'companies:export') {
      setEvalResult({
        decision: 'REQUIRE_APPROVAL',
        matched_policy_id: 'pol_export_gate_01',
        matched_rule_name: 'Require Admin Approval on Bulk Exports for Analysts',
        reason: 'Policy matched: Analyst role requires administrative approval before exporting leads.',
      });
    } else {
      setEvalResult({
        decision: 'ALLOW',
        matched_policy_id: 'pol_default_allow',
        matched_rule_name: 'Standard Workspace Access',
        reason: 'Action permitted under standard role permissions.',
      });
    }
  };

  const handleMaskData = () => {
    setMaskedOutput({
      email: rawEmail ? rawEmail[0] + '***' + rawEmail.split('@')[0].slice(-1) + '@' + rawEmail.split('@')[1] : '',
      phone: rawPhone ? '+1 ***-***-' + rawPhone.slice(-4) : '',
      salary: '$150,000' ? '$50k - $250k (Confidential)' : '',
    });
  };

  const handleValidateContract = () => {
    try {
      const parsed = JSON.parse(contractPayload);
      setContractValidation({
        is_valid: true,
        is_accepted: true,
        completeness_score: 1.0,
        violations: [],
        freshness_hours: 0.1,
      });
    } catch (e: any) {
      setContractValidation({
        is_valid: false,
        is_accepted: false,
        completeness_score: 0.0,
        violations: ['JSON Parse Error: ' + e.message],
      });
    }
  };

  const handleCheckSuppression = () => {
    if (checkTarget.includes('competitor') || checkTarget.includes('.gov')) {
      setSuppressionResult({
        is_suppressed: true,
        reason: 'Suppressed by rule: Enterprise Competitor Exclusion & Government Domain Policy.',
      });
    } else {
      setSuppressionResult({
        is_suppressed: false,
        reason: 'Target is clean. Allowed for enrichment and research.',
      });
    }
  };

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 6 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
          <PolicyIcon color="primary" sx={{ fontSize: 36 }} />
          <Typography variant="h4" fontWeight={700}>
            Enterprise Governance, Policy Engine & Data Contracts
          </Typography>
          <Chip label="Phase 29 Active" color="primary" variant="outlined" size="small" />
        </Box>
        <Typography variant="body1" color="text.secondary">
          Declarative policy enforcement, field-level PII masking, data producer contracts, global suppression & legal holds.
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
          <Tab icon={<PolicyIcon />} label="Policy Engine" iconPosition="start" />
          <Tab icon={<MaskIcon />} label="Field-Level Masking" iconPosition="start" />
          <Tab icon={<ContractIcon />} label="Data Contracts" iconPosition="start" />
          <Tab icon={<SuppressionIcon />} label="Suppression & Legal Hold" iconPosition="start" />
          <Tab icon={<QuotaIcon />} label="Tenant Quotas & Limits" iconPosition="start" />
        </Tabs>
      </Paper>

      {/* Tab 0: Policy Engine */}
      {activeTab === 0 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={5}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Policy Evaluation Simulator
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Simulate how declarative rules and DSL conditions evaluate access, export, and autonomous actions.
              </Typography>
              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel>Action</InputLabel>
                <Select
                  value={evalAction}
                  label="Action"
                  onChange={(e) => setEvalAction(e.target.value)}
                >
                  <MenuItem value="companies:export">companies:export (Bulk Data Export)</MenuItem>
                  <MenuItem value="contacts:view_pii">contacts:view_pii (View Unmasked PII)</MenuItem>
                  <MenuItem value="research:autonomous_run">research:autonomous_run (Trigger Research)</MenuItem>
                </Select>
              </FormControl>
              <FormControl fullWidth sx={{ mb: 3 }}>
                <InputLabel>Actor Role</InputLabel>
                <Select
                  value={evalRole}
                  label="Actor Role"
                  onChange={(e) => setEvalRole(e.target.value)}
                >
                  <MenuItem value="ADMIN">ADMIN (Workspace Administrator)</MenuItem>
                  <MenuItem value="ANALYST">ANALYST (Lead Intelligence Analyst)</MenuItem>
                  <MenuItem value="VIEWER">VIEWER (Read-Only Auditor)</MenuItem>
                </Select>
              </FormControl>
              <Button
                variant="contained"
                startIcon={<EvaluateIcon />}
                fullWidth
                size="large"
                onClick={handleEvaluatePolicy}
              >
                Evaluate Policy Decision
              </Button>
            </Paper>
          </Grid>

          <Grid item xs={12} md={7}>
            <Paper sx={{ p: 3, bgcolor: '#1a1a2e', color: '#fff', minHeight: 280 }}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Policy Engine Decision Output:
              </Typography>
              <Divider sx={{ bgcolor: '#333', mb: 2 }} />
              {evalResult ? (
                <Box>
                  <Box sx={{ mb: 2 }}>
                    <Chip
                      label={evalResult.decision}
                      color={
                        evalResult.decision === 'ALLOW'
                          ? 'success'
                          : evalResult.decision === 'REQUIRE_APPROVAL'
                          ? 'warning'
                          : 'error'
                      }
                      sx={{ fontWeight: 700 }}
                    />
                  </Box>
                  <Typography variant="body2" sx={{ color: '#aaa', mb: 1 }}>
                    Matched Rule: <strong>{evalResult.matched_rule_name}</strong>
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#ccc' }}>
                    Reason: {evalResult.reason}
                  </Typography>
                </Box>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No evaluation run yet. Select parameters and click evaluate.
                </Typography>
              )}
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* Tab 1: Field Masking */}
      {activeTab === 1 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={5}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Field-Level PII Masking Preview
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Test pseudonymization algorithms on sensitive enterprise contact and financial fields.
              </Typography>
              <TextField
                label="Raw Email"
                fullWidth
                value={rawEmail}
                onChange={(e) => setRawEmail(e.target.value)}
                sx={{ mb: 2 }}
              />
              <TextField
                label="Raw Phone"
                fullWidth
                value={rawPhone}
                onChange={(e) => setRawPhone(e.target.value)}
                sx={{ mb: 3 }}
              />
              <Button
                variant="contained"
                startIcon={<MaskIcon />}
                fullWidth
                onClick={handleMaskData}
              >
                Apply Privacy Mask
              </Button>
            </Paper>
          </Grid>

          <Grid item xs={12} md={7}>
            <Paper sx={{ p: 3, bgcolor: '#111', color: '#00e676', fontFamily: 'monospace' }}>
              <Typography variant="subtitle2" sx={{ color: '#fff', mb: 1, fontFamily: 'sans-serif' }}>
                Masked PII Output:
              </Typography>
              <Divider sx={{ bgcolor: '#333', mb: 2 }} />
              {maskedOutput ? (
                <pre style={{ margin: 0, fontSize: '0.9rem' }}>
                  {JSON.stringify(maskedOutput, null, 2)}
                </pre>
              ) : (
                <Typography variant="body2" sx={{ color: '#888' }}>
                  Click 'Apply Privacy Mask' to inspect transformed output.
                </Typography>
              )}
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* Tab 2: Data Contracts */}
      {activeTab === 2 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Data Producer Contract Validation
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Payloads must satisfy required fields, completeness (&ge; 70%), and freshness SLAs.
              </Typography>
              <TextField
                label="Ingestion Payload (JSON)"
                multiline
                rows={8}
                fullWidth
                value={contractPayload}
                onChange={(e) => setContractPayload(e.target.value)}
                sx={{ mb: 2, fontFamily: 'monospace' }}
              />
              <Button
                variant="contained"
                startIcon={<ContractIcon />}
                fullWidth
                onClick={handleValidateContract}
              >
                Validate Against Company Profile Contract
              </Button>
            </Paper>
          </Grid>

          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3, bgcolor: '#1a1a2e', color: '#fff', minHeight: 300 }}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Contract Validation Results:
              </Typography>
              <Divider sx={{ bgcolor: '#333', mb: 2 }} />
              {contractValidation ? (
                <Box>
                  <Chip
                    label={contractValidation.is_valid ? 'CONTRACT SATISFIED' : 'CONTRACT VIOLATED'}
                    color={contractValidation.is_valid ? 'success' : 'error'}
                    sx={{ fontWeight: 700, mb: 2 }}
                  />
                  <Typography variant="body2" sx={{ mb: 1 }}>
                    Completeness Score: <strong>{(contractValidation.completeness_score * 100).toFixed(0)}%</strong>
                  </Typography>
                  <Typography variant="body2" sx={{ mb: 1 }}>
                    Freshness SLA: <strong>{contractValidation.freshness_hours}h old</strong> (Within 72h limit)
                  </Typography>
                  {contractValidation.violations.length > 0 && (
                    <Box sx={{ mt: 2 }}>
                      <Typography variant="caption" color="error">Violations:</Typography>
                      {contractValidation.violations.map((v: string, i: number) => (
                        <Typography key={i} variant="body2" sx={{ color: '#ff5252' }}>• {v}</Typography>
                      ))}
                    </Box>
                  )}
                </Box>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No contract validation executed yet.
                </Typography>
              )}
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* Tab 3: Suppression & Legal Hold */}
      {activeTab === 3 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card variant="outlined">
              <CardHeader
                avatar={<SuppressionIcon color="error" />}
                title="Global Suppression Verification"
                subheader="Prevent collection, research, or export for blocked domains or entities."
              />
              <Divider />
              <CardContent>
                <TextField
                  label="Domain or Entity to Check"
                  fullWidth
                  value={checkTarget}
                  onChange={(e) => setCheckTarget(e.target.value)}
                  sx={{ mb: 2 }}
                />
                <Button
                  variant="outlined"
                  color="error"
                  fullWidth
                  onClick={handleCheckSuppression}
                >
                  Verify Suppression Status
                </Button>
                {suppressionResult && (
                  <Box sx={{ mt: 2 }}>
                    <Alert severity={suppressionResult.is_suppressed ? 'error' : 'success'}>
                      {suppressionResult.reason}
                    </Alert>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card variant="outlined">
              <CardHeader
                avatar={<LegalHoldIcon color="warning" />}
                title="Active Legal Holds"
                subheader="Locks records under active investigation against deletion or modification."
              />
              <Divider />
              <CardContent>
                <List dense>
                  <ListItem>
                    <ListItemIcon><LegalHoldIcon color="warning" /></ListItemIcon>
                    <ListItemText
                      primary="Case REF-2026-089 (Apex Manufacturing Ltd)"
                      secondary="Placed by Compliance Officer • Immutable lock active"
                    />
                    <Chip label="ACTIVE" color="warning" size="small" />
                  </ListItem>
                  <ListItem>
                    <ListItemIcon><LegalHoldIcon color="warning" /></ListItemIcon>
                    <ListItemText
                      primary="Case REF-2026-104 (Global ERP Partner Audits)"
                      secondary="Placed by General Counsel • 12 records locked"
                    />
                    <Chip label="ACTIVE" color="warning" size="small" />
                  </ListItem>
                </List>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Tab 4: Tenant Quotas */}
      {activeTab === 4 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={4}>
            <Card variant="outlined">
              <CardHeader
                avatar={<QuotaIcon color="primary" />}
                title="Daily Research Spend Budget"
                subheader="Auto-capped to prevent budget overruns"
              />
              <Divider />
              <CardContent>
                <Typography variant="h4" fontWeight={700} color="primary.main">
                  $12.45 / $100.00
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  12.4% consumed today • Resets at 00:00 UTC
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card variant="outlined">
              <CardHeader
                avatar={<QuotaIcon color="secondary" />}
                title="Concurrent Research Runs"
                subheader="System capacity throttle"
              />
              <Divider />
              <CardContent>
                <Typography variant="h4" fontWeight={700} color="secondary.main">
                  1 / 5 Active
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  4 run slots available
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card variant="outlined">
              <CardHeader
                avatar={<QuotaIcon color="success" />}
                title="Monthly Verified Exports"
                subheader="Fair usage export threshold"
              />
              <Divider />
              <CardContent>
                <Typography variant="h4" fontWeight={700} color="success.main">
                  1,840 / 10,000
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  8,160 export records remaining
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
    </Container>
  );
};

