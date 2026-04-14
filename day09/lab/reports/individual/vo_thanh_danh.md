# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

- **Họ và tên:** Võ Thành Danh (2A202600503)
- **Vai trò trong nhóm:** Supervisor Owner (Sprint 1) + Worker Owner (Sprint 2)
- **Ngày nộp:** 2026-04-14


---

## 1. Tôi phụ trách phần nào?

**Module/file tôi chịu trách nhiệm:**
- Sprint 1: `graph.py` — `AgentState` (17 fields), `supervisor_node`, `route_decision`, `human_review_node`, `build_graph`, `run_graph`, `save_trace`
- Sprint 2: `workers/retrieval.py` — `retrieve_dense`, `_get_embedding_fn`, `_get_collection`, `_bootstrap_collection_if_empty`, `_chunk_document`, `run`; `workers/policy_tool.py` — `analyze_policy`, `_call_mcp_tool`, `run`; `workers/synthesis.py` — `synthesize`, `_call_llm`, `_build_context`, `_estimate_confidence`, `_judge_confidence`, `run`; `contracts/worker_contracts.yaml` — toàn bộ contract cho supervisor, 3 workers và MCP server

**Cách công việc của tôi kết nối với phần của thành viên khác:**

Kiệt phụ trách MCP Server (`mcp_server.py`) và Trace & Docs. Tôi gọi MCP tools của Kiệt qua `dispatch_tool()` trong `policy_tool.py`, và pipeline của tôi sinh ra trace JSON để Kiệt dùng cho `eval_trace.py` và viết docs.

**Bằng chứng (commit hash):**

- `f23fadd` — `feat(sprint1): expand supervisor routing with full keyword set and risk_high detection`
- `faa5f16` — `feat(sprint1+2): wire real workers into graph, retrieval always runs first`
- `139a586` — `feat(sprint2): add LLM-as-Judge confidence to synthesis worker (bonus +1)`
- `cf500e9` — `docs(sprint2): update worker contracts status to done`
- `29b4faa` — `test(sprint1+2): end-to-end verification complete`

---

## 2. Tôi đã ra một quyết định kỹ thuật gì?

**Quyết định:** Dùng keyword-based routing trong `supervisor_node` thay vì gọi LLM để classify task.

Tôi chia keywords thành 3 nhóm trong `graph.py` dòng 93–112:
- `policy_keywords`: `["hoàn tiền", "refund", "flash sale", "license", "cấp quyền", "access level", ...]`
- `retrieval_explicit`: `["sla", "escalation", "ticket", "sự cố", "on-call", ...]`
- `risk_keywords`: `["khẩn cấp", "emergency", "urgent", ...]`

**Lý do:**

Có hai lựa chọn: (A) gọi thêm 1 LLM call để classify, hoặc (B) dùng keyword matching. Tôi chọn (B) vì domain lab chỉ có 5 tài liệu với các topic rõ ràng (SLA, refund, access control, HR, FAQ). Keyword matching không tốn thêm latency và API cost, đồng thời `route_reason` trả về chính xác keyword nào đã match, giúp debug nhanh hơn.

**Trade-off đã chấp nhận:**

Keyword routing không xử lý tốt câu hỏi ambiguous — ví dụ câu `"Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?"` bị match keyword `"hoàn tiền"` nên route sang `policy_tool_worker`, trong khi expected route là `retrieval_worker`. Kết quả: 10/10 routing test cases trong `test_sprint12.py` pass.

**Bằng chứng từ trace/code:**

```json
// Trace: run_20260414_153143.json — câu SLA P1
{
  "task": "SLA xử lý ticket P1 là bao lâu?",
  "supervisor_route": "retrieval_worker",
  "route_reason": "SLA/incident/HR keyword detected: 'p1'",
  "latency_ms": 16078,
  "confidence": 1.0
}

// Trace: run_20260414_152839.json — câu Level 3 khẩn cấp (multi-hop + risk_high)
{
  "task": "Cần cấp quyền Level 3 để khắc phục P1 khẩn cấp. Quy trình là gì?",
  "supervisor_route": "policy_tool_worker",
  "route_reason": "policy/access keyword detected: 'level 3' | risk_high flagged: 'khẩn cấp'",
  "risk_high": true,
  "mcp_tools_used": [{"tool": "get_ticket_info", "input": {"ticket_id": "P1-LATEST"}}],
  "latency_ms": 9158,
  "confidence": 1.0
}
```

