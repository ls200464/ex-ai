"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { personaApi, chatApi, streamChat, type PersonaDetail, type SessionSummary, type MessageResponse } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

function MessageBubble({
  role,
  content,
  isStreaming,
  onRegenerate,
  onDelete,
}: {
  role: string;
  content: string;
  isStreaming?: boolean;
  onRegenerate?: () => void;
  onDelete?: () => void;
}) {
  const isUser = role === "user";
  const [hovered, setHovered] = useState(false);

  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4 group`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="flex items-center gap-1">
        {/* Action buttons for persona messages (left side) */}
        {!isUser && !isStreaming && hovered && (
          <div className="flex gap-0.5">
            {onRegenerate && (
              <button
                onClick={onRegenerate}
                className="w-6 h-6 rounded-full bg-muted hover:bg-muted-foreground/20 flex items-center justify-center text-xs transition-colors"
                title="重新生成"
              >
                🔄
              </button>
            )}
            {onDelete && (
              <button
                onClick={onDelete}
                className="w-6 h-6 rounded-full bg-muted hover:bg-destructive/20 flex items-center justify-center text-xs transition-colors hover:text-destructive"
                title="删除"
              >
                ✕
              </button>
            )}
          </div>
        )}

        <div
          className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
            isUser
              ? "bg-primary text-primary-foreground rounded-br-md"
              : "bg-muted rounded-bl-md"
          }`}
        >
          <p className="whitespace-pre-wrap break-words">
            {content}
            {isStreaming && <span className="animate-pulse">▌</span>}
          </p>
        </div>

        {/* Delete button for user messages (right side) */}
        {isUser && !isStreaming && hovered && onDelete && (
          <button
            onClick={onDelete}
            className="w-6 h-6 rounded-full bg-muted hover:bg-destructive/20 flex items-center justify-center text-xs transition-colors hover:text-destructive"
            title="删除"
          >
            ✕
          </button>
        )}
      </div>
    </div>
  );
}

