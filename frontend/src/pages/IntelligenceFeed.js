import React, { useEffect, useState } from 'react';
import { TenantLayout } from '../components/layout/TenantLayout';
import { useTenant } from '../context/TenantContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import axios from 'axios';
import { toast } from 'sonner';
import { TrendingUp, ExternalLink, Calendar } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function IntelligenceFeed() {
  const { currentTenant, brandingStyles } = useTenant();
  const [intelligence, setIntelligence] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (currentTenant) {
      fetchIntelligence();
    }
  }, [currentTenant]);

  const fetchIntelligence = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/intelligence`, {
        params: { tenant_id: currentTenant?.id, per_page: 50 }
      });
      setIntelligence(response.data.data || []);
    } catch (error) {
      console.error('Failed to fetch intelligence:', error);
      toast.error('Failed to load intelligence');
    } finally {
      setLoading(false);
    }
  };

  const primaryColor = brandingStyles?.primary_color || 'hsl(210, 85%, 52%)';

  return (
    <TenantLayout>
      <div className="p-6 md:p-8">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-heading font-bold text-[hsl(var(--foreground))]">
            Business Intelligence
          </h1>
          <p className="text-[hsl(var(--foreground-secondary))] mt-1">
            Market insights and competitive analysis for {currentTenant?.name}
          </p>
        </div>

        {/* Intelligence Feed */}
        {loading ? (
          <div className="text-center py-12 text-[hsl(var(--foreground-secondary))]">Loading intelligence...</div>
        ) : intelligence.length === 0 ? (
          <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
            <CardContent className="py-12 text-center">
              <TrendingUp className="h-12 w-12 mx-auto mb-4 text-[hsl(var(--foreground-muted))]" />
              <h3 className="text-lg font-semibold text-[hsl(var(--foreground))] mb-2">No intelligence reports yet</h3>
              <p className="text-[hsl(var(--foreground-secondary))]">Reports will appear here based on your configured schedule</p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {intelligence.map((item) => (
              <Card 
                key={item.id}
                className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]"
                data-testid={`intelligence-item-${item.id}`}
              >
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <CardTitle className="text-xl text-[hsl(var(--foreground))]">
                        {item.title}
                      </CardTitle>
                      <div className="flex items-center gap-3 mt-2 text-xs text-[hsl(var(--foreground-muted))]">
                        <div className="flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          {new Date(item.created_at).toLocaleDateString()}
                        </div>
                        <Badge 
                          className="text-white"
                          style={{background: primaryColor}}
                        >
                          {item.type}
                        </Badge>
                      </div>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="prose prose-invert max-w-none">
                    <div className="text-sm text-[hsl(var(--foreground-secondary))] whitespace-pre-wrap">
                      {item.content}
                    </div>
                  </div>
                  
                  {/* Source Links */}
                  {item.source_urls && item.source_urls.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-[hsl(var(--border))]">
                      <p className="text-xs font-semibold text-[hsl(var(--foreground-muted))] mb-2">SOURCES:</p>
                      <div className="space-y-1">
                        {item.source_urls.slice(0, 5).map((url, idx) => (
                          <a
                            key={idx}
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-2 text-xs hover:underline"
                            style={{color: primaryColor}}
                            data-testid={`source-link-${idx}`}
                          >
                            <ExternalLink className="h-3 w-3" />
                            {url.length > 60 ? url.substring(0, 60) + '...' : url}
                          </a>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </TenantLayout>
  );
}