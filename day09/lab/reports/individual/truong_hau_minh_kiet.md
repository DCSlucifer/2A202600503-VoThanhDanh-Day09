# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Trương Hậu Minh Kiệt  
**Vai trò trong nhóm:** MCP Owner / Trace & Docs Owner  
**Ngày nộp:** 2026-04-14  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

Trong nhóm, tôi phụ trách chính phần `Sprint 3` và `Sprint 4`, tức là lớp `MCP + Trace + Docs`. File tôi làm trực tiếp nhiều nhất là mcp_server.py và eval_trace.py. Ngoài ra tôi cũng cập nhật contracts/worker_contracts.yamlđể mô tả đúng trạng thái MCP, và hoàn thiện ba tài liệu bắt buộc là docs/system_architecture.md, docs/routing_decisions.mdvà docs/single_vs_multi_comparison.md.

Phần việc của tôi kết nối trực tiếp với phần Danh làm ở Sprint 1 và 2. Danh đã dựng `graph.py` và các workers, còn tôi nối thêm lớp tool qua MCP, sửa trace để quan sát rõ hơn, rồi dùng chính trace đó để hoàn thiện phần so sánh, tài liệu và báo cáo nhóm. Bằng chứng rõ nhất là các file kể trên và các artifact như artifacts/grading_run.jsonl và artifacts/eval_report.json.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Tôi quyết định ghi rõ trace MCP theo hai lớp: vừa giữ `mcp_tools_used` để lưu toàn bộ input/output của tool call, vừa thêm alias rõ nghĩa hơn là `mcp_tool_called` và `mcp_result` để bám sát rubric chấm điểm.

Lúc đầu, pipeline chỉ lưu `mcp_tools_used`, tức là một list object chứa `tool`, `input`, `output`, `timestamp`. Về mặt kỹ thuật cách này đủ dùng, nhưng khi đối chiếu với `SCORING.md` tôi thấy rubric nhấn mạnh các trường kiểu `mcp_tool_called` và `mcp_result`. Nếu để nguyên một field duy nhất thì giảng viên vẫn có thể hiểu, nhưng tôi thấy rủi ro là trace “đúng ý” nhưng “không đúng tên trường” nên dễ mất điểm trình bày.

Lựa chọn thay thế là chỉ giữ `mcp_tools_used` và giải thích trong báo cáo. Tôi không chọn cách đó vì nó phụ thuộc vào việc người chấm có đọc giải thích hay không. Tôi chọn cách thêm alias ngay trong state tại graph.py và cập nhật logic append trong workers/policy_tool.py. Trade-off của cách này là state lớn hơn một chút, nhưng đổi lại trace đọc trực tiếp hơn và bám rubric chắc hơn.

**Bằng chứng từ trace/code:**

```python
state.setdefault("mcp_tools_used", [])
state.setdefault("mcp_tool_called", [])
state.setdefault("mcp_result", [])

state["mcp_tools_used"].append(mcp_result)
state["mcp_tool_called"].append(mcp_result["tool"])
state["mcp_result"].append(mcp_result.get("output"))
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** `python eval_trace.py --analyze` bị crash trên Windows console khi đọc trace và in kết quả phân tích.

Symptom ban đầu là pipeline đã chạy ra trace `.json`, nhưng khi tôi chạy phân tích thì script chết với `UnicodeDecodeError` và sau đó lại gặp thêm `UnicodeEncodeError` do console `cp1252` không in được emoji. Lỗi này làm Sprint 4 rất nguy hiểm, vì nhìn bề ngoài có file trace nhưng command chính dùng để tổng hợp metrics lại không chạy end-to-end.

Root cause nằm ở eval_trace.py. File trace được mở mà không chỉ định `encoding="utf-8"`, trong khi nội dung trace có tiếng Việt. Sau khi sửa phần đọc file, script vẫn còn chết vì các dòng `print("📊 ...")` không phù hợp với console encoding mặc định trên Windows.

Cách tôi sửa là:
- mở trace bằng `encoding="utf-8"`
- cấu hình lại `sys.stdout.reconfigure(encoding="utf-8")` nếu có thể
- đổi các dòng in có emoji sang ASCII-safe text

Sau khi sửa, tôi chạy được cả:
- `python eval_trace.py --analyze`
- `python eval_trace.py --compare --day08-scorecard ...`
- `python eval_trace.py --grading`

Đây là lỗi tôi thấy rất “đúng vai” của mình, vì nó không nằm ở logic domain mà nằm ở lớp observability và khả năng demo/nộp bài thực tế.

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

Tôi làm tốt nhất ở chỗ biến phần Sprint 3 và 4 từ trạng thái “có file” thành trạng thái “chạy được, có artifact, có docs bám evidence”. Tôi cũng chú ý khá nhiều đến việc phần báo cáo phải khớp với trace thật, vì SCORING phạt rất nặng nếu report không khớp code hoặc trace.

Điểm tôi còn yếu là tôi chưa cải thiện được chất lượng reasoning ở các câu multi-hop khó như `gq09`; hiện tôi mới giúp phần orchestration, trace và docs rõ ràng hơn, còn answer quality của các case khó vẫn chưa thật chắc.

Nhóm phụ thuộc vào tôi ở phần MCP, trace phân tích, so sánh Day 08 và Day 09, cũng như việc hoàn thiện các tài liệu bắt buộc. Nếu phần này chưa xong thì repo vẫn có code chạy, nhưng sẽ thiếu bằng chứng để chấm Sprint 3 và Sprint 4. Ngược lại, tôi phụ thuộc vào phần graph/workers của Danh vì toàn bộ MCP và trace của tôi chỉ có ý nghĩa khi supervisor và workers cơ bản đã chạy được.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Nếu có thêm 2 giờ, tôi sẽ cải tiến trace và policy reasoning cho `gq09`, vì log hiện tại cho thấy route và workers đã đi đúng đường nhưng answer cuối vẫn thiếu các chi tiết quan trọng về `3 kênh notification` và `Level 2 emergency bypass`. Tôi sẽ thử thêm một bước synthesis có template riêng cho câu multi-hop, thay vì dùng cùng một grounded prompt cho mọi loại câu hỏi.

---

*Lưu file này với tên: `reports/individual/truong_hau_minh_kiet.md`*
