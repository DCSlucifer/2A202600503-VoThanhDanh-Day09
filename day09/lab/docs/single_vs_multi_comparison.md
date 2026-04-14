# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** 2A202600502-TruongHauMinhKiet-Day09  
**Ngày:** 2026-04-14

Nguồn số liệu:
- Day 08: scorecard baseline đã chạy trước đó, tóm tắt từ `scorecard_baseline.md`
- Day 09: batch mới nhất `15` câu từ `python eval_trace.py --test-file data/test_questions.json`

---

## 1. Metrics Comparison

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta | Ghi chú |
|--------|----------------------|---------------------|-------|---------|
| Avg confidence | `N/A` | `0.887` | `N/A` | Day 08 scorecard không log confidence |
| Avg latency (ms) | `N/A` | `8,431` | `N/A` | Day 08 scorecard không log latency |
| Abstain rate (%) | `2/10 (20%)` | `3/15 (20%)` | `0%` | Day 08 lấy từ 2 câu abstain trong scorecard baseline |
| Observable routing traces | `0/10` | `15/15` | `+15 traces` | Day 09 có `supervisor_route` + `route_reason` |
| Tool-assisted runs | `0/10 (0%)` | `2/15 (13%)` | `+13%` | Day 09 có MCP calls trong batch 15 câu |
| Faithfulness (scorecard) | `3.90/5` | `N/A` | `N/A` | Day 09 hiện chưa rerun LLM judge theo bộ metric Day 08 |
| Completeness (scorecard) | `4.40/5` | `N/A` | `N/A` | Chưa chấm lại Day 09 bằng cùng judge |

Hai metric so sánh thực tế rõ nhất là `Observable routing traces` và `Tool-assisted runs`, vì Day 09 có trace cho từng bước trong khi Day 08 không có lớp orchestration nên cả hai đều bằng `0`.

---

## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | Tốt ở câu factual đơn giản | Tốt, đa số câu single-document route đúng trong batch 15 câu |
| Latency | Không có log cụ thể | Trung bình batch 15 câu là `8,431 ms` |
| Observation | Single-agent trả lời nhanh gọn hơn về mặt flow | Day 09 route đúng, nhưng phụ thuộc nhiều hơn vào trạng thái retrieval local |

**Kết luận:**  
Với câu một tài liệu, multi-agent không tự động tốt hơn về answer quality. Giá trị lớn nhất của Day 09 ở đây là quan sát được pipeline, không phải giảm latency.

### 2.2 Câu hỏi multi-hop (cross-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | Không có routing layer để tách access vs SLA | Có route rõ sang `policy_tool_worker`, trace ghi được 2 nguồn và MCP call |
| Routing visible? | `0/10` | `15/15` |
| Observation | Khó biết fail nằm ở retrieval hay reasoning | Trace `run_20260414_120158.json` cho thấy route đúng, workers đúng, nhưng answer vẫn cần policy logic chặt hơn |

**Kết luận:**  
Multi-agent giúp bài multi-hop dễ debug hơn rất nhiều. Khi câu hỏi khó, chỉ cần nhìn `workers_called` và `mcp_tools_used` là biết pipeline đã “đi đúng đường” hay chưa.

### 2.3 Câu hỏi cần abstain

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Abstain rate | `2/10 (20%)` | `3/15 (20%)` |
| Hallucination cases | Có vài câu trả lời quá ngắn kiểu “liên hệ bộ phận liên quan” | Có trace mới bị abstain vì collection local trống |
| Observation | Single-agent biết abstain nhưng không giải thích được vì sao | Day 09 khi abstain thì trace cho thấy ngay `retrieved_chunks=[]` và không có source |

**Kết luận:**  
Tỷ lệ abstain của Day 09 hiện cao hơn trên bộ trace đang có, nhưng bù lại lý do abstain minh bạch hơn hẳn. Đây là chỗ observability thắng chất lượng tạm thời.

---

