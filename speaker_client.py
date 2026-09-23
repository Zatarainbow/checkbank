#!/usr/bin/env python3
"""
speaker_client.py
------------------
Script chạy trực tiếp trên MÁY TÍNH CÁ NHÂN của bạn.
Script này sẽ liên tục kiểm tra (poll) API trên Vercel để nhận các đơn donate đã thanh toán
và dùng giọng nói đọc to qua loa máy tính!
"""

import os
import sys
import time
import tempfile
import urllib.parse
import requests

# Địa chỉ domain Vercel của bạn
DEFAULT_URL = "https://checkbank-weld.vercel.app"
SERVER_URL = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else os.environ.get("SERVER_URL", DEFAULT_URL).rstrip("/")

POLL_INTERVAL = 2  # Kiểm tra mỗi 2 giây


def speak_google_tts(text: str) -> bool:
    """Tạo giọng đọc tiếng Việt bằng Google TTS và phát qua ffplay/mpv/aplay"""
    try:
        encoded_text = urllib.parse.quote(text)
        url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={encoded_text}&tl=vi&client=tw-ob"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                f.write(res.content)
                temp_path = f.name

            # Phát âm thanh qua loa
            if sys.platform.startswith("linux"):
                os.system(f"ffplay -nodisp -autoexit '{temp_path}' > /dev/null 2>&1 || mpv --no-video '{temp_path}' > /dev/null 2>&1")
            elif sys.platform == "darwin":
                os.system(f"afplay '{temp_path}'")
            elif sys.platform == "win32":
                os.system(f'start /min "" "{temp_path}"')

            try:
                os.remove(temp_path)
            except Exception:
                pass
            return True
    except Exception as e:
        print(f"[WARN] Google TTS: {e}")
    return False


def speak(text: str):
    """Đọc văn bản qua loa máy tính"""
    print(f"\n🔊 ĐANG ĐỌC QUA LOA: \"{text}\"")
    success = speak_google_tts(text)
    if not success:
        print("[ERROR] Không thể phát âm thanh qua loa!")


def poll_loop():
    print("=" * 65)
    print("🎙️  PAYOS VOICE DONATION LISTENER")
    print(f"📡 Kết nối máy chủ: {SERVER_URL}")
    print("🔊 Đang đợi có donate mới từ payOS để đọc to qua loa...")
    print("   (Nhấn Ctrl+C để dừng)")
    print("=" * 65)

    # Thử kết nối kiểm tra
    try:
        resp = requests.get(f"{SERVER_URL}/api/alerts/poll?mark_read=false", timeout=6)
        if resp.status_code == 200:
            print("✅ Đã kết nối thành công tới server Vercel!")
        else:
            print(f"⚠️ Server trả về mã HTTP: {resp.status_code}")
    except Exception as e:
        print(f"⚠️ Chưa kết nối được: {e}")

    # Vòng lặp lắng nghe liên tục
    while True:
        try:
            url = f"{SERVER_URL}/api/alerts/poll?mark_read=true"
            response = requests.get(url, timeout=8)

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

        except requests.exceptions.RequestException:
            pass
        except KeyboardInterrupt:
            print("\n👋 Đã tắt lắng nghe giọng nói. Tạm biệt!")
            break
        except Exception as e:
            print(f"[ERROR] {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    poll_loop()
