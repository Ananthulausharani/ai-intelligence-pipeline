"""
Generates architecture.pdf using Playwright Chromium.
Ensures a strict 3-page layout with professional styling, SVG diagrams, and comprehensive technical depth.
"""

import asyncio
import os
import re
from playwright.async_api import async_playwright

HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AI Intelligence Pipeline — Architecture & 500K Scale Design</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');

  @page {
    size: A4 portrait;
    margin: 8mm 10mm 8mm 10mm;
  }

  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    color: #1e293b;
    background: #ffffff;
    font-size: 8.2pt;
    line-height: 1.32;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }

  .page {
    width: 100%;
    height: 279mm;
    max-height: 279mm;
    overflow: hidden;
    position: relative;
    padding: 2mm 0;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }

  .page-break {
    page-break-after: always;
    break-after: page;
  }

  /* Header & Footer */
  .page-header {
    border-bottom: 1.5px solid #0f172a;
    padding-bottom: 4px;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
  }

  .page-title {
    font-size: 14pt;
    font-weight: 800;
    color: #0f172a;
    letter-spacing: -0.02em;
    line-height: 1.1;
  }

  .page-subtitle {
    font-size: 7.5pt;
    color: #64748b;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .page-footer {
    border-top: 1px solid #e2e8f0;
    padding-top: 4px;
    margin-top: 6px;
    display: flex;
    justify-content: space-between;
    font-size: 7pt;
    color: #94a3b8;
    font-weight: 500;
  }

  /* Typography & Structure */
  h2 {
    font-size: 9.5pt;
    font-weight: 700;
    color: #0f172a;
    margin: 6px 0 3px 0;
    padding-bottom: 2px;
    border-bottom: 1px solid #cbd5e1;
    display: flex;
    align-items: center;
    gap: 5px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  h3 {
    font-size: 8.5pt;
    font-weight: 700;
    color: #1e293b;
    margin: 4px 0 2px 0;
  }

  p {
    margin-bottom: 4px;
    color: #334155;
    text-align: justify;
  }

  strong {
    color: #0f172a;
  }

  code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 7.2pt;
    background: #f1f5f9;
    padding: 1px 3px;
    border-radius: 2px;
    color: #0369a1;
  }

  /* Grid Layouts */
  .grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }

  .grid-3 {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 6px;
  }

  /* Card / Box */
  .card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    padding: 5px 7px;
    margin-bottom: 5px;
  }

  .card-highlight {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
  }

  .card-warning {
    background: #fffbeb;
    border: 1px solid #fef3c7;
  }

  .card-blue {
    background: #f0f9ff;
    border: 1px solid #bae6fd;
  }

  /* Badges */
  .badge {
    display: inline-block;
    font-size: 6.5pt;
    font-weight: 700;
    padding: 1px 4px;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .badge-mvp {
    background: #dbeafe;
    color: #1d4ed8;
    border: 1px solid #bfdbfe;
  }

  .badge-prod {
    background: #fef3c7;
    color: #b45309;
    border: 1px solid #fde68a;
  }

  .badge-metric {
    background: #dcfce7;
    color: #15803d;
    border: 1px solid #bbf7d0;
  }

  /* Diagram styles */
  .diagram-container {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 5px;
    padding: 6px;
    margin: 4px 0 6px 0;
  }

  /* Tables */
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 7.2pt;
    margin: 4px 0 6px 0;
  }

  th, td {
    padding: 3px 5px;
    border: 1px solid #e2e8f0;
    text-align: left;
  }

  th {
    background: #0f172a;
    color: #f8fafc;
    font-weight: 600;
  }

  tr:nth-child(even) {
    background: #f8fafc;
  }

  ul {
    margin-left: 12px;
    margin-bottom: 4px;
  }

  li {
    margin-bottom: 2px;
    color: #334155;
  }
</style>
</head>
<body>

