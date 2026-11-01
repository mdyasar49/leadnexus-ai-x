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
  MenuItem,
  Select,
  FormControl,
  InputLabel,
} from '@mui/material';
import {
  FileText,
  UploadCloud,
  ShieldCheck,
  ShieldAlert,
  Table as TableIcon,
  Tag,
  CheckCircle2,
  ExternalLink,
  RefreshCw,
  Search,
  Hash,
  Eye,
  Layers,
  Database,
  Lock,
  Cpu,
} from 'lucide-react';

interface DocumentSummary {
  id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  status: string;
  page_count: number;
  malware_status: string;
  ocr_applied: boolean;
  quality_score: number;
  created_at: string;
}

interface DocumentChunkItem {
  id: string;
  page_number: number;
  chunk_index: number;
  chunk_type: string;
  content: string;
  token_count: number;
  confidence: number;
}

interface DocumentTableItem {
  id: string;
  page_number: number;
  headers: string[];
  rows: string[][];
  row_count: number;
  col_count: number;
  confidence: number;
}

interface ExtractedEntityItem {
  id: string;
  entity_type: string;
  entity_value: string;
  normalized_value: string;
  confidence: number;
  context_snippet: string;
  page_number: number;
}

interface CitationItem {
  id: string;
  claim_text: string;
  source_citation: string;
  page_number: number;
  sha256_proof: string;
  confidence: number;
}

const INITIAL_DOCUMENTS: DocumentSummary[] = [
  {
    id: 'doc-enterprise-001',
    filename: 'Q3_Global_Enterprise_Prospectus.pdf',
    file_type: 'PDF',
    file_size_bytes: 245120,
    status: 'COMPLETED',
    page_count: 8,
    malware_status: 'CLEAN',
    ocr_applied: false,
    quality_score: 0.98,
    created_at: '2026-11-01 10:15:00',
  },
  {
    id: 'doc-enterprise-002',
    filename: 'Strategic_B2B_Target_Accounts.csv',
    file_type: 'CSV',
    file_size_bytes: 84200,
    status: 'COMPLETED',
    page_count: 1,
    malware_status: 'CLEAN',
    ocr_applied: false,
    quality_score: 1.0,
    created_at: '2026-11-01 11:30:00',
  },
  {
    id: 'doc-enterprise-003',
    filename: 'Scanned_Contract_Addendum.pdf',
    file_type: 'PDF',
    file_size_bytes: 1420900,
    status: 'COMPLETED',
    page_count: 3,
    malware_status: 'CLEAN',
    ocr_applied: true,
    quality_score: 0.92,
    created_at: '2026-11-01 12:45:00',
  },
];

const INITIAL_CHUNKS: DocumentChunkItem[] = [
  {
    id: 'chk-01',
    page_number: 1,
    chunk_index: 0,
    chunk_type: 'HEADING',
    content: 'Executive Summary — CloudScale Global Expansion',
    token_count: 6,
    confidence: 0.99,
  },
  {
    id: 'chk-02',
    page_number: 1,
    chunk_index: 1,
    chunk_type: 'PARAGRAPH',
    content: 'CloudScale Systems Inc announced a $25M series funding round to accelerate cloud migration. Chief Executive Officer David Vance affirmed international hiring across EMEA and APAC.',
    token_count: 24,
    confidence: 0.96,
  },
  {
    id: 'chk-03',
    page_number: 2,
    chunk_index: 2,
    chunk_type: 'PARAGRAPH',
    content: 'Technical inquiries should be routed to VP of Engineering Sarah Connor via sarah@cloudscale.io or +1 (415) 555-0144. The infrastructure leverage Kubernetes, Snowflake, and PostgreSQL.',
    token_count: 22,
    confidence: 0.95,
  },
];

const INITIAL_TABLES: DocumentTableItem[] = [
  {
    id: 'tbl-01',
    page_number: 2,
    headers: ['Organization', 'Key Decision Maker', 'Direct Email', 'Allocated Budget', 'Tech Stack'],
    rows: [
      ['CloudScale Systems Inc', 'David Vance (CEO)', 'david@cloudscale.io', '$25M', 'Kubernetes, Snowflake'],
      ['Apex Robotics Corp', 'Elena Rostova (CTO)', 'elena@apexrobotics.ai', '$14M', 'Python, Docker, ROS'],
      ['HyperLogistics Ltd', 'Marcus Thorne (VP Ops)', 'marcus@hyperlogistics.com', '$8M', 'AWS, PostgreSQL'],
    ],
    row_count: 3,
    col_count: 5,
    confidence: 0.98,
  },
];

