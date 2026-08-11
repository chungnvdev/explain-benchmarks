# explain-benchmarks

Số liệu trong các video `$ explain` của mình đều do máy đo, không phải số minh hoạ.
Repo này chứa toàn bộ script đã dùng, để ai muốn cũng kiểm chứng lại được.

Mỗi script chỉ cần **Python**, không phải cài gì thêm.

```bash
python3 11-deadlock/benchmark_deadlock.py
```

## Danh sách

| # | Chủ đề | Đo cái gì | Kết quả đo được |
|---|---|---|---|
| 11 | [Deadlock](11-deadlock/) | 2 giao dịch khoá chéo nhau | không có lock ordering: **0/2** giao dịch xong, treo vô hạn · có ordering: **2/2** xong trong ~113 ms |

## Cách đọc kết quả

Mỗi thư mục có `result.txt` là output thô của đúng lần chạy dùng trong video.
Chạy lại trên máy bạn, con số có thể lệch chút theo cấu hình, nhưng kết luận thì không đổi.

---

Nguyễn Việt Chung — AIDev
