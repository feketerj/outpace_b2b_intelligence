import { useState, useEffect, useCallback } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import apiClient from '@/lib/api';

// ─── Opportunities Tab ────────────────────────────────────────────────────────

function OpportunitiesTab() {
  const [records, setRecords] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchOpportunities = useCallback(async () => {
    setLoading(true);
    try {
      const params = search ? { search } : {};
      const response = await apiClient.get('/api/admin/database/opportunities', { params });
      setRecords(response.data?.items ?? response.data ?? []);
    } catch (err) {
      console.error('Failed to fetch opportunities:', err);
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    fetchOpportunities();
  }, [fetchOpportunities]);

  const handleDelete = async (id) => {
    if (!confirm('Delete this opportunity?')) return;
    try {
      await apiClient.delete(`/api/admin/database/opportunities/${id}`);
      setRecords((prev) => prev.filter((r) => r.id !== id));
    } catch (err) {
      console.error('Failed to delete opportunity:', err);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Input
          placeholder="Search opportunities…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm"
        />
        <Button variant="outline" onClick={fetchOpportunities} disabled={loading}>
          {loading ? 'Loading…' : 'Refresh'}
        </Button>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>ID</TableHead>
            <TableHead>Title</TableHead>
            <TableHead>Tenant</TableHead>
            <TableHead>Created</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {records.length === 0 ? (
            <TableRow>
              <TableCell colSpan={5} className="text-center text-muted-foreground">
                {loading ? 'Loading…' : 'No records found.'}
              </TableCell>
            </TableRow>
          ) : (
            records.map((record) => (
              <TableRow key={record.id}>
                <TableCell className="font-mono text-xs">{record.id}</TableCell>
                <TableCell>{record.title ?? record.name ?? '—'}</TableCell>
                <TableCell>{record.tenant_id ?? '—'}</TableCell>
                <TableCell>
                  {record.created_at
                    ? new Date(record.created_at).toLocaleDateString()
                    : '—'}
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleDelete(record.id)}
                  >
                    Delete
                  </Button>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}

// ─── Intelligence Tab ─────────────────────────────────────────────────────────

function IntelligenceTab() {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchIntelligence = useCallback(async () => {
    setLoading(true);
    try {
      const response = await apiClient.get('/api/admin/database/intelligence');
      setRecords(response.data?.items ?? response.data ?? []);
    } catch (err) {
      console.error('Failed to fetch intelligence records:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchIntelligence();
  }, [fetchIntelligence]);

  const handleDelete = async (id) => {
    if (!confirm('Delete this intelligence report?')) return;
    try {
      await apiClient.delete(`/api/admin/database/intelligence/${id}`);
      setRecords((prev) => prev.filter((r) => r.id !== id));
    } catch (err) {
      console.error('Failed to delete intelligence record:', err);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button variant="outline" onClick={fetchIntelligence} disabled={loading}>
          {loading ? 'Loading…' : 'Refresh'}
        </Button>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>ID</TableHead>
            <TableHead>Title</TableHead>
            <TableHead>Tenant</TableHead>
            <TableHead>Created</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {records.length === 0 ? (
            <TableRow>
              <TableCell colSpan={5} className="text-center text-muted-foreground">
                {loading ? 'Loading…' : 'No records found.'}
              </TableCell>
            </TableRow>
          ) : (
            records.map((record) => (
              <TableRow key={record.id}>
                <TableCell className="font-mono text-xs">{record.id}</TableCell>
                <TableCell>{record.title ?? record.name ?? '—'}</TableCell>
                <TableCell>{record.tenant_id ?? '—'}</TableCell>
                <TableCell>
                  {record.created_at
                    ? new Date(record.created_at).toLocaleDateString()
                    : '—'}
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleDelete(record.id)}
                  >
                    Delete
                  </Button>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}

// ─── Chat Messages Tab ────────────────────────────────────────────────────────

function ChatTab() {
  // FIX: Previously iterated hardcoded IDs ['test-conv-1', 'smoke-test-123', 'final-test']
  // Now fetches real conversation list from the API
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedConvId, setSelectedConvId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [messagesLoading, setMessagesLoading] = useState(false);

  // Fetch all conversations via the admin database endpoint
  // Falls back to extracting distinct conversation_ids from chat turns
  const fetchConversations = useCallback(async () => {
    setLoading(true);
    try {
      // Primary: try dedicated conversations list endpoint
      let convData = null;

      try {
        const response = await apiClient.get('/api/chat/conversations');
        convData = response.data?.items ?? response.data ?? [];
      } catch {
        // Fallback: fetch from admin database endpoint for chat turns
        const response = await apiClient.get('/api/admin/database/chat_turns');
        const turns = response.data?.items ?? response.data ?? [];

        // Deduplicate by conversation_id to synthesize a conversation list
        const seen = new Set();
        convData = turns
          .filter((t) => {
            if (seen.has(t.conversation_id)) return false;
            seen.add(t.conversation_id);
            return true;
          })
          .map((t) => ({
            id: t.conversation_id,
            tenant_id: t.tenant_id,
            user_id: t.user_id,
            created_at: t.created_at,
          }));
      }

      setConversations(convData);
    } catch (err) {
      console.error('Failed to fetch conversations:', err);
      setConversations([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  // Fetch messages for a selected conversation
  const fetchMessages = useCallback(async (convId) => {
    if (!convId) return;
    setMessagesLoading(true);
    setMessages([]);
    try {
      const response = await apiClient.get(`/api/chat/conversations/${convId}/messages`);
      setMessages(response.data?.items ?? response.data ?? []);
    } catch {
      // Fallback: query admin endpoint with conversation_id filter
      try {
        const response = await apiClient.get('/api/admin/database/chat_turns', {
          params: { conversation_id: convId },
        });
        setMessages(response.data?.items ?? response.data ?? []);
      } catch (err) {
        console.error('Failed to fetch messages:', err);
      }
    } finally {
      setMessagesLoading(false);
    }
  }, []);

  const handleSelectConversation = (convId) => {
    setSelectedConvId(convId);
    fetchMessages(convId);
  };

  const handleDeleteConversation = async (convId) => {
    if (!confirm(`Delete conversation ${convId}?`)) return;
    try {
      await apiClient.delete(`/api/chat/conversations/${convId}`);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (selectedConvId === convId) {
        setSelectedConvId(null);
        setMessages([]);
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button variant="outline" onClick={fetchConversations} disabled={loading}>
          {loading ? 'Loading…' : 'Refresh'}
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Conversation list */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-sm">Conversations</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {conversations.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground">
                {loading ? 'Loading…' : 'No conversations found.'}
              </p>
            ) : (
              <ul className="divide-y">
                {conversations.map((conv) => (
                  <li
                    key={conv.id}
                    className={`p-3 cursor-pointer hover:bg-muted/50 flex items-center justify-between ${
                      selectedConvId === conv.id ? 'bg-muted' : ''
                    }`}
                  >
                    <button
                      className="text-left flex-1 min-w-0"
                      onClick={() => handleSelectConversation(conv.id)}
                    >
                      <p className="text-xs font-mono truncate">{conv.id}</p>
                      <p className="text-xs text-muted-foreground">
                        {conv.created_at
                          ? new Date(conv.created_at).toLocaleDateString()
                          : 'Unknown date'}
                      </p>
                    </button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="ml-2 text-destructive hover:text-destructive"
                      onClick={() => handleDeleteConversation(conv.id)}
                    >
                      ✕
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* Messages panel */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-sm">
              {selectedConvId ? `Messages — ${selectedConvId}` : 'Select a conversation'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!selectedConvId ? (
              <p className="text-sm text-muted-foreground">Select a conversation to view messages.</p>
            ) : messagesLoading ? (
              <p className="text-sm text-muted-foreground animate-pulse">Loading messages…</p>
            ) : messages.length === 0 ? (
              <p className="text-sm text-muted-foreground">No messages in this conversation.</p>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {messages.map((msg, idx) => (
                  <div
                    key={msg.id ?? idx}
                    className={`flex ${
                      msg.role === 'user' ? 'justify-end' : 'justify-start'
                    }`}
                  >
                    <div
                      className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                        msg.role === 'user'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted text-foreground'
                      }`}
                    >
                      <p className="text-xs font-semibold mb-1 capitalize">{msg.role ?? 'unknown'}</p>
                      <p className="whitespace-pre-wrap">{msg.content ?? msg.message ?? ''}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ─── Main DatabaseManager Page ────────────────────────────────────────────────

export default function DatabaseManager() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1
          className="text-3xl font-bold"
          style={{ color: 'hsl(var(--foreground))' }}
        >
          Database Manager
        </h1>
        <p style={{ color: 'hsl(var(--muted-foreground))' }}>
          View and manage database records.
        </p>
      </div>

      <Tabs defaultValue="opportunities">
        <TabsList>
          <TabsTrigger value="opportunities">Opportunities</TabsTrigger>
          <TabsTrigger value="intelligence">Intelligence</TabsTrigger>
          <TabsTrigger value="chat">Chat Messages</TabsTrigger>
        </TabsList>

        <TabsContent value="opportunities" className="mt-4">
          <OpportunitiesTab />
        </TabsContent>

        <TabsContent value="intelligence" className="mt-4">
          <IntelligenceTab />
        </TabsContent>

        <TabsContent value="chat" className="mt-4">
          <ChatTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
