# System Architecture — Lab Day 09

**Nhóm:** 2A202600502-TruongHauMinhKiet-Day09  
**Ngày:** 2026-04-14  
**Version:** 1.1

---

## 1. Tổng quan kiến trúc

Hệ thống của nhóm dùng pattern `Supervisor-Worker` với một shared state đi xuyên toàn pipeline. `Supervisor` trong [graph.py](<D:\AIThucChien\Day-09-Lab\2A202600502-TruongHauMinhKiet-Day09\day09\lab\graph.py>) chỉ làm nhiệm vụ phân loại câu hỏi, bật cờ `needs_tool`, `risk_high`, rồi route sang worker phù hợp. Phần domain knowledge được tách ra cho từng worker: `retrieval_worker` lấy evidence từ ChromaDB, `policy_tool_worker` xử lý ngoại lệ policy và gọi MCP tools, `synthesis_worker` tổng hợp câu trả lời grounded kèm confidence.

Nhóm chọn pattern này thay vì single agent vì Day 08 là một pipeline monolithic: khi trả lời sai rất khó biết lỗi đến từ retrieval, policy check hay generation. Sang Day 09, trace ghi rõ `supervisor_route`, `route_reason`, `workers_called`, `mcp_tools_used`, nên việc debug tách được theo từng lớp.

---

## 2. Sơ đồ Pipeline

```
User Request
     |
     v
+------------------+
| Supervisor       |
| - route_reason   |
| - needs_tool     |
| - risk_high      |
+--------+---------+
         |
         v
   route_decision
         |
   +-----+---------------------------+
   |                                 |
   v                                 v
retrieval_worker             human_review (placeholder)
   |                                 |
   +-------------+-------------------+
                 |
                 v
        policy_tool_worker
        - analyze policy
        - call MCP tools
                 |
                 v
          synthesis_worker
          - grounded answer
          - sources
          - confidence
                 |
                 v
               Output
```

---

## 3. Vai trò từng thành phần

### Supervisor (`graph.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Phân loại task và quyết định luồng xử lý |
| **Input** | `task` từ user |
| **Output** | `supervisor_route`, `route_reason`, `risk_high`, `needs_tool` |
| **Routing logic** | Rule-based keyword routing: refund/access sang `policy_tool_worker`, SLA/incident/HR sang `retrieval_worker`, mã lỗi lạ sang `human_review` |
| **HITL condition** | `risk_high=True` hoặc mã lỗi lạ không có context rõ |

### Retrieval Worker (`workers/retrieval.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Embed query, query ChromaDB, trả về chunks và nguồn |
| **Embedding model** | `all-MiniLM-L6-v2`, fallback `text-embedding-3-small` nếu cần |
| **Top-k** | Mặc định `3`, trong graph đang override `7` để giữ được chunk SLA P1 |
| **Stateless?** | Yes |

### Policy Tool Worker (`workers/policy_tool.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Kiểm tra policy, phát hiện exception, gọi MCP khi cần |
| **MCP tools gọi** | `search_kb`, `get_ticket_info` |
| **Exception cases xử lý** | `flash_sale_exception`, `digital_product_exception`, `activated_exception`, note temporal scoping cho đơn trước `01/02/2026` |

### Synthesis Worker (`workers/synthesis.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **LLM model** | `gpt-4o-mini`, fallback Gemini nếu có key phù hợp |
| **Temperature** | `0.1` |
| **Grounding strategy** | Prompt ép trả lời chỉ từ context, có citation và phải abstain nếu thiếu evidence |
| **Abstain condition** | Không có chunks hoặc context không đủ |

### MCP Server (`mcp_server.py`)

| Tool | Input | Output |
|------|-------|--------|
| `search_kb` | `query`, `top_k` | `chunks`, `sources`, `total_found` |
| `get_ticket_info` | `ticket_id` | ticket details, notifications, SLA deadline |
| `check_access_permission` | `access_level`, `requester_role`, `is_emergency` | `can_grant`, `required_approvers`, `emergency_override`, `notes` |
| `create_ticket` | `priority`, `title`, `description` | `ticket_id`, `url`, `created_at` |

---

## 4. Shared State Schema

| Field | Type | Mô tả | Ai đọc/ghi |
|-------|------|-------|-----------|
| `task` | `str` | Câu hỏi đầu vào | supervisor đọc |
| `supervisor_route` | `str` | Worker được chọn | supervisor ghi |
| `route_reason` | `str` | Lý do route | supervisor ghi |
| `risk_high` | `bool` | Cờ câu hỏi nhạy cảm/khẩn cấp | supervisor ghi |
| `needs_tool` | `bool` | Có cần gọi MCP hay không | supervisor ghi |
| `retrieved_chunks` | `list` | Evidence từ retrieval | retrieval ghi, synthesis/policy đọc |
| `retrieved_sources` | `list` | Danh sách nguồn retrieve được | retrieval ghi, synthesis đọc |
| `policy_result` | `dict` | Kết quả policy check | policy ghi, synthesis đọc |
| `mcp_tools_used` | `list` | Toàn bộ MCP call với input/output | policy ghi |
| `mcp_tool_called` | `list` | Alias explicit cho tên tool đã gọi | policy ghi |
| `mcp_result` | `list` | Alias explicit cho raw tool outputs | policy ghi |
| `final_answer` | `str` | Câu trả lời cuối | synthesis ghi |
| `confidence` | `float` | Độ tin cậy | synthesis ghi |
| `workers_called` | `list` | Chuỗi worker đã chạy | graph/workers ghi |
| `history` | `list` | Trace ngắn từng bước | supervisor/workers ghi |
| `latency_ms` | `int` | Tổng thời gian xử lý | graph ghi |

---

## 5. Lý do chọn Supervisor-Worker so với Single Agent (Day 08)

| Tiêu chí | Single Agent (Day 08) | Supervisor-Worker (Day 09) |
|----------|----------------------|--------------------------|
| Debug khi sai | Khó, vì pipeline là một khối | Dễ hơn, có trace theo bước và worker độc lập |
| Thêm capability mới | Phải sửa prompt/pipeline chính | Thêm MCP tool hoặc worker riêng |
| Routing visibility | `0/10` traces có route info | `15/15` trace của batch Sprint 4 có `supervisor_route` + `route_reason` |
| Tool usage | `0/10` | `2/15` trace của batch Sprint 4 có MCP tool call |

Quan sát thực tế từ repo hiện tại: truy vấn `Flash Sale` và `Level 3 + P1 khẩn cấp` đều được route đúng sang `policy_tool_worker`, trong khi truy vấn `SLA ticket P1` đi thẳng sang `retrieval_worker`. Điều này giúp đọc trace xong là biết lỗi nằm ở route hay ở retrieval.

---

## 6. Giới hạn và điểm cần cải tiến

1. `policy_tool_worker` hiện vẫn còn rule-based nhiều, nên các case access phức tạp như `Level 3 + emergency` có thể route đúng nhưng synthesis chưa kết luận đủ chặt.
2. Các trace mới nhất cho thấy local Chroma collection có lúc trống. Nhóm đã vá `retrieval_worker` để bootstrap index từ `data/docs`, nhưng vẫn nên chạy lại full eval sau khi build sạch.
3. `human_review` mới là placeholder, chưa có cơ chế pause/interrupt thật.
