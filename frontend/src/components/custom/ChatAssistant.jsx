import React, { useState, useEffect, useRef } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Card } from '../ui/card';
import { apiClient, showApiError } from '../../lib/api';
import { MessageCircle, X, Send } from 'lucide-react';

export const ChatAssistant = ({ agentType = 'opportunities', primaryColor, tenantId = null }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [sending, setSending] = useState(false);
  const [conversationId] = useState(`conv-${Date.now()}`);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async () => {
    if (!inputValue.trim() || sending) return;

    const userMessage = inputValue;
    setInputValue('');
    
    // Add user message immediately
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setSending(true);

    try {
      const payload = {
        conversation_id: conversationId,
        message: userMessage,
        agent_type: agentType
      };
      // Include tenant_id for super_admin preview mode
      if (tenantId) {
        payload.tenant_id = tenantId;
      }
      const response = await apiClient.post('/api/chat/message', payload);

      // Add assistant response
      setMessages(prev => [...prev, { role: 'assistant', content: response.data.content }]);
    } catch (error) {
      console.error('Chat error:', error);
      const traceId = error.response?.data?.trace_id || error.response?.headers?.['x-trace-id'];
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: traceId 
          ? `Sorry, I encountered an error. Please try again. (Ref: ${traceId})` 
          : 'Sorry, I encountered an error. Please try again.'
      }]);
    } finally {
      setSending(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <>
      {/* Chat Bubble */}
      {!isOpen && (
        <Button
          onClick={(e) => {
            e.stopPropagation();
            setIsOpen(true);
          }}
          className="fixed bottom-6 right-6 h-14 w-14 rounded-full shadow-lg flex items-center justify-center text-white hover:scale-110 transition-transform duration-200 p-0"
          style={{ background: primaryColor, zIndex: 9999 }}
          data-testid="chat-assistant-toggle"
        >
          <MessageCircle className="h-6 w-6" />
        </Button>
      )}

      {/* Chat Panel */}
      {isOpen && (
        <Card className="fixed bottom-6 right-6 w-96 h-[500px] bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))] shadow-2xl flex flex-col z-[9999]">
          {/* Header */}
          <div 
            className="px-4 py-3 border-b border-[hsl(var(--border))] flex items-center justify-between text-white"
            style={{ background: primaryColor }}
          >
            <div className="flex items-center gap-2">
              <MessageCircle className="h-5 w-5" />
              <span className="font-semibold">AI Assistant</span>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="hover:bg-white/20 rounded p-1 transition-colors"
              data-testid="chat-close-button"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {messages.length === 0 && (
              <div className="text-center text-sm text-[hsl(var(--foreground-muted))] py-8">
                <MessageCircle className="h-12 w-12 mx-auto mb-3 opacity-50" />
                <p>Ask me anything about {agentType === 'opportunities' ? 'contract opportunities' : 'intelligence reports'}!</p>
              </div>
            )}
            
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-2 ${
                    msg.role === 'user'
                      ? 'text-white'
                      : 'bg-[hsl(var(--background-tertiary))] border border-[hsl(var(--border))] text-[hsl(var(--foreground-secondary))]'
                  }`}
                  style={msg.role === 'user' ? { background: primaryColor } : {}}
                >
                  <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                </div>
              </div>
            ))}
            
            {sending && (
              <div className="flex justify-start">
                <div className="bg-[hsl(var(--background-tertiary))] border border-[hsl(var(--border))] rounded-lg px-4 py-2">
                  <div className="flex gap-1">
                    <div className="h-2 w-2 bg-[hsl(var(--foreground-muted))] rounded-full animate-bounce" style={{animationDelay: '0ms'}} />
                    <div className="h-2 w-2 bg-[hsl(var(--foreground-muted))] rounded-full animate-bounce" style={{animationDelay: '150ms'}} />
                    <div className="h-2 w-2 bg-[hsl(var(--foreground-muted))] rounded-full animate-bounce" style={{animationDelay: '300ms'}} />
                  </div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="p-4 border-t border-[hsl(var(--border))]">
            <div className="flex gap-2">
              <Input
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Type your message..."
                disabled={sending}
                className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                data-testid="chat-input"
              />
              <Button
                onClick={sendMessage}
                disabled={sending || !inputValue.trim()}
                className="text-white"
                style={{ background: primaryColor }}
                data-testid="chat-send-button"
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
            <p className="text-xs text-[hsl(var(--foreground-muted))] mt-2">
              Press Enter to send
            </p>
          </div>
        </Card>
      )}
    </>
  );
};
