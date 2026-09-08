import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { createPortal } from 'react-dom';
import './zone3-new.css';
import './chat.css';
import './packet.css';
import './document-viewer.css';
import './case-switcher.css';
import './alert-colors.css';
import './architecture-details.css';
import './provider-picker.css';
import './ui-polish.css';
import doorlightWordmark from './assets/doorlight-wordmark-dark.png';

type Event = { id: string; at: string; phase: 'assistant' | 'tool' | 'agent' | 'control' | 'result' | 'error'; title: string; detail: string; state: 'queued' | 'active' | 'complete' | 'blocked'; overview?: string[]; tools?: string[] };
type Provider = 'GEMINI' | 'OLLAMA';
type AgentTarget = 'ORCHESTRATOR' | 'transaction-intake-agent' | 'policy-agent' | 'document-intake-agent' | 'evidence-agent' | 'reconciliation-agent' | 'compliance-agent' | 'risk-agent';
type VisualEvidence = { lane: 'AMBER' | 'RED'; title: string; explanation: string; quote: string; citation: string; imageUrl: string; originalImageUrl: string };
type Run = { id: string; caseId: string; provider: Provider; request: string; targetAgent?: Exclude<AgentTarget, 'ORCHESTRATOR'>; followUp?: boolean; showLive?: boolean; status: 'RUNNING' | 'AWAITING_HUMAN' | 'COMPLETE' | 'FAILED'; intent?: string; final?: string; lane?: 'GREEN' | 'AMBER' | 'RED'; visualEvidence?: VisualEvidence; events: Event[]; createdAt: string };
type Health = { gemini: string; geminiModel: string; ollama: string; ollamaHost?: string; ollamaHint?: string; ollamaModel: string; ollamaVisionModel: string };
type CaseOption = { id: string; property: string; closingDate: string; lane: 'GREEN' | 'AMBER' | 'RED'; issue: string };
type SourcePageRecord = { number: number; text: string; imageUrl: string };
type SourceDocumentRecord = { name: string; version: string; page: number; pageCount?: number; text: string; classification?: string; sourceHash?: string; controlling?: boolean; sourceFormat?: string; visionEligible?: boolean; extractionTargets?: string[]; imageUrl?: string; pdfUrl?: string; sourcePages?: SourcePageRecord[] };
type SourceReaderDocument = { name: string; version: string; pages: string; pdfUrl: string; sourcePages: SourcePageRecord[] };
type TransactionContext = { id: string; documents: SourceDocumentRecord[] };
type ChatMessage = { id: string; role: 'user' | 'assistant' | 'system'; content: string; lane?: 'GREEN' | 'AMBER' | 'RED'; showLive?: boolean; visualEvidence?: VisualEvidence };
const api = async (url: string, init?: RequestInit) => { const response = await fetch(`/api${url}`, init); const result = await response.json(); if (!response.ok) throw new Error(result.error || 'Request failed'); return result; };
const demoCases: CaseOption[] = [
  { id: '48290', property: '48 Redwood Place, Harborfield', closingDate: 'September 15, 2026', lane: 'GREEN', issue: 'Complete packet' },
  { id: '48291', property: '123 Main Street, Harborfield', closingDate: 'September 17, 2026', lane: 'AMBER', issue: 'Escrow receipt pending' },
  { id: '48292', property: '77 Juniper Lane, Harborfield', closingDate: 'September 22, 2026', lane: 'RED', issue: 'Seller signature missing' }
];

const architectureAgents = [
  { stage: '01', name: 'Transaction Intake', plain: 'Creates one reliable starting record.', does: 'Organizes the case, parties, property, financing, representation, and important dates.', tools: 'Transaction lookup · Party normalizer · Milestone reader', output: 'Normalized case' },
  { stage: '02', name: 'Policy & Rules', plain: 'Chooses the right review checklist.', does: 'Matches the location and transaction details to the supplied Doorlight policy version.', tools: 'Policy search · Checklist selector', output: 'Applicable checklist' },
  { stage: '03', name: 'Document Intake', plain: 'Turns the packet into an organized source library.', does: 'Reads pages, classifies files, checks versions and duplicates, records hashes and metadata, and runs vision/OCR preflight.', tools: 'OCR · Classifier · Versioning · Hashing · Metadata', output: 'Document inventory' },
  { stage: '04', name: 'Evidence', plain: 'Finds proof and shows exactly where it came from.', does: 'Retrieves relevant passages and attaches document, version, page, region, confidence, and extractor information.', tools: 'Document search · Evidence retrieval · Citation builder', output: 'Cited facts' },
  { stage: '05', name: 'Reconciliation', plain: 'Checks whether the documents agree.', does: 'Builds the agreement and amendment chain, then compares parties, property, signatures, money, title, terms, and dates.', tools: 'Chain builder · Term comparator · Signature and title search', output: 'Controlling facts and conflicts' },
  { stage: '06', name: 'Compliance', plain: 'Checks every requirement one at a time.', does: 'Compares the selected checklist with cited evidence and records supported, partial, missing, contradictory, not applicable, or human judgment.', tools: 'Checklist · Policy search · Evidence retrieval · Evaluator', output: 'Requirement results' },
  { stage: '07', name: 'Risk & Escalation', plain: 'Makes the final readiness recommendation.', does: 'Reviews prior artifacts, identifies material blockers or smaller gaps, and returns Green, Amber, or Red with reasons and next steps.', tools: 'Risk rubric · Blocker search · Gap search · Validator', output: 'Validated recommendation' }
];

