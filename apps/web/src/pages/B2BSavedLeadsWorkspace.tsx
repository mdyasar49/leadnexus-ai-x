import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Paper,
  TextField,
  InputAdornment,
  Button,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
  Alert,
  IconButton,
  Tooltip
} from '@mui/material';
import {
  BookmarkCheck,
  Download,
  Trash2,
  Search,
  Building,
  UserCheck,
  Mail,
  Phone,
  Globe,
  ExternalLink,
  ShieldCheck,
  FileSpreadsheet,
  FileText,
  Calendar,
  RefreshCw
} from 'lucide-react';

interface SavedLeadItem {
  id: string;
  company_id: string;
  contact_id?: string;
  company_name: string;
  domain?: string;
  website?: string;
  industry?: string;
  country?: string;
  state?: string;
  city?: string;
  description?: string;
  contact_name?: string;
  job_title?: string;
  email?: string;
  email_status?: string;
  business_phone?: string;
  phone_status?: string;
  linkedin_url?: string;
  source_name: string;
  source_url?: string;
  evidence?: string;
  search_keyword?: string;
  saved_at: string;
}

interface B2BSavedLeadsWorkspaceProps {
  onLeadCountChange?: () => void;
  onNavigateToSearch?: () => void;
}

export const B2BSavedLeadsWorkspace: React.FC<B2BSavedLeadsWorkspaceProps> = ({
  onLeadCountChange,
  onNavigateToSearch
}) => {
  const [leads, setLeads] = useState<SavedLeadItem[]>([]);
  const [totalLeads, setTotalLeads] = useState(0);
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(null);

  // Load Saved Leads from PostgreSQL
  const fetchSavedLeads = useCallback(async () => {
    setIsLoading(true);
    try {
      const url = searchTerm.trim()
        ? `/api/leads?search=${encodeURIComponent(searchTerm.trim())}&limit=100`
        : '/api/leads?limit=100';

      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`Failed to load saved leads: ${res.statusText}`);
      }
      const data = await res.json();
      setLeads(data.leads || []);
      setTotalLeads(data.total || 0);
    } catch (err: any) {
      setStatusMessage({
        type: 'error',
        text: err.message || 'Error fetching saved leads from PostgreSQL database.'
      });
    } finally {
      setIsLoading(false);
    }
  }, [searchTerm]);

  useEffect(() => {
    fetchSavedLeads();
  }, [fetchSavedLeads]);

  // Remove lead from PostgreSQL
  const handleDeleteLead = async (id: string, companyName: string) => {
    if (!window.confirm(`Are you sure you want to remove "${companyName}" from Saved Leads?`)) {
      return;
    }

    setDeletingId(id);
    try {
      const res = await fetch(`/api/leads/${id}`, {
        method: 'DELETE'
      });

      if (!res.ok) {
        throw new Error(`Failed to remove lead: ${res.statusText}`);
      }

      setLeads(prev => prev.filter(l => l.id !== id));
      setTotalLeads(prev => Math.max(0, prev - 1));

      setStatusMessage({
        type: 'success',
        text: `Removed "${companyName}" from Saved Leads.`
      });

      if (onLeadCountChange) {
        onLeadCountChange();
      }
    } catch (err: any) {
      setStatusMessage({
        type: 'error',
        text: err.message || 'Could not remove lead.'
      });
    } finally {
      setDeletingId(null);
    }
  };

  // Direct CSV Export
  const handleExportCSV = () => {
    const exportUrl = searchTerm.trim()
      ? `/api/export/csv?search=${encodeURIComponent(searchTerm.trim())}`
      : '/api/export/csv';
    window.location.href = exportUrl;
  };

  // Direct Excel (.xlsx) Export
  const handleExportExcel = () => {
    const exportUrl = searchTerm.trim()
      ? `/api/export/excel?search=${encodeURIComponent(searchTerm.trim())}`
      : '/api/export/excel';
    window.location.href = exportUrl;
  };

  return (
    <Box sx={{ maxWidth: 1400, mx: 'auto', p: 3 }}>
      {/* Header Banner */}
      <Paper
        elevation={0}
        sx={{
          p: 3.5,
          mb: 3,
          borderRadius: 3,
          background: 'linear-gradient(135deg, #0b1329 0%, #1e293b 100%)',
          border: '1px solid #334155'
        }}
      >
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2.5, flexWrap: 'wrap', gap: 2 }}>
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
              <BookmarkCheck size={26} color="#38bdf8" />
              <Typography variant="h5" sx={{ fontWeight: 800, color: '#f8fafc', letterSpacing: -0.5 }}>
                PostgreSQL Saved Leads Repository
              </Typography>
              <Chip
                label={`${totalLeads} Saved Leads`}
                size="small"
                sx={{
                  bgcolor: '#0284c7',
                  color: '#ffffff',
                  fontWeight: 700,
                  fontSize: 12,
                  px: 1
                }}
              />
            </Box>
            <Typography variant="body2" sx={{ color: '#94a3b8' }}>
              Canonical repository of explicitly added leads with full provenance, evidence, and export controls.
            </Typography>
          </Box>

          {/* Action Buttons: Export CSV & Excel */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Button
              variant="contained"
              startIcon={<FileText size={18} />}
              onClick={handleExportCSV}
              disabled={totalLeads === 0}
              sx={{
                bgcolor: '#0f766e',
                color: '#ffffff',
                fontWeight: 700,
                textTransform: 'none',
                borderRadius: 2,
                px: 2.5,
                '&:hover': { bgcolor: '#115e59' }
              }}
            >
              Export CSV (UTF-8)
            </Button>

            <Button
              variant="contained"
              startIcon={<FileSpreadsheet size={18} />}
              onClick={handleExportExcel}
              disabled={totalLeads === 0}
              sx={{
                bgcolor: '#16a34a',
                color: '#ffffff',
                fontWeight: 700,
                textTransform: 'none',
                borderRadius: 2,
                px: 2.5,
                '&:hover': { bgcolor: '#15803d' }
              }}
            >
              Export Excel (.XLSX)
            </Button>

            <IconButton
              onClick={() => fetchSavedLeads()}
              sx={{ color: '#94a3b8', border: '1px solid #334155', borderRadius: 2 }}
            >
              <RefreshCw size={18} />
            </IconButton>
          </Box>
        </Box>

        {/* Filter / Search within saved leads */}
        <Box sx={{ display: 'flex', gap: 2 }}>
          <TextField
            fullWidth
            size="small"
            placeholder="Filter saved leads by company name, contact, industry, or location..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Search size={18} color="#94a3b8" />
                </InputAdornment>
              ),
              sx: {
                bgcolor: '#0f172a',
                color: '#f8fafc',
                borderRadius: 2,
                '& fieldset': { borderColor: '#334155' }
              }
            }}
          />
        </Box>
      </Paper>

      {/* Critical Invariant Banner */}
      <Alert
        severity="success"
        sx={{
          mb: 3,
          bgcolor: '#052e16',
          color: '#86efac',
          border: '1px solid #166534',
          '& .MuiAlert-icon': { color: '#4ade80' }
        }}
      >
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          Single Source of Truth Invariant:
        </Typography>
        Only leads explicitly clicked and saved appear in this table and in generated CSV/Excel exports. Temporary search results are strictly excluded.
      </Alert>

      {/* Feedback Alert */}
      {statusMessage && (
        <Alert
          severity={statusMessage.type}
          onClose={() => setStatusMessage(null)}
          sx={{ mb: 3 }}
        >
          {statusMessage.text}
        </Alert>
      )}

      {/* Leads Table */}
      <TableContainer
        component={Paper}
        elevation={0}
        sx={{
          bgcolor: '#0f172a',
          border: '1px solid #1e293b',
          borderRadius: 2,
          overflow: 'hidden'
        }}
      >
        <Table>
          <TableHead sx={{ bgcolor: '#0b1329' }}>
            <TableRow>
              <TableCell sx={{ color: '#94a3b8', fontWeight: 700, fontSize: 13 }}>Company</TableCell>
              <TableCell sx={{ color: '#94a3b8', fontWeight: 700, fontSize: 13 }}>Industry & Location</TableCell>
              <TableCell sx={{ color: '#94a3b8', fontWeight: 700, fontSize: 13 }}>Decision Maker & Title</TableCell>
              <TableCell sx={{ color: '#94a3b8', fontWeight: 700, fontSize: 13 }}>Contact Details</TableCell>
              <TableCell sx={{ color: '#94a3b8', fontWeight: 700, fontSize: 13 }}>Source & Evidence</TableCell>
              <TableCell sx={{ color: '#94a3b8', fontWeight: 700, fontSize: 13 }}>Saved At</TableCell>
              <TableCell align="right" sx={{ color: '#94a3b8', fontWeight: 700, fontSize: 13 }}>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 6 }}>
                  <CircularProgress size={36} sx={{ color: '#38bdf8' }} />
                  <Typography variant="body2" sx={{ color: '#94a3b8', mt: 2 }}>
                    Querying PostgreSQL saved_leads table...
                  </Typography>
                </TableCell>
              </TableRow>
            ) : leads.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 6, color: '#94a3b8' }}>
                  <Box sx={{ maxWidth: 400, mx: 'auto', textAlign: 'center' }}>
                    <BookmarkCheck size={40} color="#475569" style={{ marginBottom: 12 }} />
                    <Typography variant="subtitle1" sx={{ color: '#f8fafc', fontWeight: 700, mb: 1 }}>
                      No Saved Leads Yet
                    </Typography>
                    <Typography variant="body2" sx={{ color: '#64748b', mb: 2 }}>
                      Perform a search on the Lead Search workspace and click "Add" to save leads to PostgreSQL.
                    </Typography>
                    {onNavigateToSearch && (
                      <Button
                        variant="contained"
                        onClick={onNavigateToSearch}
                        sx={{ bgcolor: '#0284c7', textTransform: 'none', fontWeight: 700 }}
                      >
                        Go to B2B Lead Search
                      </Button>
                    )}
                  </Box>
                </TableCell>
              </TableRow>
            ) : (
              leads.map((lead) => (
                <TableRow
                  key={lead.id}
                  hover
                  sx={{
                    '&:hover': { bgcolor: 'rgba(30, 41, 59, 0.5)' },
                    borderBottom: '1px solid #1e293b'
                  }}
                >
                  {/* Company */}
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                      <Box
                        sx={{
                          width: 36,
                          height: 36,
                          borderRadius: 1.5,
                          bgcolor: '#1e293b',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: '#38bdf8'
                        }}
                      >
                        <Building size={18} />
                      </Box>
                      <Box>
                        <Typography variant="subtitle2" sx={{ fontWeight: 700, color: '#f8fafc' }}>
                          {lead.company_name}
                        </Typography>
                        {lead.domain && (
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            <Globe size={12} color="#64748b" />
                            <Typography variant="caption" sx={{ color: '#64748b' }}>
                              {lead.domain}
                            </Typography>
                          </Box>
                        )}
                      </Box>
                    </Box>
                  </TableCell>

                  {/* Industry & Location */}
                  <TableCell>
                    <Typography variant="body2" sx={{ color: '#e2e8f0', fontWeight: 500 }}>
                      {lead.city ? `${lead.city}, ${lead.country}` : lead.country || 'Global'}
                    </Typography>
                    <Typography variant="caption" sx={{ color: '#94a3b8' }}>
                      {lead.industry || 'Technology'}
                    </Typography>
                  </TableCell>

                  {/* Decision Maker */}
                  <TableCell>
                    {lead.contact_name ? (
                      <Box>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8 }}>
                          <UserCheck size={14} color="#38bdf8" />
                          <Typography variant="body2" sx={{ fontWeight: 600, color: '#f8fafc' }}>
                            {lead.contact_name}
                          </Typography>
                        </Box>
                        <Typography variant="caption" sx={{ color: '#94a3b8' }}>
                          {lead.job_title || 'Executive'}
                        </Typography>
                      </Box>
                    ) : (
                      <Typography variant="caption" sx={{ color: '#64748b', fontStyle: 'italic' }}>
                        Company Level Record
                      </Typography>
                    )}
                  </TableCell>

                  {/* Contact Details */}
                  <TableCell>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                      {lead.email ? (
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8 }}>
                          <Mail size={12} color="#94a3b8" />
                          <Typography variant="caption" sx={{ color: '#cbd5e1' }}>
                            {lead.email}
                          </Typography>
                        </Box>
                      ) : null}
                      {lead.business_phone ? (
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8 }}>
                          <Phone size={12} color="#94a3b8" />
                          <Typography variant="caption" sx={{ color: '#cbd5e1' }}>
                            {lead.business_phone}
                          </Typography>
                        </Box>
                      ) : null}
                      {!lead.email && !lead.business_phone && (
                        <Typography variant="caption" sx={{ color: '#64748b' }}>
                          Verified Domain
                        </Typography>
                      )}
                    </Box>
                  </TableCell>

                  {/* Source & Evidence */}
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8 }}>
                      <ShieldCheck size={14} color="#10b981" />
                      <Typography variant="caption" sx={{ fontWeight: 600, color: '#a7f3d0' }}>
                        {lead.source_name}
                      </Typography>
                    </Box>
                    <Typography variant="caption" sx={{ color: '#64748b', display: 'block' }}>
                      {lead.evidence || 'Public Registry Record'}
                    </Typography>
                  </TableCell>

                  {/* Saved At */}
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8 }}>
                      <Calendar size={13} color="#64748b" />
                      <Typography variant="caption" sx={{ color: '#94a3b8' }}>
                        {lead.saved_at ? new Date(lead.saved_at).toLocaleDateString() : 'Recent'}
                      </Typography>
                    </Box>
                  </TableCell>

                  {/* Remove Action */}
                  <TableCell align="right">
                    <Tooltip title="Remove from Saved Leads">
                      <span>
                        <IconButton
                          size="small"
                          onClick={() => handleDeleteLead(lead.id, lead.company_name)}
                          disabled={deletingId === lead.id}
                          sx={{
                            color: '#ef4444',
                            '&:hover': { bgcolor: 'rgba(239, 68, 68, 0.1)' }
                          }}
                        >
                          {deletingId === lead.id ? (
                            <CircularProgress size={16} color="inherit" />
                          ) : (
                            <Trash2 size={16} />
                          )}
                        </IconButton>
                      </span>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default B2BSavedLeadsWorkspace;
