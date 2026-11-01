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
  Tooltip,
  Autocomplete,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem
} from '@mui/material';
import {
  Search,
  Plus,
  Check,
  Building,
  UserCheck,
  Mail,
  Phone,
  Globe,
  ExternalLink,
  ShieldCheck,
  Filter,
  BookmarkCheck,
  Sparkles
} from 'lucide-react';

interface SearchCriteria {
  category: string;
  value: string;
}

interface SearchResultLead {
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
  source_name: string;
  source_url?: string;
  evidence?: string;
  search_keyword?: string;
  is_saved: boolean;
  saved_id?: string;
}

interface SuggestionItem {
  category: string;
  value: string;
  label: string;
}

interface B2BLeadSearchWorkspaceProps {
  onLeadSaved?: () => void;
  onNavigateToSaved?: () => void;
}

export const B2BLeadSearchWorkspace: React.FC<B2BLeadSearchWorkspaceProps> = ({
  onLeadSaved,
  onNavigateToSaved
}) => {
  const [query, setQuery] = useState('Enterprise Cloud Australia');
  const [criteria, setCriteria] = useState<SearchCriteria[]>([
    { category: 'Location', value: 'Australia' },
    { category: 'Industry', value: 'Software & Cloud' }
  ]);
  const [suggestions, setSuggestions] = useState<SuggestionItem[]>([]);
  const [isSearchingSuggestions, setIsSearchingSuggestions] = useState(false);
  
  const [results, setResults] = useState<SearchResultLead[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [savingLeadIds, setSavingLeadIds] = useState<Record<string, boolean>>({});
  const [feedbackMessage, setFeedbackMessage] = useState<{ type: 'success' | 'info' | 'error'; text: string } | null>(null);

  // Criteria Dialog State
  const [criteriaDialogOpen, setCriteriaDialogOpen] = useState(false);
  const [newCriteriaCategory, setNewCriteriaCategory] = useState('Technology');
  const [newCriteriaValue, setNewCriteriaValue] = useState('');

  // Fetch suggestions with debounce
  useEffect(() => {
    if (!query.trim() || query.length < 2) {
      setSuggestions([]);
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearchingSuggestions(true);
      try {
        const res = await fetch(`/api/search/suggestions?q=${encodeURIComponent(query.trim())}`);
        if (res.ok) {
          const data = await res.json();
          setSuggestions(data.suggestions || []);
        }
      } catch (err) {
        console.error('Failed to load suggestions:', err);
      } finally {
        setIsSearchingSuggestions(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [query]);

  // Execute universal search
  const handleExecuteSearch = useCallback(async () => {
    setIsLoading(true);
    setFeedbackMessage(null);
    try {
      const res = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query.trim(),
          criteria: criteria,
          limit: 30,
          offset: 0
        })
      });

      if (!res.ok) {
        throw new Error(`Search error ${res.status}: ${res.statusText}`);
      }

      const data = await res.json();
      setResults(data.results || []);
      setTotalResults(data.total || 0);

      if ((data.results || []).length === 0) {
        setFeedbackMessage({
          type: 'info',
          text: 'No leads matched current criteria. Try adjusting keywords or location.'
        });
      }
    } catch (err: any) {
      setFeedbackMessage({
        type: 'error',
        text: err.message || 'Search execution failed.'
      });
    } finally {
      setIsLoading(false);
    }
  }, [query, criteria]);

  // Run initial search once on mount
  useEffect(() => {
    handleExecuteSearch();
  }, [handleExecuteSearch]);

  // Add explicit lead to PostgreSQL
  const handleAddLead = async (lead: SearchResultLead) => {
    const leadKey = `${lead.company_id}_${lead.contact_id || 'org'}`;
    setSavingLeadIds(prev => ({ ...prev, [leadKey]: true }));

    try {
      const res = await fetch('/api/leads/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_id: lead.company_id,
          contact_id: lead.contact_id,
          source_name: lead.source_name || 'Public Web Intelligence',
          source_url: lead.source_url || (lead.domain ? `https://${lead.domain}` : undefined),
          evidence: lead.evidence || 'Verified entity record',
          search_keyword: query
        })
      });

      if (!res.ok) {
        throw new Error(`Failed to save lead: ${res.statusText}`);
      }

      const savedData = await res.json();

      // Update local state to show Added
      setResults(prev =>
        prev.map(item => {
          if (item.company_id === lead.company_id && item.contact_id === lead.contact_id) {
            return { ...item, is_saved: true, saved_id: savedData.saved_id };
          }
          return item;
        })
      );

      setFeedbackMessage({
        type: 'success',
        text: `Lead for "${lead.company_name}" added to PostgreSQL Saved Leads.`
      });

      if (onLeadSaved) {
        onLeadSaved();
      }
    } catch (err: any) {
      setFeedbackMessage({
        type: 'error',
        text: err.message || 'Could not save lead.'
      });
    } finally {
      setSavingLeadIds(prev => ({ ...prev, [leadKey]: false }));
    }
  };

  const handleRemoveCriteria = (index: number) => {
    setCriteria(prev => prev.filter((_, i) => i !== index));
  };

  const handleAddCriteriaConfirm = () => {
    if (newCriteriaValue.trim()) {
      setCriteria(prev => [...prev, { category: newCriteriaCategory, value: newCriteriaValue.trim() }]);
      setNewCriteriaValue('');
      setCriteriaDialogOpen(false);
    }
  };

  return (
    <Box sx={{ maxWidth: 1400, mx: 'auto', p: 3 }}>
      {/* Search Header Banner */}
      <Paper
        elevation={0}
        sx={{
          p: 3.5,
          mb: 3,
          borderRadius: 3,
          background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
          border: '1px solid #334155'
        }}
      >
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
              <Sparkles size={24} color="#38bdf8" />
              <Typography variant="h5" sx={{ fontWeight: 800, color: '#f8fafc', letterSpacing: -0.5 }}>
                LeadNexus AI X — Universal B2B Lead Search
              </Typography>
            </Box>
            <Typography variant="body2" sx={{ color: '#94a3b8' }}>
              Search verified companies and decision-makers across public registries, official records, and web intelligence.
            </Typography>
          </Box>
          {onNavigateToSaved && (
            <Button
              variant="outlined"
              startIcon={<BookmarkCheck size={18} />}
              onClick={onNavigateToSaved}
              sx={{
                borderColor: '#38bdf8',
                color: '#38bdf8',
                textTransform: 'none',
                fontWeight: 600,
                borderRadius: 2,
                '&:hover': { bgcolor: 'rgba(56, 189, 248, 0.1)', borderColor: '#38bdf8' }
              }}
            >
              Open Saved Leads
            </Button>
          )}
        </Box>

        {/* Global Search Bar with Autocomplete Suggestions */}
        <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
          <Autocomplete
            freeSolo
            fullWidth
            options={suggestions}
            getOptionLabel={(option) => (typeof option === 'string' ? option : option.label)}
            onInputChange={(_, value) => setQuery(value)}
            onChange={(_, val) => {
              if (val && typeof val !== 'string') {
                setCriteria(prev => [...prev, { category: val.category, value: val.value }]);
              }
            }}
            renderOption={(props, option) => (
              <li {...props} key={`${option.category}-${option.value}`}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 0.5 }}>
                  <Chip
                    label={option.category}
                    size="small"
                    sx={{
                      fontSize: 10,
                      height: 20,
                      fontWeight: 700,
                      bgcolor: '#0284c7',
                      color: '#ffffff'
                    }}
                  />
                  <Typography variant="body2" sx={{ fontWeight: 600, color: '#f8fafc' }}>
                    {option.value}
                  </Typography>
                </Box>
              </li>
            )}
            renderInput={(params) => (
              <TextField
                {...params}
                placeholder="Search by company name, technology (e.g. Odoo), industry, or location..."
                variant="outlined"
                value={query}
                InputProps={{
                  ...params.InputProps,
                  startAdornment: (
                    <InputAdornment position="start">
                      <Search size={20} color="#94a3b8" />
                    </InputAdornment>
                  ),
                  endAdornment: (
                    <>
                      {isSearchingSuggestions ? <CircularProgress color="inherit" size={18} /> : null}
                      {params.InputProps.endAdornment}
                    </>
                  ),
                  sx: {
                    bgcolor: '#0b1329',
                    color: '#f8fafc',
                    borderRadius: 2,
                    fontSize: 15,
                    border: '1px solid #334155',
                    '& fieldset': { border: 'none' }
                  }
                }}
              />
            )}
          />

          <Button
            variant="contained"
            onClick={handleExecuteSearch}
            disabled={isLoading}
            sx={{
              px: 4,
              borderRadius: 2,
              bgcolor: '#0284c7',
              fontWeight: 700,
              textTransform: 'none',
              fontSize: 15,
              '&:hover': { bgcolor: '#0369a1' }
            }}
          >
            {isLoading ? <CircularProgress size={22} color="inherit" /> : 'Confirm & Search'}
          </Button>
        </Box>

        {/* Selected Criteria Badges */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
          <Typography variant="caption" sx={{ color: '#94a3b8', fontWeight: 600 }}>
            Active Search Criteria:
          </Typography>
          {criteria.map((item, idx) => (
            <Chip
              key={idx}
              label={`${item.category}: ${item.value}`}
              onDelete={() => handleRemoveCriteria(idx)}
              sx={{
                bgcolor: '#1e293b',
                color: '#38bdf8',
                border: '1px solid #0284c7',
                fontWeight: 600,
                fontSize: 12,
                borderRadius: 1.5,
                '& .MuiChip-deleteIcon': {
                  color: '#38bdf8',
                  '&:hover': { color: '#f87171' }
                }
              }}
            />
          ))}
          <Button
            size="small"
            startIcon={<Plus size={14} />}
            onClick={() => setCriteriaDialogOpen(true)}
            sx={{
              color: '#94a3b8',
              fontSize: 12,
              textTransform: 'none',
              border: '1px dashed #475569',
              borderRadius: 1.5,
              px: 1.5,
              py: 0.5,
              '&:hover': { color: '#f8fafc', borderColor: '#94a3b8' }
            }}
          >
            Add Filter Criterion
          </Button>
        </Box>
      </Paper>

      {/* Invariant Reminder Banner */}
      <Alert
        severity="info"
        sx={{
          mb: 3,
          bgcolor: '#0b192c',
          color: '#bae6fd',
          border: '1px solid #0369a1',
          '& .MuiAlert-icon': { color: '#38bdf8' }
        }}
      >
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          Strict Data Isolation Active:
        </Typography>
        Search results below are temporary. Only leads where you explicitly click <strong>"Add"</strong> are persisted to PostgreSQL and will appear on the Saved Leads export table.
      </Alert>

      {/* Feedback Messages */}
      {feedbackMessage && (
        <Alert
          severity={feedbackMessage.type}
          onClose={() => setFeedbackMessage(null)}
          sx={{ mb: 3 }}
        >
          {feedbackMessage.text}
        </Alert>
      )}

      {/* Results Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6" sx={{ fontWeight: 700, color: '#f8fafc' }}>
          Search Results ({totalResults})
        </Typography>
        <Typography variant="caption" sx={{ color: '#64748b' }}>
          Displaying verified company and executive profiles
        </Typography>
      </Box>

      {/* Results Table */}
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
              <TableCell sx={{ color: '#94a3b8', fontWeight: 700, fontSize: 13 }}>Location & Industry</TableCell>
              <TableCell sx={{ color: '#94a3b8', fontWeight: 700, fontSize: 13 }}>Decision Maker</TableCell>
              <TableCell sx={{ color: '#94a3b8', fontWeight: 700, fontSize: 13 }}>Contact Details</TableCell>
              <TableCell sx={{ color: '#94a3b8', fontWeight: 700, fontSize: 13 }}>Source & Evidence</TableCell>
              <TableCell align="right" sx={{ color: '#94a3b8', fontWeight: 700, fontSize: 13 }}>Action</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={6} align="center" sx={{ py: 6 }}>
                  <CircularProgress size={36} sx={{ color: '#38bdf8' }} />
                  <Typography variant="body2" sx={{ color: '#94a3b8', mt: 2 }}>
                    Querying enterprise discovery indices & public registries...
                  </Typography>
                </TableCell>
              </TableRow>
            ) : results.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center" sx={{ py: 6, color: '#94a3b8' }}>
                  No leads found. Enter a keyword or click Confirm & Search above.
                </TableCell>
              </TableRow>
            ) : (
              results.map((lead) => {
                const leadKey = `${lead.company_id}_${lead.contact_id || 'org'}`;
                const isSaving = savingLeadIds[leadKey];

                return (
                  <TableRow
                    key={leadKey}
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

                    {/* Location & Industry */}
                    <TableCell>
                      <Typography variant="body2" sx={{ color: '#e2e8f0', fontWeight: 500 }}>
                        {lead.city ? `${lead.city}, ${lead.country}` : lead.country || 'Global'}
                      </Typography>
                      <Typography variant="caption" sx={{ color: '#94a3b8' }}>
                        {lead.industry || 'Enterprise Technology'}
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
                          Company Profile (No Contact Assigned)
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
                            Public Domain Verification
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

                    {/* Action: Add vs Added */}
                    <TableCell align="right">
                      {lead.is_saved ? (
                        <Chip
                          icon={<Check size={14} color="#10b981" />}
                          label="Added"
                          size="small"
                          sx={{
                            bgcolor: 'rgba(16, 185, 129, 0.15)',
                            color: '#10b981',
                            fontWeight: 700,
                            border: '1px solid #10b981',
                            px: 1
                          }}
                        />
                      ) : (
                        <Button
                          variant="contained"
                          size="small"
                          startIcon={isSaving ? <CircularProgress size={14} color="inherit" /> : <Plus size={14} />}
                          onClick={() => handleAddLead(lead)}
                          disabled={isSaving}
                          sx={{
                            bgcolor: '#0284c7',
                            color: '#ffffff',
                            fontWeight: 700,
                            textTransform: 'none',
                            fontSize: 12,
                            borderRadius: 1.5,
                            '&:hover': { bgcolor: '#0369a1' }
                          }}
                        >
                          Add
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Add Criteria Dialog */}
      <Dialog
        open={criteriaDialogOpen}
        onClose={() => setCriteriaDialogOpen(false)}
        PaperProps={{
          sx: { bgcolor: '#0f172a', border: '1px solid #1e293b', borderRadius: 2, minWidth: 420 }
        }}
      >
        <DialogTitle sx={{ color: '#f8fafc', fontWeight: 700 }}>Add Filter Criterion</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <FormControl fullWidth size="small">
            <InputLabel sx={{ color: '#94a3b8' }}>Category</InputLabel>
            <Select
              value={newCriteriaCategory}
              label="Category"
              onChange={(e) => setNewCriteriaCategory(e.target.value)}
              sx={{ bgcolor: '#0b1329', color: '#f8fafc', '& .MuiOutlinedInput-notchedOutline': { borderColor: '#334155' } }}
            >
              <MenuItem value="Keyword">Keyword</MenuItem>
              <MenuItem value="Location">Location</MenuItem>
              <MenuItem value="Industry">Industry</MenuItem>
              <MenuItem value="Technology">Technology</MenuItem>
              <MenuItem value="Job Title">Job Title</MenuItem>
              <MenuItem value="Company Type">Company Type</MenuItem>
            </Select>
          </FormControl>

          <TextField
            fullWidth
            size="small"
            label="Filter Value"
            placeholder="e.g. Australia, Odoo, VP of Sales..."
            value={newCriteriaValue}
            onChange={(e) => setNewCriteriaValue(e.target.value)}
            InputLabelProps={{ sx: { color: '#94a3b8' } }}
            InputProps={{
              sx: { bgcolor: '#0b1329', color: '#f8fafc', '& fieldset': { borderColor: '#334155' } }
            }}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2, borderTop: '1px solid #1e293b' }}>
          <Button onClick={() => setCriteriaDialogOpen(false)} sx={{ color: '#94a3b8' }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleAddCriteriaConfirm}
            sx={{ bgcolor: '#0284c7', fontWeight: 700 }}
          >
            Add Criterion
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default B2BLeadSearchWorkspace;