const technologyLayers = [
  { label: 'Interface', title: 'TypeScript · React · Vite', copy: 'The browser UI provides Light chat, source-page reading, extracted context, live workflow history, and this architecture guide.', path: 'src/' },
  { label: 'Application', title: 'Python · FastAPI · Uvicorn', copy: 'One local API host keeps the existing /api contract, plans runs, invokes agents, applies permissions, and returns results.', path: 'backend/app.py' },
  { label: 'Agent Protocol', title: 'Official A2A Python SDK', copy: 'Each specialist publishes an Agent Card and accepts A2A JSON-RPC tasks through its own executor, handler, and task store.', path: 'backend/a2a_runtime.py' },
  { label: 'AI Providers', title: 'Gemini · Ollama · Qwen Vision', copy: 'Gemini or local Llama can refine validated risk wording. Local Qwen vision performs the bounded document-image preflight.', path: 'backend/providers.py · backend/vision.py' },
  { label: 'Data', title: 'SQLite · PNG · PDF · JSON', copy: 'SQLite retains runs, artifacts, and audits. Synthetic documents are kept as readable page images, PDFs, and source text.', path: 'backend/store.py · public/demo-packet/' }
];
const agentTargets: { id: AgentTarget; name: string }[] = [
  { id: 'ORCHESTRATOR', name: 'Doorlight Orchestrator' }, { id: 'transaction-intake-agent', name: 'Transaction Intake Agent' },
  { id: 'policy-agent', name: 'Policy & Rules Agent' }, { id: 'document-intake-agent', name: 'Document Intake Agent' },
  { id: 'evidence-agent', name: 'Evidence Agent' }, { id: 'reconciliation-agent', name: 'Reconciliation Agent' },
  { id: 'compliance-agent', name: 'Compliance Agent' }, { id: 'risk-agent', name: 'Risk Agent' }
];

