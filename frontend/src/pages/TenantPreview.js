import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { TenantLayout } from '../components/layout/TenantLayout';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { ExportModal } from '../components/custom/ExportModal';
import { ChatAssistant } from '../components/custom/ChatAssistant';
import axios from 'axios';
import { toast } from 'sonner';
import { FileText, RefreshCw, Download } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { useNavigate } from 'react-router-dom';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function TenantPreview() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const tenantId = searchParams.get('tenant_id');
  
  const [tenant, setTenant] = useState(null);
  const [opportunities, setOpportunities] = useState([]);
  const [intelligence, setIntelligence] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showExportModal, setShowExportModal] = useState(false);

  useEffect(() => {
    if (tenantId) {
      fetchTenantData();
    }
  }, [tenantId]);

  const fetchTenantData = async () => {
    try {
      // Fetch tenant info
      const tenantRes = await axios.get(`${API_URL}/api/tenants/${tenantId}`);
      setTenant(tenantRes.data);
      
      // Fetch opportunities
      const oppsRes = await axios.get(`${API_URL}/api/opportunities`, {
        params: { tenant_id: tenantId, per_page: 50 }
      });
      setOpportunities(oppsRes.data.data || []);
      
      // Fetch intelligence
      const intelRes = await axios.get(`${API_URL}/api/intelligence`, {
        params: { tenant_id: tenantId, per_page: 50 }
      });
      setIntelligence(intelRes.data.data || []);
      
      // Apply branding
      applyBranding(tenantRes.data.branding, tenantRes.data.master_branding);
    } catch (error) {
      console.error('Failed to load preview:', error);
      toast.error('Failed to load tenant preview');
    } finally {
      setLoading(false);
    }
  };

  const applyBranding = (branding, masterBranding) => {
    const effectiveBranding = masterBranding || branding || {};
    const root = document.documentElement;
    
    if (effectiveBranding.primary_color) {
      root.style.setProperty('--tenant-primary', effectiveBranding.primary_color.replace('hsl(', '').replace(')', ''));
    }
  };

  const getScoreColor = (score) => {
    if (score >= 75) return 'bg-[hsl(var(--accent-success))]';
    if (score >= 50) return 'bg-[hsl(var(--accent-info))]';
    return 'bg-[hsl(var(--foreground-muted))]';
  };

  const primaryColor = (tenant?.master_branding || tenant?.branding)?.primary_color || 'hsl(210, 85%, 52%)';
  const logo = (tenant?.master_branding || tenant?.branding)?.logo_base64 || (tenant?.master_branding || tenant?.branding)?.logo_url;

  if (loading) {
    return (
      <div className="min-h-screen bg-[hsl(var(--background))] flex items-center justify-center">
        <div className="text-[hsl(var(--foreground-secondary))]">Loading preview...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[hsl(var(--background))]">
      {/* Preview Banner */}
      <div className="bg-[hsl(var(--accent-warning))] text-black px-4 py-2 text-center text-sm font-medium sticky top-0 z-50">
        🔍 PREVIEW MODE - Viewing as: {tenant?.name} | 
        <button onClick={() => window.close()} className="ml-4 underline hover:no-underline">
          Close Preview
        </button>
      </div>

      {/* Simulated Tenant Dashboard */}
      <div className="flex h-screen">
        {/* Sidebar */}
        <div className="w-64 bg-[hsl(var(--background-secondary))] border-r border-[hsl(var(--border))] flex flex-col">
          <div className="p-6 border-b border-[hsl(var(--border))]">
            {logo && <img src={logo} alt={tenant?.name} className="h-10 object-contain mb-3" />}
            <h1 className="text-xl font-heading font-bold text-[hsl(var(--foreground))]">
              {tenant?.name}
            </h1>
          </div>
          <div className="flex-1 p-4">
            <div className="text-sm text-[hsl(var(--foreground-secondary))]">
              Preview of client dashboard
            </div>
          </div>
          <div className="p-4 border-t border-[hsl(var(--border))]">
            <div className="text-xs text-center text-[hsl(var(--foreground-muted))]">
              Powered by {tenant?.master_client_id ? (tenant.master_client_name || 'Partner') : 'OutPace Intelligence'}
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-7xl mx-auto">
            <Tabs defaultValue="opportunities" className="w-full">
              <TabsList className="mb-6">
                <TabsTrigger value="opportunities">
                  Opportunities ({opportunities.length})
                </TabsTrigger>
                <TabsTrigger value="intelligence">
                  Intelligence ({intelligence.length})
                </TabsTrigger>
              </TabsList>

              <TabsContent value="opportunities">
                <div className="flex items-center justify-between mb-6">
                  <h1 className="text-3xl font-heading font-bold text-[hsl(var(--foreground))]">
                    Contract Opportunities
                  </h1>
                  <Button
                    onClick={() => setShowExportModal(true)}
                    variant="outline"
                    disabled={opportunities.length === 0}
                    className="border-[hsl(var(--border))]"
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Export
                  </Button>
                </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-4 mb-6">
              <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
                <CardContent className="p-4">
                  <div className="text-2xl font-bold font-mono">{opportunities.length}</div>
                  <div className="text-sm text-[hsl(var(--foreground-secondary))]">Total</div>
                </CardContent>
              </Card>
              <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
                <CardContent className="p-4">
                  <div className="text-2xl font-bold font-mono">{opportunities.filter(o => o.score >= 75).length}</div>
                  <div className="text-sm text-[hsl(var(--foreground-secondary))]">High Priority</div>
                </CardContent>
              </Card>
              <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
                <CardContent className="p-4">
                  <div className="text-2xl font-bold font-mono">{intelligence.length}</div>
                  <div className="text-sm text-[hsl(var(--foreground-secondary))]">Intelligence</div>
                </CardContent>
              </Card>
            </div>

            {/* Opportunities */}
            <div className="grid grid-cols-1 gap-4">
              {opportunities.map((opp) => (
                <Card key={opp.id} className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
                  <CardContent className="p-6">
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="text-lg font-semibold text-[hsl(var(--foreground))]">{opp.title}</h3>
                      <Badge className={`${getScoreColor(opp.score)} text-white font-mono`}>{opp.score}</Badge>
                    </div>
                    {opp.ai_relevance_summary && (
                      <div className="text-sm mb-2 px-3 py-2 rounded border-l-4 bg-[hsl(var(--background-tertiary))]" style={{borderColor: primaryColor}}>
                        <p className="text-xs text-[hsl(var(--foreground-muted))] mb-1 font-semibold">AI ANALYSIS</p>
                        <p className="text-[hsl(var(--foreground-secondary))]">{opp.ai_relevance_summary}</p>
                      </div>
                    )}
                    <p className="text-sm text-[hsl(var(--foreground-secondary))]">{opp.description?.slice(0, 150)}...</p>
                    <div className="flex gap-4 text-xs text-[hsl(var(--foreground-muted))] mt-3">
                      <span>Agency: {opp.agency}</span>
                      <span>•</span>
                      <span>Value: {opp.estimated_value || 'N/A'}</span>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </div>
      </div>

      <ExportModal
        open={showExportModal}
        onOpenChange={setShowExportModal}
        opportunities={opportunities}
        intelligence={intelligence}
        primaryColor={primaryColor}
      />
    </div>
  );
}