---

## 3. Tôi đã sửa một lỗi gì?

**Lỗi:** Câu hỏi SLA P1 bị synthesis abstain dù route đúng — retrieval trả về chunk P2, P3, P4 nhưng thiếu chunk P1.

**Symptom (pipeline làm gì sai?):**

Khi hỏi `"SLA xử lý ticket P1 là bao lâu?"`, supervisor route đúng sang `retrieval_worker`, nhưng `final_answer` trả về `"Không đủ thông tin trong tài liệu nội bộ"` và `confidence: 0.3`. Pipeline abstain sai vì P1 SLA nằm rõ trong tài liệu `sla_p1_2026.txt`.

**Root cause (lỗi nằm ở đâu?):**

Lỗi nằm ở retrieval layer. Chunk chứa thông tin P1 (`"15 phút first response, 4 giờ resolution"`) xếp hạng cosine similarity thứ 7 (score `0.5549`). Với `top_k=3` mặc định, chunk này không bao giờ được retrieve, nên synthesis không có evidence về P1 → abstain.

**Cách sửa:**

Tôi tăng `top_k` lên 7 cho tất cả queries trong `graph.py` dòng 205:
```python
# Commit: 0d7b943
# graph.py — retrieval_worker_node()
state["retrieval_top_k"] = 7  # P1 SLA chunk ranks 7th; lower values cause abstain
```

**Bằng chứng trước/sau:**

| Metric | Trước sửa (`top_k=3`) | Sau sửa (`top_k=7`) |
|--------|----------------------|---------------------|
| Chunk P1 retrieved? | ✗ Không (rank 7, bị cắt) | ✓ Có (rank 7, nằm trong top_k) |
| `final_answer` | "Không đủ thông tin" | SLA P1: 15 phút first response, 4 giờ resolution |
| `confidence` | `0.3` | `1.0` |
| Commit | — | `0d7b943` |

Trace sau sửa: `run_20260414_153143.json` cho thấy 7 chunks được retrieve, chunk P1 ở vị trí thứ 7 với score `0.5549`, và synthesis trả lời đúng.

---

## 4. Tôi tự đánh giá đóng góp của mình

**Tôi làm tốt nhất ở điểm nào?**

Thiết kế luồng orchestration trong `graph.py` để retrieval luôn chạy trước policy (dòng 242), đảm bảo policy worker luôn có context. Commit chain từ `f23fadd` đến `29b4faa` (10 commits) cho thấy tôi iterate liên tục: mở rộng routing keywords, sửa word-boundary regex cho `p1`, tăng `top_k`, thêm LLM-as-Judge.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

`analyze_policy()` trong `policy_tool.py` vẫn là rule-based, chưa dùng LLM để phân tích policy phức tạp. Câu hỏi liên quan đơn hàng trước `01/02/2026` (temporal scoping) mới chỉ flag `policy_version_note` chứ chưa handle logic thật.

**Nhóm phụ thuộc vào tôi ở đâu?**

Toàn bộ pipeline chạy qua `graph.py` — nếu tôi chưa xong Sprint 1, Kiệt không có trace JSON nào để viết docs và eval. Tương tự, 3 workers là input cho synthesis, nếu worker thiếu thì pipeline không chạy được end-to-end.

**Phần tôi phụ thuộc vào thành viên khác:**

Tôi cần `mcp_server.py` từ Kiệt để `_call_mcp_tool()` trong `policy_tool.py` gọi được `dispatch_tool()`. Nếu MCP server chưa implement, policy worker vẫn chạy nhưng mất khả năng gọi tool (trace sẽ không có `mcp_tools_used`).

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

Tôi sẽ thay `analyze_policy()` trong `policy_tool.py` bằng một LLM call để phân tích policy thay vì rule-based. Lý do: trace `run_20260414_152839.json` cho thấy câu Level 3 khẩn cấp route đúng và MCP gọi đúng, nhưng `policy_result.policy_name` vẫn trả về `"refund_policy_v4"` thay vì `"access_control_sop"` — vì logic rule-based chỉ check refund exceptions, không phân biệt được domain access control. Một LLM classifier ở policy layer sẽ fix chính xác vấn đề này.

---


