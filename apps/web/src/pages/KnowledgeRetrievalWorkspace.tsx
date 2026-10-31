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
  Drawer,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  CircularProgress,
  Alert,
  Tabs,
  Tab,
  IconButton
} from '@mui/material';
import {
  Psychology as RAGIcon,
  Search as SearchIcon,
  MenuBook as EvidenceIcon,
  CheckCircle as GroundedIcon,
  WarningAmber as WarningIcon,
  HelpOutline as InsufficientIcon,
  Launch as ExternalIcon,
  Close as CloseIcon,
  PlayArrow as ExecuteIcon,
  CompareArrows as CompareIcon
} from '@mui/icons-material';

interface CitationItem {
  citation_number: number;
  source_title: string;
  source_url: string;
  snippet: string;
  confidence: number;
  observed_at: string;
}

interface ValidationData {
  is_grounded: boolean;
  groundedness_score: number;
  supported_claims: number;
  unsupported_claims: number;
}

export const KnowledgeRetrievalWorkspace: React.FC = () => {
  const [activeTab, setActiveTab] = useState<number>(0);
  const [queryInput, setQueryInput] = useState<string>("Why is OmniRetail Australia a high-priority Odoo lead?");
  const [loading, setLoading] = useState<boolean>(false);
  const [queryResponse, setQueryResponse] = useState<any>(null);
  const [selectedCitation, setSelectedCitation] = useState<CitationItem | null>(null);
  const [drawerOpen, setDrawerOpen] = useState<boolean>(false);
  const [leadSummary, setLeadSummary] = useState<any>(null);
  const [targetCompanyId, setTargetCompanyId] = useState<string>('');

  const handleExecuteQuery = async () => {
    if (!queryInput.trim()) return;
    setLoading(true);
    try {
      const res = await fetch('/api/v1/ai/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: queryInput })
      });
      const data = await res.json();
      if (res.ok) {
        setQueryResponse(data);
      }
    } catch (err) {
      console.error('AI Query failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenCitation = (cit: CitationItem) => {
    setSelectedCitation(cit);
    setDrawerOpen(true);
  };

  const handleFetchLeadSummary = async () => {
    if (!targetCompanyId.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/ai/lead/${targetCompanyId}/summary`);
      if (res.ok) {
        const data = await res.json();
        setLeadSummary(data);
      }
    } catch (err) {
      console.error('Lead 360 summary error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="xl" sx={{ mt: 3, mb: 4 }}>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" fontWeight={700} color="primary" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <RAGIcon fontSize="large" /> Grounded AI Knowledge Retrieval & RAG Assistant
        </Typography>
        <Typography variant="subtitle1" color="text.secondary">
          Evidence-grounded intelligence assistant. Zero hallucinations, verifiable citations, and prediction-observation separation.
        </Typography>
      </Box>

      {/* Navigation Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs value={activeTab} onChange={(_, val) => setActiveTab(val)} indicatorColor="primary" textColor="primary">
          <Tab icon={<SearchIcon />} label="Grounded RAG Assistant" />
          <Tab icon={<EvidenceIcon />} label="Lead 360 AI Summary" />
          <Tab icon={<CompareIcon />} label="Company Comparison" />
        </Tabs>
      </Paper>

      {/* Tab 0: Grounded Query Assistant */}
      {activeTab === 0 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={7}>
            <Card>
              <CardHeader title="Ask the Grounded Research Assistant" subheader="Answers are constructed strictly from retrieved public web evidence and knowledge graph relations." />
              <Divider />
              <CardContent>
                <TextField
                  fullWidth
                  multiline
                  rows={3}
                  label="Enter your intelligence question"
                  value={queryInput}
                  onChange={(e) => setQueryInput(e.target.value)}
                  sx={{ mb: 2 }}
                />
                <Button
                  variant="contained"
                  color="primary"
                  startIcon={<ExecuteIcon />}
                  onClick={handleExecuteQuery}
                  disabled={loading}
                >
                  {loading ? 'Synthesizing...' : 'Execute Grounded Query'}
                </Button>
              </CardContent>
            </Card>

            {queryResponse && (
              <Card sx={{ mt: 3 }}>
                <CardHeader
                  title="Synthesized Intelligence Response"
                  action={
                    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                      <Chip
                        size="small"
                        icon={queryResponse.validation.is_grounded ? <GroundedIcon /> : <WarningIcon />}
                        label={`Grounded: ${(queryResponse.validation.groundedness_score * 100).toFixed(0)}%`}
                        color={queryResponse.validation.is_grounded ? 'success' : 'warning'}
                      />
                      <Chip size="small" label={queryResponse.answer_state} />
                    </Box>
                  }
                />
                <Divider />
                <CardContent>
                  <Paper variant="outlined" sx={{ p: 2, whiteSpace: 'pre-wrap', backgroundColor: '#fafafa', fontFamily: 'inherit' }}>
                    {queryResponse.response}
                  </Paper>
                </CardContent>
              </Card>
            )}
          </Grid>

          {/* Citations & Evidence Drawer Trigger */}
          <Grid item xs={12} md={5}>
            <Card>
              <CardHeader
                title="Corroborating Evidence & Citations"
                subheader="Click any citation badge to inspect raw text and provenance in the Evidence Drawer."
              />
              <Divider />
              <CardContent>
                {loading && <Box sx={{ textAlign: 'center', p: 3 }}><CircularProgress /></Box>}
                {queryResponse && queryResponse.citations && queryResponse.citations.length > 0 ? (
                  <List>
                    {queryResponse.citations.map((c: CitationItem) => (
                      <ListItem
                        key={c.citation_number}
                        button
                        onClick={() => handleOpenCitation(c)}
                        divider
                        sx={{ borderRadius: 1, mb: 1, backgroundColor: '#fdfdfd' }}
                      >
                        <ListItemIcon>
                          <Chip size="small" label={`[${c.citation_number}]`} color="primary" />
                        </ListItemIcon>
                        <ListItemText
                          primary={<Typography variant="subtitle2" fontWeight={600}>{c.source_title}</Typography>}
                          secondary={`${c.snippet.substring(0, 100)}...`}
                        />
                      </ListItem>
                    ))}
                  </List>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    Execute a research query to view supporting citations.
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Tab 1: Lead 360 AI Summary */}
      {activeTab === 1 && (
        <Card>
          <CardHeader title="Lead 360 AI Intelligence Summary" subheader="Comprehensive synthesis combining Intent, Technologies, Decision Makers, and Research Gaps." />
          <Divider />
          <CardContent>
            <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
              <TextField
                size="small"
                label="Target Company UUID"
                value={targetCompanyId}
                onChange={(e) => setTargetCompanyId(e.target.value)}
                sx={{ width: 350 }}
              />
              <Button variant="contained" onClick={handleFetchLeadSummary} disabled={loading}>
                Generate Lead 360
              </Button>
            </Box>

            {leadSummary && (
              <Box>
                <Typography variant="h6" fontWeight={700} gutterBottom>
                  {leadSummary.company_name} ({leadSummary.lead_priority_tier})
                </Typography>
                <Typography variant="body1" paragraph>
                  <strong>Why this lead matters:</strong> {leadSummary.why_this_lead_matters}
                </Typography>
                <Typography variant="body1" paragraph>
                  <strong>Why now:</strong> {leadSummary.why_now}
                </Typography>
                <Typography variant="subtitle2" fontWeight={700} sx={{ mt: 2 }}>
                  Identified Decision Makers ({leadSummary.decision_makers.length}):
                </Typography>
                {leadSummary.decision_makers.map((dm: any, i: number) => (
                  <Chip key={i} label={`${dm.name} (${dm.title})`} sx={{ mr: 1, mt: 1 }} />
                ))}
              </Box>
            )}
          </CardContent>
        </Card>
      )}

      {/* Tab 2: Company Comparison */}
      {activeTab === 2 && (
        <Card>
          <CardHeader title="Side-by-Side Company Comparison" subheader="Comparative intelligence across Lead Score, Technology, and Intent." />
          <Divider />
          <CardContent>
            <Typography variant="body2" color="text.secondary">
              Select two companies to evaluate comparative ICP fit and technology adoption.
            </Typography>
          </CardContent>
        </Card>
      )}

      {/* Reusable Evidence Drawer */}
      <Drawer
        anchor="right"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        PaperProps={{ sx: { width: { xs: '100%', sm: 480 }, p: 3 } }}
      >
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6" fontWeight={700}>Evidence Drawer</Typography>
          <IconButton onClick={() => setDrawerOpen(false)}><CloseIcon /></IconButton>
        </Box>
        <Divider sx={{ mb: 2 }} />

        {selectedCitation && (
          <Box>
            <Typography variant="subtitle2" color="text.secondary">CITATION INDEX</Typography>
            <Typography variant="h5" fontWeight={700} color="primary" gutterBottom>
              Citation #{selectedCitation.citation_number}
            </Typography>

            <Typography variant="subtitle2" color="text.secondary" sx={{ mt: 2 }}>SOURCE TITLE</Typography>
            <Typography variant="body1" fontWeight={600}>{selectedCitation.source_title}</Typography>

            <Typography variant="subtitle2" color="text.secondary" sx={{ mt: 2 }}>SOURCE URL</Typography>
            <Typography variant="body2" sx={{ wordBreak: 'break-all' }}>
              <a href={selectedCitation.source_url} target="_blank" rel="noopener noreferrer">
                {selectedCitation.source_url} <ExternalIcon fontSize="inherit" />
              </a>
            </Typography>

            <Typography variant="subtitle2" color="text.secondary" sx={{ mt: 2 }}>EVIDENCE TEXT / SNIPPET</Typography>
            <Paper variant="outlined" sx={{ p: 2, mt: 1, backgroundColor: '#f9f9f9' }}>
              <Typography variant="body2">{selectedCitation.snippet}</Typography>
            </Paper>

            <Typography variant="subtitle2" color="text.secondary" sx={{ mt: 2 }}>OBSERVED DATE</Typography>
            <Typography variant="body2">{selectedCitation.observed_at}</Typography>

            <Typography variant="subtitle2" color="text.secondary" sx={{ mt: 2 }}>CONFIDENCE SCORE</Typography>
            <Chip size="small" label={`${(selectedCitation.confidence * 100).toFixed(0)}%`} color="success" sx={{ mt: 0.5 }} />
          </Box>
        )}
      </Drawer>
    </Container>
  );
};

export default KnowledgeRetrievalWorkspace;

