# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** 2A202600502-Trương Hầu Minh Kiệt, 2A202600503-Võ Thành Danh
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| Võ Thành Danh | Supervisor Owner | ___ |
| Võ Thành Danh | Worker Owner | ___ |
| Trương Hầu Minh Kiệt | MCP Owner | ___ |
| Trương Hầu Minh Kiệt | Trace & Docs Owner | ___ |

**Ngày nộp:** 2026-04-14  
**Repo:** `day09/lab`  
**Độ dài khuyến nghị:** 600–1000 từ

---

> **Hướng dẫn nộp group report:**
> 
> - File này nộp tại: `reports/group_report.md`
> - Deadline: Được phép commit **sau 18:00** (xem SCORING.md)
> - Tập trung vào **quyết định kỹ thuật cấp nhóm** — không trùng lặp với individual reports
> - Phải có **bằng chứng từ code/trace** — không mô tả chung chung
> - Mỗi mục phải có ít nhất 1 ví dụ cụ thể từ code hoặc trace thực tế của nhóm

---

## 1. Kiến trúc nhóm đã xây dựng (150–200 từ)

> Mô tả ngắn gọn hệ thống nhóm: bao nhiêu workers, routing logic hoạt động thế nào,
> MCP tools nào được tích hợp. Dùng kết quả từ `docs/system_architecture.md`.

**Hệ thống tổng quan:**

Nhóm xây dựng một hệ thống `Supervisor-Worker` gồm 3 workers chính: `retrieval_worker`, `policy_tool_worker`, và `synthesis_worker`. Supervisor trong `graph.py` chỉ chịu trách nhiệm đọc câu hỏi đầu vào, xác định loại task, bật cờ `needs_tool` hoặc `risk_high`, sau đó route sang worker phù hợp. Retrieval worker lấy evidence từ ChromaDB, policy worker kiểm tra exception cases như `Flash Sale`, `digital product`, đồng thời gọi MCP tools khi cần, còn synthesis worker tạo câu trả lời grounded từ evidence và policy result. Trace được ghi xuyên suốt ở shared state với các field như `supervisor_route`, `route_reason`, `workers_called`, `mcp_tools_used`, `confidence`, và `latency_ms`.

**Routing logic cốt lõi:**
> Mô tả logic supervisor dùng để quyết định route (keyword matching, LLM classifier, rule-based, v.v.)

Nhóm dùng `rule-based keyword routing` thay vì thêm một LLM classifier nữa. Các câu chứa `hoàn tiền`, `refund`, `flash sale`, `access level`, `level 2`, `level 3` được ưu tiên route sang `policy_tool_worker`. Các câu chứa `P1`, `SLA`, `ticket`, `escalation`, `remote`, `mật khẩu` được route sang `retrieval_worker`. Các mã lỗi không rõ ngữ cảnh như `ERR-403-AUTH` sẽ đi qua nhánh `human_review` placeholder rồi quay về retrieval. Cách làm này giúp route_reason rất dễ đọc từ trace và debug nhanh hơn.

**MCP tools đã tích hợp:**
> Liệt kê tools đã implement và 1 ví dụ trace có gọi MCP tool.

- `search_kb`: dùng để tìm lại chunks từ knowledge base khi `policy_tool_worker` cần tool hỗ trợ hoặc retrieval ban đầu không đủ.
- `get_ticket_info`: dùng để lấy thông tin ticket mock như `P1-LATEST`, bao gồm `notifications_sent`, `sla_deadline`, `status`.
- `check_access_permission`: tool hỗ trợ kiểm tra điều kiện cấp quyền, dù trong flow hiện tại chủ yếu mới demo trực tiếp ở `mcp_server.py`.

---

## 2. Quyết định kỹ thuật quan trọng nhất (200–250 từ)

> Chọn **1 quyết định thiết kế** mà nhóm thảo luận và đánh đổi nhiều nhất.
> Phải có: (a) vấn đề gặp phải, (b) các phương án cân nhắc, (c) lý do chọn phương án đã chọn.

