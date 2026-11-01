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
  Hub,
  AccountTree,
  VerifiedUser,
  Storage,
  Search,
  Speed,
  Policy,
  Share,
  Refresh,
  CheckCircle,
  Warning,
  Security,
  CompareArrows,
  Layers,
} from '@mui/icons-material';

interface DataContract {
  id: string;
  domain: string;
  asset_name: string;
  sla_freshness_seconds: number;
  owner_team: string;
  status: string;
  quality_rules_count: number;
}

interface CatalogItem {
  id: string;
  domain: string;
  asset_name: string;
  entity_type: string;
  description: string;
  classification: string;
  owner_email: string;
  tags: string[];
}

interface LineageNode {
  source: string;
  target: string;
  transformation: string;
  source_domain: string;
  target_domain: string;
}

interface CrossDomainRel {
  primary: string;
  related: string;
  type: string;
  confidence: number;
}

interface QualityRadar {
  completeness: number;
  validity: number;
  timeliness: number;
  uniqueness: number;
  overall: number;
}

const DOMAINS = [
  'COMPANIES',
  'PEOPLE',
  'CONTACTS',
  'LEADS',
  'EVIDENCE',
  'SIGNALS',
  'INTENT',
  'RESEARCH',
  'GRAPH',
  'ANALYTICS',
  'WORKFLOWS',
  'MONITORING',
  'INTEGRATIONS',
];

