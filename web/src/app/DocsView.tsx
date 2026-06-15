"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import type {
  AgentDocsResponse,
  DocsEndpoint,
  DocsTag,
  GenerateExampleResponse,
  TryItOutResponse,
} from "@/types/api-docs";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const CodeMirrorEditor = dynamic(
  () => import("@/components/CodeMirrorEditor").then((m) => ({ default: m.CodeMirrorEditor })),
  {
    ssr: false,
    loading: () => (
      <div className="h-32 rounded-lg bg-neutral-900/80 border border-neutral-800 animate-pulse" />
    ),
  }
);

const API_DOCS = "/api/agent-docs";
const GENERATE_EXAMPLE = "/api-reference/generate-example";
const TRY_IT_OUT = "/api/try-it-out";
const AGENT_CHAT = "/api/agent/chat";
const BEARER_STORAGE_KEY = "api-docs-bearer-token";

function getStoredBearerToken(): string {
  if (typeof window === "undefined") return "";
  try {
    return sessionStorage.getItem(BEARER_STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function DocsView() {
  const [docs, setDocs] = useState<AgentDocsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [externalUrl, setExternalUrl] = useState("");
  const [openapiUrl, setOpenapiUrl] = useState<string | null>(null);

  const loadDocs = useCallback(async (urlParam: string | null) => {
    setLoading(true);
    setError(null);
    try {
      const target = urlParam
        ? `${API_DOCS}?openapi_url=${encodeURIComponent(urlParam)}`
        : API_DOCS;
      const res = await fetch(target);
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || res.statusText || "Failed to load docs");
      }
      const data: AgentDocsResponse = await res.json();
      setDocs(data);
      setOpenapiUrl(urlParam);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load docs");
      setDocs(null);
    } finally {
      setLoading(false);
    }
  }, []);

  // On mount: if ?openapi_url= in URL, load external docs
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const urlParam = params.get("openapi_url");
    if (urlParam) loadDocs(urlParam);
  }, [loadDocs]);

  const handleMyApi = () => loadDocs(null);
  const handleExternalSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const url = externalUrl.trim();
    if (!url) return;
    loadDocs(url);
    const u = new URL(window.location.href);
    u.searchParams.set("openapi_url", url);
    window.history.replaceState({}, "", u.toString());
  };

  if (docs) {
    return (
      <DocsUI
        docs={docs}
        openapiUrl={openapiUrl}
        onReset={() => {
          setDocs(null);
          setOpenapiUrl(null);
          window.history.replaceState({}, "", window.location.pathname || "/");
        }}
      />
    );
  }

  const isDebug = process.env.NODE_ENV === "development";

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 sm:p-8 safe-area-padding relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 bg-[#0a0a0a]" aria-hidden />
      <div
        className="absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_50%_-20%,rgba(120,119,198,0.15),transparent)]"
        aria-hidden
      />
      <div
        className="absolute inset-0 bg-[radial-gradient(ellipse_60%_50%_at_50%_100%,rgba(34,197,94,0.06),transparent)]"
        aria-hidden
      />
      <div
        className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-sky-500/[0.03] rounded-full blur-3xl"
        aria-hidden
      />

      <div className="relative w-full max-w-lg space-y-10 min-w-0">
        {/* Hero */}
        <div className="text-center space-y-3">
          <h1 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
            API Docs
          </h1>
          <p className="text-neutral-400 text-sm sm:text-base max-w-sm mx-auto">
            Paste any OpenAPI or Swagger URL to browse docs, chat, and generate
            code examples.
          </p>
        </div>

        {error && (
          <div className="rounded-xl bg-rose-950/40 border border-rose-800/60 text-rose-200 px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {loading && (
          <div className="flex flex-col items-center gap-3 py-8">
            <div className="w-8 h-8 rounded-full border-2 border-neutral-600 border-t-emerald-500 animate-spin" />
            <p className="text-neutral-500 text-sm">Loading docs…</p>
          </div>
        )}

        {!loading && (
          <div className="space-y-6">
            {/* Document an API — primary card */}
            <div className="rounded-2xl bg-neutral-900/80 border border-neutral-700/80 shadow-xl shadow-black/20 p-6 space-y-4">
              <div className="flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/20 text-emerald-400 text-sm font-medium">
                  →
                </span>
                <h2 className="text-sm font-semibold text-neutral-200 uppercase tracking-wider">
                  Document an API
                </h2>
              </div>
              <p className="text-neutral-400 text-sm">
                Base URL or direct link to OpenAPI/Swagger JSON (e.g.
                …/openapi.json or …/swagger.json).
              </p>
              <form
                onSubmit={handleExternalSubmit}
                className="flex flex-col sm:flex-row gap-3"
              >
                <input
                  type="url"
                  value={externalUrl}
                  onChange={(e) => setExternalUrl(e.target.value)}
                  placeholder="https://api.example.com or …/openapi.json"
                  className="flex-1 min-w-0 px-4 py-3 rounded-xl bg-neutral-950/80 border border-neutral-700 text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50 transition-all"
                />
                <button
                  type="submit"
                  className="sm:shrink-0 px-5 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium transition-colors"
                >
                  Load
                </button>
              </form>
            </div>

            {/* Load my API docs — only in debug */}
            {isDebug && (
              <div className="rounded-2xl bg-neutral-900/50 border border-neutral-800 border-dashed p-6 space-y-3">
                <h2 className="text-xs font-medium text-neutral-500 uppercase tracking-widest">
                  Document my API (dev)
                </h2>
                <p className="text-neutral-500 text-sm">
                  Use this app’s OpenAPI (same origin).
                </p>
                <button
                  type="button"
                  onClick={handleMyApi}
                  className="w-full px-4 py-3 rounded-xl bg-neutral-800 text-neutral-300 font-medium hover:bg-neutral-700 hover:text-neutral-100 border border-neutral-700 transition-colors"
                >
                  Load my API docs
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

interface ChatMessage {
  role: string;
  content: string;
}

function DocsUI({
  docs,
  openapiUrl,
  onReset,
}: {
  docs: AgentDocsResponse;
  openapiUrl: string | null;
  onReset: () => void;
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [contextTagNames, setContextTagNames] = useState<string[]>([]);
  const [atMentionHighlight, setAtMentionHighlight] = useState(0);
  const [bearerToken, setBearerToken] = useState(() => getStoredBearerToken());
  const [authPopoverOpen, setAuthPopoverOpen] = useState(false);
  const chatInputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    try {
      if (bearerToken) sessionStorage.setItem(BEARER_STORAGE_KEY, bearerToken);
      else sessionStorage.removeItem(BEARER_STORAGE_KEY);
    } catch {
      /* ignore */
    }
  }, [bearerToken]);

  const resizeTextarea = useCallback(() => {
    const el = chatInputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, []);

  useEffect(() => {
    resizeTextarea();
  }, [chatInput, resizeTextarea]);

  const closeSidebar = () => setSidebarOpen(false);

  const addContextTag = (tagName: string) => {
    if (!tagName || contextTagNames.includes(tagName)) return;
    setContextTagNames((prev) => [...prev, tagName].sort());
  };

  const removeContextTag = (tagName: string) => {
    setContextTagNames((prev) => prev.filter((t) => t !== tagName));
  };

  // When user types "@", show overlay with modules. Query = text after last "@".
  const atMatch = chatInput.match(/@([^\s]*)$/);
  const atMentionQuery = atMatch ? atMatch[1].toLowerCase() : null;
  const matchingTags =
    atMentionQuery === null
      ? []
      : docs.tags.filter((t) => t.name.toLowerCase().includes(atMentionQuery));
  const showAtOverlay = atMentionQuery !== null && docs.tags.length > 0;

  const applyAtMention = (tagName: string) => {
    addContextTag(tagName);
    setChatInput((prev) => prev.replace(/@[^\s]*$/, "").trimEnd());
    setAtMentionHighlight(0);
    chatInputRef.current?.focus();
  };

  const sendChat = async (e: React.FormEvent) => {
    e.preventDefault();
    const content = chatInput.trim();
    if (!content || chatLoading) return;
    const userMsg: ChatMessage = { role: "user", content };
    setChatMessages((prev) => [...prev, userMsg]);
    setChatInput("");
    setChatLoading(true);
    try {
      const messages = [...chatMessages, userMsg].map((m) => ({
        role: m.role,
        content: m.content,
      }));
      const body: {
        messages: { role: string; content: string }[];
        openapi_url?: string;
        context_tag_names?: string[];
      } = { messages };
      if (openapiUrl) body.openapi_url = openapiUrl;
      if (contextTagNames.length > 0) body.context_tag_names = contextTagNames;
      const res = await fetch(AGENT_CHAT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok)
        throw new Error((data as { detail?: string }).detail || res.statusText);
      const assistant = (
        data as { message?: { role: string; content: string } }
      ).message;
      if (assistant?.content != null)
        setChatMessages((prev) => [
          ...prev,
          { role: "assistant", content: assistant.content },
        ]);
    } catch (err) {
      setChatMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: err instanceof Error ? err.message : "Failed to send.",
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen min-w-0 flex-1 flex-col overflow-x-hidden relative safe-area-padding">
      {/* Same background as landing page */}
      <div className="fixed inset-0 -z-10 bg-[#0a0a0a]" aria-hidden />
      <div
        className="fixed inset-0 -z-10 bg-[radial-gradient(ellipse_80%_60%_at_50%_-20%,rgba(120,119,198,0.15),transparent)]"
        aria-hidden
      />
      <div
        className="fixed inset-0 -z-10 bg-[radial-gradient(ellipse_60%_50%_at_50%_100%,rgba(34,197,94,0.06),transparent)]"
        aria-hidden
      />
      <div
        className="fixed top-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] -z-10 bg-sky-500/[0.03] rounded-full blur-3xl"
        aria-hidden
      />

      <div className="fixed top-4 left-4 right-4 z-30 flex justify-center pointer-events-none">
        <header className="pointer-events-auto w-full max-w-4xl h-14 flex items-center gap-2 sm:gap-4 px-4 sm:px-5 rounded-2xl border border-white/10 bg-neutral-900/40 backdrop-blur-xl shadow-lg shadow-black/20">
          <button
            type="button"
            onClick={() => setSidebarOpen((o) => !o)}
            className="lg:hidden p-2 -ml-2 rounded-lg text-neutral-400 hover:text-neutral-100 hover:bg-white/5 transition-colors"
            aria-label="Toggle menu"
          >
            <svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 6h16M4 12h16M4 18h16"
              />
            </svg>
          </button>
          <a
            href="#overview"
            className="font-semibold text-neutral-50 truncate min-w-0 flex-1 sm:flex-initial tracking-tight"
          >
            {docs.title}
          </a>
          <nav className="hidden sm:flex gap-1">
            <a
              href="#overview"
              className="text-sm text-neutral-400 hover:text-neutral-100 px-3 py-2 rounded-lg hover:bg-white/5 transition-colors"
            >
              Overview
            </a>
            <a
              href="#overview-modules"
              className="text-sm text-neutral-400 hover:text-neutral-100 px-3 py-2 rounded-lg hover:bg-white/5 transition-colors"
            >
              API Reference
            </a>
          </nav>
          <div className="flex-1 min-w-0" />
          <div className="relative shrink-0">
              <button
                type="button"
                onClick={() => setAuthPopoverOpen((o) => !o)}
                className="text-sm text-neutral-400 hover:text-neutral-100 shrink-0 transition-colors flex items-center gap-1.5 px-2 py-1.5 rounded-lg hover:bg-white/5"
                aria-expanded={authPopoverOpen}
                aria-haspopup="dialog"
              >
                <span className="hidden sm:inline">Auth</span>
                <span className="sm:hidden">Auth</span>
                {bearerToken ? (
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" aria-label="Token set" />
                ) : null}
              </button>
              {authPopoverOpen && (
                <>
                  <div
                    className="fixed inset-0 z-40"
                    aria-hidden
                    onClick={() => setAuthPopoverOpen(false)}
                  />
                  <div
                    className="absolute right-0 top-full mt-1 z-50 w-72 sm:w-80 p-3 rounded-xl border border-white/10 bg-neutral-900 shadow-xl"
                    role="dialog"
                    aria-label="Bearer token for Try It Out"
                  >
                    <label htmlFor="bearer-token-input" className="block text-xs font-medium text-neutral-400 uppercase tracking-wider mb-2">
                      Bearer token
                    </label>
                    <p className="text-neutral-500 text-xs mb-2">
                      Used when you click Send on endpoints that require authentication.
                    </p>
                    <input
                      id="bearer-token-input"
                      type="password"
                      autoComplete="off"
                      value={bearerToken}
                      onChange={(e) => setBearerToken(e.target.value)}
                      placeholder="Paste your JWT or API key"
                      className="w-full px-3 py-2 rounded-lg bg-neutral-950 border border-neutral-700 text-neutral-100 text-sm placeholder-neutral-500 focus:outline-none focus:ring-1 focus:ring-emerald-500/50 focus:border-emerald-500/50"
                    />
                  </div>
                </>
              )}
          </div>
          {docs.base_url && (
            <a
              href={`${docs.base_url}/docs`}
              target="_blank"
              rel="noopener noreferrer"
              className="hidden sm:inline text-sm text-neutral-400 hover:text-neutral-100 shrink-0 transition-colors"
            >
              Try in Swagger
            </a>
          )}
          <button
            type="button"
            onClick={() => {
              setBearerToken("");
              onReset();
            }}
            className="text-sm text-neutral-400 hover:text-neutral-100 shrink-0 transition-colors"
          >
            Change API
          </button>
        </header>
      </div>

      {/* Backdrop when sidebar is open on mobile */}
      <button
        type="button"
        aria-label="Close menu"
        onClick={closeSidebar}
        className={`fixed inset-0 z-20 bg-black/60 backdrop-blur-sm transition-opacity lg:hidden ${
          sidebarOpen ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
      />

      <aside
        className={`fixed top-20 left-0 bottom-0 w-[min(280px,85vw)] overflow-y-auto z-20 lg:z-10 transition-transform duration-200 ease-out
          bg-surface border-r border-neutral-800
          lg:left-4 lg:top-24 lg:bottom-4 lg:w-[var(--side-width)] lg:rounded-2xl lg:border lg:border-white/10 lg:bg-neutral-900/40 lg:backdrop-blur-xl lg:shadow-lg lg:shadow-black/20
          ${
            sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
          }
        `}
      >
        <nav className="p-4 space-y-5">
          <p className="text-[11px] font-medium text-neutral-500 uppercase tracking-widest px-2">
            Getting started
          </p>
          <ul className="space-y-0.5">
            <li>
              <a
                href="#overview"
                onClick={closeSidebar}
                className="flex items-center gap-2 py-2.5 px-3 rounded-lg text-neutral-400 hover:bg-white/5 hover:text-neutral-100 transition-colors"
              >
                Introduction
              </a>
            </li>
          </ul>
          <p className="text-[11px] font-medium text-neutral-500 uppercase tracking-widest pt-4 px-2">
            API modules
          </p>
          {docs.tags.map((tag) => (
            <div key={tag.name}>
              <a
                href={`#tag-${tag.name.toLowerCase().replace(/\s+/g, "-")}`}
                onClick={closeSidebar}
                className="block py-2 px-3 rounded-lg text-neutral-300 hover:bg-white/5 hover:text-neutral-50 font-medium transition-colors"
              >
                {tag.name}
              </a>
              <ul className="ml-3 mt-0.5 space-y-0.5 border-l border-neutral-800 pl-3">
                {tag.endpoints.map((ep) => (
                  <li key={ep.endpoint_id}>
                    <a
                      href={`#${ep.endpoint_id}`}
                      onClick={closeSidebar}
                      className="flex items-center gap-2 py-1.5 px-2 rounded text-sm text-neutral-500 hover:bg-white/5 hover:text-neutral-200 transition-colors"
                    >
                      <span
                        className={`method method-${ep.method.toLowerCase()} shrink-0`}
                      >
                        {ep.method}
                      </span>
                      <span className="truncate">
                        {(ep.summary || ep.path).slice(0, 36)}
                        {(ep.summary || ep.path).length > 36 ? "…" : ""}
                      </span>
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
      </aside>

      {/* Right-side chat: container above, input + button below (outside, no divider) */}
      <div
        className="fixed top-20 right-0 bottom-0 w-[min(320px,90vw)] hidden lg:flex flex-col z-10
          lg:right-4 lg:top-24 lg:bottom-4 lg:w-[var(--chat-width)] gap-3"
      >
        <aside className="flex-1 min-h-0 flex flex-col rounded-2xl border border-white/10 bg-neutral-900/40 backdrop-blur-xl shadow-lg shadow-black/20 overflow-hidden">
          <div className="p-3">
            <p className="text-[11px] font-medium text-neutral-500 uppercase tracking-widest">
              Chat
            </p>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0 flex flex-col">
            {chatMessages.length === 0 && (
              <p className="text-neutral-500 text-sm">
                Ask about this API or request code examples.
              </p>
            )}
            {chatMessages.map((m, i) => (
              <div
                key={i}
                className={`flex ${
                  m.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm break-words ${
                    m.role === "user"
                      ? "bg-emerald-600/90 text-white rounded-br-md"
                      : "bg-neutral-700/80 text-neutral-100 rounded-bl-md"
                  } ${m.role === "assistant" ? "chat-markdown" : ""}`}
                >
                  <span
                    className={`font-medium text-[10px] uppercase tracking-wide block mb-1 ${
                      m.role === "user"
                        ? "text-emerald-100"
                        : "text-neutral-400"
                    }`}
                  >
                    {m.role === "user" ? "You" : "Assistant"}
                  </span>
                  {m.role === "user" ? (
                    <span className="whitespace-pre-wrap">{m.content}</span>
                  ) : (
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      rehypePlugins={[rehypeHighlight]}
                      components={{
                        h1: ({ children }) => (
                          <h1 className="text-base font-semibold mt-2 mb-1 first:mt-0">
                            {children}
                          </h1>
                        ),
                        h2: ({ children }) => (
                          <h2 className="text-sm font-semibold mt-2 mb-1 first:mt-0">
                            {children}
                          </h2>
                        ),
                        h3: ({ children }) => (
                          <h3 className="text-sm font-medium mt-1.5 mb-0.5 first:mt-0">
                            {children}
                          </h3>
                        ),
                        p: ({ children }) => (
                          <p className="my-1 last:mb-0">{children}</p>
                        ),
                        ul: ({ children }) => (
                          <ul className="list-disc list-inside my-1 space-y-0.5">
                            {children}
                          </ul>
                        ),
                        ol: ({ children }) => (
                          <ol className="list-decimal list-inside my-1 space-y-0.5">
                            {children}
                          </ol>
                        ),
                        li: ({ children }) => (
                          <li className="leading-relaxed">{children}</li>
                        ),
                        code: ({ className, children }) => {
                          const isBlock = className?.startsWith("language-");
                          if (isBlock) {
                            return (
                              <code
                                className={className}
                                style={{ whiteSpace: "pre-wrap" }}
                              >
                                {children}
                              </code>
                            );
                          }
                          return (
                            <code className="bg-neutral-800/80 px-1 py-0.5 rounded text-neutral-200 font-mono text-xs">
                              {children}
                            </code>
                          );
                        },
                        pre: ({ children }) => (
                          <pre className="!mt-2 !mb-2 overflow-x-auto rounded-lg bg-neutral-900/90 p-2 text-xs border border-neutral-600/50 [&>code]:!p-0 [&>code]:!bg-transparent">
                            {children}
                          </pre>
                        ),
                        blockquote: ({ children }) => (
                          <blockquote className="border-l-2 border-neutral-500 pl-2 my-1 text-neutral-300 italic">
                            {children}
                          </blockquote>
                        ),
                        strong: ({ children }) => (
                          <strong className="font-semibold text-neutral-50">
                            {children}
                          </strong>
                        ),
                      }}
                    >
                      {m.content}
                    </ReactMarkdown>
                  )}
                </div>
              </div>
            ))}
            {chatLoading && (
              <p className="text-neutral-500 text-sm">Thinking…</p>
            )}
          </div>
        </aside>
        <div className="shrink-0 flex flex-col gap-2">
          {/* Single container: chips + input + send button at bottom-right */}
          <div className="relative flex-1 min-w-0">
            <form onSubmit={sendChat} className="block">
              <div className="relative min-h-[80px] py-3 px-3 pr-14 pb-14 rounded-2xl bg-neutral-900/80 border border-white/10 focus-within:ring-1 focus-within:ring-white/20 flex flex-wrap items-center gap-2 content-start">
                {contextTagNames.map((name) => (
                  <span
                    key={name}
                    className="inline-flex items-center gap-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 pl-2.5 pr-1 py-0.5 text-xs font-medium shrink-0"
                  >
                    {name}
                    <button
                      type="button"
                      onClick={() => removeContextTag(name)}
                      className="rounded-full p-0.5 hover:bg-emerald-500/30 transition-colors"
                      aria-label={`Remove ${name} from context`}
                    >
                      <svg
                        className="w-3 h-3"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M6 18L18 6M6 6l12 12"
                        />
                      </svg>
                    </button>
                  </span>
                ))}
                <textarea
                  ref={chatInputRef}
                  rows={1}
                  value={chatInput}
                  onChange={(e) => {
                    setChatInput(e.target.value);
                    setAtMentionHighlight(0);
                    resizeTextarea();
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      if (showAtOverlay && matchingTags.length > 0) {
                        const idx = Math.min(
                          atMentionHighlight,
                          matchingTags.length - 1
                        );
                        if (matchingTags[idx]) {
                          e.preventDefault();
                          applyAtMention(matchingTags[idx].name);
                        }
                      } else {
                        e.preventDefault();
                        const form = e.currentTarget.form;
                        if (form && chatInput.trim()) form.requestSubmit();
                      }
                      return;
                    }
                    if (e.key === "Escape") {
                      setChatInput((prev) =>
                        prev.replace(/@[^\s]*$/, "").trimEnd()
                      );
                      return;
                    }
                    if (showAtOverlay && matchingTags.length > 0) {
                      if (e.key === "ArrowDown") {
                        e.preventDefault();
                        setAtMentionHighlight(
                          (i) => (i + 1) % matchingTags.length
                        );
                      } else if (e.key === "ArrowUp") {
                        e.preventDefault();
                        setAtMentionHighlight(
                          (i) =>
                            (i - 1 + matchingTags.length) % matchingTags.length
                        );
                      }
                    }
                  }}
                  placeholder={
                    contextTagNames.length > 0
                      ? "Ask… (@ for more context)"
                      : "Ask about the API… (@ for module context)"
                  }
                  className="flex-1 w-full min-w-0 max-h-[200px] resize-none overflow-y-auto bg-transparent border-0 py-1 text-sm text-neutral-100 placeholder:text-neutral-500 focus:outline-none focus:ring-0 [&::-webkit-resizer]:hidden"
                  disabled={chatLoading}
                  style={{ height: "auto", resize: "none" }}
                />
                {/* Send button at bottom-right inside the same container */}
                <button
                  type="submit"
                  disabled={chatLoading || !chatInput.trim()}
                  className="absolute bottom-3 right-3 w-8 h-8 rounded-full bg-white text-black hover:bg-neutral-200 disabled:opacity-50 disabled:pointer-events-none disabled:bg-white/10 disabled:text-neutral-200 flex items-center justify-center transition-colors"
                  aria-label="Send"
                >
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M5 10l7-7m0 0l7 7m-7-7v18"
                    />
                  </svg>
                </button>
              </div>
            </form>
            {/* @ overlay — module options as chips */}
            {showAtOverlay && (
              <div
                className="absolute left-0 right-0 bottom-full mb-1 rounded-xl border border-white/10 bg-neutral-900 shadow-lg overflow-hidden z-50 p-2 min-w-[160px]"
                role="listbox"
              >
                {matchingTags.length === 0 ? (
                  <p className="text-xs text-neutral-500 py-1">No match</p>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {matchingTags.map((tag, i) => {
                      const safeHighlight = Math.min(
                        atMentionHighlight,
                        matchingTags.length - 1
                      );
                      return (
                        <button
                          key={tag.name}
                          type="button"
                          role="option"
                          aria-selected={i === safeHighlight}
                          onClick={() => applyAtMention(tag.name)}
                          className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                            i === safeHighlight
                              ? "bg-emerald-500/30 text-emerald-300 border border-emerald-500/50"
                              : "bg-neutral-800 text-neutral-400 border border-neutral-700 hover:bg-neutral-700 hover:text-neutral-300"
                          }`}
                        >
                          {tag.name}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Content wrapper: padding reserves space for fixed sidebars so main never overlaps */}
      <div
        className="flex min-h-screen min-w-0 flex-1 flex-col pt-20
          pl-0 pr-0 lg:pl-[calc(var(--side-width)+var(--side-gap)*2)] lg:pr-[calc(var(--chat-width)+var(--side-gap)*2)]"
      >
        <main className="min-h-[calc(100vh-5rem)] min-w-0 flex-1 w-full p-4 sm:p-6 lg:p-10">
          <section id="overview" className="mb-12">
            <h1 className="text-xl sm:text-2xl font-semibold text-neutral-50 mb-2 tracking-tight">
              Overview
            </h1>
            {docs.version && (
              <p className="text-neutral-500 text-sm mb-4">
                Version {docs.version}
              </p>
            )}
            {(docs.overview_summary ?? docs.description) && (
              <div className="text-neutral-400 text-sm sm:text-base whitespace-pre-wrap mb-6 overflow-x-hidden leading-relaxed">
                {docs.overview_summary ?? docs.description}
              </div>
            )}
            <h2
              id="overview-modules"
              className="text-base sm:text-lg font-medium text-neutral-100 mb-4 tracking-tight"
            >
              Modules
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-[repeat(auto-fill,minmax(160px,1fr))] gap-3 sm:gap-4">
              {docs.tags.map((tag) => (
                <a
                  key={tag.name}
                  href={`#tag-${tag.name.toLowerCase().replace(/\s+/g, "-")}`}
                  className="block p-4 rounded-xl bg-card border border-neutral-800 hover:border-neutral-600 text-neutral-100 transition-colors"
                >
                  <span className="font-medium block">{tag.name}</span>
                  <span className="text-sm text-neutral-500">
                    {tag.endpoints.length} endpoint
                    {tag.endpoints.length !== 1 ? "s" : ""}
                  </span>
                </a>
              ))}
            </div>
          </section>

          {docs.tags.map((tag) => (
            <TagSection
              key={tag.name}
              tag={tag}
              baseUrl={docs.base_url}
              openapiUrl={openapiUrl}
              stacks={docs.stacks}
              bearerToken={bearerToken}
            />
          ))}
        </main>
      </div>
    </div>
  );
}

function TagSection({
  tag,
  baseUrl,
  openapiUrl,
  stacks,
  bearerToken,
}: {
  tag: DocsTag;
  baseUrl: string;
  openapiUrl: string | null;
  stacks: { value: string; label: string }[];
  bearerToken: string;
}) {
  const tagId = `tag-${tag.name.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <section id={tagId} className="mb-10 sm:mb-12">
      <h2 className="text-lg sm:text-xl font-medium text-neutral-50 border-b border-neutral-800 pb-3 mb-5 sm:mb-6 tracking-tight">
        {tag.name}
      </h2>
      {tag.endpoints.map((ep) => (
        <EndpointCard
          key={ep.endpoint_id}
          endpoint={ep}
          baseUrl={baseUrl}
          openapiUrl={openapiUrl}
          stacks={stacks}
          bearerToken={bearerToken}
        />
      ))}
    </section>
  );
}

type TabId = "params" | "body" | "code" | "response";

const TAB_LABELS: { id: TabId; label: string }[] = [
  { id: "params", label: "Parameters" },
  { id: "body", label: "Body" },
  { id: "code", label: "Code Example" },
  { id: "response", label: "Response" },
];

function statusColor(code: number) {
  if (code < 300) return "text-emerald-400";
  if (code < 400) return "text-amber-400";
  return "text-rose-400";
}

function EndpointCard({
  endpoint,
  baseUrl,
  openapiUrl,
  stacks,
  bearerToken,
}: {
  endpoint: DocsEndpoint;
  baseUrl: string;
  openapiUrl: string | null;
  stacks: { value: string; label: string }[];
  bearerToken: string;
}) {
  const hasParams = endpoint.parameters.length > 0;
  const hasBody = endpoint.how_to_call.has_body;
  const defaultTab: TabId = hasParams ? "params" : hasBody ? "body" : "code";
  const [activeTab, setActiveTab] = useState<TabId>(defaultTab);

  const initParams = useMemo(() => {
    const m: Record<string, string> = {};
    for (const p of endpoint.parameters) {
      m[p.name] = p.example != null ? String(p.example) : "";
    }
    return m;
  }, [endpoint.parameters]);
  const [paramValues, setParamValues] = useState<Record<string, string>>(initParams);

  const initBodyJson = useMemo(() => {
    if (endpoint.example_body) return JSON.stringify(endpoint.example_body, null, 2);
    return "{}";
  }, [endpoint.example_body]);
  const [bodyJson, setBodyJson] = useState(initBodyJson);

  const [selectedStack, setSelectedStack] = useState(stacks[0]?.value ?? "");
  const [generatedCode, setGeneratedCode] = useState<string | null>(null);
  const [codeLoading, setCodeLoading] = useState(false);
  const [codeError, setCodeError] = useState<string | null>(null);
  const [codeCopied, setCodeCopied] = useState(false);
  const [response, setResponse] = useState<TryItOutResponse | null>(null);
  const [execLoading, setExecLoading] = useState(false);
  const [execError, setExecError] = useState<string | null>(null);
  const [headersExpanded, setHeadersExpanded] = useState(false);

  const liveUrl = useMemo(() => {
    let u = endpoint.how_to_call.full_url;
    for (const p of endpoint.parameters.filter((pp) => pp.in === "path")) {
      const val = paramValues[p.name] ?? String(p.example ?? "");
      u = u.replace(`{${p.name}}`, encodeURIComponent(val));
    }
    const qp = endpoint.parameters.filter((pp) => pp.in === "query");
    if (qp.length > 0) {
      const qs = qp.map((p) => {
        const val = paramValues[p.name] ?? "";
        return val ? `${encodeURIComponent(p.name)}=${encodeURIComponent(val)}` : null;
      }).filter(Boolean).join("&");
      if (qs) u += (u.includes("?") ? "&" : "?") + qs;
    }
    return u;
  }, [endpoint, paramValues]);

  const handleExecute = async () => {
    setExecLoading(true);
    setExecError(null);
    setResponse(null);
    setActiveTab("response");
    try {
      const headers: Record<string, string> = {};
      if (hasBody) headers["Content-Type"] = "application/json";
      for (const p of endpoint.parameters.filter((pp) => pp.in === "header")) {
        const val = paramValues[p.name] ?? "";
        if (val) headers[p.name] = val;
      }
      if (endpoint.how_to_call.needs_auth) {
        const authParam = endpoint.parameters.find(
          (p) => p.in === "header" && p.name.toLowerCase() === "authorization"
        );
        const authFromParam = authParam ? (paramValues[authParam.name] ?? "").trim() : "";
        const authFromGlobal = bearerToken.trim();
        let authValue = authFromParam || authFromGlobal;
        if (authValue && !authValue.toLowerCase().startsWith("bearer ")) {
          authValue = "Bearer " + authValue;
        }
        if (authValue) headers["Authorization"] = authValue;
      }
      const reqBody: Record<string, unknown> = { url: liveUrl, method: endpoint.method, headers };
      if (hasBody && bodyJson.trim()) reqBody.body = bodyJson;
      if (openapiUrl) reqBody.openapi_url = openapiUrl;
      const res = await fetch(TRY_IT_OUT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(reqBody),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || res.statusText);
      setResponse(data as TryItOutResponse);
    } catch (e) {
      setExecError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setExecLoading(false);
    }
  };

  const handleGenerate = async () => {
    setCodeLoading(true);
    setCodeError(null);
    setGeneratedCode(null);
    try {
      const body: Record<string, string | null> = {
        path: endpoint.path, method: endpoint.method, stack: selectedStack, base_url: baseUrl,
      };
      if (openapiUrl) body.openapi_url = openapiUrl;
      const res = await fetch(GENERATE_EXAMPLE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data: GenerateExampleResponse | { detail?: string } = await res.json();
      if (!res.ok) throw new Error((data as { detail?: string }).detail || res.statusText);
      setGeneratedCode((data as GenerateExampleResponse).code);
    } catch (e) {
      setCodeError(e instanceof Error ? e.message : "Failed to generate");
    } finally {
      setCodeLoading(false);
    }
  };

  const handleCopyCode = () => {
    if (!generatedCode) return;
    navigator.clipboard.writeText(generatedCode).then(() => {
      setCodeCopied(true);
      setTimeout(() => setCodeCopied(false), 2000);
    });
  };

  const visibleTabs = TAB_LABELS.filter((t) => {
    if (t.id === "params" && !hasParams) return false;
    if (t.id === "body" && !hasBody) return false;
    return true;
  });

  let prettyResponseBody = response?.body ?? "";
  if (response) {
    try { prettyResponseBody = JSON.stringify(JSON.parse(response.body), null, 2); } catch { /* keep raw */ }
  }

  const authParam = endpoint.parameters.find((p) => p.in === "header" && p.name.toLowerCase() === "authorization");
  const authFromParam = authParam ? (paramValues[authParam.name] ?? "").trim() : "";
  const hasAuthToken = !!(authFromParam || bearerToken.trim());

  const showAuthHint =
    endpoint.how_to_call.needs_auth &&
    !hasAuthToken &&
    (!response || response.status_code === 401);

  return (
    <article id={endpoint.endpoint_id} className="mb-6 sm:mb-8 rounded-2xl bg-card border border-neutral-800 overflow-hidden">
      {/* Header: method + live URL + Send button */}
      <div className="flex items-center gap-2 sm:gap-3 flex-wrap p-4 sm:px-6 sm:pt-6 sm:pb-3 min-w-0">
        <span className={`method method-${endpoint.method.toLowerCase()} shrink-0`}>{endpoint.method}</span>
        <code className="flex-1 min-w-0 text-xs sm:text-sm text-neutral-300 bg-neutral-900 px-2.5 py-1.5 rounded-lg break-all font-mono">{liveUrl}</code>
        <button type="button" onClick={handleExecute} disabled={execLoading} className="shrink-0 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-medium transition-colors">
          {execLoading ? "Sending..." : "Send"}
        </button>
      </div>

      <div className="px-4 sm:px-6 pb-3">
        {endpoint.summary && <p className="font-medium text-neutral-100 mb-1">{endpoint.summary}</p>}
        {endpoint.description && <div className="text-neutral-500 text-sm whitespace-pre-wrap leading-relaxed">{endpoint.description}</div>}
      </div>

      {/* Tab bar */}
      <div className="border-t border-neutral-800 px-4 sm:px-6 flex gap-0 overflow-x-auto">
        {visibleTabs.map((t) => (
          <button key={t.id} type="button" onClick={() => setActiveTab(t.id)}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${activeTab === t.id ? "border-emerald-500 text-neutral-100" : "border-transparent text-neutral-500 hover:text-neutral-300"}`}>
            {t.label}
            {t.id === "response" && response && (
              <span className={`ml-1.5 text-xs font-semibold ${statusColor(response.status_code)}`}>{response.status_code}</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="p-4 sm:p-6 pt-4 border-t border-neutral-800 min-h-[120px]">
        {/* PLACEHOLDER_TAB_CONTENT */}
        {/* Parameters tab */}
        {activeTab === "params" && hasParams && (
          <div className="space-y-3">
            {endpoint.parameters.map((p) => (
              <div key={p.name} className="flex flex-col sm:flex-row sm:items-center gap-2">
                <div className="flex items-center gap-2 sm:w-48 shrink-0">
                  <code className="text-neutral-200 font-mono text-xs">{p.name}</code>
                  <span className="text-[10px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded bg-neutral-800 text-neutral-500">{p.in}</span>
                  {p.required && <span className="text-[10px] text-rose-400 font-semibold">*</span>}
                </div>
                <input type="text" value={paramValues[p.name] ?? ""} onChange={(e) => setParamValues((prev) => ({ ...prev, [p.name]: e.target.value }))}
                  placeholder={p.example != null ? String(p.example) : p.type}
                  className="flex-1 min-w-0 px-3 py-2 rounded-lg bg-neutral-900/80 border border-neutral-700 text-neutral-200 text-sm placeholder-neutral-600 font-mono focus:outline-none focus:ring-1 focus:ring-emerald-500/50 focus:border-emerald-500/50" />
                {p.description && <span className="text-xs text-neutral-600 hidden lg:block max-w-[200px] truncate" title={p.description}>{p.description}</span>}
              </div>
            ))}
          </div>
        )}

        {/* Body tab */}
        {activeTab === "body" && hasBody && (
          <div>
            {endpoint.request_body_schema?.description && <p className="text-neutral-500 text-sm mb-3">{endpoint.request_body_schema.description}</p>}
            <div className="rounded-lg overflow-hidden border border-neutral-800">
              <CodeMirrorEditor value={bodyJson} onChange={(val) => setBodyJson(val)} height="240px" theme="dark" basicSetup={{ lineNumbers: true, foldGutter: true, bracketMatching: true }} className="text-sm codemirror-dark" />
            </div>
            {endpoint.request_body_schema?.schema?.properties && (
              <div className="mt-4 overflow-x-auto">
                <p className="text-xs font-medium text-neutral-500 uppercase tracking-wider mb-2">Schema</p>
                <table className="w-full min-w-[400px] text-sm border-collapse border border-neutral-800 rounded-xl overflow-hidden">
                  <thead><tr className="bg-neutral-900/80">
                    <th className="text-left p-2.5 border-b border-neutral-800 text-neutral-300 font-medium">Field</th>
                    <th className="text-left p-2.5 border-b border-neutral-800 text-neutral-300 font-medium">Type</th>
                    <th className="text-left p-2.5 border-b border-neutral-800 text-neutral-300 font-medium">Required</th>
                    <th className="text-left p-2.5 border-b border-neutral-800 text-neutral-300 font-medium">Description</th>
                  </tr></thead>
                  <tbody>
                    {endpoint.request_body_schema.schema.properties.map((prop) => (
                      <tr key={prop.name} className="border-b border-neutral-800/80">
                        <td className="p-2.5"><code className="text-neutral-200 font-mono text-xs">{prop.name}</code></td>
                        <td className="p-2.5 text-neutral-500 text-xs">{prop.type}</td>
                        <td className="p-2.5 text-neutral-500 text-xs">{prop.required ? "required" : "optional"}</td>
                        <td className="p-2.5 text-neutral-500 text-xs">{prop.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Code Example tab */}
        {activeTab === "code" && (
          <div>
            <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center mb-4">
              <div className="flex flex-col gap-1.5 min-w-0 sm:min-w-[220px]">
                <span className="text-xs font-medium text-neutral-500 uppercase tracking-wider">Framework</span>
                <Select value={selectedStack} onValueChange={setSelectedStack}>
                  <SelectTrigger className="w-full"><SelectValue placeholder="Pick a framework" /></SelectTrigger>
                  <SelectContent>
                    <SelectGroup><SelectLabel>Web</SelectLabel>
                      {stacks.filter((s) => !["react-native","flutter","swift-ios","kotlin-android"].includes(s.value)).map((s) => (
                        <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                      ))}
                    </SelectGroup>
                    <SelectGroup><SelectLabel>Mobile</SelectLabel>
                      {stacks.filter((s) => ["react-native","flutter","swift-ios","kotlin-android"].includes(s.value)).map((s) => (
                        <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </div>
              <button type="button" onClick={handleGenerate} disabled={codeLoading}
                className="sm:self-end px-4 py-2.5 rounded-xl bg-neutral-100 hover:bg-white disabled:opacity-50 text-neutral-900 text-sm font-medium touch-manipulation transition-colors shrink-0">
                {codeLoading ? "Generating..." : "Generate example"}
              </button>
            </div>
            {codeError && <p className="text-neutral-400 text-sm mb-3">{codeError}</p>}
            {generatedCode && (
              <div className="relative rounded-lg overflow-hidden border border-neutral-800">
                <CodeMirrorEditor value={generatedCode} readOnly editable={false} height="auto" maxHeight="500px" theme="dark" basicSetup={{ lineNumbers: true, foldGutter: false }} className="text-sm codemirror-dark" />
                <button type="button" onClick={handleCopyCode} className="absolute top-2.5 right-2.5 px-2.5 py-1.5 rounded-lg text-xs bg-neutral-800/90 hover:bg-neutral-700 text-neutral-300 transition-colors z-10">
                  {codeCopied ? "Copied!" : "Copy"}
                </button>
              </div>
            )}
            {!generatedCode && !codeLoading && !codeError && (
              <p className="text-neutral-600 text-sm">Select a framework and click &quot;Generate example&quot; to see code.</p>
            )}
          </div>
        )}

        {/* Response tab */}
        {activeTab === "response" && (
          <div>
            {execLoading && (
              <div className="flex items-center gap-3 py-6">
                <div className="w-5 h-5 rounded-full border-2 border-neutral-600 border-t-emerald-500 animate-spin" />
                <span className="text-neutral-500 text-sm">Sending request...</span>
              </div>
            )}
            {execError && <div className="rounded-xl bg-rose-950/40 border border-rose-800/60 text-rose-200 px-4 py-3 text-sm">{execError}</div>}
            {showAuthHint && (
              <div className="rounded-xl bg-amber-950/30 border border-amber-800/50 text-amber-200 px-4 py-3 text-sm mb-4">
                Add a Bearer token above to authenticate. Click &quot;Auth&quot; in the header to set your token.
              </div>
            )}
            {response && (
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <span className={`text-lg font-bold ${statusColor(response.status_code)}`}>{response.status_code}</span>
                  <span className="text-neutral-500 text-sm">{response.elapsed_ms}ms</span>
                </div>
                <div>
                  <button type="button" onClick={() => setHeadersExpanded((v) => !v)} className="text-xs font-medium text-neutral-500 uppercase tracking-wider hover:text-neutral-300 transition-colors flex items-center gap-1">
                    Response Headers <span className="text-[10px]">{headersExpanded ? "\u25BC" : "\u25B6"}</span>
                  </button>
                  {headersExpanded && (
                    <div className="mt-2 rounded-lg bg-neutral-900/80 border border-neutral-800 p-3 text-xs font-mono text-neutral-400 max-h-40 overflow-auto">
                      {Object.entries(response.headers).map(([k, v]) => (
                        <div key={k}><span className="text-neutral-300">{k}</span>: {v}</div>
                      ))}
                    </div>
                  )}
                </div>
                <div>
                  <p className="text-xs font-medium text-neutral-500 uppercase tracking-wider mb-2">Response Body</p>
                  <div className="rounded-lg overflow-hidden border border-neutral-800">
                    <CodeMirrorEditor value={prettyResponseBody} readOnly editable={false} height="auto" maxHeight="400px" theme="dark" basicSetup={{ lineNumbers: true, foldGutter: true }} className="text-sm codemirror-dark" />
                  </div>
                </div>
              </div>
            )}
            {!response && !execLoading && !execError && (
              <p className="text-neutral-600 text-sm py-4">Click &quot;Send&quot; to execute the request and see the response.</p>
            )}
          </div>
        )}
      </div>

      {/* Response schema */}
      {endpoint.responses.length > 0 && (
        <div className="px-4 sm:px-6 pb-4 sm:pb-6">
          <h4 className="text-sm font-medium text-neutral-200 mb-2">Response Schema</h4>
          <ul className="space-y-3">
            {endpoint.responses.map((r) => (
              <li key={r.code} className="p-3 rounded-xl bg-neutral-900/50 border border-neutral-800 space-y-2">
                <p className="text-sm"><strong className="text-neutral-200">{r.code}</strong>: <span className="text-neutral-500">{r.description}</span></p>
                {r.body_schema?.properties && r.body_schema.properties.length > 0 && (
                  <div className="mt-2 overflow-x-auto">
                    <table className="w-full min-w-[400px] text-xs border-collapse border border-neutral-800 rounded-xl overflow-hidden">
                      <thead><tr className="bg-neutral-900/80">
                        <th className="text-left p-2 border-b border-neutral-800 text-neutral-300 font-medium">Field</th>
                        <th className="text-left p-2 border-b border-neutral-800 text-neutral-300 font-medium">Type</th>
                        <th className="text-left p-2 border-b border-neutral-800 text-neutral-300 font-medium">Description</th>
                      </tr></thead>
                      <tbody>
                        {r.body_schema.properties.map((prop) => (
                          <tr key={prop.name} className="border-b border-neutral-800/80">
                            <td className="p-2"><code className="text-neutral-200 font-mono text-xs">{prop.name}</code></td>
                            <td className="p-2 text-neutral-500">{prop.type}</td>
                            <td className="p-2 text-neutral-500">{prop.description}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {r.body_schema && !r.body_schema.properties?.length && (
                  <p className="text-xs text-neutral-500">Type: <code className="text-neutral-400">{r.body_schema.type ?? "object"}</code></p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}