**Quyết định:** Dùng supervisor rule-based kết hợp worker chuyên trách, thay vì giữ một single-agent pipeline hoặc thêm LLM classifier cho routing.

**Bối cảnh vấn đề:**

Khi chuyển từ Day 08 sang Day 09, nhóm cần giải quyết hai vấn đề cùng lúc: tách pipeline thành các phần dễ test độc lập và giữ cho trace đủ rõ để nhìn vào là biết lỗi nằm ở đâu. Nếu dùng lại single-agent pipeline, việc debug retrieval, policy, và synthesis sẽ tiếp tục bị dính vào nhau. Nếu dùng LLM classifier để route, hệ thống sẽ có thêm một LLM call, tăng latency, tăng cost, và route_reason sẽ khó giải thích hơn khi chấm lab.

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| Single-agent như Day 08 | Code ngắn, ít moving parts | Khó debug, không có route_reason, khó mở rộng MCP |
| LLM classifier + workers | Routing linh hoạt hơn | Thêm latency, thêm chi phí, route_reason khó giải thích bằng trace |

**Phương án đã chọn và lý do:**

Nhóm chọn supervisor rule-based và worker chuyên trách. Cách này đủ chính xác cho domain nhỏ của lab, đồng thời tạo được `route_reason` rất cụ thể như `policy/access keyword detected: 'level 3'` hay `SLA/incident/HR keyword detected: 'p1'`. Quyết định này cũng chia vai rõ ràng trong nhóm: Danh tập trung Sprint 1-2 với graph và workers, còn Kiệt phát triển Sprint 3-4 với MCP, trace, docs, và phần so sánh Day 08/Day 09.

**Bằng chứng từ trace/code:**
> Dẫn chứng cụ thể (VD: route_reason trong trace, đoạn code, v.v.)

``` 
route_reason = "policy/access keyword detected: 'level 3' | risk_high flagged: 'khẩn cấp'"
workers_called = ["retrieval_worker", "policy_tool_worker", "synthesis_worker"]
mcp_tools_used = [{"tool": "get_ticket_info", ...}]
```

---

## 3. Kết quả grading questions (150–200 từ)

> Sau khi chạy pipeline với grading_questions.json (public lúc 17:00):
> - Nhóm đạt bao nhiêu điểm raw?
> - Câu nào pipeline xử lý tốt nhất?
> - Câu nào pipeline fail hoặc gặp khó khăn?

**Tổng điểm raw ước tính:** Chưa tự chấm chính xác theo rubric từng criteria, nhưng nhóm đã chạy đủ `10/10` câu và nhìn theo log thì các câu factual/abstain mạnh hơn các câu temporal hoặc multi-hop phức tạp.

**Câu pipeline xử lý tốt nhất:**
- ID: `gq10` — Lý do tốt: pipeline kết luận đúng `KHÔNG được hoàn tiền` cho đơn `Flash Sale`, cite đúng policy refund và không bị đánh lừa bởi điều kiện `lỗi nhà sản xuất`.

**Câu pipeline fail hoặc partial:**
- ID: `gq09` — Fail ở đâu: pipeline route đúng sang `policy_tool_worker`, nhưng phần answer chưa nêu đúng 3 kênh SLA notification và cũng chưa nêu đúng điều kiện `Level 2 emergency bypass` theo Access Control SOP.  
  Root cause: retrieval/policy branch hiện chưa tổng hợp đủ cross-document facts cho câu multi-hop khó nhất.

**Câu gq07 (abstain):** Nhóm xử lý thế nào?

Ở `gq07`, pipeline trả lời `Không đủ thông tin trong tài liệu nội bộ.` thay vì bịa ra một con số phạt SLA. Đây là cách nhóm chủ động ưu tiên anti-hallucination, vì tài liệu `sla_p1_2026.txt` không chứa mức phạt tài chính cụ thể.

**Câu gq09 (multi-hop khó nhất):** Trace ghi được 2 workers không? Kết quả thế nào?

