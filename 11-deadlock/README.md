# 11 · Deadlock

Hai giao dịch chạy cùng lúc: tài khoản 1 → 2 và 2 → 1.
Mỗi giao dịch khoá tài khoản nguồn, làm một chút việc (50 ms), rồi mới khoá tài khoản đích.

Luồng A giữ khoá 1 chờ khoá 2. Luồng B giữ khoá 2 chờ khoá 1. Không ai đi tiếp được.
Không có exception, không có log, hệ thống chỉ đứng im.

## Chạy

```bash
python3 benchmark_deadlock.py
```

## Kết quả đo được

| | Không lock ordering | Có lock ordering |
|---|---|---|
| Giao dịch hoàn thành | **0/2** (cả 5 lần chạy) | **2/2** (cả 5 lần chạy) |
| Thời gian | treo tới khi script bỏ cuộc | ~113 ms |

Cách sửa là **lock ordering**: mọi luồng luôn lấy khoá theo cùng một thứ tự toàn cục
(ở đây là theo id tài khoản tăng dần), bất kể tiền đi chiều nào.

Output thô: [result.txt](result.txt)
