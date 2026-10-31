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
  Archive as ArchiveIcon,
  Layers as TierIcon,
  Restore as RestoreIcon,
  DeleteForever as PurgeIcon,
  Lock as LegalHoldIcon,
  AutoDelete as RetentionIcon,
  CheckCircle as ValidIcon,
  Visibility as ViewIcon,
  Psychology as MemoryIcon
} from '@mui/icons-material';

export const EnterpriseDataLifecycleWorkspace: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);

  // Archive Packages State
  const [packages, setPackages] = useState([
    {
      id: 'pkg_signals_2026_q2_01',
      name: 'Q2 2026 Raw Crawler Signals Archive',
      entity_type: 'RAW_SIGNAL',
      records_count: 84200,
      checksum: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
      storage_uri: 's3://leadnexus-cold-archives/ws_default/pkg_signals_2026_q2_01.json.gz',
      status: 'ACTIVE',
    },
    {
      id: 'pkg_contacts_2026_unverified_01',
      name: 'Unverified Stale Contacts Archive (60d+ Expired)',
      entity_type: 'CONTACT',
      records_count: 1410,
      checksum: 'd41d8cd98f00b204e9800998ecf8427e',
      storage_uri: 's3://leadnexus-cold-archives/ws_default/pkg_contacts_2026_unverified_01.json.gz',
      status: 'ACTIVE',
    },
  ]);

  // Tombstones
  const [tombstones] = useState([
    {
      id: 'ts_001',
      entity_type: 'CONTACT',
      original_entity_id: 'cont_expired_9012',
      archive_package_id: 'pkg_contacts_2026_unverified_01',
      archived_at: '2026-10-30T10:14:00Z',
    },
    {
      id: 'ts_002',
      entity_type: 'RAW_SIGNAL',
      original_entity_id: 'sig_old_crawl_491',
      archive_package_id: 'pkg_signals_2026_q2_01',
      archived_at: '2026-10-31T08:00:00Z',
    },
  ]);

  // AI Cache Purge Feedback
  const [purgeResult, setPurgeResult] = useState<string | null>(null);

  const handlePurgeAICache = () => {
    setPurgeResult('Successfully purged 420 ephemeral conversation turns and 1,840 transient RAG document chunk vectors older than 14 days.');
  };

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 6 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
          <ArchiveIcon color="primary" sx={{ fontSize: 36 }} />
          <Typography variant="h4" fontWeight={700}>
            Enterprise Data Lifecycle, Archival & Retention
          </Typography>
          <Chip label="Phase 32 Active" color="primary" variant="outlined" size="small" />
        </Box>
        <Typography variant="body1" color="text.secondary">
          Tiered storage governance (HOT/WARM/COLD/ARCHIVED), cryptographic archive packages, tombstone tracking, and ephemeral AI memory minimization.
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
          <Tab icon={<TierIcon />} label="Storage Tier Hierarchy" iconPosition="start" />
          <Tab icon={<RetentionIcon />} label="Retention Policies" iconPosition="start" />
          <Tab icon={<ArchiveIcon />} label="Archive Packages" iconPosition="start" />
          <Tab icon={<RestoreIcon />} label="Tombstones & Restoration" iconPosition="start" />
          <Tab icon={<MemoryIcon />} label="Ephemeral AI Memory Hygiene" iconPosition="start" />
        </Tabs>
      </Paper>

      {/* Tab 0: Tier Hierarchy */}
      {activeTab === 0 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={3}>
            <Card variant="outlined">
              <CardHeader
                title="HOT TIER"
                subheader="PostgreSQL & Redis Cache"
                action={<Chip label="Active (< 30d)" color="error" size="small" />}
              />
              <Divider />
              <CardContent>
                <Typography variant="body2" color="text.secondary">
                  Active verified leads, ongoing research runs, real-time qualification scores, high-frequency read/write operations.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={3}>
            <Card variant="outlined">
              <CardHeader
                title="WARM TIER"
                subheader="PostgreSQL Indexed"
                action={<Chip label="Stable (30-90d)" color="warning" size="small" />}
              />
              <Divider />
              <CardContent>
                <Typography variant="body2" color="text.secondary">
                  Established company entities, historical technology signals, decision maker profiles. Infrequent mutation.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={3}>
            <Card variant="outlined">
              <CardHeader
                title="COLD TIER"
                subheader="PostgreSQL Partitioned"
                action={<Chip label="Stale (> 90d)" color="info" size="small" />}
              />
              <Divider />
              <CardContent>
                <Typography variant="body2" color="text.secondary">
                  Read-only archived crawler runs, superseded evidence observations, candidate candidates for S3 archival packaging.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={3}>
            <Card variant="outlined">
              <CardHeader
                title="ARCHIVED TIER"
                subheader="GCS / S3 Compressed"
                action={<Chip label="Cold Manifests" color="success" size="small" />}
              />
              <Divider />
              <CardContent>
                <Typography variant="body2" color="text.secondary">
                  Immutable compressed JSON packages with SHA-256 integrity checksums. Active tables retain lightweight tombstones.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Tab 1: Retention Policies */}
      {activeTab === 1 && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Enterprise Retention SLAs
              </Typography>
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Entity Category</TableCell>
                      <TableCell>Retention SLA</TableCell>
                      <TableCell>Target Tier</TableCell>
                      <TableCell>Legal Hold Exemption</TableCell>
                      <TableCell>Status</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    <TableRow>
                      <TableCell>Audit Logs</TableCell>
                      <TableCell>365 Days</TableCell>
                      <TableCell><Chip label="ARCHIVED" size="small" /></TableCell>
                      <TableCell><Chip icon={<LegalHoldIcon />} label="Exempt if Held" color="warning" size="small" /></TableCell>
                      <TableCell><Chip label="ENFORCED" color="success" size="small" /></TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>Raw Browser Snapshots (HTML)</TableCell>
                      <TableCell>30 Days</TableCell>
                      <TableCell><Chip label="PURGED" size="small" color="error" /></TableCell>
                      <TableCell><Chip icon={<LegalHoldIcon />} label="Exempt if Held" color="warning" size="small" /></TableCell>
                      <TableCell><Chip label="ENFORCED" color="success" size="small" /></TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>Unverified Contact Points</TableCell>
                      <TableCell>60 Days</TableCell>
                      <TableCell><Chip label="ARCHIVED" size="small" /></TableCell>
                      <TableCell><Chip icon={<LegalHoldIcon />} label="Exempt if Held" color="warning" size="small" /></TableCell>
                      <TableCell><Chip label="ENFORCED" color="success" size="small" /></TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* Tab 2: Archive Packages */}
      {activeTab === 2 && (
        <Grid container spacing={3}>
          {packages.map((pkg) => (
            <Grid item xs={12} md={6} key={pkg.id}>
              <Card variant="outlined">
                <CardHeader
                  avatar={<ArchiveIcon color="primary" />}
                  title={<Typography variant="subtitle1" fontWeight={600}>{pkg.name}</Typography>}
                  subheader={`ID: ${pkg.id} • ${pkg.records_count.toLocaleString()} records`}
                  action={<Chip label={pkg.status} color="success" size="small" />}
                />
                <Divider />
                <CardContent>
                  <Typography variant="body2" sx={{ mb: 1 }}>
                    Storage URI: <code>{pkg.storage_uri}</code>
                  </Typography>
                  <Typography variant="caption" sx={{ display: 'block', mb: 2, fontFamily: 'monospace' }}>
                    SHA-256: {pkg.checksum.slice(0, 32)}...
                  </Typography>
                  <Button variant="outlined" size="small" startIcon={<ViewIcon />}>
                    Preview Manifest Records
                  </Button>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Tab 3: Tombstones */}
      {activeTab === 3 && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Active Archive Tombstones
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Tombstones act as lightweight pointer references in active database tables, ensuring graph queries and foreign keys remain unbroken after cold archival.
              </Typography>
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Tombstone ID</TableCell>
                      <TableCell>Entity Type</TableCell>
                      <TableCell>Original Entity ID</TableCell>
                      <TableCell>Archive Package</TableCell>
                      <TableCell>Archived At</TableCell>
                      <TableCell align="right">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {tombstones.map((ts) => (
                      <TableRow key={ts.id}>
                        <TableCell><code>{ts.id}</code></TableCell>
                        <TableCell><Chip label={ts.entity_type} size="small" /></TableCell>
                        <TableCell><code>{ts.original_entity_id}</code></TableCell>
                        <TableCell><code>{ts.archive_package_id}</code></TableCell>
                        <TableCell>{ts.archived_at}</TableCell>
                        <TableCell align="right">
                          <Button size="small" variant="outlined" startIcon={<RestoreIcon />}>
                            Restore to Warm Tier
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* Tab 4: AI Memory Hygiene */}
      {activeTab === 4 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card variant="outlined">
              <CardHeader
                avatar={<MemoryIcon color="secondary" />}
                title="Ephemeral AI Memory & Vector Cache Purge"
                subheader="Minimizes storage footprint and enforces privacy minimization"
              />
              <Divider />
              <CardContent>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  Purges transient chat assistant conversation turns (&gt; 14 days) and temporary RAG chunk embeddings (&gt; 30 days) while strictly preserving canonical research findings and ground truth evidence claims.
                </Typography>
                <Button
                  variant="contained"
                  color="warning"
                  startIcon={<PurgeIcon />}
                  onClick={handlePurgeAICache}
                >
                  Execute Ephemeral AI Purge
                </Button>
                {purgeResult && (
                  <Alert severity="success" sx={{ mt: 2 }}>
                    {purgeResult}
                  </Alert>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
    </Container>
  );
};
