import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Tabs,
  Tab,
  Paper,
  Grid,
  Card,
  CardContent,
  CardHeader,
  Button,
  TextField,
  Chip,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  CircularProgress,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon
} from '@mui/material';
import {
  AccountTree as OntologyIcon,
  Search as SearchIcon,
  Rule as ValidationIcon,
  FactCheck as ProposalIcon,
  Article as ArticleIcon,
  Security as SecurityIcon,
  CheckCircle as ApprovedIcon,
  ErrorOutline as ErrorIcon,
  WarningAmber as WarningIcon,
  Refresh as RefreshIcon,
  PlayArrow as ExecuteIcon
} from '@mui/icons-material';

interface ConceptItem {
  id: string;
  canonical_name: string;
  display_name: string;
  ontology_type: string;
  version: string;
  status: string;
  confidence: number;
  alias_count: number;
}

interface ProposalItem {
  id: string;
  title: string;
  proposal_type: string;
  status: string;
  proposed_by: string;
  created_at: string;
}

interface ValidationErrorItem {
  error_code: string;
  severity: string;
  message: string;
  details: any;
}

export const KnowledgeOntologyWorkspace: React.FC = () => {
  const [activeTab, setActiveTab] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [concepts, setConcepts] = useState<ConceptItem[]>([]);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [proposals, setProposals] = useState<ProposalItem[]>([]);
  const [validationErrors, setValidationErrors] = useState<ValidationErrorItem[]>([]);
  const [dslQuery, setDslQuery] = useState<string>("technology = 'ODOO' AND industry = 'RETAIL'");
  const [dslResults, setDslResults] = useState<any>(null);
  const [contextPreview, setContextPreview] = useState<any>(null);
  const [alertMsg, setAlertMsg] = useState<{ text: string; severity: 'success' | 'error' | 'info' | 'warning' } | null>(null);

  // Fetch initial concepts
  const fetchConcepts = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/ontology/concepts?limit=50');
      if (res.ok) {
        const data = await res.json();
        setConcepts(data);
      }
    } catch (err) {
      console.error('Error fetching concepts:', err);
    } finally {
      setLoading(false);
    }
  };

  // Fetch proposals
  const fetchProposals = async () => {
    try {
      const res = await fetch('/api/v1/ontology/proposals');
      if (res.ok) {
        const data = await res.json();
        setProposals(data);
      }
    } catch (err) {
      console.error('Error fetching proposals:', err);
    }
  };

  // Run validation
  const runValidation = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/ontology/validation');
      if (res.ok) {
        const data = await res.json();
        setValidationErrors(data.errors || []);
        setAlertMsg({ text: `Validation completed: ${data.total_errors} issues detected.`, severity: data.total_errors === 0 ? 'success' : 'warning' });
      }
    } catch (err) {
      console.error('Validation failed:', err);
      setAlertMsg({ text: 'Failed to run validation.', severity: 'error' });
    } finally {
      setLoading(false);
    }
  };

  // Execute Semantic Query DSL
  const handleExecuteDSL = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/ontology/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dsl_query: dslQuery, limit: 25 })
      });
      const data = await res.json();
      if (res.ok) {
        setDslResults(data);
        setAlertMsg({ text: `DSL Query executed in ${data.execution_time_ms}ms (${data.result_count} records).`, severity: 'success' });
      } else {
        setAlertMsg({ text: data.detail || 'DSL syntax error', severity: 'error' });
      }
    } catch (err) {
      setAlertMsg({ text: 'Error connecting to Semantic Query service.', severity: 'error' });
    } finally {
      setLoading(false);
    }
  };

  // Seed Taxonomies
  const handleSeedTaxonomies = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/ontology/seed', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setAlertMsg({ text: `Taxonomies successfully seeded! (${data.counts.concepts} concepts created).`, severity: 'success' });
        fetchConcepts();
      }
    } catch (err) {
      setAlertMsg({ text: 'Failed to seed standard taxonomies.', severity: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConcepts();
    fetchProposals();
  }, []);

  return (
    <Container maxWidth="xl" sx={{ mt: 3, mb: 4 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box>
          <Typography variant="h4" fontWeight={700} color="primary" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <OntologyIcon fontSize="large" /> Semantic Ontology & Knowledge Management
          </Typography>
          <Typography variant="subtitle1" color="text.secondary">
            Formal semantic classification, taxonomy governance, evidence grounding, and secure AI context assembly.
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button variant="outlined" startIcon={<RefreshIcon />} onClick={fetchConcepts} disabled={loading}>
            Refresh
          </Button>
          <Button variant="contained" color="secondary" onClick={handleSeedTaxonomies} disabled={loading}>
            Seed Taxonomies
          </Button>
        </Box>
      </Box>

      {alertMsg && (
        <Alert severity={alertMsg.severity} sx={{ mb: 2 }} onClose={() => setAlertMsg(null)}>
          {alertMsg.text}
        </Alert>
      )}

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs value={activeTab} onChange={(_, val) => setActiveTab(val)} indicatorColor="primary" textColor="primary" variant="scrollable">
          <Tab icon={<OntologyIcon />} label="Concept Registry" />
          <Tab icon={<ProposalIcon />} label="Governance & Proposals" />
          <Tab icon={<ValidationIcon />} label="Ontology Validation" />
          <Tab icon={<SearchIcon />} label="Semantic Query DSL" />
          <Tab icon={<SecurityIcon />} label="AI Context Assembly" />
          <Tab icon={<ArticleIcon />} label="Knowledge Articles" />
        </Tabs>
      </Paper>

      {/* Tab 0: Concept Registry */}
      {activeTab === 0 && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Card>
              <CardHeader
                title="Canonical Concept Explorer"
                subheader="Canonical concepts normalized across public web evidence sources (PostgreSQL canonical store)."
                action={
                  <TextField
                    size="small"
                    placeholder="Search canonical name..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                }
              />
              <Divider />
              <CardContent sx={{ p: 0 }}>
                {loading ? (
                  <Box sx={{ p: 4, textAlign: 'center' }}><CircularProgress /></Box>
                ) : (
                  <Table size="small">
                    <TableHead sx={{ backgroundColor: 'action.hover' }}>
                      <TableRow>
                        <TableCell><strong>Canonical Name</strong></TableCell>
                        <TableCell><strong>Display Name</strong></TableCell>
                        <TableCell><strong>Ontology Type</strong></TableCell>
                        <TableCell><strong>Version</strong></TableCell>
                        <TableCell><strong>Status</strong></TableCell>
                        <TableCell><strong>Aliases</strong></TableCell>
                        <TableCell><strong>Confidence</strong></TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {concepts
                        .filter(c => c.canonical_name.toLowerCase().includes(searchQuery.toLowerCase()))
                        .map((c) => (
                          <TableRow key={c.id} hover>
                            <TableCell><Typography fontWeight={600}>{c.canonical_name}</Typography></TableCell>
                            <TableCell>{c.display_name}</TableCell>
                            <TableCell>
                              <Chip size="small" label={c.ontology_type} color="primary" variant="outlined" />
                            </TableCell>
                            <TableCell><Chip size="small" label={c.version} /></TableCell>
                            <TableCell>
                              <Chip
                                size="small"
                                label={c.status}
                                color={c.status === 'PUBLISHED' ? 'success' : 'default'}
                              />
                            </TableCell>
                            <TableCell>{c.alias_count} aliases</TableCell>
                            <TableCell>{(c.confidence * 100).toFixed(0)}%</TableCell>
                          </TableRow>
                        ))}
                      {concepts.length === 0 && (
                        <TableRow>
                          <TableCell colSpan={7} sx={{ textAlign: 'center', py: 3 }}>
                            No canonical concepts found. Click 'Seed Taxonomies' to initialize.
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Tab 1: Governance & Proposals */}
      {activeTab === 1 && (
        <Card>
          <CardHeader
            title="Taxonomy Change Proposals & Reviews"
            subheader="Human-in-the-loop workflow governing concept creations, merges, deprecations, and aliases."
          />
          <Divider />
          <CardContent sx={{ p: 0 }}>
            <Table size="small">
              <TableHead sx={{ backgroundColor: 'action.hover' }}>
                <TableRow>
                  <TableCell><strong>Proposal Title</strong></TableCell>
                  <TableCell><strong>Type</strong></TableCell>
                  <TableCell><strong>Status</strong></TableCell>
                  <TableCell><strong>Proposed By</strong></TableCell>
                  <TableCell><strong>Submitted At</strong></TableCell>
                  <TableCell><strong>Actions</strong></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {proposals.map((p) => (
                  <TableRow key={p.id} hover>
                    <TableCell><Typography fontWeight={600}>{p.title}</Typography></TableCell>
                    <TableCell><Chip size="small" label={p.proposal_type} /></TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={p.status}
                        color={p.status === 'APPROVED' || p.status === 'APPLIED' ? 'success' : p.status === 'REJECTED' ? 'error' : 'warning'}
                      />
                    </TableCell>
                    <TableCell>{p.proposed_by}</TableCell>
                    <TableCell>{new Date(p.created_at).toLocaleDateString()}</TableCell>
                    <TableCell>
                      <Button size="small" variant="text" color="primary">Review</Button>
                    </TableCell>
                  </TableRow>
                ))}
                {proposals.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} sx={{ textAlign: 'center', py: 3 }}>
                      No active proposals pending review.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Tab 2: Ontology Validation */}
      {activeTab === 2 && (
        <Card>
          <CardHeader
            title="Ontology Integrity & Validation Dashboard"
            subheader="Automated verification of cycle absence, parent hierarchy validity, and alias collisions."
            action={
              <Button variant="contained" color="warning" startIcon={<ValidationIcon />} onClick={runValidation} disabled={loading}>
                Run Validation Scan
              </Button>
            }
          />
          <Divider />
          <CardContent>
            {validationErrors.length === 0 ? (
              <Box sx={{ textAlign: 'center', py: 4 }}>
                <ApprovedIcon color="success" sx={{ fontSize: 48, mb: 1 }} />
                <Typography variant="h6">Ontology Graph is Valid & Consistent</Typography>
                <Typography variant="body2" color="text.secondary">
                  Zero circular loops or invalid parent relationships detected in current workspace.
                </Typography>
              </Box>
            ) : (
              <List>
                {validationErrors.map((err, idx) => (
                  <ListItem key={idx} divider>
                    <ListItemIcon>
                      <ErrorIcon color={err.severity === 'ERROR' ? 'error' : 'warning'} />
                    </ListItemIcon>
                    <ListItemText
                      primary={<Typography fontWeight={600}>{err.error_code}: {err.message}</Typography>}
                      secondary={JSON.stringify(err.details)}
                    />
                  </ListItem>
                ))}
              </List>
            )}
          </CardContent>
        </Card>
      )}

      {/* Tab 3: Semantic Query DSL */}
      {activeTab === 3 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card>
              <CardHeader
                title="Safe Semantic Query Builder"
                subheader="Construct controlled semantic searches without raw SQL injection."
              />
              <CardContent>
                <TextField
                  fullWidth
                  multiline
                  rows={4}
                  label="Semantic DSL Statement"
                  value={dslQuery}
                  onChange={(e) => setDslQuery(e.target.value)}
                  sx={{ mb: 2 }}
                />
                <Button
                  variant="contained"
                  color="primary"
                  startIcon={<ExecuteIcon />}
                  onClick={handleExecuteDSL}
                  disabled={loading}
                >
                  Execute Query
                </Button>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={6}>
            <Card>
              <CardHeader title="Query Results & Execution Plan" />
              <CardContent>
                {dslResults ? (
                  <Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      Matches: <strong>{dslResults.result_count}</strong> | Latency: <strong>{dslResults.execution_time_ms}ms</strong>
                    </Typography>
                    <Paper variant="outlined" sx={{ p: 1, maxHeight: 300, overflow: 'auto', backgroundColor: '#fcfcfc' }}>
                      <pre style={{ margin: 0, fontSize: 12 }}>{JSON.stringify(dslResults.results, null, 2)}</pre>
                    </Paper>
                  </Box>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    Execute a query to inspect compiled plan and results.
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Tab 4: AI Context Assembly */}
      {activeTab === 4 && (
        <Card>
          <CardHeader
            title="AI Context Assembly & Prompt Injection Defense"
            subheader="Assemble bounded, sanitized context packets combining Entity, Ontology, Evidence, and Research Gaps."
          />
          <Divider />
          <CardContent>
            <Typography variant="body1" paragraph>
              The AI Context Layer transforms raw database facts and untrusted web evidence into an isolated, strictly bounded prompt packet. Any prompt injection triggers embedded within untrusted text are neutralized automatically.
            </Typography>
            <Alert severity="info" icon={<SecurityIcon />} sx={{ mb: 2 }}>
              Strict Security Policy: External evidence text is delimited from system instructions. AI is bounded to evidence and cannot execute instructions found in public documents.
            </Alert>
          </CardContent>
        </Card>
      )}

      {/* Tab 5: Knowledge Articles */}
      {activeTab === 5 && (
        <Card>
          <CardHeader
            title="Technical Knowledge Articles & Research Playbooks"
            subheader="Internal technical documentation and classification guides (strictly non-CRM)."
          />
          <Divider />
          <CardContent>
            <Typography variant="body2" color="text.secondary">
              Authoritative guides explaining taxonomy definitions, Odoo ecosystem classifications, and research best practices.
            </Typography>
          </CardContent>
        </Card>
      )}
    </Container>
  );
};

export default KnowledgeOntologyWorkspace;