function App() {
  const [request, setRequest] = useState('');
  const [run, setRun] = useState<Run>();
  const [runHistory, setRunHistory] = useState<Run[]>([]);
  const [selectedLiveRunId, setSelectedLiveRunId] = useState<string>();
  const [contextRun, setContextRun] = useState<Run>();
  const [caseId, setCaseId] = useState('48291');
  const [provider, setProvider] = useState<Provider>('GEMINI');
  const [targetAgent, setTargetAgent] = useState<AgentTarget>('ORCHESTRATOR');
  const [sessionId] = useState(() => crypto.randomUUID());
  const [chatHistory, setChatHistory] = useState<Record<string, ChatMessage[]>>({});
  const [health, setHealth] = useState<Health>();
  const [error, setError] = useState('');
  const [selectedVisualEvidence, setSelectedVisualEvidence] = useState<VisualEvidence>();
  const [view, setView] = useState<'ASSISTANT' | 'LIVE' | 'ARCHITECTURE' | 'TRANSACTION' | 'CONTEXT'>('ASSISTANT');
  useEffect(() => { const previous = window.history.scrollRestoration; window.history.scrollRestoration = 'manual'; window.scrollTo(0, 0); return () => { window.history.scrollRestoration = previous; }; }, []);
  const loadHealth = async () => { try { setHealth(await api('/health')); } catch {} };
  useEffect(() => { void loadHealth(); const timer = setInterval(() => void loadHealth(), 6000); return () => clearInterval(timer); }, []);
  useEffect(() => { if (!run || run.status !== 'RUNNING') return; const timer = setInterval(async () => { try { setRun(await api(`/runs/${run.id}`)); } catch {} }, 400); return () => clearInterval(timer); }, [run?.id, run?.status]);
  useEffect(() => { if (!run) return; setRunHistory(current => [run, ...current.filter(item => item.id !== run.id)].slice(0, 20)); }, [run]);
  useEffect(() => { if (run && !run.targetAgent && !run.followUp && (run.status === 'COMPLETE' || run.status === 'AWAITING_HUMAN')) setContextRun(run); }, [run?.id, run?.status, run?.targetAgent, run?.followUp]);
  useEffect(() => { if (!run?.final) return; setChatHistory(current => { const messages = current[run.caseId] || []; if (messages.some(message => message.id === run.id)) return current; return { ...current, [run.caseId]: [...messages, { id: run.id, role: 'assistant', content: run.final!, lane: run.lane, showLive: run.showLive, visualEvidence: run.visualEvidence }] }; }); }, [run?.id, run?.caseId, run?.final, run?.lane, run?.showLive, run?.visualEvidence]);
  const active = useMemo(() => run ? [...run.events].reverse().find((event: Event) => event.state === 'active') || run.events[run.events.length - 1] : undefined, [run]);
  const selectedCase = demoCases.find(item => item.id === caseId)!;
  const changeCase = (id: string) => { const currentScroll = window.scrollY; setCaseId(id); setRun(undefined); requestAnimationFrame(() => window.scrollTo(0, currentScroll)); };
  const start = async (event: React.FormEvent) => { event.preventDefault(); const prompt = request.trim(); if (!prompt || run?.status === 'RUNNING') return; setError(''); try { const next = await api('/runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ request: prompt, caseId, sessionId, provider, targetAgent: targetAgent === 'ORCHESTRATOR' ? undefined : targetAgent }) }); const userMessage: ChatMessage = { id: `user-${next.id}`, role: 'user', content: prompt }; setChatHistory(current => ({ ...current, [caseId]: [...(current[caseId] || []), userMessage].slice(-100) })); setRequest(''); setRun(next); setSelectedLiveRunId(next.id); setView('ASSISTANT'); } catch (caught) { setError((caught as Error).message); } };
  return <div className="app">
    <aside><div className="wordmark"><img src={doorlightWordmark} alt="Doorlight"/></div><p className="side-label">ZONE 3 PROTOTYPE</p><div className="provider-picker"><label htmlFor="provider">MODEL PROVIDER</label><select id="provider" value={provider} onChange={event => setProvider(event.target.value as Provider)}><option value="GEMINI">Gemini API</option><option value="OLLAMA">Local Ollama</option></select><small>{provider === 'GEMINI' ? `Cloud · ${health?.geminiModel || 'Checking...'}` : health?.ollama === 'CONNECTED' ? `Local · ${health.ollamaModel} · ${health.ollamaHost}` : health?.ollamaHint || 'Checking Ollama connectivity...'}</small><label htmlFor="agent-target">ASK A2A AGENT</label><select id="agent-target" value={targetAgent} onChange={event => { const next = event.target.value as AgentTarget; setTargetAgent(next); const name = agentTargets.find(agent => agent.id === next)?.name || 'Doorlight Orchestrator'; setChatHistory(current => ({ ...current, [caseId]: [...(current[caseId] || []), { id: `switch-${Date.now()}`, role: 'system' as const, content: `Responder switched to ${name}.` }].slice(-100) })); }}><option value="ORCHESTRATOR">Doorlight Orchestrator</option>{agentTargets.filter(agent => agent.id !== 'ORCHESTRATOR').map(agent => <option value={agent.id} key={agent.id}>{agent.name}</option>)}</select><small>{targetAgent === 'ORCHESTRATOR' ? 'Ask Light to explain agents, answer case questions, or run a full review.' : 'Direct mode · asks this specialist about its role, tools, and case work.'}</small></div><button className={view === 'ASSISTANT' ? 'selected' : ''} onClick={() => setView('ASSISTANT')}>Light</button><button className={view === 'LIVE' ? 'selected' : ''} onClick={() => setView('LIVE')}>Live Overview</button><button className={view === 'ARCHITECTURE' ? 'selected' : ''} onClick={() => setView('ARCHITECTURE')}>System Architecture</button><button className={view === 'TRANSACTION' ? 'selected' : ''} onClick={() => setView('TRANSACTION')}>Source Documents</button><button className={view === 'CONTEXT' ? 'selected' : ''} onClick={() => setView('CONTEXT')}>Context Overview</button><div className={'connection '+((provider === 'GEMINI' ? health?.gemini === 'CONFIGURED' : health?.ollama === 'CONNECTED') ? 'online' : 'offline')}><i/>{provider === 'GEMINI' ? health?.gemini === 'CONFIGURED' ? `Gemini Configured · ${health.geminiModel}` : 'Gemini API Key Unavailable' : health?.ollama === 'CONNECTED' ? `Ollama Connected · ${health.ollamaModel}` : 'Ollama Unavailable From WSL'}</div></aside>
    <main><header><div><span>DOORLIGHT · ZONE 3</span><h1>Governed Agent System</h1></div></header>
      {view === 'ASSISTANT' && <AssistantWindow request={request} setRequest={setRequest} start={start} run={run} active={active} error={error} messages={chatHistory[selectedCase.id] || []} selectedCase={selectedCase} setCase={changeCase} showLive={() => setView('LIVE')} openVisualEvidence={setSelectedVisualEvidence}/>} 
      {view === 'LIVE' && <RunPanel run={run} runs={runHistory} selectedRunId={selectedLiveRunId} selectRun={setSelectedLiveRunId} openVisualEvidence={setSelectedVisualEvidence}/>} 
      {view === 'ARCHITECTURE' && <Architecture/>}
      {view === 'TRANSACTION' && <Transaction selectedCase={selectedCase} setCase={changeCase}/>} 
      {view === 'CONTEXT' && <ContextOverview selectedCase={selectedCase} setCase={changeCase} run={contextRun}/>} 
    </main>{selectedVisualEvidence && <VisualEvidenceModal evidence={selectedVisualEvidence} close={() => setSelectedVisualEvidence(undefined)}/>} 
  </div>;
}

function AssistantWindow({ request, setRequest, start, run, active, error, messages, selectedCase, setCase, showLive, openVisualEvidence }: { request: string; setRequest: (value: string) => void; start: (event: React.FormEvent) => Promise<void>; run?: Run; active?: Event; error: string; messages: ChatMessage[]; selectedCase: CaseOption; setCase: (id: string) => void; showLive: () => void; openVisualEvidence: (evidence: VisualEvidence) => void }) {
  const updates = run?.events.filter(event => ['agent', 'tool', 'control'].includes(event.phase)) || [];
  return <section className="assistant-window">
    <div className="chat-topline"><span>TRANSACTION {selectedCase.id} · {selectedCase.property.toUpperCase()}</span><small>Read-only Review Context</small></div><div className="case-switcher"><span>DEMO CASES</span>{demoCases.map(item => <button type="button" className={item.id === selectedCase.id ? `selected ${item.lane.toLowerCase()}` : item.lane.toLowerCase()} onClick={() => setCase(item.id)} key={item.id}>CASE · {item.id}</button>)}</div>
    <div className="conversation"><div className="conversation-label">LIGHT · SESSION HISTORY</div>{messages.map(message => message.role === 'system' ? <div className="responder-switch" key={message.id}>{message.content}</div> : <article className={`message ${message.role} ${message.lane?.toLowerCase() || ''}`} key={message.id}><span>{message.role === 'user' ? 'YOU' : 'LIGHT'}</span>{message.lane && <b className="alert-badge">{message.lane} ALERT</b>}{message.role === 'assistant' ? <ResponseText content={message.content}/> : <p>{message.content}</p>}{message.role === 'assistant' && message.visualEvidence && <VisualEvidenceCard evidence={message.visualEvidence} open={() => openVisualEvidence(message.visualEvidence!)}/>} {message.role === 'assistant' && message.showLive && <button className="text-link" type="button" onClick={showLive}>Open Live Overview →</button>}</article>)}{run?.status === 'RUNNING' && <article className="message assistant working-message"><span>LIGHT</span><p>I’m checking the authorized case context now.</p>{run.showLive && <ActivityDropdown updates={updates} active={active} provider={run.provider} showLive={showLive}/>}</article>}</div>
    <form className="assistant-composer" onSubmit={start}><div><input id="assistant-prompt" value={request} onChange={event => setRequest(event.target.value)} placeholder="Ask Light or the selected agent a real-estate question"/><button aria-label="Send message" disabled={run?.status === 'RUNNING' || !request.trim()}>{run?.status === 'RUNNING' ? 'Working…' : 'Send'}</button></div><section>{['What does the Evidence Agent do?', 'Which records need signatures?', 'Explain escrow in simple terms.', 'Run a full readiness review.'].map(prompt => <button type="button" key={prompt} onClick={() => setRequest(prompt)}>{prompt}</button>)}</section>{error && <p className="assistant-error">{error}</p>}</form>
  </section>;
}

const responseHeadings = new Set(['Why this is Green', 'Why this is Amber', 'Why this is Red', 'What the agents confirmed', 'What is missing', 'Why this is not Red', 'What this means', 'What the agents found', 'Why this matters', 'Source', 'Next step']);
function ResponseText({ content }: { content: string }) {
  const lines = content.split('\n').map(line => line.trim()).filter(Boolean);
  return <div className="response-copy">{lines.map((line, index) => responseHeadings.has(line) ? <h4 key={index}>{line}</h4> : line.startsWith('• ') ? <p className="response-point" key={index}>{line.slice(2)}</p> : <p key={index}>{line}</p>)}</div>;
}

function ActivityDropdown({ updates, active, provider, showLive }: { updates: Event[]; active?: Event; provider: Provider; showLive: () => void }) {
  return <details className="activity-dropdown" open><summary><span className="activity-dot"/><div><b>{active?.title || 'Preparing the workflow'}</b><small>{active?.phase === 'agent' ? `${provider === 'GEMINI' ? 'Gemini API' : 'Local Ollama'} agent active` : active?.phase === 'tool' ? 'Approved tool active' : 'Orchestrator active'}</small></div><i>⌄</i></summary><div className="activity-list">{updates.slice(-5).reverse().map(event => <article key={event.id}><span className={event.state}/><div><b>{event.title}</b><p>{event.detail}</p></div></article>)}<button type="button" onClick={showLive}>See Full Live Overview</button></div></details>;
}

function VisualEvidenceCard({ evidence, open }: { evidence: VisualEvidence; open: () => void }) {
  return <figure className={`visual-evidence ${evidence.lane.toLowerCase()}`}><div className="visual-evidence-head"><span>{evidence.title}</span><b>{evidence.citation}</b></div><button type="button" className="visual-evidence-image" onClick={open} title="Open full-screen source reader" aria-label={`Open highlighted source evidence from ${evidence.citation}`}><img src={evidence.imageUrl} alt={`${evidence.lane} evidence highlighted on ${evidence.citation}`}/><span>Open full source view ↗</span></button><figcaption><b>Highlighted text:</b> “{evidence.quote}”<br/>{evidence.explanation}<small>Annotated demo copy · click the image to inspect it in the source reader.</small></figcaption></figure>;
}

function useModalBehavior(close: () => void) {
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === 'Escape') close(); };
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', closeOnEscape);
    return () => { document.body.style.overflow = previousOverflow; document.removeEventListener('keydown', closeOnEscape); };
  }, [close]);
}

