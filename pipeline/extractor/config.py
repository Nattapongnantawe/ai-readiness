# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_RPM     = int(os.getenv("GEMINI_RPM", "8"))        # free tier: ตั้งต่ำไว้ก่อน
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:YOUR_PASSWORD@localhost:5432/jobmarket")
BATCH_SIZE     = int(os.getenv("BATCH_SIZE", "5"))         # งานต่อ 1 request
MAX_ITEM_CHARS = 400
