import os
import time
import json
import hmac
import hashlib
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Khởi tạo FastAPI
app = FastAPI(title="payOS Donation System", version="1.0.0")

# CORS middleware hỗ trợ truy cập từ web, OBS hoặc script máy tính cá nhân
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cấu hình PayOS Credentials (ưu tiên đọc từ biến môi trường, có fallback)
PAYOS_CLIENT_ID = os.environ.get("PAYOS_CLIENT_ID", "01c53879-4ad0-46c8-bb0f-16a2470490c8")
PAYOS_API_KEY = os.environ.get("PAYOS_API_KEY", "94996c24-3b50-4003-a663-6a185101916e")
PAYOS_CHECKSUM_KEY = os.environ.get("PAYOS_CHECKSUM_KEY", "2aa9e5e522ba6dd1e559136cf53d976eb42bcfcd0355b86f416c0e303b4a698e").strip()

# Thử import thư viện payos chính thức nếu có
try:
    from payos import PayOS
    payos_client = PayOS(
        client_id=PAYOS_CLIENT_ID,
        api_key=PAYOS_API_KEY,
        checksum_key=PAYOS_CHECKSUM_KEY
    ) if PAYOS_CHECKSUM_KEY else None
except Exception:
    payos_client = None

# Lưu trữ dữ liệu (Hỗ trợ bộ nhớ RAM + file cache /tmp cho serverless Vercel)
CACHE_FILE = "/tmp/payos_donations.json"

def load_db() -> Dict[str, Any]:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"donations": {}, "unread_alerts": []}

def save_db(data: Dict[str, Any]):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# Khởi tạo db
db = load_db()

# Models
class CreateDonationRequest(BaseModel):
    name: str
    amount: int
    message: Optional[str] = "Ủng hộ bạn!"

