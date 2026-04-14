document.addEventListener("DOMContentLoaded", () => {
    // Tab switching
    const tabBtns = document.querySelectorAll(".tab-btn");
    const tabPanels = document.querySelectorAll(".tab-panel");

    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            tabBtns.forEach(b => b.classList.remove("active"));
            tabPanels.forEach(p => p.classList.remove("active"));
            
            btn.classList.add("active");
            const targetId = `panel-${btn.dataset.tab}`;
            document.getElementById(targetId).classList.add("active");

            if (btn.dataset.tab === "traces") {
                loadTraces();
            }
        });
    });

    // Check hitl overlay clicks to not close accidentally
    document.getElementById("hitl-overlay").addEventListener("click", (e) => {
        if (e.target.id === "hitl-overlay") {
            // Do not close on background click for safety
        }
    });
});

let pendingAgentState = null;

function fillQuery(text) {
    document.getElementById("chat-input").value = text;
    // Fix: Trigger submit properly so preventDefault works
    document.getElementById("send-btn").click();
}

window.fillQuery = fillQuery;

function escapeHtml(unsafe) {
    if (!unsafe) return "";
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

function formatSources(sources) {
    if (!sources || sources.length === 0) return "";
    return sources.map((s, i) => `<span class="badge-tag">[${i+1}] ${escapeHtml(s)}</span>`).join(" ");
}

function renderMessage(content, sender, isHtml=false) {
    const chatMsgs = document.getElementById("chat-messages");
    // Remove welcome card if present
    const wc = chatMsgs.querySelector(".welcome-card");
    if (wc) wc.remove();

    const msgDiv = document.createElement("div");
    msgDiv.className = `msg ${sender}`;
    
    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";
    if (isHtml) {
        bubble.innerHTML = content;
    } else {
        bubble.textContent = content;
    }
    
    msgDiv.appendChild(bubble);
    
    const meta = document.createElement("div");
    meta.className = "msg-meta";
    meta.textContent = sender === "user" ? "You" : "Supervisor Orchestrator";
    msgDiv.appendChild(meta);
    
    chatMsgs.appendChild(msgDiv);
    chatMsgs.scrollTop = chatMsgs.scrollHeight;
    return msgDiv; /* allow removing typing indicator later */
}

function renderTyping() {
    const chatMsgs = document.getElementById("chat-messages");
    const msgDiv = document.createElement("div");
    msgDiv.className = `msg agent typing-msg`;
    msgDiv.innerHTML = `
        <div class="msg-bubble">
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    `;
    chatMsgs.appendChild(msgDiv);
    chatMsgs.scrollTop = chatMsgs.scrollHeight;
    return msgDiv;
}

function drawTraceNode(type, title, detailHTML, badgesHTML="") {
    const container = document.getElementById("sidebar-trace-nodes");
    const empty = container.querySelector(".sidebar-empty");
    if (empty) empty.remove();

    const _html = `
        <div class="trace-node ${type}">
            <div class="node-icon"></div>
            <div class="node-content">
                <div class="node-title">${title} <span>✓</span></div>
                <div>${badgesHTML}</div>
                <div class="node-detail">${detailHTML}</div>
            </div>
        </div>
    `;
    
    const div = document.createElement("div");
    div.innerHTML = _html;
    container.appendChild(div.firstElementChild);
}

function clearTraceSidebar() {
    const container = document.getElementById("sidebar-trace-nodes");
    container.innerHTML = `<div class="trace-timeline" id="trace-timeline"></div>`;
}

function appendToTimeline(type, title, detailHTML, badgesHTML="") {
    const tl = document.getElementById("trace-timeline");
    const _html = `
        <div class="trace-node ${type}">
            <div class="node-icon"></div>
            <div class="node-content">
                <div class="node-title">${title}</div>
                <div>${badgesHTML}</div>
                <div class="node-detail">${detailHTML}</div>
            </div>
        </div>
    `;
    const temp = document.createElement("div");
    temp.innerHTML = _html;
    tl.appendChild(temp.firstElementChild);
}

async function sendChat(e) {
    e.preventDefault();
    const input = document.getElementById("chat-input");
    const val = input.value.trim();
    if (!val) return;

    input.value = "";
    renderMessage(val, "user");
    
    document.getElementById("send-btn").disabled = true;
    const typing = renderTyping();
    clearTraceSidebar();
    document.getElementById("trace-latency").textContent = "running...";

    try {
        // Step 1: Hit Analyze (Supervisor)
        const res = await fetch("/api/agent/analyze", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({query: val})
        });
        const data = await res.json();
        
        if (data.error) throw new Error(data.error);

        pendingAgentState = data.state;
        
        let badges = [];
        if (pendingAgentState.risk_high) badges.push(`<span class="badge-tag badge-danger">RISK_HIGH</span>`);
        if (pendingAgentState.needs_tool) badges.push(`<span class="badge-tag">NEEDS_TOOL</span>`);
        
        appendToTimeline("supervisor", "Supervisor Node", `<strong>Route:</strong> ${pendingAgentState.supervisor_route}<br><strong>Reason:</strong> ${pendingAgentState.route_reason}`, badges.join(""));

        if (data.hitl_required) {
            // Show HITL Modal
            document.getElementById("hitl-task").textContent = val;
            document.getElementById("hitl-reason").textContent = pendingAgentState.route_reason;
            document.getElementById("hitl-overlay").classList.add("active");
            
            appendToTimeline("hitl", "Human Review", `Execution paused. Awaiting human input...`);
            
            // We wait here until user clicks a modal button
        } else {
            // Auto continue
            await executeRestOfPipeline("approve");
        }

    } catch (error) {
        typing.remove();
        renderMessage(`❌ System Error: ${error.message}`, "agent");
        document.getElementById("send-btn").disabled = false;
    }
}
window.sendChat = sendChat;

