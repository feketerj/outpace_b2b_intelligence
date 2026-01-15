import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { TenantLayout } from '../components/layout/TenantLayout';
import { useTenant } from '../context/TenantContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import axios from 'axios';
import { toast } from 'sonner';
import { showApiError } from '../lib/api';
import { ArrowLeft, Save, Trash2, ExternalLink, Calendar, DollarSign, Building2 } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function OpportunityDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { brandingStyles } = useTenant();
  const [opportunity, setOpportunity] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notes, setNotes] = useState('');
  const [status, setStatus] = useState('new');

  useEffect(() => {
    if (id) {
      fetchOpportunity();
    }
  }, [id]);

  const fetchOpportunity = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/opportunities/${id}`);
      setOpportunity(response.data);
      setNotes(response.data.client_notes || '');
      setStatus(response.data.client_status || 'new');
    } catch (error) {
      showApiError(error, 'Failed to load opportunity');
      navigate('/dashboard');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      await axios.patch(`${API_URL}/api/opportunities/${id}`, {
        client_status: status,
        client_notes: notes
      });
      toast.success('Saved!');
    } catch (error) {
      showApiError(error, 'Failed to save');
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('Delete this opportunity?')) return;
    try {
      await axios.delete(`${API_URL}/api/opportunities/${id}`);
      toast.success('Deleted');
      navigate('/dashboard');
    } catch (error) {
      showApiError(error, 'Failed to delete');
    }
  };

  const primaryColor = brandingStyles?.primary_color || 'hsl(210, 85%, 52%)';
  
  const getScoreColor = (score) => {
    if (score >= 75) return 'bg-[hsl(var(--accent-success))]';
    if (score >= 50) return 'bg-[hsl(var(--accent-info))]';
    return 'bg-[hsl(var(--foreground-muted))]';
  };

  if (loading) {
    return (
      <TenantLayout>
        <div className="flex items-center justify-center h-full">
          <div className="text-[hsl(var(--foreground-secondary))]">Loading...</div>
        </div>
      </TenantLayout>
    );
  }

  return (
    <TenantLayout>
      <div className="p-6 md:p-8 max-w-5xl mx-auto">
        <Button
          variant="outline"
          size="sm"
          onClick={() => navigate('/dashboard')}
          className="mb-4 border-[hsl(var(--border))]"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>

        <div className="flex items-start justify-between mb-6">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-3xl font-heading font-bold text-[hsl(var(--foreground))]">
                {opportunity?.title}
              </h1>
              <Badge className={`${getScoreColor(opportunity?.score || 0)} text-white font-mono text-lg px-3 py-1`}>
                {opportunity?.score}
              </Badge>
            </div>
            <div className="flex items-center gap-4 text-sm text-[hsl(var(--foreground-muted))]">
              <span className="font-medium">
                Solicitation #: {opportunity?.solicitation_id || opportunity?.external_id || 'N/A'}
              </span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <Building2 className="h-4 w-4" />
                {opportunity?.agency || 'N/A'}
              </span>
              <span className="flex items-center gap-1">
                <Calendar className="h-4 w-4" />
                {opportunity?.due_date ? new Date(opportunity.due_date).toLocaleDateString() : 'N/A'}
              </span>
              <span className="flex items-center gap-1">
                <DollarSign className="h-4 w-4" />
                {opportunity?.estimated_value || 'N/A'}
              </span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            {opportunity?.ai_relevance_summary && (
              <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
                <CardHeader>
                  <CardTitle className="text-[hsl(var(--foreground))]">AI Analysis</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-[hsl(var(--foreground-secondary))]">{opportunity.ai_relevance_summary}</p>
                </CardContent>
              </Card>
            )}

            <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
              <CardHeader>
                <CardTitle className="text-[hsl(var(--foreground))]">Description</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-[hsl(var(--foreground-secondary))] whitespace-pre-wrap">{opportunity?.description}</p>
              </CardContent>
            </Card>

            {opportunity?.source_url && (
              <a
                href={opportunity.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-sm hover:underline"
                style={{color: primaryColor}}
              >
                <ExternalLink className="h-4 w-4" />
                View Original
              </a>
            )}
          </div>

          <div className="space-y-4">
            <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
              <CardHeader>
                <CardTitle className="text-sm">Status</CardTitle>
              </CardHeader>
              <CardContent>
                <Select value={status} onValueChange={setStatus}>
                  <SelectTrigger className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]">
                    <SelectItem value="new">New</SelectItem>
                    <SelectItem value="interested">Interested</SelectItem>
                    <SelectItem value="dismissed">Dismissed</SelectItem>
                    <SelectItem value="won">Won</SelectItem>
                    <SelectItem value="lost">Lost</SelectItem>
                  </SelectContent>
                </Select>
              </CardContent>
            </Card>

            <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
              <CardHeader>
                <CardTitle className="text-sm">Notes</CardTitle>
              </CardHeader>
              <CardContent>
                <Textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Add your notes..."
                  rows={6}
                  className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))] text-sm"
                />
              </CardContent>
            </Card>

            <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
              <CardContent className="p-4 space-y-2">
                <Button
                  onClick={handleSave}
                  className="w-full text-white"
                  style={{background: primaryColor}}
                >
                  <Save className="h-4 w-4 mr-2" />
                  Save
                </Button>
                <Button
                  onClick={handleDelete}
                  variant="outline"
                  className="w-full border-[hsl(var(--accent-danger))] text-[hsl(var(--accent-danger))]"
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </TenantLayout>
  );
}