function VisualEvidenceModal({ evidence, close }: { evidence: VisualEvidence; close: () => void }) {
  useModalBehavior(close);
  return createPortal(<div className="source-modal visual-evidence-modal" role="dialog" aria-modal="true" aria-label={`${evidence.lane} source evidence`} onMouseDown={event => { if (event.target === event.currentTarget) close(); }}><div className="source-modal-head"><div><span>Risk Evidence · Annotated Source Page</span><b>{evidence.title} · {evidence.citation}</b></div><div className="source-reader-controls"><a href={evidence.originalImageUrl} target="_blank" rel="noreferrer">Open Original</a><button type="button" onClick={close}>Close</button></div></div><section className="source-image-reader"><img src={evidence.imageUrl} alt={`${evidence.lane} highlighted source evidence`}/><p><b>Highlighted text:</b> “{evidence.quote}” · {evidence.explanation}</p></section></div>, globalThis.document.body);
}

function RunPanel({ run: currentRun, runs, selectedRunId, selectRun, openVisualEvidence }: { run?: Run; runs: Run[]; selectedRunId?: string; selectRun: (id: string) => void; openVisualEvidence: (evidence: VisualEvidence) => void }) {
  const visibleRun = runs.find(item => item.id === selectedRunId) || currentRun;
  const active = useMemo(() => {
    if (!visibleRun) return undefined;
    const activeEvent = [...visibleRun.events].reverse().find(event => event.state === 'active');
    return activeEvent || (visibleRun.status === 'RUNNING' ? visibleRun.events[visibleRun.events.length - 1] : undefined);
  }, [visibleRun]);
  const history = runs.filter(item => item.id !== visibleRun?.id);
  const run = visibleRun;
  if (!run) return <section className="empty live-empty">
    <div className="live-empty-intro"><span>READY TO RUN</span><h2>Workflow Activity Will Appear Here</h2><p>Ask Light to run a full readiness review. This page will then show each specialist result, the tools it used, and the final governed outcome.</p></div>
    <div className="live-empty-flow" aria-label="Workflow preview">
      <article><i>01</i><div><b>Start In Light</b><p>Select a transaction and request a readiness review.</p></div></article>
      <em>→</em>
      <article><i>02</i><div><b>Watch Seven Agents</b><p>Independent A2A services return validated artifacts in order.</p></div></article>
      <em>→</em>
      <article><i>03</i><div><b>Review The Outcome</b><p>See the risk recommendation, cited reason, tools, and next step.</p></div></article>
    </div>
    <footer><span>Official A2A JSON-RPC</span><span>Local Controlled Tools</span><span>Audited Human Review</span></footer>
  </section>;
  const progress = run.status === 'RUNNING' ? Math.min(94, Math.round((run.events.length / 16) * 100)) : 100;
  const agentReports = run.events.filter(event => event.phase === 'agent' && event.state !== 'active' && event.overview?.length);
  const controls = run.events.filter(event => event.phase === 'control');
  return <section className="run-panel">
    <div className="run-history"><div><span>SESSION RUN HISTORY</span><small>Stored in this page until refresh</small></div><button type="button" className="selected" onClick={() => selectRun(run.id)}>Current · {run.caseId}</button>{history.map(item => <button type="button" key={item.id} onClick={() => selectRun(item.id)}>{item.caseId} · {item.lane || item.status.replaceAll('_', ' ')}</button>)}</div>
    <div className="run-top"><div><span>LIVE EXECUTION</span><h2>{run.status === 'RUNNING' ? active?.title || 'Preparing Agent Run' : run.status.replaceAll('_', ' ')}</h2><p>{run.request}</p></div><b className={run.lane?.toLowerCase() || run.status.toLowerCase()}>{run.lane || run.status.replaceAll('_', ' ')}</b></div>
    <div className="progress"><div><span>Workflow Progress</span><b>{progress}%</b></div><i><em style={{ width: `${progress}%` }}/></i></div>
    {active && <article className="live-card"><span>{active.phase === 'agent' ? `${run.provider === 'GEMINI' ? 'GEMINI' : 'OLLAMA'} AGENT UPDATE` : active.phase === 'tool' ? 'Approved tool active' : 'Control plane update'}</span><h3>{active.title}</h3><p>{active.detail}</p><small>Observable operational activity. The system does not display private chain-of-thought.</small></article>}
    {run.final && <article className={'final '+run.lane?.toLowerCase()}><span>FINAL DECISION</span><ResponseText content={run.final}/></article>}
    {run.visualEvidence && <VisualEvidenceCard evidence={run.visualEvidence} open={() => openVisualEvidence(run.visualEvidence!)}/>} 
    <div className="execution-grid organized-execution"><section><h3>What Each Agent Did</h3>{agentReports.length ? agentReports.map(event => <Trace event={event} key={event.id}/>) : <p className="trace-empty">Completed plain-language agent summaries will appear here.</p>}</section><section className="tool-summary"><h3>Tools Used</h3>{agentReports.map(event => <article className="tool-group" key={event.id}><b>{event.title.replace(' · A2A', '')}</b><ul>{event.tools?.map(tool => <li key={tool}>{tool.replaceAll('_', ' ')}</li>)}</ul></article>)}<div className="workflow-controls"><b>Workflow Controls</b>{controls.filter(event => !event.title.includes('Controlled tools')).map(event => <small key={event.id}>{event.title}</small>)}</div></section></div>
  </section>;
}
function Trace({ event }: { event: Event }) { return <article className={`trace ${event.state}`}><i>{event.state === 'active' ? '●' : event.state === 'blocked' ? '!' : '✓'}</i><div><b>{event.title}</b>{event.overview ? <ol className="agent-overview">{event.overview.map((sentence, index) => <li key={index}>{sentence}</li>)}</ol> : <p>{event.detail}</p>}</div></article>; }
function Architecture() {
  return <section className="architecture arch-guide">
    <header className="arch-hero">
      <div><span>DOORLIGHT MVP · SYSTEM GUIDE</span><h2>How Light Reviews A Transaction</h2><p>This is a local demonstration of the Zone 3 workflow in the original Doorlight diagram. Light coordinates seven focused agents, keeps their evidence traceable, and applies a permission check before any local follow-up action is created.</p></div>
      <div className="arch-facts"><div><b>7</b><small>Independent Agents</small></div><div><b>A2A</b><small>JSON-RPC Protocol</small></div><div><b>1</b><small>Governed Orchestrator</small></div></div>
    </header>

    <section className="arch-section">
      <div className="arch-section-title"><span>THE 60-SECOND VIEW</span><h3>One Question Becomes A Traceable Decision</h3><p>Read left to right. Light controls every handoff; specialist agents never call one another directly.</p></div>
      <div className="journey-diagram">
        <article><i>01</i><b>User Asks Light</b><p>A question and selected transaction enter through the React interface.</p></article><em>→</em>
        <article className="primary"><i>02</i><b>Light Plans The Run</b><p>The Python orchestrator identifies the intent, case, context, and required stages.</p></article><em>→</em>
        <article><i>03</i><b>Agents Build Evidence</b><p>Seven A2A services return separate, validated artifacts in order.</p></article><em>→</em>
        <article><i>04</i><b>Risk Chooses A Lane</b><p>The Risk Agent returns Green, Amber, or Red with citations and a next step.</p></article><em>→</em>
        <article><i>05</i><b>Permission Is Applied</b><p>Light allows a safe local task or sends the case to human review.</p></article>
      </div>
    </section>

    <section className="arch-section agent-pipeline-section">
      <div className="arch-section-title"><span>THE AGENT PIPELINE</span><h3>Seven Specialists, One Clear Order</h3><p>Each stage has one responsibility. Its structured result becomes context for the next stage through Light.</p></div>
      <div className="agent-pipeline">
        {architectureAgents.map((agent, index) => <React.Fragment key={agent.stage}>
          <article>
            <div className="agent-stage"><span>{agent.stage}</span><small>STAGE</small></div>
            <div className="agent-copy"><h4>{agent.name}</h4><b>{agent.plain}</b><p>{agent.does}</p><dl><div><dt>TOOLS</dt><dd>{agent.tools}</dd></div><div><dt>RETURNS</dt><dd>{agent.output}</dd></div></dl></div>
          </article>
          {index < architectureAgents.length - 1 && <i className="pipeline-arrow">↓</i>}
        </React.Fragment>)}
      </div>
    </section>

    <section className="arch-section protocol-section">
      <div className="arch-section-title"><span>HOW THE AGENTS COMMUNICATE</span><h3>A2A Is The Contract Between Services</h3><p>A2A means Agent-to-Agent. It gives each agent a discoverable identity, a standard request format, a managed task, and a structured result.</p></div>
      <div className="protocol-diagram">
        <article><small>BROWSER</small><b>React UI</b><code>POST /api/runs</code></article><em>HTTP</em>
        <article className="protocol-hub"><small>COORDINATOR</small><b>FastAPI Orchestrator</b><code>ClientFactory</code></article><em>A2A JSON-RPC</em>
        <article><small>DISCOVERY</small><b>Agent Card</b><code>/.well-known/agent-card.json</code></article><em>CREATES</em>
        <article><small>AGENT SERVICE</small><b>Executor + Handler</b><code>Task → Artifact</code></article>
      </div>
      <div className="protocol-notes">
        <p><b>Agent Card</b> says who the agent is, what it can do, and where it accepts requests.</p>
        <p><b>AgentExecutor</b> runs that specialist’s own prompt and allowed tools.</p>
        <p><b>DefaultRequestHandler</b> manages the A2A request and task lifecycle.</p>
        <p><b>InMemoryTaskStore</b> tracks protocol tasks; SQLite separately retains the demo’s workflow history and audit records.</p>
      </div>
    </section>

    <section className="arch-section decision-section">
      <div className="arch-section-title"><span>RISK, PERMISSIONS, AND STAGE 8</span><h3>The Recommendation Controls What Happens Next</h3><p>The model-backed Risk Agent owns the displayed recommendation. Light does not replace it with a hardcoded case color.</p></div>
      <div className="risk-diagram">
        <div className="risk-source"><small>RISK AGENT</small><b>Evidence + Checklist + Conflicts</b><span>↓</span><strong>Green, Amber, Or Red?</strong></div>
        <div className="risk-lanes">
          <article className="green"><b>GREEN</b><p>No retained material blocker.</p><span>Local readiness task allowed</span></article>
          <article className="amber"><b>AMBER</b><p>A limited confirmation is still open.</p><span>Transaction coordinator review</span></article>
          <article className="red"><b>RED</b><p>A material, legal, or major compliance issue exists.</p><span>Broker or appropriate expert review</span></article>
        </div>
      </div>
      <div className="stage-eight"><b>After The Risk Decision</b><span>Commission calculation is advisory</span><span>Closing control can hold the package</span><span>Communication creates a draft only</span><span>Every action is logged</span></div>
    </section>

    <section className="arch-section">
      <div className="arch-section-title"><span>TECHNOLOGY STACK</span><h3>What The MVP Is Built With</h3><p>The browser and server use different languages because each is suited to a different part of the system.</p></div>
      <div className="technology-grid">{technologyLayers.map(layer => <article key={layer.label}><span>{layer.label}</span><h4>{layer.title}</h4><p>{layer.copy}</p><code>{layer.path}</code></article>)}</div>
    </section>

    <section className="arch-section repository-section">
      <div className="arch-section-title"><span>PROJECT MAP</span><h3>Where The Important Files Live</h3><p>The repository separates the interface, orchestration, agent services, reusable tools, stored demo data, and tests.</p></div>
      <div className="repository-map">
        <pre>{`doorlight-a2a/
├── src/                     React UI and styling
│   ├── main.tsx             Screens, chat, workflow views
│   └── *.css                Responsive visual system
├── backend/                 Python application
│   ├── app.py               API and Orchestrator
│   ├── a2a_runtime.py       Agent Cards and JSON-RPC wiring
│   ├── agents/              One module per specialist agent
│   ├── services.py          Read-only agent tools
│   ├── workflow_services.py Permissioned Stage 8 services
│   ├── providers.py         Gemini and Ollama adapters
│   ├── vision.py            Local vision/OCR preflight
│   └── store.py             SQLite history and audit trail
├── public/demo-packet/      Synthetic PNG and PDF sources
├── tests/                   Agent and workflow checks
├── pyproject.toml           Python dependencies
└── package.json             UI scripts and dependencies`}</pre>
        <div><article><span>AGENT MODULE</span><b>Prompt + Tools + Run Logic</b><p>Every file in <code>backend/agents/</code> describes one specialist’s instructions, allowed tool belt, responsibilities, and artifact output.</p></article><article><span>SHARED SERVICES</span><b>Concrete, Testable Operations</b><p>The tools search documents, extract evidence, compare terms, select policies, calculate fingerprints, and evaluate requirements over the retained packet.</p></article></div>
      </div>
    </section>

    <section className="arch-section boundary-section">
      <div className="arch-section-title"><span>WHAT IS REAL TODAY</span><h3>A Working Local System With A Safe Demo Boundary</h3></div>
      <div className="boundary-grid"><article><b>Working In This MVP</b><ul><li>Official A2A Agent Cards and JSON-RPC endpoints</li><li>Seven independent agent executors and artifacts</li><li>Real local document search, comparison, hashing, and OCR preflight</li><li>Gemini and Ollama provider selection</li><li>SQLite run, artifact, permission, and audit history</li><li>Green, Amber, and Red workflow paths</li></ul></article><article><b>Represented, But Not Connected</b><ul><li>CRM, MLS, email, calendar, and mobile applications</li><li>Live e-sign, escrow, title, lender, and insurance systems</li><li>Production authentication, MFA, WAF, encryption, and API gateway</li><li>External messages, payments, signatures, recording, or closing</li><li>Real customer documents or legal decision-making</li></ul></article></div>
      <p className="arch-closing"><b>In one sentence:</b> Doorlight turns a transaction question and a packet of documents into an evidence-backed recommendation through a governed network of specialized A2A agents.</p>
    </section>
  </section>;
}
function Transaction({ selectedCase, setCase }: { selectedCase: CaseOption; setCase: (id: string) => void }) {
  const [transactionState, setTransaction] = useState<TransactionContext>();
  const transaction = transactionState as TransactionContext;
  const [selectedDocument, setSelectedDocument] = useState<SourceReaderDocument>();
  const [documentQuery, setDocumentQuery] = useState('');
  useEffect(() => { setTransaction(undefined); void api(`/transaction/${selectedCase.id}`).then(setTransaction); }, [selectedCase.id]);
  const sourceDocuments = useMemo(() => {
    if (!transaction) return [];
    const query = documentQuery.trim().toLowerCase();
    return transaction.documents.filter(document => !query || `${document.name} ${document.classification}`.toLowerCase().includes(query)).sort((left, right) => left.name.localeCompare(right.name));
  }, [transaction, documentQuery]);
  return <section className="transaction source-library">
    <span>RETAINED SOURCE LIBRARY</span><h2>Transaction {selectedCase.id} · Original Documents</h2>
    <p>Each item is an original transaction document. This library makes no readiness or approval decision; AI findings appear only after the workflow runs.</p>
    <div className="case-switcher packet-switcher"><span>DEMO CASES</span>{demoCases.map(item => <button type="button" className={item.id === selectedCase.id ? `selected ${item.lane.toLowerCase()}` : item.lane.toLowerCase()} onClick={() => setCase(item.id)} key={item.id}>CASE · {item.id} · {item.issue}</button>)}</div>
    {transaction && <><div className="packet-heading"><div><span>Original Packet</span><h3>Source Pages</h3></div><small>{transaction.documents.length} Retained Records</small></div>
    <section className="source-library-toolbar" aria-label="Find a source document"><label><span>Find A Document</span><input value={documentQuery} onChange={event => setDocumentQuery(event.target.value)} placeholder="Search document name or type"/></label></section>
    <div className="source-library-summary"><span>{sourceDocuments.length} {sourceDocuments.length === 1 ? 'Document' : 'Documents'}</span><small>Original pages · Read-only</small></div>
    <section className="source-list">{sourceDocuments.map(document => { const sourcePages = document.sourcePages?.length ? document.sourcePages : [{ number: 1, text: document.text, imageUrl: document.imageUrl || '' }]; const packet = { name: document.name, version: document.version, pages: `${sourcePages.length} ${sourcePages.length === 1 ? 'page' : 'pages'}`, pdfUrl: document.pdfUrl || '', sourcePages }; return <article className="source-row" key={`${document.name}-${document.version}`}><div className="source-row-title"><h4>{document.name}</h4><p>{packet.version} · {packet.pages}</p></div><div className="source-row-actions"><button type="button" onClick={() => setSelectedDocument(packet)}>Read</button><a href={packet.pdfUrl} target="_blank" rel="noreferrer">PDF</a></div></article>})}</section>
    {!sourceDocuments.length && <div className="source-empty"><b>No Matching Documents</b><p>Try another document name or return to All.</p></div>}</>}
    {!transaction && <div className="surface-loading"><i/><div><b>Loading Source Library</b><p>Reading the retained document inventory for transaction {selectedCase.id}…</p></div></div>}
    {selectedDocument && <SourcePage key={`${selectedDocument.name}-${selectedDocument.version}`} document={selectedDocument} selectedCase={selectedCase} close={() => setSelectedDocument(undefined)}/>}
  </section>;
}