async function handleHITL(action) {
    document.getElementById("hitl-overlay").classList.remove("active");
    if (!pendingAgentState) return;

    if (action === "approve") {
        appendToTimeline("hitl", "Human Action", `Approved by human. Route changed to <strong>retrieval_worker</strong>.`);
    } else {
        appendToTimeline("hitl", "Human Action", `Denied by human. Aborting pipeline.`);
    }
    
    await executeRestOfPipeline(action);
}
window.handleHITL = handleHITL;

async function executeRestOfPipeline(hitl_action) {
    const typing = document.querySelector(".typing-msg");
    
    try {
        const res = await fetch("/api/agent/execute", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                state: pendingAgentState,
                hitl_action: hitl_action
            })
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        
        const finalState = data.state;
        
        if (typing) typing.remove();

        // Render Answer
        let htmlAns = finalState.final_answer.replace(/\n/g, "<br>");
        if (finalState.sources && finalState.sources.length > 0) {
            htmlAns += `<br><br><div style="font-size: 0.9em; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.1)">Sources: ${formatSources(finalState.sources)}</div>`;
        }
        renderMessage(htmlAns, "agent", true);

        // Update Timeline
        if (hitl_action !== "deny") {
            appendToTimeline("worker", "Retrieval Worker", `Retrieved ${finalState.retrieved_chunks.length} chunks from Vector DB.`);
            
            if (finalState.supervisor_route === "policy_tool_worker") {
                let toolBadge = finalState.mcp_tool_called && finalState.mcp_tool_called.length > 0 ? 
                    `<span class="badge-tag" style="background: rgba(0,255,204,0.1); border: 1px solid #00ffcc; color: #00ffcc">${finalState.mcp_tool_called[0]}</span>` : "";
                appendToTimeline("worker", "Policy Tool Worker", `Evaluated policy logic.`, toolBadge);
            }
            
            appendToTimeline("synthesis", "Synthesis Node", `Generated grounded answer. Confidence: ${finalState.confidence.toFixed(2)}`);
        }
        
        document.getElementById("trace-latency").textContent = `${finalState.latency_ms}ms`;

    } catch (error) {
        if (typing) typing.remove();
        renderMessage(`❌ Execution Error: ${error.message}`, "agent");
    } finally {
        document.getElementById("send-btn").disabled = false;
        pendingAgentState = null;
    }
}

// ============== TRACES ==============
async function loadTraces() {
    const c = document.getElementById("trace-list-container");
    c.innerHTML = "<p>Refreshing...</p>";
    try {
        const res = await fetch("/api/traces");
        const data = await res.json();
        
        if (data.traces.length === 0) {
            c.innerHTML = "<p class='text-muted'>No traces found.</p>";
            return;
        }

        let h = "";
        data.traces.forEach(t => {
            const hitlBadge = t.hitl ? `<span style="color:#ff4757">●</span> HITL` : "";
            h += `
            <div class="trace-item" onclick="viewTrace('${t.id}', this)">
                <div class="trace-item-header">
                    <span class="trace-item-id">${t.timestamp}</span>
                    <span class="badge-tag">${t.route}</span>
                </div>
                <div class="trace-item-task">${escapeHtml(t.task)}</div>
                <div class="trace-item-meta">
                    <span>${t.latency}ms</span>
                    <span>${hitlBadge}</span>
                </div>
            </div>`;
        });
        c.innerHTML = h;

        // Auto select first
        if (data.traces.length > 0) {
            setTimeout(() => {
                const first = c.querySelector(".trace-item");
                if (first) first.click();
            }, 100);
        }

    } catch(e) {
        c.innerHTML = `<p style="color:var(--danger)">Error loading traces.</p>`;
    }
}
window.loadTraces = loadTraces;

async function viewTrace(id, element) {
    document.querySelectorAll(".trace-item").forEach(i => i.classList.remove("active"));
    if (element) element.classList.add("active");

    const codeBlock = document.getElementById("trace-json-view");
    document.getElementById("detail-trace-id").textContent = id;
    codeBlock.textContent = "Loading trace data...";

    try {
        const res = await fetch(`/api/traces/${id}`);
        const data = await res.json();
        codeBlock.textContent = JSON.stringify(data, null, 2);
        if (window.hljs) hljs.highlightElement(codeBlock);
    } catch(e) {
        codeBlock.textContent = `Error loading trace ${id}`;
    }
}
window.viewTrace = viewTrace;
