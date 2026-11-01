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
  Slider,
  CircularProgress,
  Alert,
  IconButton,
  Tooltip,
  MenuItem,
  Select,
  FormControl,
  InputLabel
} from '@mui/material';
import {
  Network,
  Share2,
  Search,
  Compass,
  Award,
  Sliders,
  Layers,
  ArrowRight,
  UserCheck,
  Building,
  Cpu,
  MapPin,
  RefreshCw,
  ExternalLink,
  ShieldCheck,
  CheckCircle,
  Database
} from 'lucide-react';

interface GraphStats {
  total_nodes: number;
  total_edges: number;
  graph_density: number;
  node_type_distribution: Record<string, number>;
  edge_relationship_distribution: Record<string, number>;
}

interface RankedInfluencer {
  node_id: string;
  name: string;
  node_type: string;
  canonical_key: string;
  attributes: Record<string, any>;
  pagerank_score: number;
  degree_centrality: number;
  total_connections: number;
  influence_tier: string;
}

interface HybridResult {
  node_id: string;
  name: string;
  node_type: string;
  attributes: Record<string, any>;
  final_score: number;
  lexical_score: number;
  vector_score: number;
  graph_score: number;
  explanation: string;
}

interface ShortestPathResponse {
  found: boolean;
  source_id: string;
  target_id: string;
  degree_of_separation: number;
  path_nodes: Array<{ id: string; name: string; node_type: string; attributes: Record<string, any> }>;
  path_edges: Array<{ id: string; relationship_type: string; weight: number; confidence: number }>;
  confidence_score: number;
}

