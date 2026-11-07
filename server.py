#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hell Info Server - Updated with Real Integrity Tokens
"""

import asyncio
import aiohttp
import orjson
import time
import uuid
import json
import logging
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Hell Info Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════════
OOREDOO_BFF = "https://apis.ooredoo.dz/api/ooredoo-bff"
OOREDOO_AUTH = "https://apis.ooredoo.dz/api/auth/realms/myooredoo/protocol/openid-connect/token"
CLIENT_ID = "myooredoo-app"

# ⭐ X-Signature (ثابت، لا يتغير)
X_SIG = "f320f896f3da2a5a0284f9af316efb4ab0432b26406413568db116fa9dc60feb"

# ⭐ Integrity Tokens الحقيقية من Traces (احفظ قائمة)
INTEGRITY_TOKENS = [
    "JWBTpxXcH7KY9EXYeIRp8NjQMx2dt3vF8ejjoARazyoFzOw6Cu8+wkeV+zSVHSTeI6a12SG/FU+Q/9uBrcN71RlYO4CulD2x375NKwJRAInar8DVUilHBKUfjEsoHd6EwfLCfdYzLNXJu9POfEf6tqKn3PUe0pY6qZxWLhyVAFHw8Qwb52ZqdI2soCH4S3mrz+OZL+YovdGSUKlXKIkxVroAMTAg3jljLF7gvXaEsB/O3uW+tbkBMwSX2uTOwf+rh3sgOF/zPhKCFgRvZmU1o87Fa96Y/+wOcK+UpfXTCBYVrvQ1wG6ryC7vHMSqgUhYJK4tbSoti0zv4av9pwxh9Iv2MgsMENjyKBK/TuFZxEG3xQCKj1LTMgn2xBEeKcbsKrEW3xDRwsccGI3D7GHnbUlhdI4ujDIRQVKHaZSwhTp+32Cr4EB/Qt8p/xRbdgCde9MUlM4AYIGlfyVoHSkOvTu5c0DIIy1EhowtAkbKIJl49wsYKWvpT/nXFWzeXP3R2qzaclCnIb9qihhrarmwz8l8XH2T+f7AK2uSNiuWLG5Fy2mM/YLmuJPZT9Ciag/mpy7JGImKNQAcFbSAInBdKQjUKT+COzZfrXj5rwil9/HDMtuzIovq8hrQGY+roTfVPheTLWmcjkVCOL8VXAHjPb22vOuqrkMioWT9CQ5O8RgW7RKHrObeKQMp8F7tSjOqkxYDFkPVN1G4nkEBrTlPKK9YtPl+j7IuH9fGcDTwhCTTqP8peuBryW0L11tApvAEi7VkJyBxpVxW",
    "JWBTpxXcH7KR/kzaHeUUydDWODuU4i3H4fL9gCgKzyYfyN4qLJJE8keV+zSVHSTeI6aEyC2tbSza/NGmkflQ/UgaNZSN9SKxz7tcdQckHY25n6mOaDZ9PPMQmF4sKZqDwebce/c1SNGNn6qvTULW/L348aJvy7Vii6dyPTu3OSPV9AwKwGwQKNHN61HyK3jx/fa8Os5ux9u3Q654YLZrAJ99QGEm/C9nEBPmlHC98RjovLGBnuJOGx6k7fnyrt/Ogy5fNg+tBgi5HEsoXDAwutX7TOWfx4YKHpKW//TvPRQgp69e2Xqa+CvGJJ+a/WlPMPhRCSsfo0OG04mVvlkc8eXiLzV/GPuJCEmcRf9Z6V+xoDyMtU7OZ3XT5BMhI/D/N68LsRn/9dIBH6X7n0WAW3tzeKZK1zENWFKrd7aLlzEdwFzO/1JTQsEDom5TRie0Kd5yic4BGvS1C1BsA2wJhzyiZ2j7RUE9m8tOAkPEIs929FYIfmH8XcCQKHT0TqT0+N+wCiyfNawPlDhZWcObscFZeEmKgvqiUFCoCj6xI1hvyHK0nu7fnZ/sGc6oNT/SrFjubYWjOyoYFL7gMnlYAhyjZhjuAwN1m1/wjwrOx8DbFr2NW8qb3hv+CIzK1zL3LDryKjqNkTxcOp4aJnmSTa73guCEmWc7pnLkLw5O8RgW7RKHrObeeQ0l9lu4HWXwlhdWRxvVMQDimhtTrGASL6sIuaxyhOkrH4HFImP70SaCoK9+euMxnzkPjg9HqPIFj+I0KSMloVxW",
]

# Cache
OTP_CACHE = {}
CACHE_TTL = 300

def cache_set(msisdn, nonce, chronos, psig):
    OTP_CACHE[msisdn] = {
        "nonce": nonce, "chronos": chronos, "psig": psig,
        "expires": time.time() + CACHE_TTL
    }

def cache_get(msisdn):
    entry = OTP_CACHE.get(msisdn)
    if entry and entry["expires"] > time.time():
        return entry
    return None

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def new_corr():
    return str(uuid.uuid1()) + str(int(time.time() * 1000))

def new_fp():
    """fingerprint جديد 64 hex (مثل التطبيق الحقيقي)"""
    return uuid.uuid4().hex + uuid.uuid4().hex[:32]

# ═══════════════════════════════════════════════════════════
# HTTP Session
# ═══════════════════════════════════════════════════════════
_session = None

async def get_session():
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=20),
            connector=aiohttp.TCPConnector(limit=200, keepalive_timeout=60)
        )
    return _session

async def async_post(url, headers, json_data=None, data=None):
    session = await get_session()
    try:
        async with session.post(url, headers=headers, json=json_data, data=data, ssl=False) as r:
            body = await r.text()
            try:
                j = orjson.loads(body) if body else None
            except:
                j = None
            return {"code": r.status, "body": body, "json": j, "headers": dict(r.headers)}
    except Exception as e:
        logger.error(f"HTTP POST error: {e}")
        return None

# ═══════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════
@app.get("/")
async def root():
    return {"status": "ok", "service": "Hell Info Server"}

@app.post("/send-otp")
async def send_otp(data: dict):
    try:
        msisdn = data["msisdn"]
        iid = data["iid"]
        psig = data["psig"]
    except KeyError:
        return {"success": False, "error": "missing fields"}

    cached = cache_get(msisdn)
    if cached:
        logger.info(f"send-otp: cache hit for {msisdn}")
        return {"success": True, "cached": True}

    logger.info(f"send-otp: processing {msisdn} | iid={iid[:20]}")

    # ⭐ استخدام fingerprint جديد (مثل التطبيق)
    fp = new_fp()

    # ⭐ جرّب كل integrity tokens حتى ينجح
    for attempt, integ in enumerate(INTEGRITY_TOKENS, 1):
        h1 = {
            "user-agent": "Dart/3.11 (dart:io)",
            "accept": "*/*",
            "accept-encoding": "gzip",
            "x-msisdn": msisdn,
            "x-device-fingerprint": fp,
            "x-platform-origin": "mobile-android",
            "platform": "android",
            "x-version": "1.5.17",
            "x-signature": X_SIG,
            "x-timestamp": now_iso(),
            "x-instance-id": iid,
            "x-correlation-id": new_corr(),
            "x-native-integrity-token": integ,
            "x-path": "/api/auth/realms/myooredoo/protocol/openid-connect/token",
            "x-method": "POST",
            "content-type": "application/json; charset=utf-8",
        }

        r1 = await async_post(f"{OOREDOO_BFF}/checkpoint/token", h1, json_data={})
        if not r1:
            continue

        nonce = r1["headers"].get("x-nonce-id") or r1["headers"].get("X-Nonce-Id")
        chronos = r1["headers"].get("x-chronos-id") or r1["headers"].get("X-Chronos-Id")

        if nonce and chronos:
            logger.info(f"send-otp: checkpoint OK (attempt {attempt}, HTTP {r1['code']})")

            # OTP request
            h2 = {
                "user-agent": "Dart/3.11 (dart:io)",
                "accept": "*/*",
                "accept-encoding": "gzip",
                "x-msisdn": msisdn,
                "x-device-fingerprint": fp,
                "x-nonce-id": nonce,
                "x-platform-origin": "mobile-android",
                "platform": "android",
                "x-version": "1.5.17",
                "x-signature": X_SIG,
                "x-chronos-id": chronos,
                "x-timestamp": now_iso(),
                "x-platform-info": psig,
                "x-force-update": "true",
                "x-instance-id": iid,
                "Content-Type": "application/x-www-form-urlencoded",
            }
            body = f"client_id={CLIENT_ID}&grant_type=password&username={msisdn}"
            r2 = await async_post(OOREDOO_AUTH, h2, data=body)

            if r2 and r2["code"] in (200, 202, 401, 403):
                cache_set(msisdn, nonce, chronos, psig)
                logger.info(f"send-otp: SUCCESS (HTTP {r2['code']})")
                return {"success": True}
            else:
                logger.warning(f"send-otp: OTP request failed (HTTP {r2['code'] if r2 else 'net'})")

        else:
            logger.warning(f"send-otp: no nonce (attempt {attempt}, HTTP {r1['code']})")

    return {"success": False, "error": "WAF rejected all integrity tokens"}


@app.post("/verify-otp")
async def verify_otp(data: dict):
    try:
        msisdn = data["msisdn"]
        otp = data["otp"]
        iid = data["iid"]
        psig = data["psig"]
    except KeyError:
        return {"success": False, "error": "missing fields"}

    logger.info(f"verify-otp: processing {msisdn}")

    # ⭐ احذف cache بعد كل محاولة (لتجنب nonce منتهي)
    cached = cache_get(msisdn)
    if cached:
        nonce = cached["nonce"]
        chronos = cached["chronos"]
        logger.info(f"verify-otp: cache hit")
    else:
        # جرّب checkpoint من جديد
        fp = new_fp()
        for integ in INTEGRITY_TOKENS:
            h1 = {
                "user-agent": "Dart/3.11 (dart:io)",
                "accept": "*/*",
                "accept-encoding": "gzip",
                "x-msisdn": msisdn,
                "x-device-fingerprint": fp,
                "x-platform-origin": "mobile-android",
                "platform": "android",
                "x-version": "1.5.17",
                "x-signature": X_SIG,
                "x-timestamp": now_iso(),
                "x-instance-id": iid,
                "x-correlation-id": new_corr(),
                "x-native-integrity-token": integ,
                "x-path": "/api/auth/realms/myooredoo/protocol/openid-connect/token",
                "x-method": "POST",
                "content-type": "application/json; charset=utf-8",
            }
            r1 = await async_post(f"{OOREDOO_BFF}/checkpoint/token", h1, json_data={})
            if r1:
                nonce = r1["headers"].get("x-nonce-id") or r1["headers"].get("X-Nonce-Id")
                chronos = r1["headers"].get("x-chronos-id") or r1["headers"].get("X-Chronos-Id")
                if nonce:
                    break
        else:
            return {"success": False, "error": "checkpoint failed"}

    # OTP verify
    fp2 = new_fp()
    h2 = {
        "user-agent": "Dart/3.11 (dart:io)",
        "accept": "*/*",
        "accept-encoding": "gzip",
        "x-msisdn": msisdn,
        "x-device-fingerprint": fp2,
        "x-nonce-id": nonce,
        "x-platform-origin": "mobile-android",
        "platform": "android",
        "x-version": "1.5.17",
        "x-signature": X_SIG,
        "x-chronos-id": chronos,
        "x-timestamp": now_iso(),
        "x-platform-info": psig,
        "x-force-update": "true",
        "x-instance-id": iid,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    body = f"client_id={CLIENT_ID}&grant_type=password&username={msisdn}&otp={otp}"
    r2 = await async_post(OOREDOO_AUTH, h2, data=body)

    if r2 and r2["code"] == 200 and r2.get("json"):
        token = r2["json"].get("access_token")
        if token:
            logger.info(f"verify-otp: SUCCESS (token_len={len(token)})")
            OTP_CACHE.pop(msisdn, None)
            return {"success": True, "token": token}

    logger.warning(f"verify-otp: failed (HTTP {r2['code'] if r2 else 'net'})")
    # احذف cache (لأن nonce قد يكون منتهي)
    OTP_CACHE.pop(msisdn, None)
    return {"success": False, "error": "OTP invalid or WAF"}


if __name__ == "__main__":
    print("🚀 Hell Info Server starting...")
    uvicorn.run(app, host="0.0.0.0", port=5000, log_level="info")
