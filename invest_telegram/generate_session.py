"""
GitHub Actions용 텔레그램 세션 문자열 생성 스크립트
최초 1회 로컬에서 실행 → 출력된 문자열을 GitHub Secret에 저장

실행: python generate_session.py
"""

import os
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    session_str = client.session.save()

print("\n" + "="*60)
print("아래 문자열을 복사해서 GitHub Secret 'TELEGRAM_SESSION_STRING' 에 저장하세요:")
print("="*60)
print(session_str)
print("="*60 + "\n")
