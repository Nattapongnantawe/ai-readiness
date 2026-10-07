# -*- coding: utf-8 -*-
"""เรียก Gemini แบบ structured output + rate limit + retry + สลับรุ่นสำรองอัตโนมัติ"""
import json
import os
import time

from google import genai
from google.genai import types

from .prompt import SYSTEM_PROMPT
from .schemas import BatchExtraction

# รุ่นสำรอง (แก้ได้ใน .env: GEMINI_FALLBACK=gemini-3.8-flash,gemini-flash-lite-latest)
FALLBACK = [m.strip() for m in os.getenv(
    "GEMINI_FALLBACK", "gemini-3.8-flash,gemini-flash-latest,gemini-flash-lite-latest").split(",")
    if m.strip()]


class QuotaExhausted(Exception):
    """โดน quota รายวัน — หยุดแล้วค่อยรันต่อพรุ่งนี้"""


class GeminiExtractor:
    def __init__(self, api_key: str, model: str, rpm: int = 8, max_retries: int = 15):
        if not api_key:
            raise ValueError("ไม่พบ GEMINI_API_KEY ใน .env")
        self.client = genai.Client(api_key=api_key)
        self.models = [model] + [m for m in FALLBACK if m != model]
        self.idx = 0
        self.dead = set()            # รุ่นที่ quota หมด / ไม่มีอยู่ -> ไม่กลับไปใช้
        self.min_interval = 60.0 / max(rpm, 1)
        self.max_retries = max_retries
        self._last = 0.0

    @property
    def model(self) -> str:
        return self.models[self.idx]

    def _wait(self):
        dt = time.monotonic() - self._last
        if dt < self.min_interval:
            time.sleep(self.min_interval - dt)
        self._last = time.monotonic()

    def _switch(self, reason: str, kill: bool = False) -> bool:
        """สลับไปรุ่นถัดไปที่ยังใช้ได้ (วนรอบ) คืน False ถ้าไม่เหลือเลย"""
        if kill:
            self.dead.add(self.model)
        n = len(self.models)
        for step in range(1, n + 1):
            j = (self.idx + step) % n
            if self.models[j] not in self.dead and j != self.idx:
                self.idx = j
                print(f"    🔁 {reason} -> สลับไปใช้ {self.model}")
                return True
        return self.model not in self.dead      # เหลือตัวเดียว: ลองตัวเดิมต่อ

    def extract(self, payload: list) -> BatchExtraction:
        cfg = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=BatchExtraction,
            temperature=0.0,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        body = json.dumps(payload, ensure_ascii=False)
        quota_hits = busy_hits = 0
        for attempt in range(1, self.max_retries + 1):
            self._wait()
            try:
                resp = self.client.models.generate_content(
                    model=self.model, contents=body, config=cfg)
                if isinstance(resp.parsed, BatchExtraction):
                    return resp.parsed
                return BatchExtraction.model_validate_json(resp.text)
            except Exception as e:                       # noqa: BLE001
                msg = str(e)
                if "404" in msg or "NOT_FOUND" in msg:
                    if self._switch(f"ไม่พบโมเดล {self.model}", kill=True):
                        continue
                    raise RuntimeError("ไม่มีโมเดลที่ใช้ได้ — แก้ GEMINI_MODEL ใน .env") from e
                if "503" in msg or "UNAVAILABLE" in msg:
                    busy_hits += 1
                    if busy_hits >= 2 and self._switch(f"{self.model} ยุ่ง (503)"):
                        busy_hits = 0
                        continue
                    wait = min(10 * busy_hits, 30)
                elif "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    quota_hits += 1
                    if "PerDay" in msg or quota_hits >= 3:
                        if self._switch(f"quota ของ {self.model} หมด", kill=True):
                            quota_hits = 0
                            continue
                        raise QuotaExhausted(msg[:300]) from e
                    wait = 60 * quota_hits
                else:
                    wait = min(2 ** attempt * 3, 60)
                print(f"    ⚠️ attempt {attempt} [{self.model}]: {msg[:90]} -> รอ {wait}s")
                time.sleep(wait)
        raise RuntimeError("Gemini ล้มเหลวเกินจำนวน retry")