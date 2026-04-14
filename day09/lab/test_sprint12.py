"""
test_sprint12.py — Kiểm tra Sprint 1 + Sprint 2
Chạy: python test_sprint12.py
"""
import sys
import json
import glob

sys.stdout.reconfigure(encoding="utf-8")

PASS = "✅"
FAIL = "❌"
results = []


def check(label, condition, detail=""):
    status = PASS if condition else FAIL
    msg = f"  {status} {label}"
    if detail:
        msg += f"\n       {detail}"
    print(msg)
    results.append(condition)
    return condition


# ─────────────────────────────────────────────
# 1. ChromaDB Index
# ─────────────────────────────────────────────
print("\n── ChromaDB Index ──────────────────────────────")
try:
    import chromadb
    from sentence_transformers import SentenceTransformer

    client = chromadb.PersistentClient(path="./chroma_db")
    col = client.get_collection("day09_docs")
    count = col.count()
    check("Collection 'day09_docs' exists", True)
    check(f"Chunk count >= 50", count >= 50, f"count = {count}")

    model = SentenceTransformer("all-MiniLM-L6-v2")
    emb = model.encode(["SLA ticket P1"])[0].tolist()
    r = col.query(query_embeddings=[emb], n_results=3, include=["metadatas"])
    sources = [m["source"] for m in r["metadatas"][0]]
    check("Query 'SLA P1' returns sla_p1_2026.txt chunks",
          any("sla_p1_2026" in s for s in sources), f"sources = {sources}")
except Exception as e:
    check("ChromaDB index accessible", False, str(e))


# ─────────────────────────────────────────────
# 2. Retrieval Worker
# ─────────────────────────────────────────────
print("\n── Retrieval Worker ────────────────────────────")
try:
    from workers.retrieval import run as retrieval_run

    for query, expected_src in [
        ("SLA ticket P1 là bao lâu?", "sla_p1_2026.txt"),
        ("Điều kiện được hoàn tiền là gì?", "policy_refund_v4.txt"),
        ("Ai phê duyệt cấp quyền Level 3?", "access_control_sop.txt"),
    ]:
        result = retrieval_run({"task": query})
        chunks = result.get("retrieved_chunks", [])
        sources = result.get("retrieved_sources", [])
        check(f"'{query[:40]}' retrieves {expected_src}",
              any(expected_src in s for s in sources),
              f"got sources: {sources}")
except Exception as e:
    check("Retrieval worker runs", False, str(e))


# ─────────────────────────────────────────────
# 3. Policy Worker
# ─────────────────────────────────────────────
print("\n── Policy Worker ───────────────────────────────")
try:
    from workers.policy_tool import run as policy_run

    # Flash Sale → exception
    r1 = policy_run({
        "task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi",
        "retrieved_chunks": [{"text": "Đơn hàng Flash Sale không được hoàn tiền.", "source": "policy_refund_v4.txt", "score": 0.9}],
        "needs_tool": False,
    })
    pr = r1.get("policy_result", {})
    check("Flash Sale → policy_applies=False", pr.get("policy_applies") is False)
    check("Flash Sale → flash_sale_exception detected",
          any(e.get("type") == "flash_sale_exception" for e in pr.get("exceptions_found", [])))

    # Normal refund → allowed
    r2 = policy_run({
        "task": "Khách hàng yêu cầu hoàn tiền trong 5 ngày, sản phẩm lỗi, chưa kích hoạt",
        "retrieved_chunks": [{"text": "Yêu cầu trong 7 ngày, sản phẩm lỗi nhà sản xuất, chưa dùng.", "source": "policy_refund_v4.txt", "score": 0.85}],
        "needs_tool": False,
    })
    check("Normal refund → policy_applies=True",
          r2.get("policy_result", {}).get("policy_applies") is True)
except Exception as e:
    check("Policy worker runs", False, str(e))


