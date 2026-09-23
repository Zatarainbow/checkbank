# 🎙️ Cổng Donate Tự Động payOS + FastAPI (Deploy Vercel) & Đọc Giọng Nói

Hệ thống website donate tự động tích hợp cổng thanh toán **payOS** (VietQR), tự động xác thực giao dịch qua **Webhook**, và phát âm thanh / đọc to lời nhắn của người ủng hộ qua loa máy tính cá nhân.

---

## 🏗️ Kiến Trúc Hoạt Động

1. **Người ủng hộ** vào website, nhập Tên, Số tiền và Lời nhắn.
2. Hệ thống gọi API payOS tạo mã thanh toán VietQR.
3. Người ủng hộ chuyển khoản ngân hàng qua mã QR.
4. **payOS gửi Webhook** (`POST /api/webhook`) về server FastAPI (Vercel).
5. Server xác thực chữ ký (Signature) bằng `CHECKSUM_KEY`.
6. **Máy tính của bạn phát giọng nói:**
   - **Cách 1 (Khuyên dùng - Không cần cài đặt):** Mở trang `/overlay` trên trình duyệt máy bạn (hoặc add vào OBS). Trình duyệt sẽ tự động phát âm thanh chuông và đọc to nội dung bằng Web Speech API tiếng Việt.
   - **Cách 2 (Script Python cục bộ):** Chạy `speaker_client.py` trên máy bạn. Script này sẽ kết nối đến Vercel và dùng `edge-tts` (giọng AI Microsoft Hoài My / Nam Minh) hoặc `pyttsx3` để đọc to qua loa.

---

## 📁 Cấu Trúc Dự Án

```
payos-donation/
├── api/
│   └── index.py             # FastAPI backend (xử lý tạo link payOS & Webhook)
├── static/
│   ├── index.html           # Giao diện web Donate (gửi form, quét VietQR)
│   └── overlay.html         # Giao diện Alert Box (OBS / Trình duyệt đọc giọng nói)
├── speaker_client.py        # Script Python chạy trên MÁY BẠN để đọc qua loa
├── vercel.json              # Cấu hình serverless Vercel
├── requirements.txt         # Thư viện cho server Vercel
├── requirements-local.txt   # Thư viện cho script trên máy tính cá nhân
├── .env.example             # Mẫu biến môi trường
└── README.md
```

---

## 🔑 Cấu Hình Thông Tin payOS

Thông tin bạn đã cung cấp:
- **Client ID:** `01c53879-4ad0-46c8-bb0f-16a2470490c8`
- **API Key:** `94996c24-3b50-4003-a663-6a185101916e`

> ⚠️ **LƯU Ý QUAN TRỌNG VỀ CHECKSUM KEY:**
> Để payOS cho phép tạo thanh toán và xác thực Webhook an toàn, bạn cần lấy thêm **Checksum Key**:
> 1. Đăng nhập [https://my.payos.vn](https://my.payos.vn).
> 2. Vào mục **Kênh thanh toán** -> Chọn kênh của bạn -> Xem chi tiết để copy **Checksum Key**.
> 3. Điền vào file `.env` hoặc cài đặt trong Environment Variables của Vercel: `PAYOS_CHECKSUM_KEY`.

---

## 🚀 Hướng Dẫn Deploy Lên Vercel

### Cách 1: Deploy qua GitHub (Dễ nhất)
1. Tạo một repository mới trên GitHub và push toàn bộ thư mục `payos-donation` lên.
2. Vào [Vercel Dashboard](https://vercel.com/new) -> Chọn **Import** repository đó.
3. Ở phần **Environment Variables**, thêm các biến sau:
   - `PAYOS_CLIENT_ID`: `01c53879-4ad0-46c8-bb0f-16a2470490c8`
   - `PAYOS_API_KEY`: `94996c24-3b50-4003-a663-6a185101916e`
   - `PAYOS_CHECKSUM_KEY`: `<Checksum key của bạn>`
4. Nhấn **Deploy**.
5. Sau khi deploy xong, bạn sẽ có URL dạng: `https://ten-du-an.vercel.app`.

### Cách 2: Deploy bằng Vercel CLI
```bash
npm install -g vercel
cd payos-donation
vercel
```

---

## 🔗 Cấu Hình Webhook Trên my.payos.vn

1. Truy cập [https://my.payos.vn](https://my.payos.vn).
2. Vào mục **Kênh thanh toán** -> Bấm **Cài đặt Webhook**.
3. Điền URL Webhook của bạn:
   ```
   https://ten-du-an.vercel.app/api/webhook
   ```
4. Bấm **Lưu** / **Xác nhận**. payOS sẽ kiểm tra webhook của bạn.

---

## 🔊 Cách Đọc Giọng Nói Trên Máy Tính Cá Nhân

Do server chạy trên Vercel (đám mây), nó không thể trực tiếp xuất âm thanh ra loa vật lý của máy bạn. Bạn có thể chọn 1 trong 2 cách sau:

### Cách 1: Mở Trang Alert Box Trên Trình Duyệt / OBS (Khuyên Dùng)
- Trên máy tính của bạn, mở trình duyệt vào link:
  `https://ten-du-an.vercel.app/overlay`
- (Hoặc trong phần mềm **OBS Studio**, tạo một **Browser Source** với URL trên).
- Mỗi khi có ai đó quét mã donate thành công, màn hình sẽ hiển thị hiệu ứng chúc mừng và trình duyệt sẽ **tự động đọc to tên người ủng hộ cùng lời nhắn qua loa máy tính**!

### Cách 2: Chạy Script Python `speaker_client.py` Trên Máy Bạn
1. Mở Terminal trên máy tính của bạn:
   ```bash
   cd payos-donation
   pip install -r requirements-local.txt
   ```
2. Khởi chạy script lắng nghe giọng nói:
   ```bash
   python speaker_client.py https://ten-du-an.vercel.app
   ```
3. Mỗi khi có webhook kích hoạt, script sẽ dùng `edge-tts` (giọng Microsoft tiếng Việt Hoài My / Nam Minh) để phát âm thanh trực tiếp ra loa.

---

## 🧪 Chạy Thử Nghiệm Tại Local (Môi Trường Máy Của Bạn)

Để chạy thử nghiệm trước khi deploy lên Vercel:

1. Cài đặt thư viện:
   ```bash
   pip install -r requirements.txt
   ```
2. Chạy server FastAPI:
   ```bash
   uvicorn api.index:app --reload --port 8000
   ```
3. Mở trình duyệt vào `http://localhost:8000`:
   - Bấm nút **"Thử đọc giọng nói test"** để kiểm tra âm thanh.
   - Thử nhập form và tạo đơn donate để kiểm tra mã VietQR payOS.