<!-- ======================================================================== -->
<!-- PAGE 1: SYSTEM ARCHITECTURE & PIPELINE FLOW                              -->
<!-- ======================================================================== -->
<div class="page">
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">AI Intelligence Pipeline: Architecture & 500K Scale Design</div>
        <div class="page-subtitle">Production Specification &amp; Local Verification Reference</div>
      </div>
      <div style="text-align: right;">
        <span class="badge badge-mvp">Validated Core MVP</span>
        <span class="badge badge-prod" style="margin-left: 3px;">Production Topology</span>
      </div>
    </div>

    <!-- Overview Statement -->
    <p style="margin-bottom: 6px;">
      The <strong>AI Intelligence Pipeline</strong> is a high-throughput, fault-tolerant ingestion and synthesis architecture engineered to extract, canonicalize, and validate structured intelligence on startups, products, jobs, and research papers from heterogeneous web sources. It theoretically scales to <strong>500,000+ records</strong> without altering core application logic, combining bounded asynchronous concurrency, persistent distributed-safe idempotency, and cascading LLM fallback resilience.
    </p>

    <!-- End-to-End Architecture Diagram (SVG) -->
    <div class="diagram-container">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
        <span style="font-weight: 700; font-size: 8pt; color: #0f172a; text-transform: uppercase;">End-to-End Architecture &amp; Data Pipeline</span>
        <div style="font-size: 6.5pt; color: #64748b;">
          <span style="color: #2563eb;">■ Blue: Validated MVP Core</span> &nbsp;|&nbsp;
          <span style="color: #d97706;">■ Orange: Production Queue &amp; Scale Layer</span> &nbsp;|&nbsp;
          <span style="color: #16a34a;">■ Green: Storage / Deliverable</span>
        </div>
      </div>

      <svg viewBox="0 0 740 230" style="width: 100%; height: auto; font-family: 'Inter', sans-serif;">
        <!-- Sources Box -->
        <rect x="10" y="10" width="130" height="75" rx="4" fill="#f8fafc" stroke="#64748b" stroke-width="1.5"/>
        <text x="75" y="26" text-anchor="middle" font-size="8.5" font-weight="700" fill="#0f172a">PUBLIC WEB SOURCES</text>
        <text x="75" y="40" text-anchor="middle" font-size="7" fill="#475569">TechCrunch, VentureBeat, WIRED</text>
        <text x="75" y="52" text-anchor="middle" font-size="7" fill="#475569">YC Jobs, Built In, RemoteOK</text>
        <text x="75" y="64" text-anchor="middle" font-size="7" fill="#475569">arXiv API &amp; GitHub REST API</text>
        <text x="75" y="77" text-anchor="middle" font-size="6.5" font-weight="600" fill="#2563eb">100% Traceable Source URLs</text>

        <!-- Arrow Sources -> Crawler Queue -->
        <path d="M140 47 L165 47" stroke="#0f172a" stroke-width="1.5" marker-end="url(#arrow)"/>

        <!-- Ingestion & Crawler Box -->
        <rect x="170" y="10" width="150" height="75" rx="4" fill="#eff6ff" stroke="#3b82f6" stroke-width="1.5"/>
        <text x="245" y="25" text-anchor="middle" font-size="8.5" font-weight="700" fill="#1e3a8a">AGENT 1: CRAWLER</text>
        <rect x="178" y="32" width="134" height="18" rx="2" fill="#dbeafe" stroke="#93c5fd" stroke-width="1"/>
        <text x="245" y="44" text-anchor="middle" font-size="7" font-weight="600" fill="#1e40af">aiohttp async (Concurrency=5-15)</text>
        <rect x="178" y="55" width="134" height="22" rx="2" fill="#fef3c7" stroke="#fcd34d" stroke-width="1"/>
        <text x="245" y="66" text-anchor="middle" font-size="6.5" font-weight="700" fill="#92400e">Playwright Fallback (Concurrency=2)</text>
        <text x="245" y="74" text-anchor="middle" font-size="6" fill="#78350f">CSR / JS Hydration Only (RemoteOK, MIT TR)</text>

        <!-- Arrow Crawler -> Agents -->
        <path d="M320 47 L345 47" stroke="#0f172a" stroke-width="1.5" marker-end="url(#arrow)"/>

        <!-- Specialized Agents Box -->
        <rect x="350" y="10" width="165" height="75" rx="4" fill="#eff6ff" stroke="#3b82f6" stroke-width="1.5"/>
        <text x="432" y="25" text-anchor="middle" font-size="8.5" font-weight="700" fill="#1e3a8a">SOURCE-AWARE AGENTS</text>
        <rect x="358" y="32" width="149" height="22" rx="2" fill="#ffffff" stroke="#bfdbfe" stroke-width="1"/>
        <text x="432" y="43" text-anchor="middle" font-size="7" font-weight="600" fill="#1e293b">Agent 2: General Ingestion</text>
        <text x="432" y="51" text-anchor="middle" font-size="6" fill="#64748b">Category Crawl → Sub-link Discovery (Max 10)</text>
        <rect x="358" y="58" width="149" height="20" rx="2" fill="#ffffff" stroke="#bfdbfe" stroke-width="1"/>
        <text x="432" y="69" text-anchor="middle" font-size="7" font-weight="600" fill="#1e293b">Agent 3: Research Paper Agent</text>
        <text x="432" y="76" text-anchor="middle" font-size="6" fill="#64748b">arXiv Atom API + GitHub Stars Enrichment</text>

        <!-- Arrow Agents -> Freshness & Cleaning -->
        <path d="M515 47 L540 47" stroke="#0f172a" stroke-width="1.5" marker-end="url(#arrow)"/>

        <!-- Cleaning + Freshness Filter -->
        <rect x="545" y="10" width="185" height="75" rx="4" fill="#f0fdf4" stroke="#16a34a" stroke-width="1.5"/>
        <text x="637" y="25" text-anchor="middle" font-size="8.5" font-weight="700" fill="#14532d">CLEANING &amp; FRESHNESS</text>
        <text x="637" y="40" text-anchor="middle" font-size="7" font-weight="600" fill="#15803d">24-Hour Publication Window</text>
        <text x="637" y="51" text-anchor="middle" font-size="6.5" fill="#334155">Hierarchical Metadata: JSON-LD, OpenGraph,</text>
        <text x="637" y="61" text-anchor="middle" font-size="6.5" fill="#334155">&lt;time datetime&gt;, Relative Natural Dates</text>
        <text x="637" y="76" text-anchor="middle" font-size="6.5" font-weight="700" fill="#b91c1c">Drop stale / date-missing records</text>

        <!-- Down Arrow Freshness -> Smart Chunking -->
        <path d="M637 85 L637 105" stroke="#0f172a" stroke-width="1.5" marker-end="url(#arrow)"/>

        <!-- Row 2: Smart Chunking, LLM Orchestrator, Entity Resolution -->
        <!-- Smart Chunking -->
        <rect x="545" y="110" width="185" height="50" rx="4" fill="#eff6ff" stroke="#3b82f6" stroke-width="1.5"/>
        <text x="637" y="125" text-anchor="middle" font-size="8.5" font-weight="700" fill="#1e3a8a">SMART CHUNKING &amp; SANITIZATION</text>
        <text x="637" y="138" text-anchor="middle" font-size="7" fill="#334155">Strips &lt;script&gt;, styles, boilerplate tags</text>
        <text x="637" y="150" text-anchor="middle" font-size="7" font-weight="600" fill="#0369a1">Bounded to 12,000 Chars (Preserves Head &amp; Tail)</text>

        <!-- Arrow Smart Chunking -> LLM -->
        <path d="M545 135 L520 135" stroke="#0f172a" stroke-width="1.5" marker-end="url(#arrow)"/>

        <!-- LLM Orchestrator -->
        <rect x="330" y="105" width="185" height="60" rx="4" fill="#fdf4ff" stroke="#a855f7" stroke-width="1.5"/>
        <text x="422" y="120" text-anchor="middle" font-size="8.5" font-weight="700" fill="#581c87">LLM ORCHESTRATOR</text>
        <text x="422" y="132" text-anchor="middle" font-size="7" font-weight="600" fill="#7e22ce">Cascading Fallback Hierarchy:</text>
        <text x="422" y="144" text-anchor="middle" font-size="7" fill="#3b0764">1. Gemini Flash → 2. Groq Llama → 3. DeepSeek</text>
        <text x="422" y="156" text-anchor="middle" font-size="6.5" font-weight="600" fill="#b91c1c">Dynamic 413 Shrinkage &amp; 429 Jittered Backoff</text>

        <!-- Arrow LLM -> Entity Resolution -->
        <path d="M330 135 L305 135" stroke="#0f172a" stroke-width="1.5" marker-end="url(#arrow)"/>

        <!-- Entity Resolution & Validation -->
        <rect x="130" y="105" width="170" height="60" rx="4" fill="#f0fdf4" stroke="#16a34a" stroke-width="1.5"/>
        <text x="215" y="120" text-anchor="middle" font-size="8.5" font-weight="700" fill="#14532d">ENTITY RESOLUTION &amp; VALIDATION</text>
        <text x="215" y="132" text-anchor="middle" font-size="7" fill="#15803d">Deterministic Resolution (Seed: 52 Startups)</text>
        <text x="215" y="143" text-anchor="middle" font-size="6.5" fill="#334155">Exact / Legal Suffix / Normalized Alias Match</text>
        <text x="215" y="154" text-anchor="middle" font-size="6.5" font-weight="600" fill="#0f172a">Pydantic Schema Validation (Zero Hallucination)</text>

        <!-- Arrow Entity Resolution -> Idempotency Store -->
        <path d="M130 135 L105 135" stroke="#0f172a" stroke-width="1.5" marker-end="url(#arrow)"/>

        <!-- Shared Idempotency & Claims Store -->
        <rect x="10" y="105" width="90" height="60" rx="4" fill="#fef3c7" stroke="#d97706" stroke-width="1.5"/>
        <text x="55" y="120" text-anchor="middle" font-size="8" font-weight="700" fill="#92400e">IDEMPOTENCY</text>
        <text x="55" y="132" text-anchor="middle" font-size="6.5" font-weight="600" fill="#78350f">Atomic Claim</text>
        <text x="55" y="143" text-anchor="middle" font-size="6" fill="#78350f">source + norm_url</text>
        <text x="55" y="154" text-anchor="middle" font-size="6" font-weight="700" fill="#b91c1c">UNIQUE Constraint</text>

        <!-- Down Arrow to Storage Layer -->
        <path d="M215 165 L215 185" stroke="#0f172a" stroke-width="1.5" marker-end="url(#arrow)"/>

        <!-- Storage Layer (Row 3) -->
        <rect x="70" y="185" width="290" height="40" rx="4" fill="#f8fafc" stroke="#475569" stroke-width="1.5"/>
        <text x="215" y="200" text-anchor="middle" font-size="8.5" font-weight="700" fill="#0f172a">PRIMARY STORE: PostgreSQL</text>
        <text x="215" y="212" text-anchor="middle" font-size="7" fill="#475569">Startups, Products, News, Jobs, Research Papers, EntityMappingLog</text>
        <text x="215" y="221" text-anchor="middle" font-size="6" font-weight="600" fill="#2563eb">ACID Consistency • Authoritative Source Traceability</text>

        <!-- Vector / Graph Store -->
        <rect x="380" y="185" width="180" height="40" rx="4" fill="#f8fafc" stroke="#475569" stroke-width="1.5"/>
        <text x="470" y="199" text-anchor="middle" font-size="8" font-weight="700" fill="#0f172a">VECTOR &amp; GRAPH PROJECTION</text>
        <text x="470" y="210" text-anchor="middle" font-size="6.5" fill="#475569">pgvector: Embeddings &amp; Semantic Search</text>
        <text x="470" y="220" text-anchor="middle" font-size="6.5" fill="#475569">Relational Edges / Neo4j Graph View</text>

        <!-- Deliverable Output -->
        <rect x="580" y="185" width="150" height="40" rx="4" fill="#f0fdf4" stroke="#16a34a" stroke-width="1.5"/>
        <text x="655" y="200" text-anchor="middle" font-size="8.5" font-weight="700" fill="#14532d">DELIVERABLE OUTPUT</text>
        <text x="655" y="212" text-anchor="middle" font-size="7" font-weight="600" fill="#15803d">Google Sheets Export</text>
        <text x="655" y="221" text-anchor="middle" font-size="6" fill="#64748b">Verified Canonical Deliverable</text>

        <!-- Defs for arrowheads -->
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 1 L 10 5 L 0 9 z" fill="#0f172a"/>
          </marker>
        </defs>
      </svg>
    </div>

    <!-- Comparative Table: Current MVP vs Production Architecture -->
    <h2>Current Implemented MVP vs. Production Scale Architecture</h2>
    <table>
      <thead>
        <tr>
          <th style="width: 18%;">Architectural Subsystem</th>
          <th style="width: 38%;">Current Implemented MVP (Validated in Codebase)</th>
          <th style="width: 44%;">Production-Scale Design (500,000+ Target)</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Crawler &amp; Ingestion</strong></td>
          <td><code>aiohttp</code> async pool (HTTP limit=5-15) + Playwright fallback (limit=2) for JS-rendered pages. Bounded batch execution via <code>fetch_many_batched()</code>.</td>
          <td>Distributed worker fleet (e.g., Celery/Ray/Kubernetes pods) consuming from URL partition queues; worker autoscaling based on queue depth.</td>
        </tr>
        <tr>
          <td><strong>Work Scheduling</strong></td>
          <td>Asyncio coroutine tasks partitioned into bounded in-memory batches of 100 items (O(batch_size) memory ceiling).</td>
          <td>Durable distributed queue (Kafka / RabbitMQ / Redis Streams) partitioned by source domain with adaptive per-domain token bucket rate limiting.</td>
        </tr>
        <tr>
          <td><strong>Idempotency Store</strong></td>
          <td><code>src/storage/idempotency.py</code>: SQLite WAL mode with atomic <code>UNIQUE(source, normalized_url)</code> constraints and thread-safe connections.</td>
          <td>Shared PostgreSQL (<code>INSERT ... ON CONFLICT DO NOTHING</code>) or Redis cluster (<code>SET ... NX EX 86400</code>) accessible across all distributed worker nodes.</td>
        </tr>
        <tr>
          <td><strong>LLM Extraction</strong></td>
          <td>Cascading provider fallback: Gemini Flash → Groq Llama → DeepSeek. Bounded 12,000 char input, 413 dynamic halving, 429 backoff with jitter.</td>
          <td>Centralized LLM gateway with Redis token bucket rate tracking, asynchronous completion worker pools, and fallback provider routing.</td>
        </tr>
        <tr>
          <td><strong>Entity Resolution</strong></td>
          <td><code>DeterministicEntityResolver</code>: seed dictionary (52 AI startups/products), legal suffix stripping, alias tables, explainable mapping logs.</td>
          <td>Distributed entity matching pipeline caching canonical dictionaries in memory with automated alias learning and human-in-the-loop review queues.</td>
        </tr>
        <tr>
          <td><strong>Persistence Layer</strong></td>
          <td>SQLite local persistence + direct Google Sheets API / CSV export. Raw source HTML preservation in CrawlResult.</td>
          <td>PostgreSQL cluster (read-replicas + write primary) for canonical records; pgvector for semantic search; relational edges for graph querying.</td>
        </tr>
      </tbody>
    </table>

    <!-- Data Lineage & Traceability Box -->
    <div class="card card-highlight">
      <h3 style="color: #166534; font-size: 8pt; margin-bottom: 2px;">Core Engineering Guarantee: Non-Negotiable Source Traceability</h3>
      <p style="margin-bottom: 0; font-size: 7.6pt;">
        Every record generated retains immutable origin metadata: <code>source_url</code> (category/board listing), <code>item_url</code> (exact normalized article/job permalink), and <code>collected_at</code> (UTC ISO timestamp). <strong>LLMs are strictly restricted to structured extraction</strong> and are never permitted to fabricate URLs, invent dates, or hallucinate canonical entity existence. If metadata is missing or unverified, fields remain strictly <code>null</code>.
      </p>
    </div>
  </div>

  <div class="page-footer">
    <span>AI Intelligence Pipeline • Engineering Architecture Document</span>
    <span>Page 1 of 3</span>
  </div>
