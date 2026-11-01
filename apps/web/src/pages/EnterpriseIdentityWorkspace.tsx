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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  LinearProgress,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Security,
  Fingerprint,
  VpnKey,
  Group,
  Sync,
  FlashOn,
  ReportProblem,
  CheckCircle,
  Cancel,
  Delete,
  Refresh,
  Lock,
  ExitToApp,
  Devices,
} from '@mui/icons-material';

interface SSOProvider {
  id: string;
  name: string;
  provider_type: string;
  entity_id_or_issuer: string;
  sso_url: string;
  is_active: boolean;
  jit_provisioning_enabled: boolean;
  default_role: string;
}

interface GroupMapping {
  id: string;
  provider_id: string;
  idp_group_name: string;
  target_role: string;
  is_active: boolean;
}

interface SCIMUser {
  id: string;
  userName: string;
  externalId: string;
  active: boolean;
  name?: { formatted?: string; givenName?: string; familyName?: string };
}

interface JITGrant {
  id: string;
  user_id: string;
  requested_role: string;
  reason: string;
  status: string;
  duration_minutes: number;
  expires_at?: string;
}

interface PAMSession {
  id: string;
  user_id: string;
  ticket_reference: string;
  justification: string;
  status: string;
  duration_minutes: number;
  expires_at: string;
}

interface ReviewCampaign {
  id: string;
  campaign_name: string;
  status: string;
  due_date: string;
}

interface ReviewItem {
  id: string;
  user_email: string;
  assigned_role: string;
  decision: string;
  notes?: string;
}

interface ServiceAccount {
  id: string;
  name: string;
  client_id: string;
  allowed_scopes: string[];
  allowed_ips: string[];
  is_active: boolean;
}

interface UserSession {
  id: string;
  ip_address: string;
  user_agent: string;
  device_info: string;
  is_revoked: boolean;
  last_activity_at: string;
}

