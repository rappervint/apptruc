# HƯỚNG DẪN ĐỒNG BỘ CODE LÊN GITHUB & PYTHONANYWHERE (TỰ ĐỘNG CẬP NHẬT)

Tài khoản GitHub của bạn: **rappervint**  
Tài khoản PythonAnywhere của bạn: **tranbinhauto**  
Tên miền web online: **https://tranbinhauto.pythonanywhere.com**

---

## BƯỚC 1: TẠO REPOSITORY TRÊN GITHUB (Chỉ làm 1 lần đầu)

1. Mở trình duyệt, truy cập: [https://github.com/new](https://github.com/new)
2. Điền thông tin:
   - **Repository name**: `apptruc`
   - Chọn **Public** (hoặc Private tùy bạn)
   - ⚠️ **LƯU Ý:** **KHÔNG** tích chọn bất kỳ ô nào (*Add a README file*, *Add .gitignore*, *Choose a license*) vì code trên máy đã có sẵn rồi.
3. Bấm nút màu xanh: **Create repository**.

---

## BƯỚC 2: ĐẨY CODE TỪ VS CODE LÊN GITHUB (Chỉ làm 1 lần đầu)

Trên máy tính của bạn, mở Terminal trong VS Code (hoặc PowerShell tại thư mục `E:\apptruc`) và chạy 2 lệnh sau:

```bash
git remote add origin https://github.com/rappervint/apptruc.git
git push -u origin main
```
*(Nếu GitHub có hiện cửa sổ yêu cầu đăng nhập, bạn chọn đăng nhập bằng trình duyệt Sign in with Browser).*

---

## BƯỚC 3: TẢI VÀ CHẠY WEB TRÊN PYTHONANYWHERE (Chỉ làm 1 lần đầu)

### 3.1. Kéo code về PythonAnywhere:
1. Đăng nhập vào [pythonanywhere.com](https://www.pythonanywhere.com/) (tài khoản `tranbinhauto`).
2. Vào mục **Consoles** ➔ Bấm vào **Bash** để mở cửa sổ dòng lệnh.
3. Chạy 2 lệnh sau:
   ```bash
   git clone https://github.com/rappervint/apptruc.git
   pip install --user Flask gunicorn
   ```

### 3.2. Cấu hình Web App trên PythonAnywhere:
1. Vào tab **Web** trên thanh menu trên cùng.
2. Nếu chưa có Web App: Bấm **Add a new web app** ➔ Bấm **Next** ➔ Chọn **Manual configuration** ➔ Chọn **Python 3.10** ➔ Bấm **Next** cho xong.
3. Cuộn xuống phần **Code**, điền chính xác đường dẫn:
   - **Source code**: `/home/tranbinhauto/apptruc`
   - **Working directory**: `/home/tranbinhauto/apptruc`
4. Ngay bên dưới có mục **WSGI configuration file**, bấm vào link file màu xanh có dạng:  
   `/var/www/tranbinhauto_pythonanywhere_com_wsgi.py`
5. Nhấn **Ctrl + A** rồi bấm **Delete** để xóa sạch nội dung cũ, sau đó dán đoạn mã này vào:

```python
import sys
import os

path = '/home/tranbinhauto/apptruc'
if path not in sys.path:
    sys.path.insert(0, path)

os.chdir(path)

from wsgi import application
```
6. Bấm nút **Save** màu xanh ở góc trên bên phải để lưu lại.
7. Quay lại tab **Web**, bấm nút màu xanh to **Reload tranbinhauto.pythonanywhere.com**.

🎉 Trang web của bạn chạy online tại: `https://tranbinhauto.pythonanywhere.com`

---

## BƯỚC 4: QUY TRÌNH ĐỒNG BỘ SAU NÀY KHI SỬA CODE (RẤT NHANH)

Sau này, bất cứ khi nào bạn sửa code trên VS Code, quy trình đồng bộ cực kỳ đơn giản:

### 1. Trên máy tính (VS Code):
Chỉ cần mở Terminal gõ:
```bash
git add .
git commit -m "Cap nhat tinh nang moi"
git push
```

### 2. Trên PythonAnywhere:
Vào cửa sổ **Bash Console** trên PythonAnywhere và gõ đúng 1 dòng này:
```bash
cd ~/apptruc && git pull && touch /var/www/tranbinhauto_pythonanywhere_com_wsgi.py
```
*(Lệnh `touch ...wsgi.py` tự động kích hoạt server nạp lại code mới ngay lập tức mà bạn không cần phải bấm Reload trên web nữa).*

---

### 💡 MẸO TẠO LỆNH TẮT 1 CHẠM TRÊN PYTHONANYWHERE:
Trong cửa sổ Bash trên PythonAnywhere, bạn chạy lệnh này 1 lần duy nhất:
```bash
echo "cd ~/apptruc && git pull && touch /var/www/tranbinhauto_pythonanywhere_com_wsgi.py && echo '>>> ĐÃ CẬP NHẬT CODE MỚI XONG! <<<' " > ~/capnhat.sh
chmod +x ~/capnhat.sh
```

Từ nay về sau, mỗi lần sửa code xong trên máy tính và `git push`, bạn chỉ cần vào PythonAnywhere gõ:
```bash
./capnhat.sh
```
Hệ thống sẽ tự kéo code mới về và tự khởi động lại web app trong vòng 2 giây!

---

## BƯỚC 5: CẤU HÌNH TRỢ LÝ AI GOOGLE GEMINI (TÙY CHỌN - TĂNG TRÍ THÔNG MINH)

Hệ thống đã tích hợp sẵn **Google Gemini Cloud AI**:
- Nếu chưa có API Key: Hệ thống tự động dùng bộ não AI Tiếng Việt tích hợp sẵn (0ms, miễn phí 100%).
- Khi có API Key: AI sẽ cực kỳ thông minh, trả lời sắc bén, linh hoạt và thấu hiểu mọi cách diễn đạt tiếng Việt.

### 5.1. Lấy API Key miễn phí từ Google:
1. Truy cập: [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Đăng nhập tài khoản Google của bạn và bấm **Create API key**.
3. Sao chép chuỗi mã Key vừa tạo.

### 5.2. Cấu hình trên máy tính (Local):
Tạo file `.env` tại thư mục gốc `E:\apptruc` với nội dung:
```env
GEMINI_API_KEY=dán_mã_key_của_bạn_vào_đây
GEMINI_MODEL=gemini-1.5-flash
```

### 5.3. Cấu hình trên PythonAnywhere:
Trong cửa sổ **Bash** trên PythonAnywhere, tạo file `.env`:
```bash
echo "GEMINI_API_KEY=dán_mã_key_của_bạn_vào_đây" > ~/apptruc/.env
touch /var/www/tranbinhauto_pythonanywhere_com_wsgi.py
```
*(Hoặc vào tab Web -> cuộn xuống mục **Environment variables** và thêm `GEMINI_API_KEY`)*