export default function EnterpriseEntityGraphWorkspace() {
  const [activeTab, setActiveTab] = useState(0);
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);

  // Tab 1: Explorer
  const [selectedNodeId, setSelectedNodeId] = useState('comp_odoo_au');
  const [nodeDetail, setNodeDetail] = useState<any>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Tab 2: Multi-Hop Query
  const [queryStartType, setQueryStartType] = useState('COMPANY');
  const [startFilterKey, setStartFilterKey] = useState('country');
  const [startFilterVal, setStartFilterVal] = useState('Australia');
  const [queryResults, setQueryResults] = useState<any>(null);
  const [loadingQuery, setLoadingQuery] = useState(false);

  // Tab 3: Shortest Path / Warm Intro
  const [sourceNodeId, setSourceNodeId] = useState('person_sarah');
  const [targetNodeId, setTargetNodeId] = useState('person_david');
  const [pathResult, setPathResult] = useState<ShortestPathResponse | null>(null);
  const [loadingPath, setLoadingPath] = useState(false);

  // Tab 4: Centrality
  const [centralityType, setCentralityType] = useState<string>('ALL');
  const [influencers, setInfluencers] = useState<RankedInfluencer[]>([]);
  const [loadingCentrality, setLoadingCentrality] = useState(false);

  // Tab 5: Hybrid Search
  const [searchQuery, setSearchQuery] = useState('Odoo ERP Sydney');
  const [lexicalWeight, setLexicalWeight] = useState(0.4);
  const [vectorWeight, setVectorWeight] = useState(0.3);
  const [graphWeight, setGraphWeight] = useState(0.3);
  const [searchResults, setSearchResults] = useState<HybridResult[]>([]);
  const [loadingSearch, setLoadingSearch] = useState(false);

  // Notifications
  const [alertMsg, setAlertMsg] = useState<{ type: 'success' | 'info' | 'error'; text: string } | null>(null);

  // Fetch stats
  const fetchStats = async () => {
    setLoadingStats(true);
    try {
      const res = await fetch('/api/v1/graph/stats');
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (e) {
      console.warn('Failed to fetch graph stats', e);
    } finally {
      setLoadingStats(false);
    }
  };

  // Fetch node detail
  const fetchNodeDetail = async (id: string) => {
    setLoadingDetail(true);
    try {
      const res = await fetch(`/api/v1/graph/nodes/${id}`);
      if (res.ok) {
        const data = await res.json();
        setNodeDetail(data);
      }
    } catch (e) {
      console.warn('Failed to fetch node detail', e);
    } finally {
      setLoadingDetail(false);
    }
  };

  // Fetch centrality
  const fetchCentrality = async () => {
    setLoadingCentrality(true);
    try {
      const filterParam = centralityType !== 'ALL' ? `?node_type=${centralityType}&limit=25` : '?limit=25';
      const res = await fetch(`/api/v1/graph/centrality${filterParam}`);
      if (res.ok) {
        const data = await res.json();
        setInfluencers(data);
      }
    } catch (e) {
      console.warn('Failed to fetch centrality', e);
    } finally {
      setLoadingCentrality(false);
    }
  };

  // Execute multi-hop query
  const handleExecuteMultiHop = async () => {
    setLoadingQuery(true);
    try {
      const payload = {
        start_node_type: queryStartType,
        start_filters: startFilterKey && startFilterVal ? { [startFilterKey]: startFilterVal } : {},
        hops: [
          { relationship_type: 'USES_TECH', target_node_type: 'TECHNOLOGY' },
          { relationship_type: 'EMPLOYED_AT', target_node_type: 'PERSON' }
        ],
        limit: 20
      };
      const res = await fetch('/api/v1/graph/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const data = await res.json();
        setQueryResults(data);
        setAlertMsg({ type: 'success', text: `Multi-hop query executed: found ${data.query_summary.total_paths_found} matching paths.` });
      }
    } catch (e) {
      setAlertMsg({ type: 'error', text: 'Multi-hop query execution failed' });
    } finally {
      setLoadingQuery(false);
    }
  };

  // Execute shortest path
  const handleFindPath = async () => {
    setLoadingPath(true);
    try {
      const res = await fetch('/api/v1/graph/shortest-path', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_id: sourceNodeId, target_id: targetNodeId, max_depth: 5 })
      });
      if (res.ok) {
        const data = await res.json();
        setPathResult(data);
        if (data.found) {
          setAlertMsg({ type: 'success', text: `Warm intro path identified! Separation: ${data.degree_of_separation} degrees, Confidence: ${(data.confidence_score * 100).toFixed(1)}%.` });
        } else {
          setAlertMsg({ type: 'info', text: 'No connection path found within current depth limits.' });
        }
      }
    } catch (e) {
      setAlertMsg({ type: 'error', text: 'Pathfinding search failed' });
    } finally {
      setLoadingPath(false);
    }
  };

  // Execute hybrid search
  const handleHybridSearch = async () => {
    setLoadingSearch(true);
    try {
      const res = await fetch('/api/v1/graph/hybrid-search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: searchQuery,
          lexical_weight: lexicalWeight,
          vector_weight: vectorWeight,
          graph_weight: graphWeight,
          limit: 15
        })
      });
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data);
        setAlertMsg({ type: 'success', text: `Hybrid query federated ${data.length} ranked entity results.` });
      }
    } catch (e) {
      setAlertMsg({ type: 'error', text: 'Hybrid search failed' });
    } finally {
      setLoadingSearch(false);
    }
  };

  useEffect(() => {
    fetchStats();
    fetchNodeDetail(selectedNodeId);
    fetchCentrality();
  }, []);

  useEffect(() => {
    fetchCentrality();
  }, [centralityType]);

  const getNodeBadgeColor = (type: string) => {
    switch (type) {
      case 'COMPANY': return '#0284c7';
      case 'PERSON': return '#10b981';
      case 'TECHNOLOGY': return '#8b5cf6';
      case 'LOCATION': return '#f59e0b';
      case 'INVESTOR': return '#ec4899';
      default: return '#64748b';
    }
  };

  const getNodeIcon = (type: string) => {
    switch (type) {
      case 'COMPANY': return <Building size={16} />;
      case 'PERSON': return <UserCheck size={16} />;
      case 'TECHNOLOGY': return <Cpu size={16} />;
      case 'LOCATION': return <MapPin size={16} />;
      default: return <Share2 size={16} />;
    }
  };

  return (
    <Box sx={{ p: 3, maxWidth: 1600, mx: 'auto' }}>
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Network size={28} color="#0284c7" />
            <Typography variant="h5" sx={{ fontWeight: 700, color: '#f8fafc' }}>
              Advanced Search, Entity Graph & Query Federation
            </Typography>
            <Chip label="Phase 46" size="small" sx={{ bgcolor: '#0284c7', color: '#fff', fontWeight: 600 }} />
          </Box>
          <Typography variant="body2" sx={{ color: '#94a3b8', mt: 0.5 }}>
            Multi-hop relational traversals, PageRank executive influence scoring, warm intro pathfinding, and hybrid BM25/Vector retrieval.
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1.5 }}>
          <Button
            variant="outlined"
            startIcon={<RefreshCw size={16} />}
            onClick={() => { fetchStats(); fetchNodeDetail(selectedNodeId); fetchCentrality(); }}
            sx={{ borderColor: '#334155', color: '#cbd5e1' }}
          >
            Refresh Graph
          </Button>
        </Box>
      </Box>

      {alertMsg && (
        <Alert severity={alertMsg.type} sx={{ mb: 3 }} onClose={() => setAlertMsg(null)}>
          {alertMsg.text}
        </Alert>
      )}

      {/* Tabs */}
      <Paper sx={{ bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2, mb: 3 }}>
        <Tabs
          value={activeTab}
          onChange={(_, val) => setActiveTab(val)}
          variant="scrollable"
          scrollButtons="auto"
          sx={{
            '& .MuiTab-root': { color: '#94a3b8', textTransform: 'none', fontWeight: 600, minHeight: 48 },
            '& .Mui-selected': { color: '#38bdf8' },
            '& .MuiTabs-indicator': { bgcolor: '#38bdf8' },
          }}
        >
          <Tab icon={<Compass size={18} />} iconPosition="start" label="Graph Explorer & 1-Hop" />
          <Tab icon={<Layers size={18} />} iconPosition="start" label="Multi-Hop Query Builder" />
          <Tab icon={<Share2 size={18} />} iconPosition="start" label="Warm Intro Pathfinding" />
          <Tab icon={<Award size={18} />} iconPosition="start" label="Executive & Company Centrality" />
          <Tab icon={<Sliders size={18} />} iconPosition="start" label="Hybrid Federated Search" />
          <Tab icon={<Database size={18} />} iconPosition="start" label="Topology & Seed Graph" />
        </Tabs>
      </Paper>

      {/* Tab 1: Graph Explorer */}
      {activeTab === 0 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={4}>
            <Paper sx={{ p: 2.5, bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, color: '#f8fafc', mb: 2 }}>
                Quick Entity Selector
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                {[
                  { id: 'comp_odoo_au', name: 'Odoo Australia Pty Ltd', type: 'COMPANY' },
                  { id: 'comp_atlassian', name: 'Atlassian Corp', type: 'COMPANY' },
                  { id: 'comp_canva', name: 'Canva Inc', type: 'COMPANY' },
                  { id: 'comp_nexus_erp', name: 'Nexus Cloud Solutions', type: 'COMPANY' },
                  { id: 'person_sarah', name: 'Sarah Jenkins (CTO)', type: 'PERSON' },
                  { id: 'person_david', name: 'David Chen (Head of Eng)', type: 'PERSON' },
                  { id: 'tech_odoo', name: 'Odoo ERP', type: 'TECHNOLOGY' },
                ].map((ent) => (
                  <Card
                    key={ent.id}
                    onClick={() => { setSelectedNodeId(ent.id); fetchNodeDetail(ent.id); }}
                    sx={{
                      bgcolor: selectedNodeId === ent.id ? '#1e293b' : '#090d16',
                      border: `1px solid ${selectedNodeId === ent.id ? '#0284c7' : '#1e293b'}`,
                      cursor: 'pointer',
                      transition: 'all 0.15s ease-in-out',
                      '&:hover': { bgcolor: '#1e293b' }
                    }}
                  >
                    <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          {getNodeIcon(ent.type)}
                          <Typography variant="body2" sx={{ fontWeight: 600, color: '#f8fafc' }}>
                            {ent.name}
                          </Typography>
                        </Box>
                        <Chip
                          label={ent.type}
                          size="small"
                          sx={{ bgcolor: getNodeBadgeColor(ent.type), color: '#fff', fontSize: 10, height: 20 }}
                        />
                      </Box>
                    </CardContent>
                  </Card>
                ))}
              </Box>
            </Paper>
          </Grid>

          <Grid item xs={12} md={8}>
            <Paper sx={{ p: 3, bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2 }}>
              {loadingDetail ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
                  <CircularProgress size={36} />
                </Box>
              ) : nodeDetail ? (
                <Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
                    <Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                        <Typography variant="h6" sx={{ fontWeight: 700, color: '#f8fafc' }}>
                          {nodeDetail.node.name}
                        </Typography>
                        <Chip
                          label={nodeDetail.node.node_type}
                          size="small"
                          sx={{ bgcolor: getNodeBadgeColor(nodeDetail.node.node_type), color: '#fff', fontWeight: 600 }}
                        />
                      </Box>
                      <Typography variant="caption" sx={{ color: '#64748b', display: 'block', mt: 0.5 }}>
                        Canonical Key: {nodeDetail.node.canonical_key} • ID: {nodeDetail.node.id}
                      </Typography>
                    </Box>
                  </Box>

                  {/* Attributes */}
                  <Typography variant="subtitle2" sx={{ fontWeight: 600, color: '#cbd5e1', mb: 1 }}>
                    Entity Attributes
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 3 }}>
                    {Object.entries(nodeDetail.node.attributes || {}).map(([k, v]) => (
                      <Chip
                        key={k}
                        label={`${k}: ${String(v)}`}
                        variant="outlined"
                        size="small"
                        sx={{ borderColor: '#334155', color: '#94a3b8' }}
                      />
                    ))}
                  </Box>

                  {/* 1-Hop Neighborhood */}
                  <Typography variant="subtitle2" sx={{ fontWeight: 600, color: '#cbd5e1', mb: 1.5 }}>
                    1-Hop Connected Neighborhood ({nodeDetail.neighborhood.nodes.length - 1} adjacent entities)
                  </Typography>
                  <TableContainer component={Paper} sx={{ bgcolor: '#090d16', border: '1px solid #1e293b' }}>
                    <Table size="small">
                      <TableHead>
                        <TableRow sx={{ '& th': { color: '#94a3b8', fontWeight: 600 } }}>
                          <TableCell>Connected Entity</TableCell>
                          <TableCell>Type</TableCell>
                          <TableCell>Relationship</TableCell>
                          <TableCell>Weight / Confidence</TableCell>
                          <TableCell>Action</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {nodeDetail.neighborhood.nodes
                          .filter((n: any) => n.id !== nodeDetail.node.id)
                          .map((conn: any) => {
                            const matchingEdge = nodeDetail.neighborhood.edges.find(
                              (e: any) => (e.source_id === conn.id && e.target_id === nodeDetail.node.id) ||
                                          (e.target_id === conn.id && e.source_id === nodeDetail.node.id)
                            );
                            return (
                              <TableRow key={conn.id} sx={{ '& td': { color: '#cbd5e1' } }}>
                                <TableCell sx={{ fontWeight: 600 }}>{conn.name}</TableCell>
                                <TableCell>
                                  <Chip
                                    label={conn.node_type}
                                    size="small"
                                    sx={{ bgcolor: getNodeBadgeColor(conn.node_type), color: '#fff', fontSize: 10, height: 20 }}
                                  />
                                </TableCell>
                                <TableCell>
                                  <Chip
                                    label={matchingEdge ? matchingEdge.relationship_type : 'CONNECTED'}
                                    variant="outlined"
                                    size="small"
                                    sx={{ borderColor: '#38bdf8', color: '#38bdf8', fontSize: 11 }}
                                  />
                                </TableCell>
                                <TableCell>
                                  {matchingEdge ? `${(matchingEdge.confidence * 100).toFixed(0)}% conf` : '-'}
                                </TableCell>
                                <TableCell>
                                  <Button
                                    size="small"
                                    variant="text"
                                    onClick={() => { setSelectedNodeId(conn.id); fetchNodeDetail(conn.id); }}
                                    sx={{ color: '#38bdf8', minWidth: 'auto', p: 0.5 }}
                                  >
                                    Hop Here
                                  </Button>
                                </TableCell>
                              </TableRow>
                            );
                          })}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Box>
              ) : null}
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* Tab 2: Multi-Hop Query Builder */}
      {activeTab === 1 && (
        <Paper sx={{ p: 3, bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, color: '#f8fafc', mb: 1 }}>
            Federated Multi-Hop Graph Query Builder
          </Typography>
          <Typography variant="body2" sx={{ color: '#94a3b8', mb: 3 }}>
            Traverse complex enterprise relational patterns (e.g. Find all Companies in Australia that use Odoo ERP and have verified Engineering Leaders).
          </Typography>

          <Grid container spacing={2} sx={{ mb: 3, alignItems: 'center' }}>
            <Grid item xs={12} sm={3}>
              <FormControl fullWidth size="small">
                <InputLabel sx={{ color: '#94a3b8' }}>Start Node Type</InputLabel>
                <Select
                  value={queryStartType}
                  onChange={(e) => setQueryStartType(e.target.value)}
                  label="Start Node Type"
                  sx={{ color: '#f8fafc', bgcolor: '#090d16', '& .MuiOutlinedInput-notchedOutline': { borderColor: '#334155' } }}
                >
                  <MenuItem value="COMPANY">COMPANY</MenuItem>
                  <MenuItem value="PERSON">PERSON</MenuItem>
                  <MenuItem value="TECHNOLOGY">TECHNOLOGY</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={3}>
              <TextField
                fullWidth
                size="small"
                label="Start Filter Attribute"
                value={startFilterKey}
                onChange={(e) => setStartFilterKey(e.target.value)}
                sx={{ bgcolor: '#090d16', input: { color: '#f8fafc' }, label: { color: '#94a3b8' } }}
              />
            </Grid>
            <Grid item xs={12} sm={3}>
              <TextField
                fullWidth
                size="small"
                label="Filter Match Value"
                value={startFilterVal}
                onChange={(e) => setStartFilterVal(e.target.value)}
                sx={{ bgcolor: '#090d16', input: { color: '#f8fafc' }, label: { color: '#94a3b8' } }}
              />
            </Grid>
            <Grid item xs={12} sm={3}>
              <Button
                fullWidth
                variant="contained"
                onClick={handleExecuteMultiHop}
                disabled={loadingQuery}
                startIcon={loadingQuery ? <CircularProgress size={16} /> : <Search size={16} />}
                sx={{ bgcolor: '#0284c7', '&:hover': { bgcolor: '#0369a1' }, height: 40 }}
              >
                Execute Multi-Hop
              </Button>
            </Grid>
          </Grid>

          {/* Planned Hop Steps */}
          <Box sx={{ mb: 3, p: 2, bgcolor: '#090d16', borderRadius: 1.5, border: '1px solid #1e293b' }}>
            <Typography variant="caption" sx={{ color: '#94a3b8', fontWeight: 600, display: 'block', mb: 1 }}>
              ACTIVE TRAVERSAL PATTERN:
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
              <Chip label={`Start: ${queryStartType} [${startFilterKey}=${startFilterVal}]`} sx={{ bgcolor: '#0284c7', color: '#fff', fontWeight: 600 }} />
              <ArrowRight size={18} color="#94a3b8" />
              <Chip label="Hop 1: -(USES_TECH)-> TECHNOLOGY" sx={{ bgcolor: '#8b5cf6', color: '#fff' }} />
              <ArrowRight size={18} color="#94a3b8" />
              <Chip label="Hop 2: -(EMPLOYED_AT)-> PERSON [Decision-Maker]" sx={{ bgcolor: '#10b981', color: '#fff' }} />
            </Box>
          </Box>

          {/* Results Table */}
          {queryResults && (
            <Box>
              <Typography variant="subtitle2" sx={{ fontWeight: 600, color: '#cbd5e1', mb: 1.5 }}>
                Matched Target Entities ({queryResults.target_entities.length} discovered)
              </Typography>
              <TableContainer component={Paper} sx={{ bgcolor: '#090d16', border: '1px solid #1e293b' }}>
                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ '& th': { color: '#94a3b8', fontWeight: 600 } }}>
                      <TableCell>Entity Name</TableCell>
                      <TableCell>Type</TableCell>
                      <TableCell>Attributes</TableCell>
                      <TableCell>Trace Path</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {queryResults.target_entities.map((ent: any) => {
                      const pathObj = queryResults.paths.find((p: any) => p.end_node.id === ent.id);
                      return (
                        <TableRow key={ent.id} sx={{ '& td': { color: '#cbd5e1' } }}>
                          <TableCell sx={{ fontWeight: 600, color: '#f8fafc' }}>{ent.name}</TableCell>
                          <TableCell>
                            <Chip
                              label={ent.node_type}
                              size="small"
                              sx={{ bgcolor: getNodeBadgeColor(ent.node_type), color: '#fff', fontSize: 10, height: 20 }}
                            />
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption" sx={{ color: '#94a3b8' }}>
                              {JSON.stringify(ent.attributes)}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption" sx={{ color: '#38bdf8' }}>
                              {pathObj ? pathObj.steps.join(' → ') : '-'}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          )}
        </Paper>
      )}

      {/* Tab 3: Warm Introduction Navigator */}
      {activeTab === 2 && (
        <Paper sx={{ p: 3, bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, color: '#f8fafc', mb: 1 }}>
            Warm Introduction & Degree of Separation Navigator
          </Typography>
          <Typography variant="body2" sx={{ color: '#94a3b8', mb: 3 }}>
            Identifies mutual colleagues, alumni networks, and shared investment bridges to calculate optimal warm introduction paths.
          </Typography>

          <Grid container spacing={2} sx={{ mb: 3, alignItems: 'center' }}>
            <Grid item xs={12} sm={4}>
              <FormControl fullWidth size="small">
                <InputLabel sx={{ color: '#94a3b8' }}>Source Contact / Executive</InputLabel>
                <Select
                  value={sourceNodeId}
                  onChange={(e) => setSourceNodeId(e.target.value)}
                  label="Source Contact / Executive"
                  sx={{ color: '#f8fafc', bgcolor: '#090d16', '& .MuiOutlinedInput-notchedOutline': { borderColor: '#334155' } }}
                >
                  <MenuItem value="person_sarah">Sarah Jenkins (CTO, Odoo AU)</MenuItem>
                  <MenuItem value="person_alex">Alex Rivera (VP Eng, Atlassian)</MenuItem>
                  <MenuItem value="person_david">David Chen (Head of Eng, Nexus)</MenuItem>
                  <MenuItem value="person_emily">Emily Zhang (ERP Architect, Nexus)</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={4}>
              <FormControl fullWidth size="small">
                <InputLabel sx={{ color: '#94a3b8' }}>Target Decision-Maker</InputLabel>
                <Select
                  value={targetNodeId}
                  onChange={(e) => setTargetNodeId(e.target.value)}
                  label="Target Decision-Maker"
                  sx={{ color: '#f8fafc', bgcolor: '#090d16', '& .MuiOutlinedInput-notchedOutline': { borderColor: '#334155' } }}
                >
                  <MenuItem value="person_david">David Chen (Head of Eng, Nexus)</MenuItem>
                  <MenuItem value="person_sarah">Sarah Jenkins (CTO, Odoo AU)</MenuItem>
                  <MenuItem value="person_alex">Alex Rivera (VP Eng, Atlassian)</MenuItem>
                  <MenuItem value="person_emily">Emily Zhang (ERP Architect, Nexus)</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={4}>
              <Button
                fullWidth
                variant="contained"
                onClick={handleFindPath}
                disabled={loadingPath || sourceNodeId === targetNodeId}
                startIcon={loadingPath ? <CircularProgress size={16} /> : <Share2 size={16} />}
                sx={{ bgcolor: '#0284c7', '&:hover': { bgcolor: '#0369a1' }, height: 40 }}
              >
                Find Warm Intro Path
              </Button>
            </Grid>
          </Grid>

          {/* Path result card */}
          {pathResult && pathResult.found && (
            <Card sx={{ bgcolor: '#090d16', border: '1px solid #1e293b', p: 3, borderRadius: 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Box>
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, color: '#38bdf8' }}>
                    Optimal Introduction Route Found
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#94a3b8' }}>
                    Separation: <strong>{pathResult.degree_of_separation} Degrees</strong> • Overall Confidence: <strong>{(pathResult.confidence_score * 100).toFixed(1)}%</strong>
                  </Typography>
                </Box>
                <Chip
                  icon={<ShieldCheck size={16} />}
                  label="Verified High-Confidence Intro"
                  sx={{ bgcolor: '#065f46', color: '#34d399', fontWeight: 600 }}
                />
              </Box>

              {/* Path timeline */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, overflowX: 'auto', py: 2 }}>
                {pathResult.path_nodes.map((node, idx) => (
                  <React.Fragment key={node.id}>
                    <Paper sx={{ p: 2, bgcolor: '#1e293b', border: '1px solid #334155', minWidth: 200 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                        {getNodeIcon(node.node_type)}
                        <Typography variant="subtitle2" sx={{ fontWeight: 700, color: '#f8fafc' }}>
                          {node.name}
                        </Typography>
                      </Box>
                      <Typography variant="caption" sx={{ color: '#38bdf8', display: 'block' }}>
                        {node.attributes.title || node.node_type}
                      </Typography>
                      {node.attributes.email && (
                        <Typography variant="caption" sx={{ color: '#64748b', display: 'block' }}>
                          {node.attributes.email}
                        </Typography>
                      )}
                    </Paper>
                    {idx < pathResult.path_nodes.length - 1 && (
                      <Box sx={{ textAlign: 'center', minWidth: 80 }}>
                        <ArrowRight size={20} color="#38bdf8" />
                        <Typography variant="caption" sx={{ color: '#94a3b8', display: 'block', fontSize: 10 }}>
                          {pathResult.path_edges[idx]?.relationship_type || 'CONNECTED'}
                        </Typography>
                      </Box>
                    )}
                  </React.Fragment>
                ))}
              </Box>
            </Card>
          )}
        </Paper>
      )}

      {/* Tab 4: Centrality & Influence */}
      {activeTab === 3 && (
        <Paper sx={{ p: 3, bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 700, color: '#f8fafc' }}>
                Executive & Company Graph Centrality Leaderboard
              </Typography>
              <Typography variant="body2" sx={{ color: '#94a3b8' }}>
                PageRank authority, normalized connection density, and algorithmic influence tiers.
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', gap: 1 }}>
              {['ALL', 'PERSON', 'COMPANY'].map((t) => (
                <Button
                  key={t}
                  size="small"
                  variant={centralityType === t ? 'contained' : 'outlined'}
                  onClick={() => setCentralityType(t)}
                  sx={{
                    bgcolor: centralityType === t ? '#0284c7' : 'transparent',
                    borderColor: '#334155',
                    color: '#f8fafc'
                  }}
                >
                  {t}
                </Button>
              ))}
            </Box>
          </Box>

          <TableContainer component={Paper} sx={{ bgcolor: '#090d16', border: '1px solid #1e293b' }}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ '& th': { color: '#94a3b8', fontWeight: 600 } }}>
                  <TableCell>Rank</TableCell>
                  <TableCell>Entity Name</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Influence Tier</TableCell>
                  <TableCell>PageRank Score</TableCell>
                  <TableCell>Degree Centrality</TableCell>
                  <TableCell>Connections</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {influencers.map((inf, idx) => (
                  <TableRow key={inf.node_id} sx={{ '& td': { color: '#cbd5e1' } }}>
                    <TableCell sx={{ fontWeight: 700, color: '#f8fafc' }}>#{idx + 1}</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>{inf.name}</TableCell>
                    <TableCell>
                      <Chip
                        label={inf.node_type}
                        size="small"
                        sx={{ bgcolor: getNodeBadgeColor(inf.node_type), color: '#fff', fontSize: 10, height: 20 }}
                      />
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={inf.influence_tier}
                        size="small"
                        variant="outlined"
                        sx={{ borderColor: '#38bdf8', color: '#38bdf8', fontWeight: 600, fontSize: 11 }}
                      />
                    </TableCell>
                    <TableCell sx={{ fontFamily: 'monospace', color: '#38bdf8' }}>
                      {inf.pagerank_score.toFixed(6)}
                    </TableCell>
                    <TableCell sx={{ fontFamily: 'monospace' }}>
                      {inf.degree_centrality.toFixed(4)}
                    </TableCell>
                    <TableCell>{inf.total_connections} edges</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {/* Tab 5: Hybrid Federated Search */}
      {activeTab === 4 && (
        <Paper sx={{ p: 3, bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, color: '#f8fafc', mb: 1 }}>
            Hybrid Federated Search Tester
          </Typography>
          <Typography variant="body2" sx={{ color: '#94a3b8', mb: 3 }}>
            Tune weights for Lexical BM25, Vector semantic similarity, and Graph centrality boost to analyze multi-factor scoring.
          </Typography>

          {/* Search bar & sliders */}
          <Grid container spacing={3} sx={{ mb: 3 }}>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Federated Search Query"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                sx={{ bgcolor: '#090d16', input: { color: '#f8fafc' }, label: { color: '#94a3b8' } }}
              />
              <Button
                variant="contained"
                onClick={handleHybridSearch}
                disabled={loadingSearch}
                startIcon={loadingSearch ? <CircularProgress size={16} /> : <Search size={16} />}
                sx={{ bgcolor: '#0284c7', '&:hover': { bgcolor: '#0369a1' }, mt: 2, height: 40 }}
              >
                Run Hybrid Search
              </Button>
            </Grid>
            <Grid item xs={12} md={6}>
              <Box sx={{ p: 2, bgcolor: '#090d16', borderRadius: 1.5, border: '1px solid #1e293b' }}>
                <Typography variant="caption" sx={{ color: '#94a3b8', fontWeight: 600 }}>
                  LEXICAL WEIGHT: {(lexicalWeight * 100).toFixed(0)}%
                </Typography>
                <Slider
                  value={lexicalWeight}
                  onChange={(_, val) => setLexicalWeight(val as number)}
                  min={0.1}
                  max={0.8}
                  step={0.05}
                  size="small"
                  sx={{ color: '#38bdf8' }}
                />
                <Typography variant="caption" sx={{ color: '#94a3b8', fontWeight: 600 }}>
                  VECTOR SEMANTIC WEIGHT: {(vectorWeight * 100).toFixed(0)}%
                </Typography>
                <Slider
                  value={vectorWeight}
                  onChange={(_, val) => setVectorWeight(val as number)}
                  min={0.1}
                  max={0.8}
                  step={0.05}
                  size="small"
                  sx={{ color: '#8b5cf6' }}
                />
                <Typography variant="caption" sx={{ color: '#94a3b8', fontWeight: 600 }}>
                  GRAPH CENTRALITY WEIGHT: {(graphWeight * 100).toFixed(0)}%
                </Typography>
                <Slider
                  value={graphWeight}
                  onChange={(_, val) => setGraphWeight(val as number)}
                  min={0.1}
                  max={0.8}
                  step={0.05}
                  size="small"
                  sx={{ color: '#10b981' }}
                />
              </Box>
            </Grid>
          </Grid>

          {/* Results table */}
          {searchResults.length > 0 && (
            <TableContainer component={Paper} sx={{ bgcolor: '#090d16', border: '1px solid #1e293b' }}>
              <Table size="small">
                <TableHead>
                  <TableRow sx={{ '& th': { color: '#94a3b8', fontWeight: 600 } }}>
                    <TableCell>Rank</TableCell>
                    <TableCell>Entity Name</TableCell>
                    <TableCell>Type</TableCell>
                    <TableCell>Final Blended Score</TableCell>
                    <TableCell>Score Breakdown (Lex / Vec / Graph)</TableCell>
                    <TableCell>Explanation</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {searchResults.map((res, idx) => (
                    <TableRow key={res.node_id} sx={{ '& td': { color: '#cbd5e1' } }}>
                      <TableCell sx={{ fontWeight: 700, color: '#f8fafc' }}>#{idx + 1}</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>{res.name}</TableCell>
                      <TableCell>
                        <Chip
                          label={res.node_type}
                          size="small"
                          sx={{ bgcolor: getNodeBadgeColor(res.node_type), color: '#fff', fontSize: 10, height: 20 }}
                        />
                      </TableCell>
                      <TableCell sx={{ fontWeight: 700, color: '#38bdf8', fontFamily: 'monospace' }}>
                        {(res.final_score * 100).toFixed(1)}%
                      </TableCell>
                      <TableCell sx={{ fontFamily: 'monospace', fontSize: 12 }}>
                        {res.lexical_score.toFixed(2)} / {res.vector_score.toFixed(2)} / {res.graph_score.toFixed(2)}
                      </TableCell>
                      <TableCell sx={{ color: '#94a3b8', fontSize: 12 }}>
                        {res.explanation}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Paper>
      )}

      {/* Tab 6: Topology & Seed Graph */}
      {activeTab === 5 && (
        <Paper sx={{ p: 3, bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, color: '#f8fafc', mb: 2 }}>
            Graph Topology Health & Enterprise Seed Catalog
          </Typography>

          <Grid container spacing={3} sx={{ mb: 4 }}>
            <Grid item xs={12} sm={3}>
              <Card sx={{ bgcolor: '#090d16', border: '1px solid #1e293b' }}>
                <CardContent>
                  <Typography variant="caption" sx={{ color: '#94a3b8' }}>Total Entity Nodes</Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, color: '#38bdf8' }}>
                    {stats?.total_nodes || 0}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Card sx={{ bgcolor: '#090d16', border: '1px solid #1e293b' }}>
                <CardContent>
                  <Typography variant="caption" sx={{ color: '#94a3b8' }}>Total Directed Edges</Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, color: '#10b981' }}>
                    {stats?.total_edges || 0}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Card sx={{ bgcolor: '#090d16', border: '1px solid #1e293b' }}>
                <CardContent>
                  <Typography variant="caption" sx={{ color: '#94a3b8' }}>Graph Density</Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, color: '#f59e0b' }}>
                    {stats?.graph_density ? (stats.graph_density * 100).toFixed(2) + '%' : '0%'}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Card sx={{ bgcolor: '#090d16', border: '1px solid #1e293b' }}>
                <CardContent>
                  <Typography variant="caption" sx={{ color: '#94a3b8' }}>Connected Types</Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, color: '#8b5cf6' }}>
                    {stats ? Object.keys(stats.node_type_distribution).length : 0}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {stats && (
            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" sx={{ fontWeight: 600, color: '#cbd5e1', mb: 1 }}>
                  Node Type Distribution
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {Object.entries(stats.node_type_distribution).map(([type, count]) => (
                    <Box key={type} sx={{ display: 'flex', justifyContent: 'space-between', p: 1.5, bgcolor: '#090d16', borderRadius: 1 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {getNodeIcon(type)}
                        <Typography variant="body2" sx={{ color: '#f8fafc', fontWeight: 600 }}>{type}</Typography>
                      </Box>
                      <Chip label={`${count} nodes`} size="small" sx={{ bgcolor: getNodeBadgeColor(type), color: '#fff' }} />
                    </Box>
                  ))}
                </Box>
              </Grid>
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" sx={{ fontWeight: 600, color: '#cbd5e1', mb: 1 }}>
                  Relationship Edge Distribution
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {Object.entries(stats.edge_relationship_distribution).map(([rel, count]) => (
                    <Box key={rel} sx={{ display: 'flex', justifyContent: 'space-between', p: 1.5, bgcolor: '#090d16', borderRadius: 1 }}>
                      <Typography variant="body2" sx={{ color: '#38bdf8', fontWeight: 600 }}>{rel}</Typography>
                      <Chip label={`${count} relationships`} size="small" variant="outlined" sx={{ borderColor: '#334155', color: '#94a3b8' }} />
                    </Box>
                  ))}
                </Box>
              </Grid>
            </Grid>
          )}
        </Paper>
      )}
    </Box>
  );
}