Với `gq09`, trace đã ghi được đầy đủ `retrieval_worker -> policy_tool_worker -> synthesis_worker` và có thêm `get_ticket_info` trong `mcp_tools_used`, nên về mặt orchestration thì pipeline đi đúng đường. Tuy nhiên answer cuối vẫn còn thiếu các chi tiết quan trọng của cả SLA notification và Level 2 emergency access, nên đây là câu nhóm coi là khó nhất và cần cải thiện thêm ở policy reasoning/synthesis.

---

## 4. So sánh Day 08 vs Day 09 — Điều nhóm quan sát được (150–200 từ)

> Dựa vào `docs/single_vs_multi_comparison.md` — trích kết quả thực tế.

**Metric thay đổi rõ nhất (có số liệu):**

Metric rõ nhất là `routing visibility`: Day 08 không có trace routing (`0/10`), còn Day 09 batch 15 câu mới nhất ghi được `15/15` trace có `supervisor_route` và `route_reason`. Ngoài ra, Day 09 còn có `2/15` traces dùng MCP tool thực tế, trong khi Day 08 là `0`.

**Điều nhóm bất ngờ nhất khi chuyển từ single sang multi-agent:**

Điều bất ngờ nhất là chất lượng answer không tự động tốt hơn chỉ vì chia thành nhiều agents. Lợi ích lớn nhất lại nằm ở khả năng quan sát và debug. Khi một câu trả lời sai, chỉ cần đọc trace là biết lỗi nằm ở route, retrieval, hay synthesis.

**Trường hợp multi-agent KHÔNG giúp ích hoặc làm chậm hệ thống:**

Với câu single-document rất đơn giản, multi-agent không tạo ra chất lượng vượt trội so với Day 08 nhưng lại tốn nhiều bước hơn. Batch 15 câu hiện có `avg_latency_ms = 8431`, cho thấy orchestration có overhead thật.

---

## 5. Phân công và đánh giá nhóm (100–150 từ)

> Đánh giá trung thực về quá trình làm việc nhóm.

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| Võ Thành Danh | `graph.py`, supervisor routing, state flow | Sprint 1 |
| Võ Thành Danh | `workers/retrieval.py`, `workers/policy_tool.py`, `workers/synthesis.py`, contracts | Sprint 2 |
| Trương Hầu Minh Kiệt | `mcp_server.py`, MCP integration, MCP trace aliases | Sprint 3 |
| Trương Hầu Minh Kiệt | `eval_trace.py`, docs, comparison report, trace analysis | Sprint 4 |

**Điều nhóm làm tốt:**

Nhóm chia vai khá rõ theo sprint nên ít bị chồng chéo code. Phần graph và workers được làm trước, sau đó phần MCP và trace được nối vào mà không phải viết lại toàn bộ pipeline. Điều này giúp docs và trace bám rất sát code thực tế.

**Điều nhóm làm chưa tốt hoặc gặp vấn đề về phối hợp:**

Một số template docs và report được điền khá muộn, nên có thời điểm trace đã đổi nhưng docs chưa cập nhật theo batch test mới nhất. Ngoài ra, supervisor routing hiện vẫn còn một rule hơi rộng ở nhánh refund.

**Nếu làm lại, nhóm sẽ thay đổi gì trong cách tổ chức?**

Nếu làm lại, nhóm sẽ chốt luôn bộ evidence chung ngay sau mỗi sprint: 1 command chạy, 1 trace mẫu, 1 note ngắn về expected output. Làm vậy sẽ giảm công sức cập nhật docs ở cuối buổi.

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì? (50–100 từ)

> 1–2 cải tiến cụ thể với lý do có bằng chứng từ trace/scorecard.

Nếu có thêm 1 ngày, nhóm sẽ tinh chỉnh supervisor để tách rõ hơn giữa `refund factual query` và `refund policy decision query`, vì trace batch 15 câu cho thấy `q02` đang route sai về mặt expected route. Ngoài ra, nhóm sẽ chạy lại Day 09 bằng một scorecard cùng hệ metric với Day 08 để so sánh thêm `faithfulness` và `completeness`.

---

*File này lưu tại: `reports/group_report.md`*  
*Commit sau 18:00 được phép theo SCORING.md*