# Hàm tạo signature chuẩn của payOS
def create_payos_signature(data: dict, checksum_key: str) -> str:
    sorted_items = sorted(data.items(), key=lambda x: x[0])
    query_parts = []
    for k, v in sorted_items:
        v_str = "" if v is None else str(v)
        query_parts.append(f"{k}={v_str}")
    data_string = "&".join(query_parts)
    return hmac.new(
        checksum_key.encode("utf-8"),
        data_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

# Hàm verify webhook signature từ payOS
def verify_webhook_data(body: dict, checksum_key: str) -> bool:
    if not checksum_key:
        return True # Nếu chưa cấu hình checksum key thì bỏ qua kiểm tra (để test)
    
    received_signature = body.get("signature")
    data = body.get("data", {})
    if not received_signature or not data:
        return False
        
    expected_signature = create_payos_signature(data, checksum_key)
    return hmac.compare_digest(received_signature, expected_signature)

# ==================== CÁC ENDPOINT API ====================

@app.get("/", response_class=HTMLResponse)
async def serve_home():
    """Trang chủ hiển thị form donate"""
    static_path = os.path.join(os.path.dirname(__file__), "..", "static", "index.html")
    if os.path.exists(static_path):
        with open(static_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Trang Donate payOS đang hoạt động!</h1><p>Vui lòng mở file static/index.html</p>")

@app.get("/overlay", response_class=HTMLResponse)
async def serve_overlay():
    """Trang Alert Box / Overlay phát giọng nói trực tiếp trên trình duyệt hoặc OBS"""
    static_path = os.path.join(os.path.dirname(__file__), "..", "static", "overlay.html")
    if os.path.exists(static_path):
        with open(static_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Trang Overlay</h1>")

@app.post("/api/create-payment")
async def create_payment(req: CreateDonationRequest, request: Request):
    """Tạo link thanh toán payOS cho người donate"""
    if req.amount < 2000:
        raise HTTPException(status_code=400, detail="Số tiền donate tối thiểu là 2,000 VND theo quy định payOS.")

    # Sinh mã đơn hàng ngẫu nhiên (Số nguyên dương an toàn)
    order_code = int(time.time() * 1000) % 900000000 + 100000000

    # Xác định Base URL để tạo URL redirect
    base_url = str(request.base_url).rstrip("/")
    if "localhost" not in base_url and not base_url.startswith("https://"):
        base_url = base_url.replace("http://", "https://")

    # Nội dung mô tả chuyển khoản (ngắn gọn, tối đa 25 ký tự không dấu)
    short_desc = f"DONATE {order_code % 100000}"

    payment_payload = {
        "orderCode": order_code,
        "amount": req.amount,
        "description": short_desc,
        "cancelUrl": f"{base_url}/?status=cancelled",
        "returnUrl": f"{base_url}/?status=success&orderCode={order_code}",
    }

    checkout_url = ""
    qr_code = ""

    # 1. Gọi trực tiếp API payOS bằng httpx / requests
    import httpx
    headers = {
        "x-client-id": PAYOS_CLIENT_ID,
        "x-api-key": PAYOS_API_KEY,
        "Content-Type": "application/json"
    }

    if PAYOS_CHECKSUM_KEY:
        # Ký request nếu có checksum key
        signature = create_payos_signature(payment_payload, PAYOS_CHECKSUM_KEY)
        payment_payload["signature"] = signature

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api-merchant.payos.vn/v2/payment-requests",
            json=payment_payload,
            headers=headers,
            timeout=15.0
        )
        data = resp.json()

        if data.get("code") == "00":
            res_data = data.get("data", {})
            checkout_url = res_data.get("checkoutUrl", "")
            qr_code = res_data.get("qrCode", "")
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Lỗi payOS: {data.get('desc', 'Không thể tạo link thanh toán')}"
            )

    # Lưu thông tin đơn donate chờ thanh toán
    current_db = load_db()
    current_db["donations"][str(order_code)] = {
        "orderCode": order_code,
        "name": req.name.strip() or "Ẩn danh",
        "amount": req.amount,
        "message": req.message.strip() or "Ủng hộ bạn!",
        "status": "PENDING",
        "checkoutUrl": checkout_url,
        "createdAt": datetime.now().isoformat()
    }
    save_db(current_db)

    return {
        "success": True,
        "orderCode": order_code,
        "checkoutUrl": checkout_url,
        "qrCode": qr_code,
        "amount": req.amount
    }

@app.post("/api/webhook")
async def payos_webhook(request: Request):
    """
    Webhook tiếp nhận kết quả thanh toán từ payOS
    Luôn trả về {code: '00', desc: 'success'} mã HTTP 200 để payOS không retry
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"code": "00", "desc": "invalid json"}, status_code=200)

    # 1. Kiểm tra chữ ký webhook
    is_valid = verify_webhook_data(body, PAYOS_CHECKSUM_KEY)
    if not is_valid:
        print("[WARN] Webhook signature không hợp lệ!")
        return JSONResponse({"code": "00", "desc": "signature mismatch"}, status_code=200)

    # 2. Kiểm tra thanh toán thành công
    data = body.get("data", {})
    code = body.get("code")
    success = body.get("success", False)

    if code == "00" and success:
        order_code = str(data.get("orderCode"))
        paid_amount = data.get("amount", 0)
        
        current_db = load_db()
        donation = current_db["donations"].get(order_code)

        if donation:
            donation["status"] = "PAID"
            donation["paidAt"] = datetime.now().isoformat()
            donor_name = donation.get("name", "Người ủng hộ")
            donor_message = donation.get("message", "")
            amount = donation.get("amount", paid_amount)
        else:
            # Giao dịch không có trong db trước đó (ví dụ tạo link thủ công)
            donor_name = data.get("counterAccountName") or "Người ủng hộ"
            donor_message = data.get("description", "Ủng hộ")
            amount = paid_amount
            current_db["donations"][order_code] = {
                "orderCode": int(order_code),
                "name": donor_name,
                "amount": amount,
                "message": donor_message,
                "status": "PAID",
                "paidAt": datetime.now().isoformat()
            }

        # 3. Đưa vào hàng đợi thông báo để máy tính đọc giọng nói
        alert_item = {
            "orderCode": order_code,
            "name": donor_name,
            "amount": amount,
            "message": donor_message,
            "speechText": f"Cảm ơn {donor_name} đã ủng hộ {amount:,} đồng. Lời nhắn: {donor_message}",
            "timestamp": time.time()
        }
        current_db["unread_alerts"].append(alert_item)
        save_db(current_db)
        print(f"[SUCCESS] Nhận donate thành công: {donor_name} - {amount} VND")

    return JSONResponse({"code": "00", "desc": "success"}, status_code=200)

@app.get("/api/alerts/poll")
async def poll_alerts(mark_read: bool = Query(True)):
    """
    Endpoint để máy tính cá nhân hoặc Web Overlay lấy các thông báo mới cần đọc giọng nói
    Nếu mark_read=True: Xóa khỏi hàng đợi sau khi đã lấy
    """
    current_db = load_db()
    alerts = list(current_db.get("unread_alerts", []))
    
    if mark_read and alerts:
        current_db["unread_alerts"] = []
        save_db(current_db)

    return {"success": True, "count": len(alerts), "alerts": alerts}

@app.get("/api/recent-donations")
async def get_recent_donations():
    """Lấy danh sách các lượt donate đã hoàn thành gần đây"""
    current_db = load_db()
    paid_donations = [
        d for d in current_db.get("donations", {}).values()
        if d.get("status") == "PAID"
    ]
    # Sắp xếp mới nhất lên đầu
    paid_donations.sort(key=lambda x: x.get("paidAt", ""), reverse=True)
    return {"success": True, "donations": paid_donations[:20]}

@app.post("/api/test-alert")
async def trigger_test_alert(req: CreateDonationRequest):
    """Endpoint thử nghiệm giọng đọc trên máy tính mà không cần chuyển khoản thật"""
    current_db = load_db()
    alert_item = {
        "orderCode": "TEST_" + str(int(time.time())),
        "name": req.name or "Người thử nghiệm",
        "amount": req.amount,
        "message": req.message or "Xin chào, đây là tin nhắn donate thử nghiệm!",
        "speechText": f"Cảm ơn {req.name} đã ủng hộ {req.amount:,} đồng. Lời nhắn: {req.message}",
        "timestamp": time.time()
    }
    current_db["unread_alerts"].append(alert_item)
    save_db(current_db)
    return {"success": True, "message": "Đã thêm thông báo thử nghiệm vào hàng đợi đọc giọng nói!", "alert": alert_item}