</div>

<div class="page-break"></div>

<!-- ======================================================================== -->
<!-- PAGE 2: SCALE REASONING, 413/429 POLICIES & FAULT TOLERANCE              -->
<!-- ======================================================================== -->
<div class="page">
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">500K Scale Strategy, Rate Handling &amp; Fault Tolerance</div>
        <div class="page-subtitle">Concurrency Bounds • Payload Optimization • Distributed Resilience</div>
      </div>
      <div>
        <span class="badge badge-metric">Benchmark: 718.4 tasks/sec</span>
      </div>
    </div>

    <!-- 500,000 Scale Strategy -->
    <h2>1. 500,000+ Record Scalability &amp; Bounded Concurrency</h2>
    <div class="grid-2">
      <div>
        <p>
          Scaling to 500,000+ items without application code modification requires decoupling workload magnitude from memory and task concurrency. Naive implementations using <code>asyncio.gather(*500000_tasks)</code> immediately cause catastrophic failure: event loop starvation, hundreds of megabytes of leaked coroutine stack frames, and socket exhaustion.
        </p>
        <p>
          <strong>Implemented Bounded Batching Pattern:</strong> As verified in <code>src/crawler/base.py</code>, the system processes workloads in discrete batches of <code>batch_size=100</code> guarded by an internal <code>asyncio.Semaphore(concurrency=5..15)</code>:
        </p>
        <div class="card" style="font-size: 7.2pt; font-family: 'JetBrains Mono', monospace; background: #0f172a; color: #f8fafc; border: none; padding: 4px 6px;">
          WORKLOAD (500k URLs)<br/>
          &nbsp;↳ Bounded Batches (N=100) &nbsp;[O(batch_size) Memory Ceiling]<br/>
          &nbsp;&nbsp;&nbsp;↳ Concurrency Semaphore (K=10) &nbsp;[Guaranteed Active Sockets ≤ K]<br/>
          &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;↳ Atomic Idempotency Claim → aiohttp fetch → Next Batch
        </div>
      </div>
      <div>
        <p>
          <strong>Horizontal Scaling Model:</strong> In a production cluster, 500,000 target URLs are partitioned across $W$ independent crawler worker containers consuming from a shared queue (e.g., Redis Streams / RabbitMQ). Each worker node runs the existing bounded crawler:
        </p>
        <ul>
          <li><strong>Zero Inter-Worker Locking:</strong> Coordination is achieved purely via atomic database claims (<code>claim_if_unseen</code>).</li>
          <li><strong>Linear Scale-Out:</strong> Aggregate crawl capacity scales linearly ($W \times \text{Worker Capacity}$) without modifying any extraction or agent logic.</li>
          <li><strong>Isolated Failure Domains:</strong> A crash in Worker $i$ does not affect Worker $j$. Unfinished claims expire via TTL and are safely requeued.</li>
        </ul>
      </div>
    </div>

    <!-- Benchmark Evidence Box -->
    <div class="card card-blue" style="margin-top: 2px; margin-bottom: 5px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;">
        <strong style="color: #0369a1; font-size: 7.8pt;">Step 23 Empirical Load Validation (Local Synthetic Transport Benchmark)</strong>
        <span style="font-size: 6.8pt; color: #0284c7; font-weight: 600;">100% Task Accounting • Zero Concurrency Leaks</span>
      </div>
      <table style="margin: 0; background: #ffffff;">
        <thead>
          <tr>
            <th>Workload Size</th>
            <th>Elapsed Time</th>
            <th>Measured Throughput</th>
            <th>Configured Concurrency</th>
            <th>Max Observed Concurrency</th>
            <th>Concurrency Bounding</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>100 Tasks</td>
            <td>0.272 s</td>
            <td>367.5 tasks/sec</td>
            <td>5</td>
            <td>5</td>
            <td><strong style="color: #16a34a;">PASS (Strictly Respected)</strong></td>
          </tr>
          <tr>
            <td>1,000 Tasks</td>
            <td>1.392 s</td>
            <td>718.4 tasks/sec</td>
            <td>10</td>
            <td>10</td>
            <td><strong style="color: #16a34a;">PASS (Strictly Respected)</strong></td>
          </tr>
          <tr>
            <td>5,000 Tasks</td>
            <td>2.934 s</td>
            <td>1,704.4 tasks/sec</td>
            <td>15</td>
            <td>15</td>
            <td><strong style="color: #16a34a;">PASS (Strictly Respected)</strong></td>
          </tr>
        </tbody>
      </table>
      <div style="font-size: 6.8pt; color: #475569; margin-top: 3px;">
        <strong>Theoretical Extrapolation:</strong> At 718.4 tasks/sec, 500,000 crawl operations require ~696 seconds (~11.6 minutes). <em>Caveat:</em> This measures internal event loop capacity and pipeline bounding. Real-world crawls are governed by domain rate limits, network RTT, and LLM throughput.
      </div>
    </div>

    <!-- HTTP vs Browser Rendering Performance Disparity -->
    <h2>2. HTTP vs. Playwright Headless Browser Workload Segregation</h2>
    <div class="grid-2">
      <div class="card">
        <strong style="color: #1e40af;">Asynchronous HTTP (aiohttp) — Primary Path (&gt;95% Volume)</strong>
        <ul style="margin-top: 2px;">
          <li>Throughput: <strong>500 – 2,000 tasks/sec</strong> per modern server core.</li>
          <li>Resource footprint: ~2 KB memory per connection; negligible CPU load.</li>
          <li>Utilized for: RSS, APIs, clean SSR HTML (TechCrunch, YC, Wired, arXiv).</li>
        </ul>
      </div>
      <div class="card card-warning">
        <strong style="color: #92400e;">Headless Browser (Playwright) — Fallback Path (&lt;5% Volume)</strong>
        <ul style="margin-top: 2px;">
          <li>Throughput: <strong>0.5 – 2.0 tasks/sec</strong> per browser tab instance.</li>
          <li>Resource footprint: ~150 MB RAM per Chromium context; high CPU overhead.</li>
          <li>Strictly restricted to: Known CSR boards (RemoteOK, WorkingNomads, MIT TR).</li>
        </ul>
      </div>
    </div>

    <!-- Exact 413 and 429 Handling Strategy -->
    <h2>3. Exact HTTP 413 and 429 Handling Strategies</h2>
    <div class="grid-2">
      <div>
        <h3>HTTP 413: Payload Too Large Strategy</h3>
        <p style="font-size: 7.6pt;">
          <strong>Root Cause:</strong> Raw web pages exceed provider token/context window limits. Handled fundamentally differently from 429 because retrying identical payloads will permanently fail.
        </p>
        <ol style="margin-left: 12px; font-size: 7.4pt; color: #334155;">
          <li><strong>Proactive Sanitization:</strong> Strip <code>&lt;script&gt;</code>, <code>&lt;style&gt;</code>, SVGs, and inline CSS; collapse whitespace. Clean text is pre-truncated to <code>12,000 characters</code>.</li>
          <li><strong>Head + Tail Context Anchoring:</strong> Truncation retains the first 7,000 chars (headlines, leads) and final 4,500 chars (author, dates, disclosures).</li>
          <li><strong>Reactive 413 Interception:</strong> If provider responds with HTTP 413, intercept error, dynamically halve payload to 6,000 chars, and re-attempt.</li>
          <li><strong>Provider Cascading:</strong> If 413 persists, cascade to the next fallback provider. Source URLs and metadata remain intact.</li>
        </ol>
      </div>
      <div>
        <h3>HTTP 429: Rate &amp; Quota Throttling Strategy</h3>
        <p style="font-size: 7.6pt;">
          <strong>Root Cause:</strong> Temporary rate limit saturation on source websites (crawler) or upstream LLM provider quotas. Handled via temporal backoff.
        </p>
        <ol style="margin-left: 12px; font-size: 7.4pt; color: #334155;">
          <li><strong>Crawler 429 Protocol:</strong> Inspect <code>Retry-After</code> header. If present, sleep for the requested duration (capped at 60s); otherwise record 429 cleanly without hammering the site.</li>
          <li><strong>LLM 429 Protocol:</strong> If Gemini Flash throttles (HTTP 429), inspect <code>Retry-After</code> or apply exponential backoff + jitter: $\text{delay} = 1.5^{\text{attempt}} + \text{jitter}$.</li>
          <li><strong>Bounded Retries &amp; Cascading:</strong> Max 3 retries. If exhausted, instantly switch to next provider: <strong>Gemini Flash → Groq Llama → DeepSeek</strong>.</li>
          <li><strong>Failure Isolation:</strong> Exhausted 429s record structured errors. Never block or cancel unrelated pipeline records.</li>
        </ol>
      </div>
    </div>

    <!-- Fault Tolerance Summary Table -->
    <h2>4. Comprehensive Fault Isolation Matrix</h2>
    <table>
      <thead>
        <tr>
          <th>Condition</th>
          <th>Crawler Action</th>
          <th>LLM Orchestrator Action</th>
          <th>System Isolation Guarantee</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>HTTP 403 Forbidden</strong></td>
          <td>Record failure immediately; 0 retries (polite crawling; no bypass).</td>
          <td>N/A (Crawl phase terminated).</td>
          <td>Single task records error; remaining 999 tasks execute uninterrupted.</td>
        </tr>
        <tr>
          <td><strong>HTTP 429 Rate Limit</strong></td>
          <td>Honor <code>Retry-After</code> (up to 60s); record failure if unrecoverable.</td>
          <td>Exponential backoff with jitter; cascade to Groq Llama → DeepSeek.</td>
          <td>Prevents IP bans; provider failover transparent to downstream agents.</td>
        </tr>
        <tr>
          <td><strong>HTTP 5xx Server Error</strong></td>
          <td>Retry up to 3 times with exponential backoff ($\text{base}=1.5$s).</td>
          <td>Retry up to 3 times; cascade to next provider.</td>
          <td>Transient upstream drops recover automatically; permanent failures isolated.</td>
        </tr>
        <tr>
          <td><strong>Timeout &amp; Connection Drop</strong></td>
          <td>Catch <code>TimeoutError</code> (20s limit); retry bounded; mark failed.</td>
          <td>Catch socket timeout (30s limit); switch provider.</td>
          <td>No socket leaks or hung processes; event loop remains responsive.</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="page-footer">
    <span>AI Intelligence Pipeline • Engineering Architecture Document</span>
    <span>Page 2 of 3</span>
  </div>
