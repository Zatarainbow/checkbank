#!/usr/bin/env python3
"""
speaker_client.py
------------------
Script chạy trực tiếp trên MÁY TÍNH CÁ NHÂN của bạn.
Script này sẽ liên tục kiểm tra (poll) API trên Vercel để nhận các đơn donate đã thanh toán
và dùng thư viện giọng nói (edge-tts / pyttsx3) để đọc to qua loa máy tính!
"""

import os
import sys
import time
import tempfile
import asyncio
import requests

# Cấu hình địa chỉ website của bạn (thay bằng URL Vercel của bạn sau khi deploy)
# Ví dụ: "https://my-payos-donation.vercel.app" hoặc "http://localhost:8000"
SERVER_URL = os.environ.get("SERVER_URL", "http://localhost:8000").rstrip("/")

POLL_INTERVAL = 3  # Khoảng thời gian kiểm tra donate mới (giây)

# Cấu hình giọng đọc tiếng Việt của Microsoft Edge (HoaiMy: giọng nữ, NamMinh: giọng nam)
EDGE_VOICE = "vi-VN-HoaiMyNeural" 


def play_audio_file(file_path: str):
    """Phát file âm thanh bằng pygame hoặc thư viện có sẵn trên OS"""
    try:
        import pygame
        pygame.mixer.init()
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        pygame.mixer.music.unload()
        return
    except Exception:
        pass

    # Fallback cho Linux / Mac / Windows lệnh hệ thống
    if sys.platform.startswith("linux"):
        os.system(f"mpv --no-video '{file_path}' > /dev/null 2>&1 || aplay '{file_path}' > /dev/null 2>&1")
    elif sys.platform == "darwin":
        os.system(f"afplay '{file_path}'")
    elif sys.platform == "win32":
        os.system(f'start /min "" "{file_path}"')


async def speak_with_edge_tts(text: str) -> bool:
    """Tạo giọng nói tiếng Việt tự nhiên chất lượng cao bằng edge-tts"""
    try:
        import edge_tts
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            temp_path = temp_file.name

        communicate = edge_tts.Communicate(text, EDGE_VOICE)
        await communicate.save(temp_path)

        play_audio_file(temp_path)

        # Xóa file tạm
        try:
            os.remove(temp_path)
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"[WARN] Không thể dùng edge-tts: {e}")
        return False


def speak_with_pyttsx3(text: str) -> bool:
    """Fallback: Đọc offline bằng pyttsx3 nếu không có mạng hoặc chưa cài edge-tts"""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        # Tìm voice tiếng Việt nếu có
        voices = engine.getProperty('voices')
        for v in voices:
            if 'vi' in v.id.lower() or 'vietnam' in v.name.lower():
                engine.setProperty('voice', v.id)
                break
        engine.say(text)
        engine.runAndWait()
        return True
    except Exception as e:
        print(f"[ERROR] pyttsx3 thất bại: {e}")
        return False


def speak(text: str):
    """Thực hiện đọc văn bản"""
    print(f"\n🔊 ĐANG ĐỌC QUA LOA: \"{text}\"")
    # Ưu tiên edge-tts giọng tự nhiên
    success = False
    try:
        success = asyncio.run(speak_with_edge_tts(text))
    except Exception:
        success = False

    # Nếu edge-tts không chạy được, dùng pyttsx3
    if not success:
        speak_with_pyttsx3(text)


def poll_loop():
    print("=" * 60)
    print("🎙️  PAYOS VOICE DONATION LISTENER")
    print(f"📡 Kết nối máy chủ: {SERVER_URL}")
    print("🔊 Đang đợi có donate mới để đọc qua loa...")
    print("   (Nhấn Ctrl+C để dừng)")
    print("=" * 60)

    # Kiểm tra kết nối ban đầu
    try:
        resp = requests.get(f"{SERVER_URL}/api/alerts/poll?mark_read=false", timeout=5)
        if resp.status_code == 200:
            print("✅ Kết nối máy chủ thành công!")
        else:
            print(f"⚠️ Máy chủ phản hồi mã {resp.status_code}")
    except Exception as e:
        print(f"⚠️ Chưa kết nối được máy chủ tại {SERVER_URL}: {e}")
        print("   Hãy đảm bảo server FastAPI đã chạy hoặc đã nhập đúng SERVER_URL.")

    while True:
        try:
            url = f"{SERVER_URL}/api/alerts/poll?mark_read=true"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                alerts = data.get("alerts", [])
                for item in alerts:
                    donor_name = item.get("name", "Người ủng hộ")
                    amount = item.get("amount", 0)
                    message = item.get("message", "")
                    speech_text = item.get("speechText") or f"Cảm ơn {donor_name} đã ủng hộ {amount:,} đồng. Lời nhắn: {message}"

                    print(f"\n🎉 [DONATE MỚI] {donor_name} vừa ủng hộ {amount:,} VND")
                    print(f"💬 Lời nhắn: {message}")
                    
                    speak(speech_text)
            else:
                print(f"[WARN] Máy chủ phản hồi lỗi: {response.status_code}")

        except requests.exceptions.RequestException as e:
            # Lỗi mạng tạm thời, bỏ qua và thử lại
            pass
        except KeyboardInterrupt:
            print("\n👋 Đã tắt lắng nghe giọng nói. Tạm biệt!")
            break
        except Exception as e:
            print(f"[ERROR] Ngoại lệ: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        SERVER_URL = sys.argv[1].rstrip("/")
    poll_loop()