## 3. Debuggability Analysis

### Day 08 — Debug workflow
```text
Khi answer sai -> phải đọc toàn bộ RAG pipeline -> tự đoán lỗi nằm ở retrieval hay generation
Không có route_reason, không có worker_io_logs
Thời gian ước tính: 15-20 phút để khoanh vùng 1 lỗi
```

### Day 09 — Debug workflow
```text
Khi answer sai -> đọc trace -> xem supervisor_route + route_reason
  -> route sai: sửa supervisor
  -> retrieval rỗng: kiểm tra Chroma/index
  -> policy sai: test policy_tool_worker độc lập
  -> synthesis sai: kiểm tra grounding prompt và confidence
Thời gian ước tính: 5-7 phút để khoanh vùng cùng loại lỗi
```

**Câu cụ thể nhóm đã debug:**  
Ở các trace `run_20260414_144528.json`, `run_20260414_144627.json`, `run_20260414_144640.json`, câu trả lời bắt đầu abstain dù route vẫn đúng. Trace cho thấy `retrieved_chunks=[]`, từ đó khoanh vùng được vấn đề nằm ở local Chroma collection trống chứ không phải supervisor route. Đây là lý do nhóm thêm bootstrap index vào `workers/retrieval.py`.

---

## 4. Extensibility Analysis

| Scenario | Day 08 | Day 09 |
|---------|--------|--------|
| Thêm 1 tool/API mới | Phải sửa pipeline chính | Thêm MCP tool và gọi từ `policy_tool_worker` |
| Thêm 1 domain mới | Phải nhồi thêm prompt | Có thể thêm worker mới |
| Thay đổi retrieval strategy | Sửa trực tiếp trong RAG core | Sửa `retrieval_worker` độc lập |
| A/B test một phần | Khó | Dễ hơn vì từng module tách biệt |

**Nhận xét:**  
Day 09 phù hợp hơn cho bài toán nội bộ có nhiều policy/domain nhỏ vì team có thể thay worker hoặc tool mà không phải đụng toàn bộ pipeline.

---

## 5. Cost & Latency Trade-off

| Scenario | Day 08 calls | Day 09 calls |
|---------|-------------|-------------|
| Simple query | `1` LLM call | `1` synthesis call |
| Complex query | `1` LLM call | `1` synthesis call + `0-2` MCP calls |
| MCP tool call | `N/A` | `2` tool calls trên batch `15` câu mới nhất |

**Nhận xét về cost-benefit:**  
Multi-agent không rẻ hơn. Ngược lại, nó tăng overhead orchestration và đôi khi tăng latency. Bù lại, nó cho visibility, traceability và khả năng mở rộng tốt hơn. Với lab này, lợi ích chính của Day 09 là debug và kiểm soát flow, không phải tối ưu tốc độ.

---

## 6. Kết luận

**Multi-agent tốt hơn single agent ở điểm nào?**

1. Có `supervisor_route`, `route_reason`, `worker_io_logs`, `mcp_tools_used`, nên debug nhanh hơn rõ rệt.
2. Dễ nối external capability qua MCP mà không phải sửa prompt chính của toàn hệ.

**Multi-agent kém hơn hoặc không khác biệt ở điểm nào?**

1. Không đảm bảo answer quality tốt hơn ở câu đơn giản, và hiện tại còn chậm hơn do nhiều bước orchestration.

**Khi nào KHÔNG nên dùng multi-agent?**

Nếu bài toán chỉ là factual QA đơn giản trên một tập tài liệu nhỏ, single-agent RAG gọn hơn và ít moving parts hơn.

**Nếu tiếp tục phát triển hệ thống này, nhóm sẽ thêm gì?**

Chạy lại full 15 câu sau khi bootstrap index sạch, rồi chấm Day 09 bằng cùng scorecard của Day 08 để có thêm 2 metric chất lượng cùng hệ quy chiếu như `faithfulness` và `completeness`.