function ContextOverview({ selectedCase, setCase, run }: { selectedCase: CaseOption; setCase: (id: string) => void; run?: Run }) {
  const [overview, setOverview] = useState<{ caseId: string; generatedBy: string; sections: { title: string; method: string; items: { label: string; value: string; citation: string }[] }[] }>();
  const workflowComplete = Boolean(run && run.caseId === selectedCase.id && !run.targetAgent && !run.followUp && (run.status === 'COMPLETE' || run.status === 'AWAITING_HUMAN'));
  useEffect(() => { setOverview(undefined); if (workflowComplete && run) void api(`/context-overview/${selectedCase.id}/${run.id}`).then(setOverview).catch(() => setOverview(undefined)); }, [selectedCase.id, run?.id, workflowComplete]);
  return <section className="transaction context-overview">
    <span>DERIVED CONTEXT OVERVIEW</span><h2>Transaction {selectedCase.id} · Agent-Extracted Facts</h2>
    <p>This tab intentionally shows derived information only. The backend runs document-specific extraction functions over retained source text and returns every displayed field with its document, version, and page citation. It is not a second copy of the raw case record.</p>
    <div className="case-switcher packet-switcher"><span>DEMO CASES</span>{demoCases.map(item => <button type="button" className={item.id === selectedCase.id ? `selected ${item.lane.toLowerCase()}` : item.lane.toLowerCase()} onClick={() => setCase(item.id)} key={item.id}>CASE · {item.id} · {item.issue}</button>)}</div>
    {!workflowComplete && <section className="context-gate"><div><span>WAITING FOR AGENT ARTIFACTS</span><h3>No Derived Context Yet</h3><p>Ask the Doorlight Orchestrator to run a full readiness review. Once Document Intake and Evidence finish, this page will organize the extracted facts and show a source citation for every field.</p></div><ol><li><b>Run</b><small>Start the review in Light</small></li><li><b>Extract</b><small>Agents read and cite the packet</small></li><li><b>Review</b><small>Derived facts appear here</small></li></ol></section>}
    {workflowComplete && !overview && <div className="surface-loading"><i/><div><b>Building Context Overview</b><p>Reading the completed Document Intake and Evidence artifacts…</p></div></div>}
    {overview && <><p className="derived-method">{overview.generatedBy}</p><section className="context-extraction-grid">{overview.sections.map(section => <article key={section.title}><div className="packet-top"><span>{section.method}</span><b className="verified">Derived</b></div><h3>{section.title}</h3>{section.items.length ? <dl>{section.items.map(item => <div key={`${item.label}-${item.citation}`}><dt>{item.label}</dt><dd>{item.value}</dd><small>{item.citation}</small></div>)}</dl> : <p>No extractable fields were found in the retained source pages.</p>}</article>)}</section></>}
  </section>;
}

