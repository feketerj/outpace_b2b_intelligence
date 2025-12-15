import React, { useEffect, useState } from 'react';
import { SuperAdminLayout } from '../components/layout/SuperAdminLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Badge } from '../components/ui/badge';
import axios from 'axios';
import { toast } from 'sonner';
import { Plus, Edit2, Trash2, Building2, Save, Palette, Code, Calendar, Zap } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function TenantsPage() {
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [editingTenant, setEditingTenant] = useState(null);
  const [formData, setFormData] = useState(getEmptyFormData());

  useEffect(() => {
    fetchTenants();
  }, []);

  function getEmptyFormData() {
    return {
      name: '',
      slug: '',
      status: 'active',
      is_master_client: false,
      branding: {
        logo_url: '',
        logo_base64: null,
        primary_color: 'hsl(210, 85%, 52%)',
        secondary_color: 'hsl(265, 60%, 55%)',
        accent_color: 'hsl(142, 70%, 45%)',
        text_color: 'hsl(0, 0%, 98%)'
      },
      search_profile: {
        naics_codes: [],
        keywords: [],
        interest_areas: [],
        competitors: [],
        highergov_api_key: '',
        highergov_search_id: '',
        fetch_full_documents: false,
        fetch_nsn: false,
        fetch_grants: true,
        fetch_contracts: true,
        auto_update_enabled: true,
        auto_update_interval_hours: 24
      },
      intelligence_config: {
        enabled: true,
        perplexity_prompt_template: '',
        schedule_cron: '0 2 * * *',
        lookback_days: 14,
        deadline_window_days: 120
      },
      agent_config: {
        scoring_agent_id: '',
        opportunities_chat_agent_id: '',
        intelligence_chat_agent_id: '',
        scoring_instructions: 'Analyze this contract opportunity and provide a relevance score and summary for the client.',
        opportunities_chat_instructions: 'You are a helpful assistant for contract opportunities.',
        intelligence_chat_instructions: 'You are a business intelligence analyst.'
      },
      scoring_weights: {
        value_weight: 0.4,
        deadline_weight: 0.3,
        relevance_weight: 0.3
      }
    };
  }

  const fetchTenants = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/tenants`);
      setTenants(response.data.data || []);
    } catch (error) {
      console.error('Failed to fetch tenants:', error);
      toast.error('Failed to load tenants');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenDialog = (tenant = null) => {
    if (tenant) {
      setEditingTenant(tenant);
      setFormData({
        name: tenant.name,
        slug: tenant.slug,
        status: tenant.status,
        is_master_client: tenant.is_master_client || false,
        branding: tenant.branding || getEmptyFormData().branding,
        search_profile: tenant.search_profile || getEmptyFormData().search_profile,
        intelligence_config: tenant.intelligence_config || getEmptyFormData().intelligence_config,
        agent_config: tenant.agent_config || getEmptyFormData().agent_config,
        scoring_weights: tenant.scoring_weights || getEmptyFormData().scoring_weights
      });
    } else {
      setEditingTenant(null);
      setFormData(getEmptyFormData());
    }
    setShowDialog(true);
  };

  const handleSaveTenant = async (e) => {
    e.preventDefault();
    
    try {
      if (editingTenant) {
        // Update existing tenant
        await axios.put(`${API_URL}/api/tenants/${editingTenant.id}`, formData);
        toast.success('Tenant updated successfully!');
      } else {
        // Create new tenant
        await axios.post(`${API_URL}/api/tenants`, formData);
        toast.success('Tenant created successfully!');
      }
      
      setShowDialog(false);
      setEditingTenant(null);
      setFormData(getEmptyFormData());
      fetchTenants();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save tenant');
    }
  };

  const handleDeleteTenant = async (tenantId, tenantName) => {
    if (!window.confirm(`Delete "${tenantName}" and ALL associated data?`)) return;

    try {
      await axios.delete(`${API_URL}/api/tenants/${tenantId}`);
      toast.success('Tenant deleted');
      fetchTenants();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Delete failed');
    }
  };

  const updateArrayField = (category, field, value) => {
    const items = value.split(',').map(s => s.trim()).filter(s => s);
    setFormData({
      ...formData,
      [category]: {
        ...formData[category],
        [field]: items
      }
    });
  };

  return (
    <SuperAdminLayout>
      <div className="p-6 md:p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-heading font-bold text-[hsl(var(--foreground))]">
              Tenant Management
            </h1>
            <p className="text-[hsl(var(--foreground-secondary))] mt-1">
              Configure client organizations, branding, and intelligence settings
            </p>
          </div>
          
          <Button 
            onClick={() => handleOpenDialog()}
            className="bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90"
            data-testid="create-tenant-button"
          >
            <Plus className="h-4 w-4 mr-2" />
            Create Tenant
          </Button>
        </div>

        {/* Tenants List */}
        {loading ? (
          <div className="text-center py-12 text-[hsl(var(--foreground-secondary))]">Loading...</div>
        ) : tenants.length === 0 ? (
          <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
            <CardContent className="py-12 text-center">
              <Building2 className="h-12 w-12 mx-auto mb-4 text-[hsl(var(--foreground-muted))]" />
              <h3 className="text-lg font-semibold text-[hsl(var(--foreground))] mb-2">No tenants yet</h3>
              <p className="text-[hsl(var(--foreground-secondary))] mb-4">Create your first client to get started</p>
              <Button 
                onClick={() => handleOpenDialog()}
                className="bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90"
              >
                <Plus className="h-4 w-4 mr-2" />
                Create Tenant
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {tenants.map((tenant) => (
              <Card 
                key={tenant.id} 
                className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))] hover:border-[hsl(var(--border-light))] transition-colors duration-150"
                data-testid={`tenant-card-${tenant.slug}`}
              >
                <CardContent className="p-6">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="text-xl font-semibold text-[hsl(var(--foreground))]">
                          {tenant.name}
                        </h3>
                        <Badge 
                          className={tenant.status === 'active' ? 'bg-[hsl(var(--accent-success))]' : 'bg-[hsl(var(--foreground-muted))]'}
                        >
                          {tenant.status}
                        </Badge>
                      </div>
                      <div className="grid grid-cols-2 gap-4 mt-4 text-sm">
                        <div>
                          <span className="text-[hsl(var(--foreground-muted))]">Slug:</span>
                          <span className="ml-2 font-mono text-[hsl(var(--foreground-secondary))]">{tenant.slug}</span>
                        </div>
                        <div>
                          <span className="text-[hsl(var(--foreground-muted))]">NAICS Codes:</span>
                          <span className="ml-2 text-[hsl(var(--foreground-secondary))]">
                            {tenant.search_profile?.naics_codes?.length || 0}
                          </span>
                        </div>
                        <div>
                          <span className="text-[hsl(var(--foreground-muted))]">Keywords:</span>
                          <span className="ml-2 text-[hsl(var(--foreground-secondary))]">
                            {tenant.search_profile?.keywords?.length || 0}
                          </span>
                        </div>
                        <div>
                          <span className="text-[hsl(var(--foreground-muted))]">Intelligence:</span>
                          <span className="ml-2 text-[hsl(var(--foreground-secondary))]">
                            {tenant.intelligence_config?.enabled ? '✓ Enabled' : '✗ Disabled'}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() => handleOpenDialog(tenant)}
                        className="bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90"
                        data-testid={`edit-tenant-${tenant.slug}`}
                      >
                        <Edit2 className="h-4 w-4 mr-2" />
                        Configure
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={async () => {
                          try {
                            toast.info('Syncing data...');
                            const response = await axios.post(`${API_URL}/api/sync/manual/${tenant.id}`);
                            toast.success(`Synced ${response.data.opportunities_synced + response.data.intelligence_synced} items!`);
                            fetchTenants();
                          } catch (error) {
                            toast.error('Sync failed');
                          }
                        }}
                        className="border-[hsl(var(--border))] hover:bg-[hsl(var(--background-tertiary)))"
                        data-testid={`sync-tenant-${tenant.slug}`}
                      >
                        <svg className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        Sync Now
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDeleteTenant(tenant.id, tenant.name)}
                        className="border-[hsl(var(--accent-danger))] text-[hsl(var(--accent-danger))] hover:bg-[hsl(var(--accent-danger))]/10"
                        data-testid={`delete-tenant-${tenant.slug}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Configuration Dialog */}
        <Dialog open={showDialog} onOpenChange={setShowDialog}>
          <DialogContent className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))] max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="text-[hsl(var(--foreground))] text-2xl">
                {editingTenant ? `Configure: ${editingTenant.name}` : 'Create New Tenant'}
              </DialogTitle>
              <DialogDescription className="text-[hsl(var(--foreground-secondary))]">
                Set up client branding, intelligence prompts, API integrations, and scheduling
              </DialogDescription>
            </DialogHeader>
            
            <form onSubmit={handleSaveTenant}>
              <Tabs defaultValue="basic" className="w-full">
                <TabsList className="grid w-full grid-cols-5 bg-[hsl(var(--background-tertiary))]">
                  <TabsTrigger value="basic">Basic</TabsTrigger>
                  <TabsTrigger value="branding"><Palette className="h-4 w-4 mr-1" />Branding</TabsTrigger>
                  <TabsTrigger value="search">Search</TabsTrigger>
                  <TabsTrigger value="intelligence"><Code className="h-4 w-4 mr-1" />Intelligence</TabsTrigger>
                  <TabsTrigger value="agents"><Zap className="h-4 w-4 mr-1" />Agents</TabsTrigger>
                </TabsList>

                {/* Basic Info Tab */}
                <TabsContent value="basic" className="space-y-4 mt-4">
                  <div className="space-y-2">
                    <Label className="text-[hsl(var(--foreground))]">Company Name *</Label>
                    <Input
                      placeholder="Enchandia"
                      value={formData.name}
                      onChange={(e) => setFormData({...formData, name: e.target.value})}
                      required
                      className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[hsl(var(--foreground))]">Slug (URL identifier) *</Label>
                    <Input
                      placeholder="enchandia"
                      value={formData.slug}
                      onChange={(e) => setFormData({...formData, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '')})}
                      required
                      disabled={!!editingTenant}
                      className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                    />
                    <p className="text-xs text-[hsl(var(--foreground-muted))]">Lowercase letters, numbers, hyphens only</p>
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[hsl(var(--foreground))]">Status</Label>
                    <Select value={formData.status} onValueChange={(value) => setFormData({...formData, status: value})}>
                      <SelectTrigger className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]">
                        <SelectItem value="active">Active</SelectItem>
                        <SelectItem value="suspended">Suspended</SelectItem>
                        <SelectItem value="inactive">Inactive</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="border-t border-[hsl(var(--border))] pt-4 mt-4">
                    <div className="bg-[hsl(var(--accent-info))]/10 p-4 rounded border border-[hsl(var(--accent-info))]/30">
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={formData.is_master_client || false}
                          onChange={(e) => setFormData({...formData, is_master_client: e.target.checked})}
                          className="h-4 w-4"
                          id="is-master"
                        />
                        <Label htmlFor="is-master" className="text-[hsl(var(--foreground))] font-medium">
                          This is a Master Client (Reseller)
                        </Label>
                      </div>
                      <p className="text-xs text-[hsl(var(--foreground-secondary))] mt-2 ml-6">
                        Master clients can create sub-clients and configure white-label branding that appears on all their clients' dashboards
                      </p>
                    </div>
                  </div>
                </TabsContent>

                {/* Branding Tab */}
                <TabsContent value="branding" className="space-y-4 mt-4">
                  <div className="space-y-2">
                    <Label className="text-[hsl(var(--foreground))]">Logo Upload</Label>
                    <Input
                      type="file"
                      accept="image/png,image/jpeg,image/jpg,image/svg+xml"
                      onChange={async (e) => {
                        const file = e.target.files[0];
                        if (file) {
                          const formDataUpload = new FormData();
                          formDataUpload.append('file', file);
                          
                          try {
                            const response = await axios.post(
                              `${API_URL}/api/upload/logo/${editingTenant?.id || 'temp'}`,
                              formDataUpload,
                              { headers: { 'Content-Type': 'multipart/form-data' } }
                            );
                            setFormData({...formData, branding: {...formData.branding, logo_base64: response.data.logo_data_uri, logo_url: null}});
                            toast.success('Logo uploaded!');
                          } catch (error) {
                            toast.error('Logo upload failed');
                          }
                        }
                      }}
                      className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                      disabled={!editingTenant}
                    />
                    {!editingTenant && (
                      <p className="text-xs text-[hsl(var(--accent-warning))]">Save tenant first, then upload logo</p>
                    )}
                    {(formData.branding.logo_base64 || formData.branding.logo_url) && (
                      <div className="mt-2">
                        <img 
                          src={formData.branding.logo_base64 || formData.branding.logo_url} 
                          alt="Logo preview"
                          className="h-16 object-contain bg-[hsl(var(--background-elevated))] p-2 rounded border border-[hsl(var(--border))]"
                        />
                      </div>
                    )}
                  </div>
                  
                  <div className="space-y-2">
                    <Label className="text-[hsl(var(--foreground))]">OR Logo URL</Label>
                    <Input
                      placeholder="https://example.com/logo.png"
                      value={formData.branding.logo_url || ''}
                      onChange={(e) => setFormData({...formData, branding: {...formData.branding, logo_url: e.target.value, logo_base64: null}})}
                      className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                    />
                    <p className="text-xs text-[hsl(var(--foreground-muted))]">Use URL OR upload file (upload takes priority)</p>
                  </div>
                  
                  <div className="border-t border-[hsl(var(--border))] pt-4 mt-4">
                    <h4 className="font-medium text-[hsl(var(--foreground))] mb-3">Brand Colors</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label className="text-[hsl(var(--foreground))]">Primary Color</Label>
                        <Input
                          placeholder="hsl(210, 85%, 52%)"
                          value={formData.branding.primary_color}
                          onChange={(e) => setFormData({...formData, branding: {...formData.branding, primary_color: e.target.value}})}
                          className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                        />
                        <div 
                          className="h-12 rounded border border-[hsl(var(--border))]"
                          style={{background: formData.branding.primary_color}}
                        />
                        <p className="text-xs text-[hsl(var(--foreground-muted))]">Main CTAs, buttons</p>
                      </div>
                      <div className="space-y-2">
                        <Label className="text-[hsl(var(--foreground))]">Secondary Color</Label>
                        <Input
                          placeholder="hsl(265, 60%, 55%)"
                          value={formData.branding.secondary_color}
                          onChange={(e) => setFormData({...formData, branding: {...formData.branding, secondary_color: e.target.value}})}
                          className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                        />
                        <div 
                          className="h-12 rounded border border-[hsl(var(--border))]"
                          style={{background: formData.branding.secondary_color}}
                        />
                        <p className="text-xs text-[hsl(var(--foreground-muted))]">Accents, highlights</p>
                      </div>
                      <div className="space-y-2">
                        <Label className="text-[hsl(var(--foreground))]">Accent Color</Label>
                        <Input
                          placeholder="hsl(142, 70%, 45%)"
                          value={formData.branding.accent_color}
                          onChange={(e) => setFormData({...formData, branding: {...formData.branding, accent_color: e.target.value}})}
                          className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                        />
                        <div 
                          className="h-12 rounded border border-[hsl(var(--border))]"
                          style={{background: formData.branding.accent_color}}
                        />
                        <p className="text-xs text-[hsl(var(--foreground-muted))]">Success states, positive metrics</p>
                      </div>
                      <div className="space-y-2">
                        <Label className="text-[hsl(var(--foreground))]">Text Color</Label>
                        <Input
                          placeholder="hsl(0, 0%, 98%)"
                          value={formData.branding.text_color}
                          onChange={(e) => setFormData({...formData, branding: {...formData.branding, text_color: e.target.value}})}
                          className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                        />
                        <div 
                          className="h-12 rounded border border-[hsl(var(--border))]"
                          style={{background: formData.branding.text_color}}
                        />
                        <p className="text-xs text-[hsl(var(--foreground-muted))]">Primary text color</p>
                      </div>
                    </div>
                  </div>
                  
                  <div className="bg-[hsl(var(--background-elevated))] p-4 rounded border border-[hsl(var(--border))] mt-4">
                    <p className="text-sm font-medium text-[hsl(var(--foreground))] mb-2">Branding Preview</p>
                    <div className="space-y-2">
                      <div className="flex items-center gap-3">
                        {(formData.branding.logo_base64 || formData.branding.logo_url) && (
                          <img 
                            src={formData.branding.logo_base64 || formData.branding.logo_url}
                            alt="Logo"
                            className="h-10 object-contain"
                          />
                        )}
                        <span className="text-lg font-semibold" style={{color: formData.branding.text_color}}>
                          {formData.name || 'Company Name'}
                        </span>
                      </div>
                      <div className="flex gap-2 mt-3">
                        <button 
                          type="button"
                          className="px-4 py-2 rounded font-medium text-white"
                          style={{background: formData.branding.primary_color}}
                        >
                          Primary Button
                        </button>
                        <button 
                          type="button"
                          className="px-4 py-2 rounded font-medium text-white"
                          style={{background: formData.branding.secondary_color}}
                        >
                          Secondary
                        </button>
                        <button 
                          type="button"
                          className="px-4 py-2 rounded font-medium text-white"
                          style={{background: formData.branding.accent_color}}
                        >
                          Accent
                        </button>
                      </div>
                    </div>
                  </div>
                </TabsContent>

                {/* Search Profile Tab (HigherGov) */}
                <TabsContent value="search" className="space-y-4 mt-4">
                  <div className="bg-[hsl(var(--accent-info))]/10 p-4 rounded border border-[hsl(var(--accent-info))]/30 mb-4">
                    <p className="text-sm text-[hsl(var(--foreground))] font-medium mb-1">HigherGov Setup Instructions:</p>
                    <ol className="text-xs text-[hsl(var(--foreground-secondary))] space-y-1 list-decimal list-inside">
                      <li>Create saved search in HigherGov platform with your filters (NAICS, keywords, etc.)</li>
                      <li>Copy the Search ID from HigherGov</li>
                      <li>Paste Search ID below</li>
                      <li>System will poll that saved search automatically</li>
                    </ol>
                  </div>
                  
                  <div className="space-y-2">
                    <Label className="text-[hsl(var(--foreground))]">HigherGov Search ID *</Label>
                    <Input
                      placeholder="your-saved-search-id-from-highergov-platform"
                      value={formData.search_profile.highergov_search_id || ''}
                      onChange={(e) => setFormData({...formData, search_profile: {...formData.search_profile, highergov_search_id: e.target.value}})}
                      className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                    />
                    <p className="text-xs text-[hsl(var(--foreground-muted))]">Get this from your saved search in HigherGov platform (prevents keyword overload)</p>
                  </div>
                  
                  <div className="space-y-2">
                    <Label className="text-[hsl(var(--foreground))]">HigherGov API Key</Label>
                    <Input
                      type="password"
                      placeholder="Client's HigherGov API key (optional - uses default if blank)"
                      value={formData.search_profile.highergov_api_key || ''}
                      onChange={(e) => setFormData({...formData, search_profile: {...formData.search_profile, highergov_api_key: e.target.value}})}
                      className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                    />
                    <p className="text-xs text-[hsl(var(--foreground-muted))]">Per-client key for usage tracking. Leave blank to use shared default key.</p>
                  </div>
                  
                  <div className="border-t border-[hsl(var(--border))] pt-4">
                    <h4 className="font-medium text-[hsl(var(--foreground))] mb-3">Auto-Update Settings</h4>
                    <div className="space-y-3">
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={formData.search_profile.auto_update_enabled !== false}
                          onChange={(e) => setFormData({...formData, search_profile: {...formData.search_profile, auto_update_enabled: e.target.checked}})}
                          className="h-4 w-4"
                          id="auto-update-toggle"
                        />
                        <Label htmlFor="auto-update-toggle" className="text-[hsl(var(--foreground))]">Enable Auto-Update (Polling Timer)</Label>
                      </div>
                      <div className="space-y-2">
                        <Label className="text-[hsl(var(--foreground))]">Update Interval (Hours)</Label>
                        <Input
                          type="number"
                          min="1"
                          max="168"
                          value={formData.search_profile.auto_update_interval_hours || 24}
                          onChange={(e) => setFormData({...formData, search_profile: {...formData.search_profile, auto_update_interval_hours: parseInt(e.target.value)}})}
                          className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                          disabled={!formData.search_profile.auto_update_enabled}
                        />
                        <p className="text-xs text-[hsl(var(--foreground-muted))]">How often to poll HigherGov (1-168 hours). Default: 24 hours (daily)</p>
                      </div>
                    </div>
                  </div>
                  
                  <div className="border-t border-[hsl(var(--border))] pt-4">
                    <h4 className="font-medium text-[hsl(var(--foreground))] mb-3">Fetch Settings</h4>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={formData.search_profile.fetch_contracts !== false}
                          onChange={(e) => setFormData({...formData, search_profile: {...formData.search_profile, fetch_contracts: e.target.checked}})}
                          className="h-4 w-4"
                        />
                        <Label className="text-[hsl(var(--foreground))]">Fetch Contracts</Label>
                      </div>
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={formData.search_profile.fetch_grants !== false}
                          onChange={(e) => setFormData({...formData, search_profile: {...formData.search_profile, fetch_grants: e.target.checked}})}
                          className="h-4 w-4"
                        />
                        <Label className="text-[hsl(var(--foreground))]">Fetch Grants</Label>
                      </div>
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={formData.search_profile.fetch_full_documents || false}
                          onChange={(e) => setFormData({...formData, search_profile: {...formData.search_profile, fetch_full_documents: e.target.checked}})}
                          className="h-4 w-4"
                        />
                        <Label className="text-[hsl(var(--foreground))]">Fetch Full Documents</Label>
                      </div>
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={formData.search_profile.fetch_nsn || false}
                          onChange={(e) => setFormData({...formData, search_profile: {...formData.search_profile, fetch_nsn: e.target.checked}})}
                          className="h-4 w-4"
                        />
                        <Label className="text-[hsl(var(--foreground))]">Fetch NSN Data</Label>
                      </div>
                    </div>
                    <p className="text-xs text-[hsl(var(--foreground-muted))] mt-2">Full documents and NSN data increase API usage</p>
                  </div>
                  
                  <div className="border-t border-[hsl(var(--border))] pt-4">
                    <h4 className="font-medium text-[hsl(var(--foreground))] mb-3">Search Criteria</h4>
                    <div className="space-y-3">
                      <div className="space-y-2">
                        <Label className="text-[hsl(var(--foreground))]">NAICS Codes</Label>
                        <Input
                          placeholder="335911, 336611"
                          value={formData.search_profile.naics_codes.join(', ')}
                          onChange={(e) => updateArrayField('search_profile', 'naics_codes', e.target.value)}
                          className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                        />
                        <p className="text-xs text-[hsl(var(--foreground-muted))]">Comma-separated NAICS codes for HigherGov filtering</p>
                      </div>
                      <div className="space-y-2">
                        <Label className="text-[hsl(var(--foreground))]">Keywords</Label>
                        <Input
                          placeholder="maritime battery, hybrid ferry, shore power"
                          value={formData.search_profile.keywords.join(', ')}
                          onChange={(e) => updateArrayField('search_profile', 'keywords', e.target.value)}
                          className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label className="text-[hsl(var(--foreground))]">Competitors</Label>
                        <Input
                          placeholder="Corvus Energy, Shift Clean Energy, Spear Power"
                          value={formData.search_profile.competitors.join(', ')}
                          onChange={(e) => updateArrayField('search_profile', 'competitors', e.target.value)}
                          className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label className="text-[hsl(var(--foreground))]">Interest Areas</Label>
                        <Input
                          placeholder="Maritime electrification, Port infrastructure, Defense platforms"
                          value={formData.search_profile.interest_areas.join(', ')}
                          onChange={(e) => updateArrayField('search_profile', 'interest_areas', e.target.value)}
                          className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                        />
                      </div>
                    </div>
                  </div>
                </TabsContent>

                {/* Intelligence Config Tab (Perplexity) */}
                <TabsContent value="intelligence" className="space-y-4 mt-4">
                  <div className="bg-[hsl(var(--accent-success))]/10 p-4 rounded border border-[hsl(var(--accent-success))]/30 mb-4">
                    <p className="text-sm text-[hsl(var(--foreground))] font-medium mb-1">✓ Automated Intelligence Reports</p>
                    <p className="text-xs text-[hsl(var(--foreground-secondary))]">
                      Configure when Perplexity generates intelligence reports automatically for this client. 
                      Reports run on schedule without manual intervention.
                    </p>
                  </div>
                  
                  <div className="flex items-center gap-2 mb-4">
                    <input
                      type="checkbox"
                      checked={formData.intelligence_config.enabled}
                      onChange={(e) => setFormData({...formData, intelligence_config: {...formData.intelligence_config, enabled: e.target.checked}})}
                      className="h-4 w-4"
                      id="intel-enabled"
                    />
                    <Label htmlFor="intel-enabled" className="text-[hsl(var(--foreground))] font-medium">Enable Automated Intelligence Reports</Label>
                  </div>
                  
                  <div className="border-t border-[hsl(var(--border))] pt-4">
                    <h4 className="font-medium text-[hsl(var(--foreground))] mb-3">Report Schedule (Automated)</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label className="text-[hsl(var(--foreground))]">Schedule Presets</Label>
                        <Select 
                          value={formData.intelligence_config.schedule_cron}
                          onValueChange={(value) => setFormData({...formData, intelligence_config: {...formData.intelligence_config, schedule_cron: value}})}
                        >
                          <SelectTrigger className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]">
                            <SelectValue placeholder="Select schedule" />
                          </SelectTrigger>
                          <SelectContent className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]">
                            <SelectItem value="0 2 * * *">Daily at 2 AM UTC</SelectItem>
                            <SelectItem value="0 6 * * *">Daily at 6 AM UTC</SelectItem>
                            <SelectItem value="0 9 * * 1">Weekly - Monday 9 AM</SelectItem>
                            <SelectItem value="0 9 * * 1,4">Twice Weekly - Mon & Thu 9 AM</SelectItem>
                            <SelectItem value="0 3 1 * *">Monthly - 1st at 3 AM</SelectItem>
                            <SelectItem value="0 */6 * * *">Every 6 Hours</SelectItem>
                            <SelectItem value="0 */12 * * *">Every 12 Hours</SelectItem>
                            <SelectItem value="custom">Custom Cron...</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label className="text-[hsl(var(--foreground))]">Custom Cron Expression</Label>
                        <Input
                          placeholder="0 2 * * * (min hour day month weekday)"
                          value={formData.intelligence_config.schedule_cron}
                          onChange={(e) => setFormData({...formData, intelligence_config: {...formData.intelligence_config, schedule_cron: e.target.value}})}
                          className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))] font-mono text-xs"
                        />
                        <p className="text-xs text-[hsl(var(--foreground-muted))]">
                          <a href="https://crontab.guru" target="_blank" rel="noopener" className="text-[hsl(var(--primary))] hover:underline">
                            Cron helper →
                          </a>
                        </p>
                      </div>
                    </div>
                  </div>
                  
                  <div className="border-t border-[hsl(var(--border))] pt-4">
                    <h4 className="font-medium text-[hsl(var(--foreground))] mb-3">Report Configuration</h4>
                    <div className="grid grid-cols-3 gap-4">
                      <div className="space-y-2">
                        <Label className="text-[hsl(var(--foreground))]">Lookback Days</Label>
                        <Input
                          type="number"
                          value={formData.intelligence_config.lookback_days}
                          onChange={(e) => setFormData({...formData, intelligence_config: {...formData.intelligence_config, lookback_days: parseInt(e.target.value)}})}
                          className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                        />
                        <p className="text-xs text-[hsl(var(--foreground-muted))]">Search window</p>
                      </div>
                      <div className="space-y-2">
                        <Label className="text-[hsl(var(--foreground))]">Deadline Window (Days)</Label>
                        <Input
                          type="number"
                          value={formData.intelligence_config.deadline_window_days}
                          onChange={(e) => setFormData({...formData, intelligence_config: {...formData.intelligence_config, deadline_window_days: parseInt(e.target.value)}})}
                          className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                        />
                        <p className="text-xs text-[hsl(var(--foreground-muted))]">Future horizon</p>
                      </div>
                      <div className="space-y-2">
                        <Label className="text-[hsl(var(--foreground))]">Next Report</Label>
                        <div className="h-10 px-3 bg-[hsl(var(--background-elevated))] border border-[hsl(var(--border))] rounded flex items-center text-sm text-[hsl(var(--foreground-secondary))]">
                          {formData.intelligence_config.enabled ? 'Scheduled' : 'Disabled'}
                        </div>
                        <p className="text-xs text-[hsl(var(--foreground-muted))]">Based on cron</p>
                      </div>
                    </div>
                  </div>
                  
                  <div className="border-t border-[hsl(var(--border))] pt-4">
                    <h4 className="font-medium text-[hsl(var(--foreground))] mb-3">Perplexity Prompt Template</h4>
                    <div className="space-y-2">
                      <Textarea
                        placeholder="Enter your custom Perplexity prompt template here...&#10;&#10;Available variables:&#10;- {{COMPANY_NAME}}&#10;- {{LOOKBACK_DAYS}}&#10;- {{DEADLINE_WINDOW}}&#10;- {{COMPETITORS}}&#10;- {{NAICS_CODES}}&#10;- {{KEYWORDS}}&#10;- {{CURRENT_DATE}}&#10;&#10;Example: See INTELLIGENCE_CONFIG_GUIDE.md"
                        value={formData.intelligence_config.perplexity_prompt_template}
                        onChange={(e) => setFormData({...formData, intelligence_config: {...formData.intelligence_config, perplexity_prompt_template: e.target.value}})}
                        rows={12}
                        className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))] font-mono text-xs"
                      />
                      <p className="text-xs text-[hsl(var(--foreground-muted))]">Paste your Enchandia-style Washington Update prompt here. Use double curly braces for variables.</p>
                    </div>
                  </div>
                </TabsContent>

                {/* Agent Config Tab (Mistral) */}
                <TabsContent value="agents" className="space-y-4 mt-4">
                  <div className="bg-[hsl(var(--accent-info))]/10 p-4 rounded border border-[hsl(var(--accent-info))]/30 mb-4">
                    <p className="text-sm text-[hsl(var(--foreground))] font-medium mb-2">Two Options:</p>
                    <ul className="text-xs text-[hsl(var(--foreground-secondary))] space-y-1">
                      <li><strong>1. Agent IDs</strong> - Create agents in Mistral platform, paste IDs here (recommended for per-client agents)</li>
                      <li><strong>2. Instructions</strong> - Set custom system prompts (fallback if no agent ID provided)</li>
                    </ul>
                  </div>
                  
                  <div className="space-y-6">
                    {/* Scoring Agent */}
                    <div className="border border-[hsl(var(--border))] rounded-lg p-4 bg-[hsl(var(--background-tertiary))]">
                      <h4 className="font-medium text-[hsl(var(--foreground))] mb-3">1. Pre-Display Scoring Agent</h4>
                      <div className="space-y-3">
                        <div className="space-y-2">
                          <Label className="text-[hsl(var(--foreground))]">Agent ID (from Mistral platform)</Label>
                          <Input
                            placeholder="ag-client-acme-scoring"
                            value={formData.agent_config.scoring_agent_id || ''}
                            onChange={(e) => setFormData({...formData, agent_config: {...formData.agent_config, scoring_agent_id: e.target.value}})}
                            className="bg-[hsl(var(--background))] border-[hsl(var(--border))]"
                          />
                          <p className="text-xs text-[hsl(var(--foreground-muted))]">If provided, uses this agent. Otherwise uses instructions below.</p>
                        </div>
                        <div className="space-y-2">
                          <Label className="text-[hsl(var(--foreground))]">OR Custom Instructions (fallback)</Label>
                          <Textarea
                            placeholder="You are an expert at analyzing government contract opportunities..."
                            value={formData.agent_config.scoring_instructions}
                            onChange={(e) => setFormData({...formData, agent_config: {...formData.agent_config, scoring_instructions: e.target.value}})}
                            rows={2}
                            className="bg-[hsl(var(--background))] border-[hsl(var(--border))] text-sm"
                          />
                        </div>
                      </div>
                    </div>
                    
                    {/* Opportunities Chat Agent */}
                    <div className="border border-[hsl(var(--border))] rounded-lg p-4 bg-[hsl(var(--background-tertiary))]">
                      <h4 className="font-medium text-[hsl(var(--foreground))] mb-3">2. Opportunities Chat Agent</h4>
                      <div className="space-y-3">
                        <div className="space-y-2">
                          <Label className="text-[hsl(var(--foreground))]">Agent ID</Label>
                          <Input
                            placeholder="ag-client-acme-opp-chat"
                            value={formData.agent_config.opportunities_chat_agent_id || ''}
                            onChange={(e) => setFormData({...formData, agent_config: {...formData.agent_config, opportunities_chat_agent_id: e.target.value}})}
                            className="bg-[hsl(var(--background))] border-[hsl(var(--border))]"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-[hsl(var(--foreground))]">OR Custom Instructions</Label>
                          <Textarea
                            placeholder="You are a helpful assistant for contract opportunities..."
                            value={formData.agent_config.opportunities_chat_instructions}
                            onChange={(e) => setFormData({...formData, agent_config: {...formData.agent_config, opportunities_chat_instructions: e.target.value}})}
                            rows={2}
                            className="bg-[hsl(var(--background))] border-[hsl(var(--border))] text-sm"
                          />
                        </div>
                      </div>
                    </div>
                    
                    {/* Intelligence Chat Agent */}
                    <div className="border border-[hsl(var(--border))] rounded-lg p-4 bg-[hsl(var(--background-tertiary))]">
                      <h4 className="font-medium text-[hsl(var(--foreground))] mb-3">3. Intelligence Chat Agent</h4>
                      <div className="space-y-3">
                        <div className="space-y-2">
                          <Label className="text-[hsl(var(--foreground))]">Agent ID</Label>
                          <Input
                            placeholder="ag-client-acme-intel-chat"
                            value={formData.agent_config.intelligence_chat_agent_id || ''}
                            onChange={(e) => setFormData({...formData, agent_config: {...formData.agent_config, intelligence_chat_agent_id: e.target.value}})}
                            className="bg-[hsl(var(--background))] border-[hsl(var(--border))]"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-[hsl(var(--foreground))]">OR Custom Instructions</Label>
                          <Textarea
                            placeholder="You are a business intelligence analyst..."
                            value={formData.agent_config.intelligence_chat_instructions}
                            onChange={(e) => setFormData({...formData, agent_config: {...formData.agent_config, intelligence_chat_instructions: e.target.value}})}
                            rows={2}
                            className="bg-[hsl(var(--background))] border-[hsl(var(--border))] text-sm"
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  <div className="bg-[hsl(var(--background-tertiary))] p-4 rounded border border-[hsl(var(--border))] mt-4">
                    <p className="text-xs text-[hsl(var(--foreground-secondary))]"><strong>How It Works:</strong></p>
                    <ul className="text-xs text-[hsl(var(--foreground-muted))] mt-2 space-y-1">
                      <li>• <strong>With Agent ID:</strong> Uses your pre-configured agent from Mistral platform</li>
                      <li>• <strong>With Instructions:</strong> Creates agent on-the-fly with custom system prompt</li>
                      <li>• Agent ID takes priority if both are set</li>
                      <li>• Each client can have unique agents with their own prompts</li>
                    </ul>
                  </div>
                </TabsContent>
              </Tabs>

              <div className="flex gap-2 pt-6 border-t border-[hsl(var(--border))] mt-6">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {setShowDialog(false); setEditingTenant(null);}}
                  className="flex-1 border-[hsl(var(--border))] hover:bg-[hsl(var(--background-tertiary))]"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  className="flex-1 bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90"
                >
                  <Save className="h-4 w-4 mr-2" />
                  {editingTenant ? 'Save Changes' : 'Create Tenant'}
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>
    </SuperAdminLayout>
  );
}