</div>

<div class="page-break"></div>

<!-- ======================================================================== -->
<!-- PAGE 3: STORAGE ARCHITECTURE, RESEARCH PIPELINE & CAPACITY               -->
<!-- ======================================================================== -->
<div class="page">
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">Storage Design, Research Pipeline &amp; Capacity Reasoning</div>
        <div class="page-subtitle">PostgreSQL Relational Schema • pgvector &amp; Graph • Production Bottlenecks</div>
      </div>
      <div>
        <span class="badge badge-mvp">ACID Guaranteed</span>
      </div>
    </div>

    <!-- Freshness vs Distributed Idempotency -->
    <h2>1. Freshness vs. Distributed Idempotency (Decoupled Concepts)</h2>
    <div class="grid-2">
      <div class="card">
        <strong style="color: #1e3a8a;">Freshness Evaluation ("Is it chronologically recent?")</strong>
        <p style="font-size: 7.4pt; margin-top: 2px;">
          Evaluated strictly against published timestamps via <code>src/agents/freshness.py</code>. Only items with verified dates within the trailing 24 hours ($[t_{\text{now}} - 24\text{h}, t_{\text{now}}]$) are admitted. Missing or unverified publication dates are dropped to prevent stale ingestion.
        </p>
      </div>
      <div class="card">
        <strong style="color: #1e3a8a;">Distributed Idempotency ("Has it been claimed/processed?")</strong>
        <p style="font-size: 7.4pt; margin-top: 2px;">
          Evaluated on stable identity: <code>source + normalize_storage_url(item_url)</code>. Strips marketing tracking parameters (<code>utm_*</code>, <code>ref</code>) and fragments. Prevents double-crawling across distributed nodes even if identical articles are scheduled concurrently.
        </p>
      </div>
    </div>
    <div class="card card-highlight" style="font-size: 7.3pt; padding: 4px 6px; margin-top: 2px;">
      <strong>Atomic Claim Race Condition Resolution:</strong> When Worker A and Worker B encounter the same URL simultaneously, both execute an atomic claim against the shared store. In the validated MVP (SQLite), this is enforced by <code>UNIQUE(source, normalized_url)</code>. In production PostgreSQL, it executes <code>INSERT INTO idempotency_claims (...) VALUES (...) ON CONFLICT DO NOTHING RETURNING id;</code>. Exactly <strong>ONE worker wins the claim</strong>; the losing worker receives <code>False</code> and safely discards the item. <em>Content modifications on an existing URL do not create duplicate records.</em>
    </div>

    <!-- Storage Architecture: Primary DB + Vector / Graph -->
    <h2>2. Storage Architecture: Primary DB, Vector &amp; Graph Projections</h2>
    <div class="grid-3">
      <div class="card">
        <strong style="color: #0f172a; font-size: 7.8pt;">A. Primary Database (PostgreSQL)</strong>
        <p style="font-size: 7.2pt; margin-top: 2px;">
          <strong>System of Record:</strong> Relational PostgreSQL with full ACID guarantees. Normalized schema tables:
        </p>
        <ul style="font-size: 7pt; margin-left: 10px;">
          <li><code>startups</code>: canonical name, domain, funding, employee count, status.</li>
          <li><code>products</code>: canonical product, startup_id FK, categories.</li>
          <li><code>jobs</code>: role title, company_id FK, location, remote flag, date.</li>
          <li><code>news</code>: title, source_url, item_url, published_date, summary.</li>
          <li><code>research_papers</code>: arXiv ID, title, authors, GitHub repo, stars.</li>
          <li><code>entity_mapping_logs</code>: raw name, canonical name, match method, confidence score.</li>
        </ul>
      </div>

      <div class="card">
        <strong style="color: #0f172a; font-size: 7.8pt;">B. Vector Storage (pgvector)</strong>
        <p style="font-size: 7.2pt; margin-top: 2px;">
          <strong>Semantic Retrieval Layer:</strong> Implemented within PostgreSQL using the <code>pgvector</code> extension.
        </p>
        <ul style="font-size: 7pt; margin-left: 10px;">
          <li>Embeddings generated via <code>text-embedding-3-small</code> or open-source BGE embeddings.</li>
          <li>Tables: <code>paper_embeddings</code> (1536-dim abstract vectors), <code>startup_embeddings</code>.</li>
          <li>HNSW / IVFFlat indexing for fast nearest-neighbor similarity search (&lt;10ms).</li>
          <li>Enables clustering of competing startups and semantic paper recommendations.</li>
        </ul>
      </div>

      <div class="card">
        <strong style="color: #0f172a; font-size: 7.8pt;">C. Graph Projection (Intelligence Graph)</strong>
        <p style="font-size: 7.2pt; margin-top: 2px;">
          <strong>Multi-Hop Relationship Layer:</strong>
        </p>
        <ul style="font-size: 7pt; margin-left: 10px;">
          <li><strong>Option A (Relational Edges):</strong> Foreign key junction tables (<code>startup_products</code>, <code>paper_startups</code>, <code>founder_startups</code>) queried via recursive CTEs.</li>
          <li><strong>Option B (Scale-Out Graph DB):</strong> Event-driven change data capture (CDC) streaming edges to <strong>Neo4j</strong> for rich graph querying:
            <br/><code>(Startup)-[:DEVELOPS]-&gt;(Product)</code>
            <br/><code>(Startup)-[:RESEARCHED]-&gt;(Paper)</code>
            <br/><code>(News)-[:MENTIONS]-&gt;(Startup)</code>
          </li>
        </ul>
      </div>
    </div>

    <!-- Research Paper Flow -->
    <h2>3. Research Paper Enrichment Flow &amp; Best-Effort GitHub Linking</h2>
    <p style="font-size: 7.4pt;">
      Research papers follow a deterministic, non-LLM acquisition pipeline verified in <code>src/agents/agent3_research.py</code>:
    </p>
    <div class="card" style="font-size: 7.2pt; font-family: 'JetBrains Mono', monospace; background: #f1f5f9; padding: 4px 6px;">
      arXiv Atom API (Search AI/CS queries) → XML Stream Parsing (title, authors, published, abstract, arXiv URL)<br/>
      &nbsp;↳ Hugging Face Papers API / Papers with Code API (Exact paper-to-code mapping resolution)<br/>
      &nbsp;&nbsp;&nbsp;↳ GitHub REST API (Fetch real-time repository star count, open issues, primary language)<br/>
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;↳ Output Canonical Paper Record &nbsp;[If GitHub unverified → github_url=null; ZERO hallucination]
    </div>

    <!-- Real-World Capacity vs Synthetic Benchmarks -->
    <h2>4. Theoretical Capacity vs. Real-World Production Bottlenecks</h2>
    <div class="grid-2">
      <div>
        <p style="font-size: 7.4pt;">
          <strong>Capacity Mathematical Projection:</strong> While local synthetic benchmarks demonstrate engine capacity of <strong>718.4 tasks/sec</strong> (theoretically crawling 500k records in 11.6 minutes), production deployments encounter severe real-world physical constraints:
        </p>
        <table style="margin-top: 2px;">
          <thead>
            <tr>
              <th>Subsystem</th>
              <th>Synthetic Test</th>
              <th>Real-World Production Reality</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Source Ingestion</strong></td>
              <td>0.3 ms local delay</td>
              <td>100–300 ms network RTT; 1–5 req/sec polite limit per domain.</td>
            </tr>
            <tr>
              <td><strong>Browser Render</strong></td>
              <td>Bypassed (mock)</td>
              <td>2,000–5,000 ms per page load + DOM hydration (Playwright).</td>
            </tr>
            <tr>
              <td><strong>LLM Extraction</strong></td>
              <td>Pre-cached / mock</td>
              <td>500–1,500 ms generation RTT; strict provider TPM/RPM quotas.</td>
            </tr>
            <tr>
              <td><strong>Database Writes</strong></td>
              <td>In-memory SQLite</td>
              <td>Disk I/O, transaction commit latency, index write overhead.</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div>
        <p style="font-size: 7.4pt;">
          <strong>Production Sizing for 500,000 Records:</strong>
        </p>
        <ul style="font-size: 7.2pt;">
          <li>Assuming polite crawling across 500 distinct host domains with 2 concurrent connections each ($1,000$ active requests) yielding an aggregate web crawl rate of ~<strong>100 pages/sec</strong>:
            <br/>$\text{Crawl Time} = \frac{500,000}{100} = 5,000\text{ s} \approx \mathbf{1.38\text{ hours}}$.</li>
          <li>Assuming 10% of crawled pages qualify under 24-hour freshness ($50,000$ LLM extractions) distributed across 3 API providers at 30 req/sec aggregate:
            <br/>$\text{Extraction Time} = \frac{50,000}{30} = 1,666\text{ s} \approx \mathbf{27.8\text{ minutes}}$.</li>
          <li><strong>Conclusion:</strong> With horizontal crawler worker fleet, the complete 500,000-record pipeline completes in <strong>under 2 hours</strong> without any modifications to application code.</li>
        </ul>
      </div>
    </div>

    <!-- Security, Compliance & Access Control Box -->
    <h2>5. Security, Ethics &amp; Access Control Architecture</h2>
    <div class="card card-warning" style="font-size: 7.2pt; padding: 4px 6px; margin-bottom: 0;">
      <strong>Strict Access Compliance:</strong> The pipeline strictly honors web standards and ethical scraping policies: (1) Respects <code>robots.txt</code> and source rate limits; (2) Zero CAPTCHA or Cloudflare bypass mechanisms; (3) Identifies with clean User-Agent headers; (4) API keys (Gemini, Groq, DeepSeek) are managed exclusively through environment variables and never logged or committed; (5) Google Sheets output acts solely as the user deliverable layer, keeping internal storage decoupled and secure.
    </div>
  </div>

  <div class="page-footer">
    <span>AI Intelligence Pipeline • Engineering Architecture Document</span>
    <span>Page 3 of 3</span>
  </div>