# ─────────────────────────────────────────────
# 4. Routing Logic
# ─────────────────────────────────────────────
print("\n── Routing Logic (10 grading questions) ────────")
try:
    from graph import supervisor_node, make_initial_state

    routing_tests = [
        ("Ticket P1 lúc 22:47 ai nhận thông báo", "retrieval_worker"),
        ("Đơn 31/01/2026 yêu cầu hoàn tiền 07/02/2026", "policy_tool_worker"),
        ("Level 3 access emergency bao nhiêu người phê duyệt", "policy_tool_worker"),
        ("Store credit bằng bao nhiêu phần trăm", "policy_tool_worker"),
        ("P1 không phản hồi sau 10 phút hệ thống làm gì", "retrieval_worker"),
        ("Nhân viên thử việc muốn làm remote", "retrieval_worker"),
        ("Mức phạt tài chính vi phạm SLA P1", "retrieval_worker"),
        ("Mật khẩu đổi mấy ngày", "retrieval_worker"),
        ("P1 lúc 2am cần cấp Level 2 access tạm thời cho contractor", "policy_tool_worker"),
        ("Flash Sale lỗi nhà sản xuất 7 ngày hoàn tiền", "policy_tool_worker"),
    ]
    for task, expected in routing_tests:
        s = make_initial_state(task)
        s = supervisor_node(s)
        route = s["supervisor_route"]
        reason = s["route_reason"]
        check(f"{task[:50]}",
              route == expected and reason not in ("", "unknown"),
              f"route={route} | reason={reason[:60]}")
except Exception as e:
    check("Routing logic runs", False, str(e))


# ─────────────────────────────────────────────
# 5. End-to-End graph.py (2 queries)
# ─────────────────────────────────────────────
print("\n── End-to-End Pipeline ─────────────────────────")
try:
    from graph import run_graph, save_trace

    # Query 1: SLA/P1 → retrieval_worker
    r1 = run_graph("SLA xử lý ticket P1 là bao lâu?")
    check("Q1 routes to retrieval_worker", r1["supervisor_route"] == "retrieval_worker",
          f"got: {r1['supervisor_route']}")
    check("Q1 workers_called has 2 entries", len(r1["workers_called"]) >= 2,
          f"workers: {r1['workers_called']}")
    check("Q1 answer not placeholder", "[PLACEHOLDER]" not in r1["final_answer"])
    check("Q1 mentions '15 phút' or '4 giờ'",
          "15 phút" in r1["final_answer"] or "4 giờ" in r1["final_answer"] or "15" in r1["final_answer"],
          f"answer: {r1['final_answer'][:100]}")

    # Query 2: Flash Sale → policy_tool_worker, 3 workers
    r2 = run_graph("Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?")
    check("Q2 routes to policy_tool_worker", r2["supervisor_route"] == "policy_tool_worker",
          f"got: {r2['supervisor_route']}")
    check("Q2 workers_called has 3 entries", len(r2["workers_called"]) >= 3,
          f"workers: {r2['workers_called']}")
    check("Q2 answer mentions Flash Sale / hoàn tiền",
          any(kw in r2["final_answer"].lower() for kw in ["flash sale", "hoàn tiền", "không được"]),
          f"answer: {r2['final_answer'][:100]}")
    check("Q2 confidence is real float (not 0.0)",
          isinstance(r2["confidence"], float) and r2["confidence"] > 0,
          f"confidence: {r2['confidence']}")

    save_trace(r1)
    save_trace(r2)

except Exception as e:
    check("Pipeline runs end-to-end", False, str(e))


# ─────────────────────────────────────────────
# 6. Trace Fields
# ─────────────────────────────────────────────
print("\n── Trace Fields ────────────────────────────────")
required_fields = [
    "run_id", "task", "supervisor_route", "route_reason",
    "workers_called", "mcp_tools_used", "retrieved_sources",
    "final_answer", "confidence", "hitl_triggered", "latency_ms",
]
try:
    traces = sorted(glob.glob("./artifacts/traces/*.json"))
    check("Trace files exist", len(traces) > 0, f"found {len(traces)} files")
    if traces:
        with open(traces[-1], encoding="utf-8") as f:
            t = json.load(f)
        missing = [f for f in required_fields if f not in t]
        check("All required trace fields present", len(missing) == 0,
              f"missing: {missing}" if missing else "")
        check("route_reason is non-empty string",
              bool(t.get("route_reason")) and t["route_reason"] not in ("", "unknown"))
        check("workers_called has >= 2 entries", len(t.get("workers_called", [])) >= 2,
              f"workers: {t.get('workers_called')}")
except Exception as e:
    check("Trace files readable", False, str(e))


# ─────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────
passed = sum(results)
total = len(results)
print(f"\n{'='*50}")
print(f"  {passed}/{total} checks passed")
if passed == total:
    print("  🎉 Sprint 1 + Sprint 2 READY")
else:
    print(f"  ⚠️  {total - passed} check(s) failed — xem chi tiết ở trên")
print("="*50)
