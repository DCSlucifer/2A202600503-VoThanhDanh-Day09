import os
import json
import traceback
import sys
import io
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify

# Fix Windows encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

app = Flask(__name__, static_folder="static", template_folder="templates")

# Import logic from Day 09 Day 09 Graph
from graph import (
    make_initial_state, supervisor_node, human_review_node,
    retrieval_worker_node, policy_tool_worker_node, synthesis_worker_node,
    save_trace
)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/agent/analyze", methods=["POST"])
def agent_analyze():
    """Run just the supervisor node to determine if HITL is required."""
    data = request.json
    query = data.get("query", "")
    
    state = make_initial_state(query)
    # Start timer explicitly by storing it since state doesn't have start_time
    state["_start_time"] = time.time()
    
    try:
        # 1. Supervisor decides route
        state = supervisor_node(state)
        
        hitl_required = (state.get("supervisor_route") == "human_review")
        return jsonify({
            "hitl_required": hitl_required,
            "state": state
        })
    except Exception as e:
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

@app.route("/api/agent/execute", methods=["POST"])
def agent_execute():
    """Run the rest of the pipeline after optional HITL."""
    data = request.json
    state = data.get("state")
    hitl_action = data.get("hitl_action")  # 'approve' or 'deny' or None
    
    start_time = state.pop("_start_time", time.time())

    try:
        # 2. Human Review interrupt
        if state.get("supervisor_route") == "human_review":
            if hitl_action == "deny":
                state["final_answer"] = "🚫 Hành động đã bị từ chối bởi Human-in-the-loop (Người kiểm duyệt)."
                state["latency_ms"] = int((time.time() - start_time) * 1000)
                save_trace(state)
                return jsonify({"state": state})
            else:
                # Approve
                state = human_review_node(state)
        
        # 3. Retrieval ALWAYS runs first
        state = retrieval_worker_node(state)
        
        # 4. Policy Tool Worker (if routed)
        if state.get("supervisor_route") == "policy_tool_worker":
            state = policy_tool_worker_node(state)
            
        # 5. Synthesis ALWAYS runs last
        state = synthesis_worker_node(state)
        
        state["latency_ms"] = int((time.time() - start_time) * 1000)
        state["history"].append(f"[graph] completed in {state['latency_ms']}ms")
        
        save_trace(state)
        
        return jsonify({"state": state})
    except Exception as e:
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/api/traces", methods=["GET"])
def list_traces():
    traces = []
    traces_dir = "artifacts/traces"
    os.makedirs(traces_dir, exist_ok=True)
    
    try:
        for f in sorted(os.listdir(traces_dir), reverse=True):
            if f.endswith(".json"):
                with open(os.path.join(traces_dir, f), "r", encoding="utf-8") as file:
                    trace = json.load(file)
                    traces.append({
                        "id": f,
                        "timestamp": f.replace("run_", "").replace(".json", ""),
                        "task": trace.get("task", ""),
                        "route": trace.get("supervisor_route", ""),
                        "latency": trace.get("latency_ms", 0),
                        "hitl": trace.get("hitl_triggered", False)
                    })
        return jsonify({"traces": traces})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/traces/<trace_id>", methods=["GET"])
def get_trace(trace_id):
    try:
        with open(f"artifacts/traces/{trace_id}", "r", encoding="utf-8") as file:
            return jsonify(json.load(file))
    except Exception as e:
        return jsonify({"error": str(e)}), 404

if __name__ == "__main__":
    print("=" * 60)
    print("  Day 09 Multi-Agent UI — http://localhost:5001")
    print("=" * 60)
    app.run(debug=True, port=5001, host="0.0.0.0")