</div>

</body>
</html>
"""


async def generate_pdf(output_path: str = "architecture.pdf") -> int:
    """Render HTML content into a PDF using Playwright Chromium and return page count."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(HTML_CONTENT, wait_until="networkidle")
        
        # Render PDF with exact A4 format and background colors
        await page.pdf(
            path=output_path,
            format="A4",
            print_background=True,
            margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
            prefer_css_page_size=True,
        )
        await browser.close()

    # Determine page count by inspecting PDF binary
    with open(output_path, "rb") as f:
        data = f.read()

    # Method 1: parse /Type /Pages /Count N
    matches = re.findall(rb"/Type\s*/Pages.*?/Count\s+(\d+)", data, re.DOTALL)
    if matches:
        return int(matches[0])

    # Method 2: count /Type /Page (excluding /Type /Pages)
    page_objects = len(re.findall(rb"/Type\s*/Page\b", data))
    pages_dict = len(re.findall(rb"/Type\s*/Pages\b", data))
    return page_objects - pages_dict


def main():
    pdf_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "architecture.pdf")
    count = asyncio.run(generate_pdf(pdf_path))
    print(f"Generated PDF: {pdf_path}")
    print(f"Total Pages: {count}")
    if count > 3:
        print(f"WARNING: PDF exceeded 3 pages ({count} pages)!")
    elif count == 3:
        print("SUCCESS: PDF is exactly 3 pages!")
    else:
        print(f"PDF is {count} pages (under 3 pages).")


if __name__ == "__main__":
    main()
