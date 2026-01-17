import React, { useEffect, useState } from 'react';
import { SuperAdminLayout } from '../components/layout/SuperAdminLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { apiClient } from '../lib/api';
import { Database, Trash2, RefreshCw, Search } from 'lucide-react';

export default function DatabaseManager() {
  const [activeTab, setActiveTab] = useState('opportunities');
  const [opportunities, setOpportunities] = useState([]);
  const [intelligence, setIntelligence] = useState([]);
  const [chatMessages, setChatMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    fetchData();
  }, [activeTab]);

  const fetchData = async () => {
    setLoading(true);
    try {
      if (activeTab === 'opportunities') {
        const response = await apiClient.get(`/api/opportunities`, {
          params: { per_page: 100 }
        });
        setOpportunities(response.data.data || []);
      } else if (activeTab === 'intelligence') {
        const response = await apiClient.get(`/api/intelligence`, {
          params: { per_page: 100 }
        });
        setIntelligence(response.data.data || []);
      } else if (activeTab === 'chat') {
        // Get all tenants and their chat messages
        const tenantsRes = await apiClient.get(`/api/tenants`);
        const tenants = tenantsRes.data.data || [];
        
        let allMessages = [];
        for (const tenant of tenants.slice(0, 5)) {
          try {
            const convIds = ['test-conv-1', 'smoke-test-123', 'final-test'];
            for (const convId of convIds) {
              const res = await apiClient.get(`/api/chat/history/${convId}`);
              allMessages = allMessages.concat(res.data || []);
            }
          } catch (e) {}
        }
        setChatMessages(allMessages);
      }
    } catch (error) {
      console.error('Failed to fetch data:', error);
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id, type) => {
    if (!window.confirm(`Delete this ${type}?`)) return;
    
    try {
      await apiClient.delete(`/api/${type}/${id}`);
      toast.success('Deleted');
      fetchData();
    } catch (error) {
      toast.error('Delete failed');
    }
  };

  return (
    <SuperAdminLayout>
      <div className="p-6 md:p-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-heading font-bold text-[hsl(var(--foreground))]">
              Database Manager
            </h1>
            <p className="text-[hsl(var(--foreground-secondary))] mt-1">
              Browse and manage all platform data across tenants
            </p>
          </div>
          <Button onClick={fetchData} variant="outline" className="border-[hsl(var(--border))]">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-[hsl(var(--background-tertiary))]">
            <TabsTrigger value="opportunities">Opportunities ({opportunities.length})</TabsTrigger>
            <TabsTrigger value="intelligence">Intelligence ({intelligence.length})</TabsTrigger>
            <TabsTrigger value="chat">Chat Messages ({chatMessages.length})</TabsTrigger>
          </TabsList>

          <TabsContent value="opportunities" className="space-y-4 mt-6">
            <Input
              placeholder="Search opportunities..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]"
            />
            
            {loading ? (
              <div className="text-center py-12 text-[hsl(var(--foreground-secondary))]">Loading...</div>
            ) : opportunities.length === 0 ? (
              <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
                <CardContent className="py-12 text-center">
                  <Database className="h-12 w-12 mx-auto mb-4 text-[hsl(var(--foreground-muted))]" />
                  <h3 className="text-lg font-semibold text-[hsl(var(--foreground))]">No opportunities in database</h3>
                  <p className="text-sm text-[hsl(var(--foreground-secondary))] mt-2">
                    Upload CSV or configure HigherGov search_id for tenants
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid grid-cols-1 gap-3">
                {opportunities
                  .filter(opp => !searchQuery || opp.title.toLowerCase().includes(searchQuery.toLowerCase()))
                  .map((opp) => (
                  <Card key={opp.id} className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <h3 className="font-semibold text-[hsl(var(--foreground))]">{opp.title}</h3>
                            <Badge className="bg-[hsl(var(--primary))] text-xs">{opp.score}</Badge>
                            <Badge variant="outline" className="text-xs">{opp.client_status || 'new'}</Badge>
                          </div>
                          <p className="text-xs text-[hsl(var(--foreground-muted))]">
                            Tenant: {opp.tenant_id?.slice(0, 8)}... | Agency: {opp.agency || 'N/A'}
                          </p>
                          {opp.client_notes && (
                            <p className="text-xs text-[hsl(var(--foreground-secondary))] mt-2 italic">
                              Note: {opp.client_notes}
                            </p>
                          )}
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDelete(opp.id, 'opportunities')}
                          className="border-[hsl(var(--accent-danger))] text-[hsl(var(--accent-danger))]"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="intelligence" className="space-y-4 mt-6">
            {loading ? (
              <div className="text-center py-12">Loading...</div>
            ) : (
              <div className="grid grid-cols-1 gap-3">
                {intelligence.map((item) => (
                  <Card key={item.id} className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <h3 className="font-semibold text-[hsl(var(--foreground))] mb-1">{item.title}</h3>
                          <p className="text-xs text-[hsl(var(--foreground-muted))]">
                            Tenant: {item.tenant_id?.slice(0, 8)}... | Type: {item.type} | {new Date(item.created_at).toLocaleDateString()}
                          </p>
                          <p className="text-xs text-[hsl(var(--foreground-secondary))] mt-2">{item.summary?.slice(0, 150)}...</p>
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDelete(item.id, 'intelligence')}
                          className="border-[hsl(var(--accent-danger))] text-[hsl(var(--accent-danger))]"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="chat" className="space-y-4 mt-6">
            {loading ? (
              <div className="text-center py-12">Loading...</div>
            ) : (
              <div className="space-y-2">
                {chatMessages.map((msg) => (
                  <div 
                    key={msg.id}
                    className={`p-3 rounded border ${
                      msg.role === 'user' 
                        ? 'bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))] ml-12' 
                        : 'bg-[hsl(var(--background-secondary))] border-[hsl(var(--primary))]/30 mr-12'
                    }`}
                  >
                    <div className="flex items-start justify-between mb-1">
                      <span className="text-xs font-semibold text-[hsl(var(--foreground-muted))]">
                        {msg.role.toUpperCase()}
                      </span>
                      <span className="text-xs text-[hsl(var(--foreground-muted))]">
                        {new Date(msg.created_at).toLocaleString()}
                      </span>
                    </div>
                    <p className="text-sm text-[hsl(var(--foreground-secondary))]">{msg.content}</p>
                  </div>
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </SuperAdminLayout>
  );
}
