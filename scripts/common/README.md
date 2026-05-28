# Common Scripts

Thư mục này chứa các helper dùng chung cho nhiều layer trong pipeline.

## Danh sách file

| File | Mục đích |
| --- | --- |
| `config.py` | Helper đọc `configs/app_config.yaml`, lấy giá trị cấu hình lồng nhau và resolve path tương đối theo root project. |

## Các hàm chính

| Hàm | Mục đích |
| --- | --- |
| `load_yaml()` | Đọc file cấu hình YAML. Nếu môi trường không có `PyYAML`, hàm sẽ dùng fallback parser đơn giản. |
| `get_nested(config, *keys, default=None)` | Lấy giá trị cấu hình lồng nhau, ví dụ `aws.bucket`. |
| `project_path(value)` | Chuyển path tương đối thành absolute path theo root project. |

## Ví dụ sử dụng

```python
from scripts.common.config import get_nested, load_yaml

config = load_yaml()
bucket = get_nested(config, "aws", "bucket")
```