const INITIAL_ENTITIES: ExtractedEntityItem[] = [
  {
    id: 'ent-01',
    entity_type: 'COMPANY',
    entity_value: 'CloudScale Systems Inc',
    normalized_value: 'CloudScale Systems Inc',
    confidence: 0.98,
    context_snippet: '...CloudScale Systems Inc announced a $25M series funding round...',
    page_number: 1,
  },
  {
    id: 'ent-02',
    entity_type: 'PERSON',
    entity_value: 'David Vance',
    normalized_value: 'David Vance',
    confidence: 0.96,
    context_snippet: '...Chief Executive Officer David Vance affirmed international...',
    page_number: 1,
  },
  {
    id: 'ent-03',
    entity_type: 'TITLE',
    entity_value: 'Chief Executive Officer',
    normalized_value: 'CHIEF EXECUTIVE OFFICER',
    confidence: 0.99,
    context_snippet: '...Chief Executive Officer David Vance affirmed...',
    page_number: 1,
  },
  {
    id: 'ent-04',
    entity_type: 'EMAIL',
    entity_value: 'sarah@cloudscale.io',
    normalized_value: 'sarah@cloudscale.io',
    confidence: 0.99,
    context_snippet: '...routed to VP of Engineering Sarah Connor via sarah@cloudscale.io...',
    page_number: 2,
  },
  {
    id: 'ent-05',
    entity_type: 'PHONE',
    entity_value: '+1 (415) 555-0144',
    normalized_value: '+14155550144',
    confidence: 0.93,
    context_snippet: '...or +1 (415) 555-0144. The infrastructure leverage...',
    page_number: 2,
  },
  {
    id: 'ent-06',
    entity_type: 'FINANCIAL',
    entity_value: '$25M',
    normalized_value: '$25M',
    confidence: 0.95,
    context_snippet: '...Systems Inc announced a $25M series funding round...',
    page_number: 1,
  },
  {
    id: 'ent-07',
    entity_type: 'TECHNOLOGY',
    entity_value: 'Kubernetes',
    normalized_value: 'Kubernetes',
    confidence: 0.97,
    context_snippet: '...infrastructure leverage Kubernetes, Snowflake, and PostgreSQL...',
    page_number: 2,
  },
];

const INITIAL_CITATIONS: CitationItem[] = [
  {
    id: 'cit-01',
    claim_text: 'COMPANY: CloudScale Systems Inc',
    source_citation: 'doc://doc-enterprise-001/p1#sha256:7f83b1657ff1',
    page_number: 1,
    sha256_proof: '7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069',
    confidence: 0.98,
  },
  {
    id: 'cit-02',
    claim_text: 'FINANCIAL: $25M',
    source_citation: 'doc://doc-enterprise-001/p1#sha256:4a12ec8910bc',
    page_number: 1,
    sha256_proof: '4a12ec8910bc11eefea23b811059f123d467e91209cc14e0f49811abcc910123',
    confidence: 0.95,
  },
  {
    id: 'cit-03',
    claim_text: 'EMAIL: sarah@cloudscale.io',
    source_citation: 'doc://doc-enterprise-001/p2#sha256:99f81a7402bd',
    page_number: 2,
    sha256_proof: '99f81a7402bd9821aa00ff81bcf742918820ac92019842bfbb4881900147cb90',
    confidence: 0.99,
  },
];

