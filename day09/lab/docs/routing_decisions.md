# Routing Decisions Log — Lab Day 09

**Tên nhóm:** 2A202600502-Trương Hầu Minh Kiệt, 2A202600503-Võ Thành Danh
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| Võ Thành Danh | Supervisor Owner | ___ |
| Võ Thành Danh | Worker Owner | ___ |
| Trương Hầu Minh Kiệt | MCP Owner | ___ |
| Trương Hầu Minh Kiệt | Trace & Docs Owner | ___ |
**Ngày:** 2026-04-14

Các quyết định dưới đây được trích từ trace thật trong `artifacts/traces/`, không phải giả định.

---

## Routing Decision #1

**Task đầu vào:**
`SLA xử lý ticket P1 là bao lâu?`

**Worker được chọn:** `retrieval_worker`
**Route reason (từ trace):** `SLA/incident/HR keyword detected: 'p1'`
**MCP tools được gọi:** `[]`
**Workers called sequence:** `retrieval_worker -> synthesis_worker`

**Kết quả thực tế:**
- `final_answer`: trả ra đúng SLA P1 gồm `15 phút first response`, `4 giờ resolution`, `10 phút escalation`
- `confidence`: `1.0`
- Correct routing? `Yes`

**Nhận xét:**
Đây là route đúng nhất và sạch nhất trong trace. Supervisor không cần gọi policy worker vì câu hỏi chỉ hỏi fact từ SLA. Trace tham chiếu: `run_20260414_120127.json`.

---

## Routing Decision #2

**Task đầu vào:**
`Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?`

**Worker được chọn:** `policy_tool_worker`
**Route reason (từ trace):** `policy/access keyword detected: 'hoàn tiền'`
**MCP tools được gọi:** `[]` trong trace `run_20260414_120148.json`
**Workers called sequence:** `retrieval_worker -> policy_tool_worker -> synthesis_worker`

**Kết quả thực tế:**
- `final_answer`: kết luận không được hoàn tiền vì Flash Sale là exception
- `confidence`: `1.0`
- Correct routing? `Yes`

**Nhận xét:**
Route này đúng vì supervisor ưu tiên policy questions sang policy worker thay vì để retrieval trả lời trực tiếp. Trace cho thấy `policy_result.exceptions_found` đã phát hiện `flash_sale_exception`, nên synthesis có đủ basis để kết luận.

---

## Routing Decision #3

**Task đầu vào:**
`Cần cấp quyền Level 3 để khắc phục P1 khẩn cấp. Quy trình là gì?`

**Worker được chọn:** `policy_tool_worker`
**Route reason (từ trace):** `policy/access keyword detected: 'level 3' | risk_high flagged: 'khẩn cấp'`
**MCP tools được gọi:** `get_ticket_info` trong trace `run_20260414_120158.json`
**Workers called sequence:** `retrieval_worker -> policy_tool_worker -> synthesis_worker`

**Kết quả thực tế:**
- `final_answer`: nêu quy trình cấp quyền tạm thời và thông tin liên quan P1
- `confidence`: `1.0`
- Correct routing? `Yes`

**Nhận xét:**
Supervisor đã route đúng vì đây là câu hỏi access control có risk cao. Trace còn ghi MCP tool call thật, nên rất dễ debug. Tuy nhiên nội dung answer vẫn cần siết lại ở policy layer để phân biệt rõ trường hợp `Level 3` không được emergency bypass. Đây là ví dụ điển hình của “route đúng nhưng domain reasoning chưa đủ chặt”.

---

## Routing Decision #4

**Task đầu vào:**
`Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?`

**Worker được chọn:** `policy_tool_worker`
**Route reason:** `policy/access keyword detected: 'hoàn tiền'`

**Nhận xét: Đây là trường hợp routing khó hơn ở run mới (`run_20260414_144627.json`)**
Retrieval local trả về `0 chunks`, nhưng policy worker vẫn gọi MCP `search_kb` và dùng rule-based exception để trả lời. Điều này cho thấy routing đúng chưa đủ; trace cần thêm cả `mcp_tools_used` để biết answer được cứu bởi tool hay bởi policy rule.

---

## Tổng kết

### Routing Distribution

| Worker | Số câu được route | % tổng |
|--------|------------------|--------|
| `retrieval_worker` | `8` | `53%` |
| `policy_tool_worker` | `7` | `46%` |
| `human_review` | `0` | `0%` |

### Routing Accuracy

- Câu route đúng: `14 / 15` trên batch test mới nhất chạy bằng `python eval_trace.py`
- Câu route sai (đã sửa bằng cách nào?): `1`
- Câu trigger HITL: `1`

Route sai đáng chú ý nhất là câu `Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?`. Theo `test_questions.json`, câu này expected route là `retrieval_worker`, nhưng supervisor hiện rule-based nên đẩy sang `policy_tool_worker` vì match keyword `hoàn tiền`. Đây là một sai số routing do luật quá rộng, không phải do worker crash.

### Lesson Learned về Routing

1. Rule-based keyword routing đủ tốt cho lab này vì domain nhỏ, trace dễ đọc và không phụ thuộc thêm một LLM classifier nữa.
2. `route_reason` nên gắn trực tiếp keyword match cụ thể như `'p1'`, `'hoàn tiền'`, `'level 3'` để khi debug có thể suy ngược đúng rule đã bắn.

### Route Reason Quality

`route_reason` hiện tại đủ dùng để debug supervisor, vì nó cho biết keyword nào kích hoạt route và có gắn `risk_high` hay không. Điểm cần cải tiến là thêm explicit note kiểu `needs_tool=True because access workflow may require MCP`, để nhìn trace là biết luôn vì sao policy worker sẽ gọi tool.