export const EnterpriseDataFabricWorkspace: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Contracts state
  const [contracts, setContracts] = useState<DataContract[]>([
    { id: 'c-1', domain: 'COMPANIES', asset_name: 'canonical_company_master', sla_freshness_seconds: 1800, owner_team: 'Data Core', status: 'ACTIVE', quality_rules_count: 3 },
    { id: 'c-2', domain: 'LEADS', asset_name: 'b2b_saved_leads_v2', sla_freshness_seconds: 900, owner_team: 'Lead Platform', status: 'ACTIVE', quality_rules_count: 4 },
    { id: 'c-3', domain: 'SIGNALS', asset_name: 'realtime_hiring_signals', sla_freshness_seconds: 300, owner_team: 'Signal Engine', status: 'ACTIVE', quality_rules_count: 2 },
    { id: 'c-4', domain: 'INTENT', asset_name: 'topic_surge_scores', sla_freshness_seconds: 3600, owner_team: 'Intelligence AI', status: 'ACTIVE', quality_rules_count: 3 },
  ]);

  // Catalog state
  const [catalogItems, setCatalogItems] = useState<CatalogItem[]>([
    { id: 'cat-1', domain: 'COMPANIES', asset_name: 'canonical_companies', entity_type: 'OrganizationEntity', description: 'Canonical firmographic entity store with domain resolution and revenue bands.', classification: 'INTERNAL', owner_email: 'core_data@infogenx.com', tags: ['canonical', 'firmographics', 'b2b'] },
    { id: 'cat-2', domain: 'PEOPLE', asset_name: 'decision_maker_profiles', entity_type: 'PersonProfile', description: 'Executive and technical decision-maker identities with linked verification states.', classification: 'CONFIDENTIAL', owner_email: 'people_ops@infogenx.com', tags: ['people', 'decision_makers', 'pii'] },
    { id: 'cat-3', domain: 'LEADS', asset_name: 'user_saved_leads', entity_type: 'SavedLeadRecord', description: 'Explicitly saved leads ready for dual UTF-8 BOM CSV and OpenPyXL Excel export.', classification: 'INTERNAL', owner_email: 'leads_team@infogenx.com', tags: ['saved_leads', 'export_ready'] },
    { id: 'cat-4', domain: 'INTENT', asset_name: 'b2b_topic_surges', entity_type: 'IntentSurgeSignal', description: 'Cross-web search surges and buying group evaluation intent indicators.', classification: 'RESTRICTED', owner_email: 'ai_intent@infogenx.com', tags: ['intent', 'surges', 'signals'] },
  ]);

  // Lineage edges
  const [lineageEdges, setLineageEdges] = useState<LineageNode[]>([
    { source: 'SIGNALS::job_feed_crawler', target: 'SIGNALS::hiring_signals_clean', transformation: 'CDC', source_domain: 'SIGNALS', target_domain: 'SIGNALS' },
    { source: 'SIGNALS::hiring_signals_clean', target: 'COMPANIES::canonical_companies', transformation: 'ENRICHMENT', source_domain: 'SIGNALS', target_domain: 'COMPANIES' },
    { source: 'COMPANIES::canonical_companies', target: 'LEADS::user_saved_leads', transformation: 'USER_ADD_ACTION', source_domain: 'COMPANIES', target_domain: 'LEADS' },
    { source: 'LEADS::user_saved_leads', target: 'ANALYTICS::executive_dashboard', transformation: 'AGGREGATION', source_domain: 'LEADS', target_domain: 'ANALYTICS' },
    { source: 'RESEARCH::autonomous_dossier', target: 'EVIDENCE::verified_citations', transformation: 'INFERENCE', source_domain: 'RESEARCH', target_domain: 'EVIDENCE' },
  ]);

  // Cross-Domain relations
  const [relations, setRelations] = useState<CrossDomainRel[]>([
    { primary: 'COMPANIES::infogenx_tech', related: 'PEOPLE::ceo_yasar', type: 'EMPLOYED_AT', confidence: 0.98 },
    { primary: 'PEOPLE::ceo_yasar', related: 'LEADS::lead_8801', type: 'SAVED_LEAD', confidence: 1.0 },
    { primary: 'COMPANIES::infogenx_tech', related: 'INTENT::odoo_migration_surge', type: 'SURFACED_INTENT', confidence: 0.91 },
    { primary: 'LEADS::lead_8801', related: 'WORKFLOWS::export_to_excel', type: 'ENQUEUED_IN', confidence: 1.0 },
  ]);

  // Quality Radar
  const [qualityRadar, setQualityRadar] = useState<QualityRadar>({
    completeness: 97.4,
    validity: 98.8,
    timeliness: 96.2,
    uniqueness: 99.5,
    overall: 97.8,
  });

  // Query console state
  const [selectedDomain, setSelectedDomain] = useState('COMPANIES');
  const [queryEntityId, setQueryEntityId] = useState('cmp-4901');
  const [federatedResult, setFederatedResult] = useState<any>(null);

  const handleExecuteFederatedQuery = () => {
    setFederatedResult({
      domain: selectedDomain,
      entity_id: queryEntityId,
      record: {
        id: queryEntityId,
        name: 'Infogenx Global Enterprise',
        domain: 'infogenx.com',
        primary_contact_email: 'y***r@infogenx.com', // Masked via Policy
        phone: '+1-555-****-91',
        status: 'ACTIVE_VERIFIED',
      },
      policies_enforced: ['PII_EMAIL_MASKING', 'PHONE_REDACTION', 'TENANT_ISOLATION'],
      subgraph: {
        total_connections: 4,
        connected_domains: ['PEOPLE', 'INTENT', 'LEADS', 'WORKFLOWS'],
      },
    });
    setActionSuccess('Federated query dispatched and privacy policies enforced.');
  };

  return (
    <Box sx={{ p: 3, maxWidth: 1400, margin: '0 auto' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" fontWeight="bold" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Hub color="primary" fontSize="large" /> Enterprise Data Fabric
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Phase 39 — Unified Data Contracts, Cross-Domain Catalog, Provenance Lineage, Entity Graph, Quality Radar & Policy Enforcement
          </Typography>
        </Box>
        <Button variant="outlined" startIcon={<Refresh />} onClick={() => setActionSuccess('Synchronized data fabric catalog.')}>
          Refresh Fabric
        </Button>
      </Box>

      {actionSuccess && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={() => setActionSuccess(null)}>
          {actionSuccess}
        </Alert>
      )}

      {/* Domain Breadcrumbs / Chips */}
      <Box sx={{ mb: 2, display: 'flex', gap: 0.8, flexWrap: 'wrap' }}>
        {DOMAINS.map((d) => (
          <Chip
            key={d}
            label={d}
            size="small"
            color={selectedDomain === d ? 'primary' : 'default'}
            onClick={() => setSelectedDomain(d)}
            variant={selectedDomain === d ? 'filled' : 'outlined'}
          />
        ))}
      </Box>

      <Paper sx={{ mb: 3 }}>
        <Tabs value={activeTab} onChange={(_, val) => setActiveTab(val)} variant="scrollable" scrollButtons="auto">
          <Tab icon={<VerifiedUser />} iconPosition="start" label="Data Contracts" />
          <Tab icon={<Storage />} iconPosition="start" label="Catalog & Discovery" />
          <Tab icon={<AccountTree />} iconPosition="start" label="Provenance Lineage" />
          <Tab icon={<Share />} iconPosition="start" label="Cross-Domain Graph" />
          <Tab icon={<Speed />} iconPosition="start" label="Quality & Freshness Radar" />
          <Tab icon={<Policy />} iconPosition="start" label="Federated Access & Policies" />
        </Tabs>
      </Paper>

      {/* TAB 0: DATA CONTRACTS */}
      {activeTab === 0 && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6" fontWeight="bold">
              Active Unified Data Contracts
            </Typography>
            <Button variant="contained" size="small" onClick={() => setActionSuccess('Contract schema validated.')}>
              Validate Contract
            </Button>
          </Box>
          <Grid container spacing={2}>
            {contracts.map((c) => (
              <Grid item xs={12} md={6} key={c.id}>
                <Card sx={{ borderLeft: '4px solid #0284c7' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                      <Typography variant="subtitle1" fontWeight="bold">
                        {c.asset_name}
                      </Typography>
                      <Chip label={c.domain} color="primary" size="small" />
                    </Box>
                    <Typography variant="body2" color="text.secondary">
                      Owner: <b>{c.owner_team}</b>
                    </Typography>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1.5 }}>
                      SLA Freshness: {c.sla_freshness_seconds}s ({c.sla_freshness_seconds / 60} mins)
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      <Chip label={`${c.quality_rules_count} Quality Rules`} size="small" variant="outlined" color="success" />
                      <Chip label={c.status} size="small" color="success" />
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* TAB 1: CATALOG & DISCOVERY */}
      {activeTab === 1 && (
        <Box>
          <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
            <TextField
              fullWidth
              size="small"
              placeholder="Search cross-domain assets, entities, tags, or fields..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              InputProps={{ startAdornment: <Search sx={{ mr: 1, color: 'text.secondary' }} /> }}
            />
          </Box>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow sx={{ backgroundColor: 'action.hover' }}>
                  <TableCell>Domain</TableCell>
                  <TableCell>Asset Name</TableCell>
                  <TableCell>Entity Type</TableCell>
                  <TableCell>Classification</TableCell>
                  <TableCell>Owner</TableCell>
                  <TableCell>Tags</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {catalogItems
                  .filter(
                    (item) =>
                      item.asset_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                      item.description.toLowerCase().includes(searchQuery.toLowerCase())
                  )
                  .map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>
                        <Chip label={item.domain} size="small" color="primary" />
                      </TableCell>
                      <TableCell sx={{ fontWeight: 'bold' }}>{item.asset_name}</TableCell>
                      <TableCell>
                        <code>{item.entity_type}</code>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={item.classification}
                          size="small"
                          color={
                            item.classification === 'RESTRICTED'
                              ? 'error'
                              : item.classification === 'CONFIDENTIAL'
                              ? 'warning'
                              : 'default'
                          }
                        />
                      </TableCell>
                      <TableCell>{item.owner_email}</TableCell>
                      <TableCell>
                        {item.tags.map((t) => (
                          <Chip key={t} label={t} size="small" sx={{ mr: 0.5 }} />
                        ))}
                      </TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}

      {/* TAB 2: PROVENANCE LINEAGE */}
      {activeTab === 2 && (
        <Box>
          <Typography variant="h6" fontWeight="bold" sx={{ mb: 2 }}>
            Data Transformation Lineage (DAG)
          </Typography>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ backgroundColor: 'action.hover' }}>
                  <TableCell>Source Asset</TableCell>
                  <TableCell>Transformation</TableCell>
                  <TableCell>Target Asset</TableCell>
                  <TableCell>Provenance Flow</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {lineageEdges.map((edge, i) => (
                  <TableRow key={i}>
                    <TableCell>
                      <code>{edge.source}</code>
                    </TableCell>
                    <TableCell>
                      <Chip label={edge.transformation} size="small" color="secondary" />
                    </TableCell>
                    <TableCell>
                      <code>{edge.target}</code>
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <Chip label={edge.source_domain} size="small" variant="outlined" />
                        <CompareArrows fontSize="small" color="action" />
                        <Chip label={edge.target_domain} size="small" color="primary" variant="outlined" />
                      </Box>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}

      {/* TAB 3: CROSS-DOMAIN GRAPH */}
      {activeTab === 3 && (
        <Box>
          <Typography variant="h6" fontWeight="bold" sx={{ mb: 2 }}>
            Cross-Domain Semantic Entity Relations
          </Typography>
          <Grid container spacing={2}>
            {relations.map((rel, i) => (
              <Grid item xs={12} md={6} key={i}>
                <Card sx={{ border: '1px solid #e0e0e0' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                      <Chip label={rel.type} color="primary" size="small" />
                      <Chip label={`${(rel.confidence * 100).toFixed(0)}% Confidence`} color="success" size="small" variant="outlined" />
                    </Box>
                    <Typography variant="body2" sx={{ my: 1 }}>
                      <code>{rel.primary}</code>
                    </Typography>
                    <Typography variant="caption" color="text.secondary" display="block">
                      Connects directly to:
                    </Typography>
                    <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                      <code>{rel.related}</code>
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* TAB 4: QUALITY & FRESHNESS RADAR */}
      {activeTab === 4 && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Typography variant="h6" fontWeight="bold">
              Multi-Dimensional Data Quality Radar
            </Typography>
            <Chip label={`Overall Score: ${qualityRadar.overall}%`} color="success" sx={{ fontSize: 14, fontWeight: 'bold' }} />
          </Box>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Card sx={{ p: 2 }}>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  Completeness: {qualityRadar.completeness}%
                </Typography>
                <LinearProgress variant="determinate" value={qualityRadar.completeness} color="primary" sx={{ height: 10, borderRadius: 5, mb: 2 }} />

                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  Validity: {qualityRadar.validity}%
                </Typography>
                <LinearProgress variant="determinate" value={qualityRadar.validity} color="success" sx={{ height: 10, borderRadius: 5, mb: 2 }} />

                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  Timeliness / SLA Freshness: {qualityRadar.timeliness}%
                </Typography>
                <LinearProgress variant="determinate" value={qualityRadar.timeliness} color="info" sx={{ height: 10, borderRadius: 5, mb: 2 }} />

                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  Uniqueness: {qualityRadar.uniqueness}%
                </Typography>
                <LinearProgress variant="determinate" value={qualityRadar.uniqueness} color="secondary" sx={{ height: 10, borderRadius: 5 }} />
              </Card>
            </Grid>

            <Grid item xs={12} md={6}>
              <Card sx={{ p: 2 }}>
                <Typography variant="subtitle2" fontWeight="bold" sx={{ mb: 1 }}>
                  Quality Rule Compliance Summary
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                  All 13 data domains are continuously evaluated against zero-null schema rules, RFC 5322 email patterns, positive numeric ranges, and strict freshness SLAs.
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  <Chip icon={<CheckCircle />} label="Zero PII Leaks" color="success" size="small" />
                  <Chip icon={<CheckCircle />} label="Freshness SLA 99.1% Compliant" color="success" size="small" />
                  <Chip icon={<CheckCircle />} label="No Duplicate Keys" color="success" size="small" />
                </Box>
              </Card>
            </Grid>
          </Grid>
        </Box>
      )}

      {/* TAB 5: FEDERATED ACCESS & POLICIES */}
      {activeTab === 5 && (
        <Box>
          <Typography variant="h6" fontWeight="bold" sx={{ mb: 2 }}>
            Federated Query Console & Privacy Policy Engine
          </Typography>
          <Grid container spacing={3}>
            <Grid item xs={12} md={5}>
              <Card sx={{ p: 2 }}>
                <Typography variant="subtitle2" fontWeight="bold" sx={{ mb: 2 }}>
                  Execute Unified Cross-Domain Query
                </Typography>
                <TextField
                  select
                  fullWidth
                  size="small"
                  label="Target Domain"
                  value={selectedDomain}
                  onChange={(e) => setSelectedDomain(e.target.value)}
                  SelectProps={{ native: true }}
                  sx={{ mb: 2 }}
                >
                  {DOMAINS.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </TextField>
                <TextField
                  fullWidth
                  size="small"
                  label="Entity ID"
                  value={queryEntityId}
                  onChange={(e) => setQueryEntityId(e.target.value)}
                  sx={{ mb: 2 }}
                />
                <Button variant="contained" fullWidth onClick={handleExecuteFederatedQuery}>
                  Execute Federated Query
                </Button>
              </Card>
            </Grid>

            <Grid item xs={12} md={7}>
              {federatedResult ? (
                <Card sx={{ p: 2, bgcolor: '#0f172a', color: '#f8fafc' }}>
                  <Typography variant="subtitle2" fontWeight="bold" sx={{ mb: 1, color: '#38bdf8' }}>
                    Sanitized Result (Policies Applied)
                  </Typography>
                  <Box sx={{ mb: 2 }}>
                    {federatedResult.policies_enforced.map((p: string) => (
                      <Chip key={p} label={p} size="small" color="warning" sx={{ mr: 0.5, mb: 0.5 }} />
                    ))}
                  </Box>
                  <pre style={{ margin: 0, fontSize: 12, overflowX: 'auto', color: '#a5f3fc' }}>
                    {JSON.stringify(federatedResult, null, 2)}
                  </pre>
                </Card>
              ) : (
                <Alert severity="info">
                  Select a domain and entity ID to dispatch a federated query. The policy engine will sanitize PII and resolve stitched relationships automatically.
                </Alert>
              )}
            </Grid>
          </Grid>
        </Box>
      )}
    </Box>
  );
};

export default EnterpriseDataFabricWorkspace;

