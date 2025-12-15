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
      branding: {
        logo_url: '',
        primary_color: 'hsl(210, 85%, 52%)',
        secondary_color: 'hsl(265, 60%, 55%)',
        text_color: 'hsl(0, 0%, 98%)'
      },
      search_profile: {
        naics_codes: [],
        keywords: [],
        interest_areas: [],
        competitors: []
      },
      intelligence_config: {
        enabled: true,
        perplexity_prompt_template: '',
        schedule_cron: '0 2 * * *',
        lookback_days: 14,
        deadline_window_days: 120
      },
      agent_config: {
        pre_display_agent_id: '',
        opportunities_chat_agent_id: '',
        intelligence_chat_agent_id: ''
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
                </TabsContent>

                {/* Branding Tab */}
                <TabsContent value="branding" className="space-y-4 mt-4">
                  <div className="space-y-2">
                    <Label className="text-[hsl(var(--foreground))]">Logo URL</Label>
                    <Input
                      placeholder="https://example.com/logo.png"
                      value={formData.branding.logo_url}
                      onChange={(e) => setFormData({...formData, branding: {...formData.branding, logo_url: e.target.value}})}
                      className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                    />
                    <p className="text-xs text-[hsl(var(--foreground-muted))]">Direct link to client logo (appears in header & exports)</p>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label className="text-[hsl(var(--foreground))]">Primary Color (HSL)</Label>
                      <Input
                        placeholder="hsl(210, 85%, 52%)"
                        value={formData.branding.primary_color}
                        onChange={(e) => setFormData({...formData, branding: {...formData.branding, primary_color: e.target.value}})}
                        className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                      />
                      <div 
                        className="h-8 rounded border border-[hsl(var(--border))]"
                        style={{background: formData.branding.primary_color}}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-[hsl(var(--foreground))]">Secondary Color (HSL)</Label>
                      <Input
                        placeholder="hsl(265, 60%, 55%)"
                        value={formData.branding.secondary_color}
                        onChange={(e) => setFormData({...formData, branding: {...formData.branding, secondary_color: e.target.value}})}
                        className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                      />
                      <div 
                        className="h-8 rounded border border-[hsl(var(--border))]"
                        style={{background: formData.branding.secondary_color}}
                      />
                    </div>
                  </div>
                </TabsContent>

                {/* Search Profile Tab (HigherGov) */}
                <TabsContent value="search" className="space-y-4 mt-4">
                  <div className="space-y-2">
                    <Label className="text-[hsl(var(--foreground))]">NAICS Codes (HigherGov)</Label>
                    <Input
                      placeholder="335911, 336611"
                      value={formData.search_profile.naics_codes.join(', ')}
                      onChange={(e) => updateArrayField('search_profile', 'naics_codes', e.target.value)}
                      className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                    />
                    <p className="text-xs text-[hsl(var(--foreground-muted))]">Comma-separated NAICS codes for HigherGov API</p>
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[hsl(var(--foreground))]">Keywords (HigherGov)</Label>
                    <Input
                      placeholder="maritime battery, hybrid ferry, shore power"
                      value={formData.search_profile.keywords.join(', ')}
                      onChange={(e) => updateArrayField('search_profile', 'keywords', e.target.value)}
                      className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[hsl(var(--foreground))]">Competitors (Intelligence)</Label>
                    <Input
                      placeholder="Corvus Energy, Shift Clean Energy, Spear Power"
                      value={formData.search_profile.competitors.join(', ')}
                      onChange={(e) => updateArrayField('search_profile', 'competitors', e.target.value)}
                      className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[hsl(var(--foreground))]">Interest Areas (Intelligence)</Label>
                    <Input
                      placeholder="Maritime electrification, Port infrastructure, Defense platforms"
                      value={formData.search_profile.interest_areas.join(', ')}
                      onChange={(e) => updateArrayField('search_profile', 'interest_areas', e.target.value)}
                      className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                    />
                  </div>
                </TabsContent>

                {/* Intelligence Config Tab (Perplexity) */}
                <TabsContent value="intelligence" className="space-y-4 mt-4">
                  <div className="flex items-center gap-2 mb-4">
                    <input
                      type="checkbox"
                      checked={formData.intelligence_config.enabled}
                      onChange={(e) => setFormData({...formData, intelligence_config: {...formData.intelligence_config, enabled: e.target.checked}})}
                      className="h-4 w-4"
                    />
                    <Label className="text-[hsl(var(--foreground))]">Enable Intelligence Reports</Label>
                  </div>
                  
                  <div className="space-y-2">
                    <Label className="text-[hsl(var(--foreground))]">Perplexity Prompt Template</Label>
                    <Textarea
                      placeholder="Enter your custom Perplexity prompt template here...&#10;&#10;Available variables:&#10;- {COMPANY_NAME}&#10;- {LOOKBACK_DAYS}&#10;- {DEADLINE_WINDOW}&#10;- {COMPETITORS}&#10;- {NAICS_CODES}&#10;- {KEYWORDS}&#10;- {CURRENT_DATE}&#10;&#10;Example: See INTELLIGENCE_CONFIG_GUIDE.md"
                      value={formData.intelligence_config.perplexity_prompt_template}
                      onChange={(e) => setFormData({...formData, intelligence_config: {...formData.intelligence_config, perplexity_prompt_template: e.target.value}})}
                      rows={12}
                      className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))] font-mono text-xs"
                    />
                    <p className="text-xs text-[hsl(var(--foreground-muted))]">Use double curly braces for variables in your template</p>
                  </div>
                  
                  <div className="grid grid-cols-3 gap-4">
                    <div className="space-y-2">
                      <Label className="text-[hsl(var(--foreground))]">Schedule (Cron)</Label>
                      <Input
                        placeholder="0 2 * * *"
                        value={formData.intelligence_config.schedule_cron}
                        onChange={(e) => setFormData({...formData, intelligence_config: {...formData.intelligence_config, schedule_cron: e.target.value}})}
                        className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                      />
                      <p className="text-xs text-[hsl(var(--foreground-muted))]">Daily 2 AM UTC</p>
                    </div>
                    <div className="space-y-2">
                      <Label className="text-[hsl(var(--foreground))]">Lookback Days</Label>
                      <Input
                        type="number"
                        value={formData.intelligence_config.lookback_days}
                        onChange={(e) => setFormData({...formData, intelligence_config: {...formData.intelligence_config, lookback_days: parseInt(e.target.value)}})}
                        className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-[hsl(var(--foreground))]">Deadline Window (Days)</Label>
                      <Input
                        type="number"
                        value={formData.intelligence_config.deadline_window_days}
                        onChange={(e) => setFormData({...formData, intelligence_config: {...formData.intelligence_config, deadline_window_days: parseInt(e.target.value)}})}
                        className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                      />
                    </div>
                  </div>
                </TabsContent>

                {/* Agent Config Tab (Mistral) */}
                <TabsContent value="agents" className="space-y-4 mt-4">
                  <p className="text-sm text-[hsl(var(--foreground-secondary))]">Configure Mistral Agent IDs (leave blank to use defaults)</p>
                  <div className="space-y-2">
                    <Label className="text-[hsl(var(--foreground))]">Pre-Display Scoring Agent ID</Label>
                    <Input
                      placeholder="ag-dev-scoring-001 (default)"
                      value={formData.agent_config.pre_display_agent_id}
                      onChange={(e) => setFormData({...formData, agent_config: {...formData.agent_config, pre_display_agent_id: e.target.value}})}
                      className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[hsl(var(--foreground))]">Opportunities Chat Agent ID</Label>
                    <Input
                      placeholder="ag-dev-opp-chat-001 (default)"
                      value={formData.agent_config.opportunities_chat_agent_id}
                      onChange={(e) => setFormData({...formData, agent_config: {...formData.agent_config, opportunities_chat_agent_id: e.target.value}})}
                      className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[hsl(var(--foreground))]">Intelligence Chat Agent ID</Label>
                    <Input
                      placeholder="ag-dev-intel-chat-001 (default)"
                      value={formData.agent_config.intelligence_chat_agent_id}
                      onChange={(e) => setFormData({...formData, agent_config: {...formData.agent_config, intelligence_chat_agent_id: e.target.value}})}
                      className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                    />
                  </div>
                  <div className="bg-[hsl(var(--background-tertiary))] p-4 rounded border border-[hsl(var(--border))]">
                    <p className="text-xs text-[hsl(var(--foreground-secondary))]"><strong>Defaults from domo_arigato.md:</strong></p>
                    <ul className="text-xs text-[hsl(var(--foreground-muted))] mt-2 space-y-1">
                      <li>• Scoring: ag-dev-scoring-001 (mistral-small, temp 0.3)</li>
                      <li>• Opp Chat: ag-dev-opp-chat-001 (mistral-small, temp 0.7)</li>
                      <li>• Intel Chat: ag-dev-intel-chat-001 (mistral-small, temp 0.7)</li>
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