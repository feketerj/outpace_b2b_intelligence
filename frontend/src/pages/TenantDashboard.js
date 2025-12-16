import React, { useEffect, useState } from 'react';
import { TenantLayout } from '../components/layout/TenantLayout';
import { useTenant } from '../context/TenantContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { ExportModal } from '../components/custom/ExportModal';
import { ChatAssistant } from '../components/custom/ChatAssistant';
import axios from 'axios';
import { toast } from 'sonner';
import { FileText, RefreshCw, Search, Filter, Download } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function TenantDashboard() {
  const { currentTenant, brandingStyles } = useTenant();
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showExportModal, setShowExportModal] = useState(false);

  useEffect(() => {
    if (currentTenant) {
      fetchOpportunities();
    }
  }, [currentTenant]);

  const fetchOpportunities = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/opportunities`, {
        params: { tenant_id: currentTenant?.id, per_page: 50 }
      });
      setOpportunities(response.data.data || []);
    } catch (error) {
      console.error('Failed to fetch opportunities:', error);
      toast.error('Failed to load opportunities');
    } finally {
      setLoading(false);
    }
  };

  const handleManualSync = async () => {
    setSyncing(true);
    try {
      toast.info('Syncing new opportunities...');
      const response = await axios.post(`${API_URL}/api/sync/manual/${currentTenant.id}`);
      toast.success(`Synced ${response.data.opportunities_synced} new opportunities!`);
      fetchOpportunities();
    } catch (error) {
      toast.error('Sync failed');
    } finally {
      setSyncing(false);
    }
  };

  const getScoreColor = (score) => {
    if (score >= 75) return 'bg-[hsl(var(--accent-success))]';
    if (score >= 50) return 'bg-[hsl(var(--accent-info))]';
    return 'bg-[hsl(var(--foreground-muted))]';
  };

  const primaryColor = brandingStyles?.primary_color || 'hsl(210, 85%, 52%)';

  return (
    <TenantLayout>
      <div className="p-6 md:p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-heading font-bold text-[hsl(var(--foreground))]">
              Contract Opportunities
            </h1>
            <p className="text-[hsl(var(--foreground-secondary))] mt-1">
              {currentTenant?.name} - AI-scored government contracts
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              onClick={() => setShowExportModal(true)}
              variant="outline"
              className="border-[hsl(var(--border))] hover:bg-[hsl(var(--background-tertiary))]"
              disabled={opportunities.length === 0}
            >
              <Download className="h-4 w-4 mr-2" />
              Export
            </Button>
            <Button
              onClick={handleManualSync}
              disabled={syncing}
              className="text-white"
              style={{background: primaryColor}}
              data-testid="manual-sync-button"
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${syncing ? 'animate-spin' : ''}`} />
              {syncing ? 'Syncing...' : 'Sync Now'}
            </Button>
          </div>
        </div>

        {/* Search Bar */}
        <div className="mb-6">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[hsl(var(--foreground-muted))]" />
            <Input
              placeholder="Search opportunities..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]"
            />
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
            <CardContent className="p-4">
              <div className="text-2xl font-bold font-mono text-[hsl(var(--foreground))]">
                {opportunities.length}
              </div>
              <div className="text-sm text-[hsl(var(--foreground-secondary))]">Total Opportunities</div>
            </CardContent>
          </Card>
          <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
            <CardContent className="p-4">
              <div className="text-2xl font-bold font-mono text-[hsl(var(--foreground))]">
                {opportunities.filter(o => o.score >= 75).length}
              </div>
              <div className="text-sm text-[hsl(var(--foreground-secondary))]">High Priority (75+)</div>
            </CardContent>
          </Card>
          <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
            <CardContent className="p-4">
              <div className="text-2xl font-bold font-mono text-[hsl(var(--foreground))]">
                {currentTenant?.last_synced_at ? new Date(currentTenant.last_synced_at).toLocaleDateString() : 'Never'}
              </div>
              <div className="text-sm text-[hsl(var(--foreground-secondary))]">Last Updated</div>
            </CardContent>
          </Card>
        </div>

        {/* Opportunities List */}
        {loading ? (
          <div className="text-center py-12 text-[hsl(var(--foreground-secondary))]">Loading opportunities...</div>
        ) : opportunities.length === 0 ? (
          <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
            <CardContent className="py-12 text-center">
              <FileText className="h-12 w-12 mx-auto mb-4 text-[hsl(var(--foreground-muted))]" />
              <h3 className="text-lg font-semibold text-[hsl(var(--foreground))] mb-2">No opportunities yet</h3>
              <p className="text-[hsl(var(--foreground-secondary))] mb-4">Configure your search criteria and click Sync Now</p>
              <Button onClick={handleManualSync} className="text-white" style={{background: primaryColor}}>
                <RefreshCw className="h-4 w-4 mr-2" />
                Sync Now
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {opportunities
              .filter(opp => !searchQuery || opp.title.toLowerCase().includes(searchQuery.toLowerCase()) || opp.description.toLowerCase().includes(searchQuery.toLowerCase()))
              .map((opp) => (
              <Card 
                key={opp.id} 
                className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))] hover:border-[hsl(var(--border-light))] transition-all duration-150 cursor-pointer"
                onClick={() => navigate(`/opportunities/${opp.id}`)}
                data-testid={`opportunity-card-${opp.id}`}
              >
                <CardContent className="p-6">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="text-lg font-semibold text-[hsl(var(--foreground))]">
                          {opp.title}
                        </h3>
                        <Badge className={`${getScoreColor(opp.score)} text-white font-mono`}>
                          {opp.score}
                        </Badge>
                      </div>
                      {opp.ai_relevance_summary && (
                        <div 
                          className="text-sm mb-3 px-3 py-2 rounded border-l-4"
                          style={{borderColor: primaryColor, background: 'hsl(var(--background-tertiary))'}}
                        >
                          <p className="text-xs text-[hsl(var(--foreground-muted))] mb-1 font-semibold">AI ANALYSIS</p>
                          <p className="text-[hsl(var(--foreground-secondary))]">{opp.ai_relevance_summary}</p>
                        </div>
                      )}
                      <p className="text-sm text-[hsl(var(--foreground-secondary))] line-clamp-2">
                        {opp.description}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-[hsl(var(--foreground-muted))]">
                    <span>Agency: {opp.agency || 'N/A'}</span>
                    <span>•</span>
                    <span>Due: {opp.due_date ? new Date(opp.due_date).toLocaleDateString() : 'N/A'}</span>
                    <span>•</span>
                    <span>Value: {opp.estimated_value || 'N/A'}</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
      
      <ExportModal
        open={showExportModal}
        onOpenChange={setShowExportModal}
        opportunities={opportunities}
        intelligence={[]}
        primaryColor={primaryColor}
      />
    </TenantLayout>
  );
}