function SourcePage({ document, selectedCase, close }: { document: SourceReaderDocument; selectedCase: CaseOption; close: () => void }) {
  useModalBehavior(close);
  const [fontScale, setFontScale] = useState(1);
  const [mode, setMode] = useState<'TEXT' | 'PAGE'>('PAGE');
  const [imageFailed, setImageFailed] = useState(false);
  const [pageIndex, setPageIndex] = useState(0);
  const page = document.sourcePages[pageIndex];
  const paragraphs = page.text.split(/\n\s*\n/).filter(Boolean);
  const showPage = mode === 'PAGE' && !imageFailed;
  const changePage = (next: number) => { setPageIndex(next); setImageFailed(false); };
  return createPortal(<div className="source-modal" role="dialog" aria-modal="true" aria-label={`${document.name} source page`} onMouseDown={event => { if (event.target === event.currentTarget) close(); }}><div className="source-modal-head"><div><span>Retained Source Document · {showPage ? 'Original Page' : 'Accessible Text View'}</span><b>{document.name} · {document.version} · Page {page.number} of {document.sourcePages.length}</b></div><div className="source-reader-controls"><button type="button" disabled={pageIndex === 0} onClick={() => changePage(pageIndex - 1)}>Previous</button><b>{pageIndex + 1} / {document.sourcePages.length}</b><button type="button" disabled={pageIndex === document.sourcePages.length - 1} onClick={() => changePage(pageIndex + 1)}>Next</button><button type="button" className={mode === 'TEXT' ? 'selected' : ''} onClick={() => setMode('TEXT')}>Text</button><button type="button" className={mode === 'PAGE' ? 'selected' : ''} onClick={() => setMode('PAGE')}>Page Image</button>{!showPage && <><button type="button" onClick={() => setFontScale(value => Math.max(.8, value - .1))} aria-label="Smaller text">A−</button><button type="button" onClick={() => setFontScale(value => Math.min(1.8, value + .1))} aria-label="Larger text">A+</button></>}<a href={document.pdfUrl} target="_blank" rel="noreferrer">Open PDF</a><button type="button" onClick={close}>Close</button></div></div>{showPage ? <section className="source-image-reader"><img src={page.imageUrl} alt={`Original synthetic page ${page.number} of ${document.name}`} onError={() => { setImageFailed(true); setMode('TEXT'); }}/><p>Page {page.number} of {document.sourcePages.length}. This pre-made page is available to the local vision/OCR intake.</p></section> : <article className="source-text-reader" style={{ fontSize: `${fontScale}em` }}><header><span>Doorlight Demo Brokerage · Transaction {selectedCase.id}</span><b>Page {page.number} of {document.sourcePages.length} · Source Preserved</b></header><h2>{document.name}</h2><p className="source-caption">Accessible text for this exact rendered page.</p>{imageFailed && <p className="source-image-fallback">The rendered image was unavailable in this browser, so its paired text page is shown instead.</p>}{paragraphs.map((paragraph, index) => <p key={index}>{paragraph}</p>)}<footer><span>Read-only source text · cite this page before using it</span><b>{document.version}</b></footer></article>}</div>, globalThis.document.body);
}

createRoot(document.getElementById('root')!).render(<App/>);