export const EnterpriseIdentityWorkspace: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [providers, setProviders] = useState<SSOProvider[]>([
    {
      id: 'sso-1',
      name: 'Okta Enterprise SSO',
      provider_type: 'SAML',
      entity_id_or_issuer: 'http://www.okta.com/exk812903n',
      sso_url: 'https://infogenx.okta.com/app/leadnexus/sso/saml',
      is_active: true,
      jit_provisioning_enabled: true,
      default_role: 'member',
    },
    {
      id: 'sso-2',
      name: 'Azure AD / Entra ID',
      provider_type: 'OIDC',
      entity_id_or_issuer: 'https://login.microsoftonline.com/tenant-guid/v2.0',
      sso_url: 'https://login.microsoftonline.com/tenant-guid/oauth2/v2.0/authorize',
      is_active: true,
      jit_provisioning_enabled: true,
      default_role: 'viewer',
    },
  ]);

  const [mappings, setMappings] = useState<GroupMapping[]>([
    { id: 'm-1', provider_id: 'sso-1', idp_group_name: 'LeadNexus-SuperAdmins', target_role: 'admin', is_active: true },
    { id: 'm-2', provider_id: 'sso-1', idp_group_name: 'Data-Research-Team', target_role: 'analyst', is_active: true },
    { id: 'm-3', provider_id: 'sso-2', idp_group_name: 'Enterprise-Employees', target_role: 'viewer', is_active: true },
  ]);

  const [scimUsers, setScimUsers] = useState<SCIMUser[]>([
    { id: 'usr-1', userName: 'alex.rivera@enterprise.com', externalId: 'ext-8812', active: true, name: { formatted: 'Alex Rivera' } },
    { id: 'usr-2', userName: 'samantha.reed@enterprise.com', externalId: 'ext-9104', active: true, name: { formatted: 'Samantha Reed' } },
    { id: 'usr-3', userName: 'marcus.vance@enterprise.com', externalId: 'ext-4091', active: false, name: { formatted: 'Marcus Vance' } },
  ]);

  const [jitGrants, setJitGrants] = useState<JITGrant[]>([
    { id: 'jit-1', user_id: 'usr-1', requested_role: 'admin', reason: 'Conduct emergency forensic audit on export quotas', status: 'PENDING', duration_minutes: 60 },
    { id: 'jit-2', user_id: 'usr-2', requested_role: 'admin', reason: 'Re-index search vector indices', status: 'APPROVED', duration_minutes: 120, expires_at: new Date(Date.now() + 3600000).toISOString() },
  ]);

  const [pamSessions, setPamSessions] = useState<PAMSession[]>([
    {
      id: 'pam-1',
      user_id: 'admin@leadnexus.io',
      ticket_reference: 'INC-88910',
      justification: 'Production PostgreSQL connection pool remediation',
      status: 'ACTIVE',
      duration_minutes: 45,
      expires_at: new Date(Date.now() + 1800000).toISOString(),
    },
  ]);

  const [campaigns, setCampaigns] = useState<ReviewCampaign[]>([
    { id: 'camp-1', campaign_name: 'Q4 Enterprise Access Certification', status: 'ACTIVE', due_date: '2026-11-15' },
  ]);

  const [reviewItems, setReviewItems] = useState<ReviewItem[]>([
    { id: 'rev-1', user_email: 'alex.rivera@enterprise.com', assigned_role: 'admin', decision: 'PENDING' },
    { id: 'rev-2', user_email: 'samantha.reed@enterprise.com', assigned_role: 'analyst', decision: 'APPROVED', notes: 'Confirmed quarterly project assignment' },
    { id: 'rev-3', user_email: 'marcus.vance@enterprise.com', assigned_role: 'member', decision: 'REVOKED', notes: 'Departed department' },
  ]);

  const [serviceAccounts, setServiceAccounts] = useState<ServiceAccount[]>([
    { id: 'sa-1', name: 'Datadog Ingestion Daemon', client_id: 'lnx_svc_a81f90b', allowed_scopes: ['leads:read', 'metrics:read'], allowed_ips: ['198.51.100.0/24'], is_active: true },
    { id: 'sa-2', name: 'Salesforce Sync Worker', client_id: 'lnx_svc_7c01ee4', allowed_scopes: ['leads:export', 'contacts:read'], allowed_ips: ['52.88.0.0/16'], is_active: true },
  ]);

  const [sessions, setSessions] = useState<UserSession[]>([
    { id: 'sess-1', ip_address: '198.51.100.22', user_agent: 'Chrome 120 (Windows)', device_info: 'Desktop (Chrome)', is_revoked: false, last_activity_at: 'Just now' },
    { id: 'sess-2', ip_address: '203.0.113.88', user_agent: 'Safari (macOS)', device_info: 'Desktop (Safari)', is_revoked: false, last_activity_at: '22 minutes ago' },
  ]);

  // Dialog States
  const [openProviderModal, setOpenProviderModal] = useState(false);
  const [openJitModal, setOpenJitModal] = useState(false);
  const [openPamModal, setOpenPamModal] = useState(false);
  const [openSAModal, setOpenSAModal] = useState(false);
  const [newJitRole, setNewJitRole] = useState('admin');
  const [newJitReason, setNewJitReason] = useState('');
  const [newPamTicket, setNewPamTicket] = useState('');
  const [newPamJustification, setNewPamJustification] = useState('');
  const [newSAName, setNewSAName] = useState('');
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const handleApproveJit = (id: string) => {
    setJitGrants((prev) =>
      prev.map((g) => (g.id === id ? { ...g, status: 'APPROVED', expires_at: new Date(Date.now() + 3600000).toISOString() } : g))
    );
    setActionSuccess('JIT Access request approved with 1-hour expiration.');
  };

  const handleTerminatePam = (id: string) => {
    setPamSessions((prev) => prev.map((p) => (p.id === id ? { ...p, status: 'TERMINATED' } : p)));
    setActionSuccess('Emergency Break-Glass PAM session terminated immediately.');
  };

  const handleReviewDecision = (id: string, decision: 'APPROVED' | 'REVOKED') => {
    setReviewItems((prev) => prev.map((item) => (item.id === id ? { ...item, decision } : item)));
    setActionSuccess(`Access certification decision recorded: ${decision}`);
  };

  const handleRevokeSession = (id: string) => {
    setSessions((prev) => prev.filter((s) => s.id !== id));
    setActionSuccess('Session remotely terminated.');
  };

  const handleRevokeAllSessions = () => {
    setSessions([]);
    setActionSuccess('Emergency Kill-Switch triggered: All active sessions terminated.');
  };

  return (
    <Box sx={{ p: 3, maxWidth: 1400, margin: '0 auto' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" fontWeight="bold" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Fingerprint color="primary" fontSize="large" /> Enterprise Identity & Workforce Access
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Phase 38 — SAML 2.0 / OIDC SSO, SCIM 2.0 Directory Sync, JIT Privilege Elevation, PAM Break-Glass, Access Reviews & Session Controls
          </Typography>
        </Box>
        <Button variant="outlined" startIcon={<Refresh />} onClick={() => setActionSuccess('Synchronized identity telemetry.')}>
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
          <Tab icon={<Security />} iconPosition="start" label="SSO & IdP Config" />
          <Tab icon={<Sync />} iconPosition="start" label="SCIM 2.0 Directory" />
          <Tab icon={<FlashOn />} iconPosition="start" label="JIT & PAM Privileged Access" />
          <Tab icon={<CheckCircle />} iconPosition="start" label="Access Certification" />
          <Tab icon={<VpnKey />} iconPosition="start" label="Service & Machine Identities" />
          <Tab icon={<Devices />} iconPosition="start" label="Session Posture & Revocation" />
        </Tabs>
      </Paper>

      {/* TAB 0: SSO & IdP CONFIGURATION */}
      {activeTab === 0 && (
        <Box>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Typography variant="h6" fontWeight="bold" sx={{ mb: 2 }}>
                Configured Identity Providers
              </Typography>
              {providers.map((p) => (
                <Card key={p.id} sx={{ mb: 2, borderLeft: '4px solid #1976d2' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                      <Typography variant="subtitle1" fontWeight="bold">
                        {p.name}
                      </Typography>
                      <Chip label={p.provider_type} color={p.provider_type === 'SAML' ? 'primary' : 'secondary'} size="small" />
                    </Box>
                    <Typography variant="caption" color="text.secondary" display="block">
                      Entity ID / Issuer: {p.entity_id_or_issuer}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1.5 }}>
                      SSO Endpoint: {p.sso_url}
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      <Chip label={p.jit_provisioning_enabled ? 'JIT Provisioning Enabled' : 'Manual Provisioning'} size="small" variant="outlined" />
                      <Chip label={`Default Role: ${p.default_role}`} size="small" variant="outlined" />
                    </Box>
                  </CardContent>
                </Card>
              ))}
              <Button variant="contained" startIcon={<Lock />} onClick={() => setOpenProviderModal(true)}>
                Add Enterprise IdP
              </Button>
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography variant="h6" fontWeight="bold" sx={{ mb: 2 }}>
                IdP Group → Workspace Role Mappings
              </Typography>
              <TableContainer component={Paper}>
                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ backgroundColor: 'action.hover' }}>
                      <TableCell>IdP Group Name</TableCell>
                      <TableCell>Mapped Role</TableCell>
                      <TableCell>Status</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {mappings.map((m) => (
                      <TableRow key={m.id}>
                        <TableCell>
                          <code>{m.idp_group_name}</code>
                        </TableCell>
                        <TableCell>
                          <Chip label={m.target_role.toUpperCase()} color="primary" size="small" />
                        </TableCell>
                        <TableCell>
                          <Chip label="ACTIVE" color="success" size="small" />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
              <Box sx={{ mt: 2, p: 2, bgcolor: 'background.paper', borderRadius: 1, border: '1px solid #e0e0e0' }}>
                <Typography variant="subtitle2" fontWeight="bold">
                  SAML Service Provider Metadata
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  ACS URL: <code>https://api.leadnexus.infogenx.com/api/v1/identity/sso/saml/consume</code>
                </Typography>
              </Box>
            </Grid>
          </Grid>
        </Box>
      )}

      {/* TAB 1: SCIM 2.0 DIRECTORY SYNC */}
      {activeTab === 1 && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6" fontWeight="bold">
              SCIM 2.0 Provisioned Users Directory
            </Typography>
            <Chip icon={<Sync />} label="SCIM 2.0 Protocol Compliant (RFC 7643 / 7644)" color="success" variant="outlined" />
          </Box>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow sx={{ backgroundColor: 'action.hover' }}>
                  <TableCell>Full Name</TableCell>
                  <TableCell>SCIM Username / Email</TableCell>
                  <TableCell>External ID</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {scimUsers.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell sx={{ fontWeight: 'medium' }}>{u.name?.formatted || 'Enterprise User'}</TableCell>
                    <TableCell>{u.userName}</TableCell>
                    <TableCell>
                      <code>{u.externalId}</code>
                    </TableCell>
                    <TableCell>
                      <Chip label={u.active ? 'ACTIVE' : 'DEPROVISIONED'} color={u.active ? 'success' : 'default'} size="small" />
                    </TableCell>
                    <TableCell>
                      {u.active ? (
                        <Button
                          size="small"
                          color="error"
                          variant="outlined"
                          onClick={() => {
                            setScimUsers((prev) => prev.map((item) => (item.id === u.id ? { ...item, active: false } : item)));
                            setActionSuccess(`User ${u.userName} deprovisioned via SCIM.`);
                          }}
                        >
                          Deprovision
                        </Button>
                      ) : (
                        <Button
                          size="small"
                          color="primary"
                          variant="outlined"
                          onClick={() => {
                            setScimUsers((prev) => prev.map((item) => (item.id === u.id ? { ...item, active: true } : item)));
                            setActionSuccess(`User ${u.userName} re-provisioned.`);
                          }}
                        >
                          Reactivate
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}

      {/* TAB 2: JIT & PAM PRIVILEGED ACCESS */}
      {activeTab === 2 && (
        <Box>
          <Grid container spacing={3}>
            {/* JIT Elevation Requests */}
            <Grid item xs={12} md={7}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6" fontWeight="bold">
                  Just-In-Time (JIT) Ephemeral Elevations
                </Typography>
                <Button variant="contained" size="small" startIcon={<FlashOn />} onClick={() => setOpenJitModal(true)}>
                  Request JIT Access
                </Button>
              </Box>
              <TableContainer component={Paper}>
                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ backgroundColor: 'action.hover' }}>
                      <TableCell>User</TableCell>
                      <TableCell>Role</TableCell>
                      <TableCell>Reason</TableCell>
                      <TableCell>Duration</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Action</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {jitGrants.map((g) => (
                      <TableRow key={g.id}>
                        <TableCell>{g.user_id}</TableCell>
                        <TableCell>
                          <Chip label={g.requested_role.toUpperCase()} color="warning" size="small" />
                        </TableCell>
                        <TableCell sx={{ maxWidth: 200 }}>
                          <Typography variant="caption" noWrap>
                            {g.reason}
                          </Typography>
                        </TableCell>
                        <TableCell>{g.duration_minutes}m</TableCell>
                        <TableCell>
                          <Chip
                            label={g.status}
                            color={g.status === 'APPROVED' ? 'success' : g.status === 'PENDING' ? 'warning' : 'default'}
                            size="small"
                          />
                        </TableCell>
                        <TableCell>
                          {g.status === 'PENDING' && (
                            <Button size="small" variant="contained" color="success" onClick={() => handleApproveJit(g.id)}>
                              Approve
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Grid>

            {/* PAM Break-Glass */}
            <Grid item xs={12} md={5}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6" fontWeight="bold" color="error" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <ReportProblem /> PAM Break-Glass Emergency
                </Typography>
                <Button variant="contained" color="error" size="small" onClick={() => setOpenPamModal(true)}>
                  Break-Glass
                </Button>
              </Box>
              {pamSessions.map((pam) => (
                <Card key={pam.id} sx={{ mb: 2, border: '2px solid #d32f2f', bgcolor: '#fffbfa' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                      <Typography variant="subtitle1" fontWeight="bold" color="error">
                        {pam.ticket_reference}
                      </Typography>
                      <Chip label={pam.status} color={pam.status === 'ACTIVE' ? 'error' : 'default'} size="small" />
                    </Box>
                    <Typography variant="body2" sx={{ mb: 1 }}>
                      {pam.justification}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 2 }}>
                      Expires: {new Date(pam.expires_at).toLocaleTimeString()} ({pam.duration_minutes} min limit)
                    </Typography>
                    {pam.status === 'ACTIVE' && (
                      <Button variant="outlined" color="error" size="small" onClick={() => handleTerminatePam(pam.id)}>
                        Terminate Session
                      </Button>
                    )}
                  </CardContent>
                </Card>
              ))}
            </Grid>
          </Grid>
        </Box>
      )}

      {/* TAB 3: ACCESS CERTIFICATION CAMPAIGNS */}
      {activeTab === 3 && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Box>
              <Typography variant="h6" fontWeight="bold">
                {campaigns[0].campaign_name}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Periodic user entitlement review and principle of least privilege enforcement.
              </Typography>
            </Box>
            <Chip label="DUE IN 14 DAYS" color="primary" />
          </Box>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow sx={{ backgroundColor: 'action.hover' }}>
                  <TableCell>User Email</TableCell>
                  <TableCell>Assigned Role</TableCell>
                  <TableCell>Certification Status</TableCell>
                  <TableCell>Reviewer Action</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {reviewItems.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell sx={{ fontWeight: 'medium' }}>{item.user_email}</TableCell>
                    <TableCell>
                      <Chip label={item.assigned_role.toUpperCase()} size="small" />
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={item.decision}
                        color={item.decision === 'APPROVED' ? 'success' : item.decision === 'REVOKED' ? 'error' : 'warning'}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        <Button
                          size="small"
                          color="success"
                          variant={item.decision === 'APPROVED' ? 'contained' : 'outlined'}
                          onClick={() => handleReviewDecision(item.id, 'APPROVED')}
                        >
                          Certify
                        </Button>
                        <Button
                          size="small"
                          color="error"
                          variant={item.decision === 'REVOKED' ? 'contained' : 'outlined'}
                          onClick={() => handleReviewDecision(item.id, 'REVOKED')}
                        >
                          Revoke
                        </Button>
                      </Box>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}

      {/* TAB 4: SERVICE & MACHINE IDENTITIES */}
      {activeTab === 4 && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6" fontWeight="bold">
              Machine-to-Machine (M2M) Service Accounts
            </Typography>
            <Button variant="contained" startIcon={<VpnKey />} onClick={() => setOpenSAModal(true)}>
              Issue Service Credentials
            </Button>
          </Box>
          <Grid container spacing={2}>
            {serviceAccounts.map((sa) => (
              <Grid item xs={12} md={6} key={sa.id}>
                <Card sx={{ borderLeft: '4px solid #4caf50' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                      <Typography variant="subtitle1" fontWeight="bold">
                        {sa.name}
                      </Typography>
                      <Chip label="ACTIVE" color="success" size="small" />
                    </Box>
                    <Typography variant="caption" color="text.secondary" display="block">
                      Client ID: <code>{sa.client_id}</code>
                    </Typography>
                    <Box sx={{ mt: 1, mb: 1 }}>
                      <Typography variant="caption" fontWeight="bold" display="block">
                        Scopes:
                      </Typography>
                      {sa.allowed_scopes.map((sc) => (
                        <Chip key={sc} label={sc} size="small" sx={{ mr: 0.5, mt: 0.5 }} />
                      ))}
                    </Box>
                    <Box>
                      <Typography variant="caption" fontWeight="bold" display="block">
                        Allowed IPs:
                      </Typography>
                      {sa.allowed_ips.map((ip) => (
                        <Chip key={ip} label={ip} size="small" variant="outlined" sx={{ mr: 0.5, mt: 0.5 }} />
                      ))}
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* TAB 5: SESSION POSTURE & REVOCATION */}
      {activeTab === 5 && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6" fontWeight="bold">
              Active User Sessions & Device Posture
            </Typography>
            <Button variant="contained" color="error" startIcon={<ExitToApp />} onClick={handleRevokeAllSessions}>
              Revoke All Sessions
            </Button>
          </Box>
          <Grid container spacing={2}>
            {sessions.map((s) => (
              <Grid item xs={12} md={6} key={s.id}>
                <Card>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                      <Typography variant="subtitle1" fontWeight="bold">
                        {s.device_info}
                      </Typography>
                      <Chip label="ACTIVE" color="success" size="small" />
                    </Box>
                    <Typography variant="body2" color="text.secondary">
                      IP Address: <code>{s.ip_address}</code>
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Last Active: {s.last_activity_at}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
                      {s.user_agent}
                    </Typography>
                    <Box sx={{ mt: 2 }}>
                      <Button size="small" color="error" variant="outlined" onClick={() => handleRevokeSession(s.id)}>
                        Kill Session
                      </Button>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* JIT Modal */}
      <Dialog open={openJitModal} onClose={() => setOpenJitModal(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Request Just-In-Time Role Elevation</DialogTitle>
        <DialogContent>
          <FormControl fullWidth sx={{ mt: 2, mb: 2 }}>
            <InputLabel>Target Role</InputLabel>
            <Select value={newJitRole} label="Target Role" onChange={(e) => setNewJitRole(e.target.value)}>
              <MenuItem value="admin">Administrator (Full Access)</MenuItem>
              <MenuItem value="analyst">Analyst (Export & Intel)</MenuItem>
            </Select>
          </FormControl>
          <TextField
            fullWidth
            label="Business Justification"
            multiline
            rows={3}
            value={newJitReason}
            onChange={(e) => setNewJitReason(e.target.value)}
            placeholder="Explain why temporary elevated permissions are required..."
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenJitModal(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={() => {
              setJitGrants((prev) => [
                ...prev,
                { id: `jit-${Date.now()}`, user_id: 'current-user', requested_role: newJitRole, reason: newJitReason, status: 'PENDING', duration_minutes: 60 },
              ]);
              setOpenJitModal(false);
              setActionSuccess('JIT elevation request submitted.');
            }}
          >
            Submit Request
          </Button>
        </DialogActions>
      </Dialog>

      {/* PAM Break-Glass Modal */}
      <Dialog open={openPamModal} onClose={() => setOpenPamModal(false)} maxWidth="sm" fullWidth>
        <DialogTitle color="error">Activate Emergency Break-Glass PAM</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mt: 1, mb: 2 }}>
            Emergency Break-Glass bypasses typical approvals. High-severity audit logs will be permanently recorded and broadcast to security leads.
          </Alert>
          <TextField
            fullWidth
            label="Incident / Ticket Reference (e.g. INC-9102)"
            value={newPamTicket}
            onChange={(e) => setNewPamTicket(e.target.value)}
            sx={{ mb: 2 }}
          />
          <TextField
            fullWidth
            label="Root Cause & Emergency Justification"
            multiline
            rows={3}
            value={newPamJustification}
            onChange={(e) => setNewPamJustification(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenPamModal(false)}>Cancel</Button>
          <Button
            variant="contained"
            color="error"
            onClick={() => {
              setPamSessions((prev) => [
                ...prev,
                {
                  id: `pam-${Date.now()}`,
                  user_id: 'admin@leadnexus.io',
                  ticket_reference: newPamTicket || 'INC-EMERGENCY',
                  justification: newPamJustification || 'Urgent outage response',
                  status: 'ACTIVE',
                  duration_minutes: 30,
                  expires_at: new Date(Date.now() + 1800000).toISOString(),
                },
              ]);
              setOpenPamModal(false);
              setActionSuccess('PAM Emergency Break-Glass activated.');
            }}
          >
            Confirm Break-Glass
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default EnterpriseIdentityWorkspace;