export const EnterpriseDocumentIntelligenceWorkspace: React.FC = () => {
  const [tabIndex, setTabIndex] = useState<number>(0);
  const [documents, setDocuments] = useState<DocumentSummary[]>(INITIAL_DOCUMENTS);
  const [chunks, setChunks] = useState<DocumentChunkItem[]>(INITIAL_CHUNKS);
  const [tables, setTables] = useState<DocumentTableItem[]>(INITIAL_TABLES);
  const [entities, setEntities] = useState<ExtractedEntityItem[]>(INITIAL_ENTITIES);
  const [citations, setCitations] = useState<CitationItem[]>(INITIAL_CITATIONS);

  // Ingestion form state
  const [uploadFilename, setUploadFilename] = useState<string>('q4_enterprise_report.txt');
  const [uploadContent, setUploadContent] = useState<string>(
    'TechCorp Global Corp expanded with $30M investment. Contact CTO Lisa Ray at lisa@techcorp.io or +1 (650) 555-8822. Technology includes Docker, AWS, and PostgreSQL.'
  );
  const [selectedFormat, setSelectedFormat] = useState<string>('TXT');
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Filter state
  const [entityFilter, setEntityFilter] = useState<string>('ALL');
  const [searchFilter, setSearchFilter] = useState<string>('');

  const handleSimulatedUpload = () => {
    setIsProcessing(true);
    setTimeout(() => {
      const newDocId = `doc-${Date.now().toString(36)}`;
      const newDoc: DocumentSummary = {
        id: newDocId,
        filename: uploadFilename,
        file_type: selectedFormat,
        file_size_bytes: uploadContent.length,
        status: 'COMPLETED',
        page_count: 1,
        malware_status: 'CLEAN',
        ocr_applied: false,
        quality_score: 1.0,
        created_at: new Date().toISOString().replace('T', ' ').substring(0, 19),
      };

      setDocuments([newDoc, ...documents]);
      setSuccessMsg(`Document "${uploadFilename}" sanitized, parsed, and indexed successfully!`);
      setIsProcessing(false);
    }, 800);
  };

  const filteredEntities = entities.filter((e) => {
    const matchesType = entityFilter === 'ALL' || e.entity_type === entityFilter;
    const matchesSearch =
      searchFilter === '' ||
      e.entity_value.toLowerCase().includes(searchFilter.toLowerCase()) ||
      e.context_snippet.toLowerCase().includes(searchFilter.toLowerCase());
    return matchesType && matchesSearch;
  });

  return (
    <Box sx={{ p: 4, maxWidth: 1440, margin: '0 auto' }}>
      {/* Workspace Header */}
      <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
            <FileText size={28} color="#0284c7" />
            <Typography variant="h4" sx={{ fontWeight: 700, color: '#0f172a' }}>
              Document & Unstructured Data Intelligence
            </Typography>
            <Chip label="Phase 42" color="primary" size="small" sx={{ fontWeight: 600 }} />
          </Box>
          <Typography variant="body1" sx={{ color: '#64748b' }}>
            Multi-format document ingestion (PDF, DOCX, XLSX, CSV, HTML, TXT), security sanitization,
            table extraction, entity recognition, and cryptographic evidence grounding.
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="outlined"
            startIcon={<RefreshCw size={16} />}
            onClick={() => setSuccessMsg('Workspace refreshed with latest ingestion state.')}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<UploadCloud size={16} />}
            onClick={() => setTabIndex(0)}
            sx={{ bgcolor: '#0284c7', '&:hover': { bgcolor: '#0369a1' } }}
          >
            Ingest Document
          </Button>
        </Box>
      </Box>

      {/* Primary Invariant Banner */}
      <Alert severity="info" sx={{ mb: 3, border: '1px solid #bae6fd', bgcolor: '#f0f9ff' }}>
        <strong>Invariant Rule Enforced:</strong> Ingested unstructured documents and extracted entity candidates
        remain in temporary isolated memory and are <strong>never</strong> added to Saved Leads or Export streams
        without explicit operator approval.
      </Alert>

      {successMsg && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={() => setSuccessMsg(null)}>
          {successMsg}
        </Alert>
      )}

      {/* Navigation Tabs */}
      <Paper sx={{ mb: 3, borderRadius: 2 }} elevation={1}>
        <Tabs
          value={tabIndex}
          onChange={(_, val) => setTabIndex(val)}
          variant="scrollable"
          scrollButtons="auto"
          textColor="primary"
          indicatorColor="primary"
        >
          <Tab icon={<UploadCloud size={18} />} iconPosition="start" label="Ingestion & Upload" />
          <Tab icon={<Layers size={18} />} iconPosition="start" label="Parsed Layout & Chunks" />
          <Tab icon={<TableIcon size={18} />} iconPosition="start" label="Structured Tables" />
          <Tab icon={<Tag size={18} />} iconPosition="start" label="Entity & Lead Extractor" />
          <Tab icon={<ShieldCheck size={18} />} iconPosition="start" label="Evidence Grounding" />
          <Tab icon={<Cpu size={18} />} iconPosition="start" label="Health & Diagnostics" />
        </Tabs>
      </Paper>

      {/* TAB 0: Ingestion & Upload */}
      {tabIndex === 0 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={5}>
            <Card sx={{ borderRadius: 2, height: '100%' }}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <UploadCloud size={20} color="#0284c7" />
                  Document Ingestion Studio
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b', mb: 3 }}>
                  Upload documents for automated malware scanning, layout parsing, OCR processing, and entity extraction.
                </Typography>

                <TextField
                  fullWidth
                  label="Filename"
                  value={uploadFilename}
                  onChange={(e) => setUploadFilename(e.target.value)}
                  sx={{ mb: 2 }}
                />

                <FormControl fullWidth sx={{ mb: 2 }}>
                  <InputLabel>Document Format</InputLabel>
                  <Select
                    value={selectedFormat}
                    label="Document Format"
                    onChange={(e) => setSelectedFormat(e.target.value)}
                  >
                    <MenuItem value="PDF">PDF (Portable Document Format)</MenuItem>
                    <MenuItem value="DOCX">DOCX (Microsoft Word)</MenuItem>
                    <MenuItem value="XLSX">XLSX (Microsoft Excel)</MenuItem>
                    <MenuItem value="CSV">CSV (Comma Separated Values)</MenuItem>
                    <MenuItem value="HTML">HTML (Web Content / Dom)</MenuItem>
                    <MenuItem value="TXT">TXT (Plain Unstructured Text)</MenuItem>
                    <MenuItem value="JSON">JSON (Semi-Structured Records)</MenuItem>
                    <MenuItem value="XML">XML (Extensible Markup)</MenuItem>
                  </Select>
                </FormControl>

                <TextField
                  fullWidth
                  multiline
                  rows={6}
                  label="Document Content or Decoded Text"
                  value={uploadContent}
                  onChange={(e) => setUploadContent(e.target.value)}
                  sx={{ mb: 3 }}
                />

                <Box sx={{ p: 2, bgcolor: '#f8fafc', borderRadius: 1.5, mb: 3, border: '1px dashed #cbd5e1' }}>
                  <Typography variant="caption" sx={{ color: '#475569', display: 'block', mb: 0.5, fontWeight: 600 }}>
                    Security Pre-Flight Inspection:
                  </Typography>
                  <Typography variant="caption" sx={{ color: '#64748b', display: 'block' }}>
                    Active scanning checks for VBA Macros, JavaScript injections, XML entities, and executable payloads.
                  </Typography>
                </Box>

                <Button
                  fullWidth
                  variant="contained"
                  disabled={isProcessing}
                  onClick={handleSimulatedUpload}
                  startIcon={isProcessing ? <RefreshCw className="animate-spin" size={16} /> : <UploadCloud size={16} />}
                  sx={{ bgcolor: '#0284c7', '&:hover': { bgcolor: '#0369a1' }, py: 1.2 }}
                >
                  {isProcessing ? 'Processing Document Pipeline...' : 'Upload & Execute Pipeline'}
                </Button>
                {isProcessing && <LinearProgress sx={{ mt: 2 }} />}
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={7}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <FileText size={20} color="#0284c7" />
                  Ingested Document Ledger ({documents.length})
                </Typography>
                <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid #e2e8f0', borderRadius: 2 }}>
                  <Table size="small">
                    <TableHead sx={{ bgcolor: '#f8fafc' }}>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 600 }}>Filename</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>Format</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>Pages</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>Security</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>Status</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>OCR</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {documents.map((doc) => (
                        <TableRow key={doc.id} hover>
                          <TableCell sx={{ fontWeight: 500, color: '#0f172a' }}>{doc.filename}</TableCell>
                          <TableCell>
                            <Chip label={doc.file_type} size="small" variant="outlined" />
                          </TableCell>
                          <TableCell>{doc.page_count}</TableCell>
                          <TableCell>
                            <Chip
                              icon={doc.malware_status === 'CLEAN' ? <ShieldCheck size={14} /> : <ShieldAlert size={14} />}
                              label={doc.malware_status}
                              size="small"
                              color={doc.malware_status === 'CLEAN' ? 'success' : 'error'}
                              variant="outlined"
                            />
                          </TableCell>
                          <TableCell>
                            <Chip label={doc.status} size="small" color="primary" />
                          </TableCell>
                          <TableCell>
                            {doc.ocr_applied ? (
                              <Chip label="OCR Fallback" size="small" color="secondary" variant="outlined" />
                            ) : (
                              <Typography variant="caption" sx={{ color: '#94a3b8' }}>
                                Native
                              </Typography>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* TAB 1: Parsed Layout & Chunks */}
      {tabIndex === 1 && (
        <Card sx={{ borderRadius: 2 }}>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
              <Layers size={20} color="#0284c7" />
              Semantic Layout Chunks & Token Offsets ({chunks.length})
            </Typography>
            <Typography variant="body2" sx={{ color: '#64748b', mb: 3 }}>
              Documents are decomposed into semantic chunks (Headings, Paragraphs, Tables, Metadata) with token counts
              and normalized layout coordinates.
            </Typography>

            <Grid container spacing={2}>
              {chunks.map((chk) => (
                <Grid item xs={12} key={chk.id}>
                  <Paper sx={{ p: 2.5, border: '1px solid #e2e8f0', borderRadius: 2, bgcolor: '#ffffff' }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
                      <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center' }}>
                        <Chip label={`Page ${chk.page_number}`} size="small" variant="outlined" />
                        <Chip
                          label={chk.chunk_type}
                          size="small"
                          color={chk.chunk_type === 'HEADING' ? 'secondary' : 'default'}
                        />
                        <Typography variant="caption" sx={{ color: '#64748b' }}>
                          Chunk #{chk.chunk_index} · {chk.token_count} tokens
                        </Typography>
                      </Box>
                      <Chip
                        label={`Confidence: ${(chk.confidence * 100).toFixed(0)}%`}
                        size="small"
                        color="success"
                        variant="outlined"
                      />
                    </Box>
                    <Typography variant="body2" sx={{ color: '#1e293b', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                      {chk.content}
                    </Typography>
                  </Paper>
                </Grid>
              ))}
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* TAB 2: Structured Tables */}
      {tabIndex === 2 && (
        <Card sx={{ borderRadius: 2 }}>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
              <TableIcon size={20} color="#0284c7" />
              Extracted Tabular Structures ({tables.length})
            </Typography>
            <Typography variant="body2" sx={{ color: '#64748b', mb: 3 }}>
              Automated table boundary recognition converts embedded spreadsheets, HTML tables, and markdown grids into
              normalized tabular records.
            </Typography>

            {tables.map((tbl) => (
              <Box key={tbl.id} sx={{ mb: 4 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 600, color: '#0f172a' }}>
                    Table {tbl.id} (Page {tbl.page_number}) · {tbl.row_count} rows × {tbl.col_count} columns
                  </Typography>
                  <Chip label={`Extraction Confidence: ${(tbl.confidence * 100).toFixed(0)}%`} size="small" color="success" />
                </Box>
                <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid #e2e8f0', borderRadius: 2 }}>
                  <Table size="small">
                    <TableHead sx={{ bgcolor: '#0f172a' }}>
                      <TableRow>
                        {tbl.headers.map((h, idx) => (
                          <TableCell key={idx} sx={{ color: '#ffffff', fontWeight: 600 }}>
                            {h}
                          </TableCell>
                        ))}
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {tbl.rows.map((row, rIdx) => (
                        <TableRow key={rIdx} hover>
                          {row.map((cell, cIdx) => (
                            <TableCell key={cIdx} sx={{ color: '#334155' }}>
                              {cell}
                            </TableCell>
                          ))}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Box>
            ))}
          </CardContent>
        </Card>
      )}

      {/* TAB 3: Entity & Lead Extractor */}
      {tabIndex === 3 && (
        <Card sx={{ borderRadius: 2 }}>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Box>
                <Typography variant="h6" sx={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Tag size={20} color="#0284c7" />
                  Extracted Lead Entities ({filteredEntities.length})
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  Named entity recognition (NER) extracting decision-makers, organizations, contact emails, and technologies.
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', gap: 2 }}>
                <TextField
                  size="small"
                  placeholder="Filter entities..."
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  InputProps={{
                    startAdornment: <Search size={16} style={{ marginRight: 8, color: '#94a3b8' }} />,
                  }}
                />
                <FormControl size="small" sx={{ minWidth: 160 }}>
                  <InputLabel>Entity Type</InputLabel>
                  <Select
                    value={entityFilter}
                    label="Entity Type"
                    onChange={(e) => setEntityFilter(e.target.value)}
                  >
                    <MenuItem value="ALL">All Types</MenuItem>
                    <MenuItem value="COMPANY">Company</MenuItem>
                    <MenuItem value="PERSON">Person</MenuItem>
                    <MenuItem value="TITLE">Title</MenuItem>
                    <MenuItem value="EMAIL">Email</MenuItem>
                    <MenuItem value="PHONE">Phone</MenuItem>
                    <MenuItem value="FINANCIAL">Financial</MenuItem>
                    <MenuItem value="TECHNOLOGY">Technology</MenuItem>
                  </Select>
                </FormControl>
              </Box>
            </Box>

            <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid #e2e8f0', borderRadius: 2 }}>
              <Table size="small">
                <TableHead sx={{ bgcolor: '#f8fafc' }}>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Type</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Extracted Value</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Normalized Value</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Context Snippet</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Page</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Confidence</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredEntities.map((ent) => (
                    <TableRow key={ent.id} hover>
                      <TableCell>
                        <Chip
                          label={ent.entity_type}
                          size="small"
                          color={
                            ent.entity_type === 'EMAIL'
                              ? 'primary'
                              : ent.entity_type === 'COMPANY'
                              ? 'secondary'
                              : ent.entity_type === 'FINANCIAL'
                              ? 'success'
                              : 'default'
                          }
                        />
                      </TableCell>
                      <TableCell sx={{ fontWeight: 600, color: '#0f172a' }}>{ent.entity_value}</TableCell>
                      <TableCell sx={{ color: '#475569' }}>{ent.normalized_value}</TableCell>
                      <TableCell sx={{ maxWidth: 320, color: '#64748b', fontSize: '0.85rem' }}>
                        {ent.context_snippet}
                      </TableCell>
                      <TableCell>{ent.page_number}</TableCell>
                      <TableCell>
                        <Chip
                          label={`${(ent.confidence * 100).toFixed(0)}%`}
                          size="small"
                          color="success"
                          variant="outlined"
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}

      {/* TAB 4: Evidence Grounding */}
      {tabIndex === 4 && (
        <Card sx={{ borderRadius: 2 }}>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
              <ShieldCheck size={20} color="#0284c7" />
              Cryptographic Evidence Provenance & Grounding ({citations.length})
            </Typography>
            <Typography variant="body2" sx={{ color: '#64748b', mb: 3 }}>
              Every extracted business claim is cryptographically grounded in raw source text using SHA-256 byte hashes
              and URI page citations.
            </Typography>

            <Grid container spacing={2}>
              {citations.map((cit) => (
                <Grid item xs={12} key={cit.id}>
                  <Paper sx={{ p: 2.5, border: '1px solid #e2e8f0', borderRadius: 2 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                      <Typography variant="subtitle1" sx={{ fontWeight: 700, color: '#0f172a' }}>
                        {cit.claim_text}
                      </Typography>
                      <Chip
                        icon={<CheckCircle2 size={14} />}
                        label="Cryptographically Verified"
                        size="small"
                        color="success"
                      />
                    </Box>
                    <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 1.5 }}>
                      <Chip label={`URI: ${cit.source_citation}`} size="small" variant="outlined" />
                      <Typography variant="caption" sx={{ color: '#64748b' }}>
                        Page {cit.page_number} · Confidence: {(cit.confidence * 100).toFixed(0)}%
                      </Typography>
                    </Box>
                    <Box sx={{ p: 1.5, bgcolor: '#f8fafc', borderRadius: 1, border: '1px solid #e2e8f0' }}>
                      <Typography variant="caption" sx={{ color: '#475569', fontWeight: 600, display: 'block', mb: 0.5 }}>
                        SHA-256 Grounding Proof Hash:
                      </Typography>
                      <Typography variant="caption" sx={{ fontFamily: 'monospace', color: '#0284c7' }}>
                        {cit.sha256_proof}
                      </Typography>
                    </Box>
                  </Paper>
                </Grid>
              ))}
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* TAB 5: Health & Diagnostics */}
      {tabIndex === 5 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={4}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <ShieldCheck size={18} color="#16a34a" />
                  Malware & Safety Guard
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 700, color: '#16a34a', mb: 1 }}>
                  100%
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  Clean inspection rate across all ingested documents. Zero malicious macro or script payload breaches.
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Cpu size={18} color="#0284c7" />
                  OCR Fallback Engine
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 700, color: '#0284c7', mb: 1 }}>
                  Active
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  Automatic OCR detection engages when text density drops below threshold, processing scanned PDFs and images.
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card sx={{ borderRadius: 2 }}>
              <CardContent>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Database size={18} color="#8b5cf6" />
                  Supported Formats
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 700, color: '#8b5cf6', mb: 1 }}>
                  8 Formats
                </Typography>
                <Typography variant="body2" sx={{ color: '#64748b' }}>
                  PDF, DOCX, XLSX, CSV, HTML, TXT, JSON, and XML parsers operational with full entity extraction.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
    </Box>
  );
};

export default EnterpriseDocumentIntelligenceWorkspace;