export default function ChatPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useRequireAuth();
  const [persona, setPersona] = useState<PersonaDetail | null>(null);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [authLoading, isAuthenticated, router]);

  if (authLoading || !isAuthenticated) {
    return (
      <div className="max-w-2xl mx-auto h-[calc(100vh-3.5rem)] flex flex-col">
        <div className="px-4 py-3 border-b">
          <div className="h-6 w-32 bg-muted rounded animate-pulse" />
        </div>
      </div>
    );
  }
  const [session, setSession] = useState<SessionSummary | null>(null);
  const [messages, setMessages] = useState<Array<{ id: string; role: string; content: string }>>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Load persona, find/create session, load messages
  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        // Load persona
        const p = await personaApi.get(params.id);
        if (cancelled) return;
        setPersona(p);

        // Find or create session
        const sessions = await chatApi.sessions(params.id);
        let s: SessionSummary;
        if (sessions.length > 0) {
          s = sessions[0];
        } else {
          s = await chatApi.createSession(params.id, "对话 " + new Date().toLocaleDateString());
        }
        if (cancelled) return;
        setSession(s);

        // Load messages
        const msgs = await chatApi.messages(s.id);
        if (cancelled) return;
        setMessages(msgs.map((m) => ({ id: m.id, role: m.role, content: m.content })));
      } catch (err: any) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    init();
    return () => { cancelled = true; };
  }, [params.id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  const handleSend = useCallback((text?: string) => {
    const content = (text ?? input).trim();
    if (!content || isStreaming) return;

    if (!text) setInput("");
    setMessages((prev) => [...prev, { id: "", role: "user", content }]);
    setIsStreaming(true);
    setStreamingContent("");

    abortRef.current = streamChat(
      params.id,
      content,
      (token) => {
        setStreamingContent((prev) => prev + token);
      },
      (doneText, messageId) => {
        setMessages((prev) => [...prev, { id: messageId || "", role: "persona", content: doneText }]);
        setStreamingContent("");
        setIsStreaming(false);
      },
      (err) => {
        setError(err);
        setIsStreaming(false);
        setStreamingContent("");
      }
    );
  }, [input, isStreaming, params.id]);

  const handleDeleteMessage = useCallback(async (msgIndex: number) => {
    const msg = messages[msgIndex];
    if (!msg) return;
    // Delete from backend if it has an ID
    if (msg.id) {
      try { await chatApi.deleteMessage(msg.id); } catch {}
    }
    setMessages((prev) => prev.filter((_, i) => i !== msgIndex));
  }, [messages]);

  const handleRegenerate = useCallback(async () => {
    // Find the last persona message and the user message before it
    const lastIdx = messages.length - 1;
    if (lastIdx < 0 || messages[lastIdx].role !== "persona") return;

    let userIdx = -1;
    for (let i = lastIdx - 1; i >= 0; i--) {
      if (messages[i].role === "user") { userIdx = i; break; }
    }
    if (userIdx === -1) return;

    const personaMsg = messages[lastIdx];
    const userMsg = messages[userIdx];

    // Delete the persona message from backend
    if (personaMsg.id) {
      try { await chatApi.deleteMessage(personaMsg.id); } catch {}
    }

    // Remove only the persona message from state (keep user message)
    setMessages((prev) => prev.slice(0, -1));

    // Re-stream without adding a duplicate user message
    setIsStreaming(true);
    setStreamingContent("");

    abortRef.current = streamChat(
      params.id,
      userMsg.content,
      (token) => setStreamingContent((prev) => prev + token),
      (doneText, messageId) => {
        setMessages((prev) => [...prev, { id: messageId || "", role: "persona", content: doneText }]);
        setStreamingContent("");
        setIsStreaming(false);
      },
      (err) => {
        setError(err);
        setIsStreaming(false);
        setStreamingContent("");
      }
    );
  }, [messages, params.id]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8 space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (!persona) return null;

  return (
    <div className="max-w-2xl mx-auto h-[calc(100vh-3.5rem)] flex flex-col">
      {/* Header */}
      <div className="px-4 py-3 border-b flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => router.push(`/personas/${params.id}`)}>
          ← 返回
        </Button>
        <div>
          <p className="font-medium text-sm">{persona.display_name || persona.name}</p>
          <p className="text-xs text-muted-foreground">
            {persona.status === "ready"
              ? "AI 人格已就绪"
              : persona.status === "archived"
              ? "已归档"
              : "生成中..."}
          </p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive mb-4">
            {error}
            <button className="ml-2 underline" onClick={() => setError(null)}>
              关闭
            </button>
          </div>
        )}

        {messages.length === 0 && !isStreaming && (
          <div className="text-center py-20 text-muted-foreground">
            <p className="text-3xl mb-3">💬</p>
            <p className="text-sm">
              {persona.status === "ready"
                ? `开始和 ${persona.display_name || persona.name} 对话吧`
                : "Persona 尚未就绪，请等待 AI 提取完成"}
            </p>
          </div>
        )}

        {messages.map((msg, i) => {
          const isLast = i === messages.length - 1;
          const isPersona = msg.role === "persona";
          return (
            <MessageBubble
              key={msg.id || i}
              role={msg.role}
              content={msg.content}
              onRegenerate={isLast && isPersona && !isStreaming ? handleRegenerate : undefined}
              onDelete={() => handleDeleteMessage(i)}
            />
          );
        })}

        {isStreaming && streamingContent && (
          <MessageBubble role="persona" content={streamingContent} isStreaming />
        )}

        {isStreaming && !streamingContent && (
          <div className="flex justify-start mb-4">
            <div className="bg-muted rounded-2xl rounded-bl-md px-4 py-2.5">
              <div className="flex gap-1">
                <span className="w-1.5 h-1.5 bg-muted-foreground/40 rounded-full animate-bounce" />
                <span className="w-1.5 h-1.5 bg-muted-foreground/40 rounded-full animate-bounce [animation-delay:0.15s]" />
                <span className="w-1.5 h-1.5 bg-muted-foreground/40 rounded-full animate-bounce [animation-delay:0.3s]" />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t bg-background">
        <div className="flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              persona.status === "ready"
                ? `跟 ${persona.display_name || persona.name} 说点什么...`
                : "Persona 尚未就绪..."
            }
            disabled={isStreaming || persona.status !== "ready"}
            className="flex-1"
          />
          <Button
            onClick={() => handleSend()}
            disabled={!input.trim() || isStreaming || persona.status !== "ready"}
          >
            发送
          </Button>
        </div>
      </div>
    </div>
  );
}
