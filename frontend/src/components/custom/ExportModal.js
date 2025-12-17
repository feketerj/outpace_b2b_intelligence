import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import axios from 'axios';
import { toast } from 'sonner';
import { Download, FileText, FileSpreadsheet } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export const ExportModal = ({ 
  open, 
  onOpenChange, 
  opportunities = [], 
  intelligence = [],
  primaryColor,
  tenantId
}) => {
  const [selectedOpps, setSelectedOpps] = useState([]);
  const [selectedIntel, setSelectedIntel] = useState([]);
  const [exporting, setExporting] = useState(false);

  const toggleOpp = (id) => {
    setSelectedOpps(prev => 
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const toggleIntel = (id) => {
    setSelectedIntel(prev => 
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const selectAllOpps = () => {
    setSelectedOpps(opportunities.map(o => o.id));
  };

  const selectAllIntel = () => {
    setSelectedIntel(intelligence.map(i => i.id));
  };

  const handleExport = async (format) => {
    const oppIds = selectedOpps.length > 0 ? selectedOpps : [];
    const intelIds = selectedIntel.length > 0 ? selectedIntel : [];
    
    if (oppIds.length === 0 && intelIds.length === 0) {
      toast.error('Select at least one item to export');
      return;
    }

    setExporting(true);
    
    try {
      const response = await axios.post(
        `${API_URL}/api/exports/${format}`,
        {
          opportunity_ids: oppIds,
          intelligence_ids: intelIds,
          tenant_id: tenantId
        },
        {
          responseType: 'blob'
        }
      );

      // Download file
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `export_${Date.now()}.${format === 'pdf' ? 'pdf' : 'xlsx'}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      
      toast.success(`${format.toUpperCase()} downloaded!`);
      onOpenChange(false);
    } catch (error) {
      console.error('Export failed:', error);
      toast.error('Export failed');
    } finally {
      setExporting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))] max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-[hsl(var(--foreground))] text-2xl">
            Export Data
          </DialogTitle>
          <DialogDescription className="text-[hsl(var(--foreground-secondary))]">
            Select items to export as branded PDF or Excel spreadsheet
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="opportunities" className="w-full">
          <TabsList className="grid w-full grid-cols-2 bg-[hsl(var(--background-tertiary))]">
            <TabsTrigger value="opportunities">
              Opportunities ({selectedOpps.length}/{opportunities.length})
            </TabsTrigger>
            <TabsTrigger value="intelligence">
              Intelligence ({selectedIntel.length}/{intelligence.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="opportunities" className="space-y-3 mt-4">
            <div className="flex justify-between items-center mb-3">
              <Button
                size="sm"
                variant="outline"
                onClick={selectAllOpps}
                className="border-[hsl(var(--border))]"
              >
                Select All
              </Button>
              <span className="text-xs text-[hsl(var(--foreground-muted))]">
                {selectedOpps.length} selected
              </span>
            </div>

            <div className="space-y-2 max-h-96 overflow-y-auto">
              {opportunities.map((opp) => (
                <div
                  key={opp.id}
                  className="flex items-start gap-3 p-3 rounded border border-[hsl(var(--border))] hover:bg-[hsl(var(--background-tertiary))] cursor-pointer"
                  onClick={() => toggleOpp(opp.id)}
                >
                  <input
                    type="checkbox"
                    checked={selectedOpps.includes(opp.id)}
                    onChange={() => toggleOpp(opp.id)}
                    className="mt-1 h-4 w-4"
                  />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-[hsl(var(--foreground))]">{opp.title}</p>
                    <p className="text-xs text-[hsl(var(--foreground-muted))]">
                      Score: {opp.score} | {opp.agency}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="intelligence" className="space-y-3 mt-4">
            <div className="flex justify-between items-center mb-3">
              <Button
                size="sm"
                variant="outline"
                onClick={selectAllIntel}
                className="border-[hsl(var(--border))]"
              >
                Select All
              </Button>
              <span className="text-xs text-[hsl(var(--foreground-muted))]">
                {selectedIntel.length} selected
              </span>
            </div>

            <div className="space-y-2 max-h-96 overflow-y-auto">
              {intelligence.map((item) => (
                <div
                  key={item.id}
                  className="flex items-start gap-3 p-3 rounded border border-[hsl(var(--border))] hover:bg-[hsl(var(--background-tertiary))] cursor-pointer"
                  onClick={() => toggleIntel(item.id)}
                >
                  <input
                    type="checkbox"
                    checked={selectedIntel.includes(item.id)}
                    onChange={() => toggleIntel(item.id)}
                    className="mt-1 h-4 w-4"
                  />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-[hsl(var(--foreground))]">{item.title}</p>
                    <p className="text-xs text-[hsl(var(--foreground-muted))]">
                      {new Date(item.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>
        </Tabs>

        <div className="flex gap-2 pt-4 border-t border-[hsl(var(--border))]">
          <Button
            data-testid="export-pdf-btn"
            onClick={() => handleExport('pdf')}
            disabled={exporting}
            className="flex-1 text-white"
            style={{background: primaryColor}}
          >
            <FileText className="h-4 w-4 mr-2" />
            {exporting ? 'Exporting...' : 'Export PDF'}
          </Button>
          <Button
            data-testid="export-excel-btn"
            onClick={() => handleExport('excel')}
            disabled={exporting}
            className="flex-1 text-white"
            style={{background: primaryColor}}
          >
            <FileSpreadsheet className="h-4 w-4 mr-2" />
            {exporting ? 'Exporting...' : 'Export Excel'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
