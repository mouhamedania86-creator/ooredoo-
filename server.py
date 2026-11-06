#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hell Info Server - Ultra Fast Version (FastAPI + aiohttp + Cache)
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
# إعدادات أوريدو
# ═══════════════════════════════════════════════════════════
OOREDOO_BFF = "https://apis.ooredoo.dz/api/ooredoo-bff"
OOREDOO_AUTH = "https://apis.ooredoo.dz/api/auth/realms/myooredoo/protocol/openid-connect/token"
CLIENT_ID = "myooredoo-app"

# ⭐ القيم من الـ Trace الجديد (الذي أرسلته مؤخراً)
X_SIG = "f320f896f3da2a5a0284f9af316efb4ab0432b26406413568db116fa9dc60feb"
X_INTEGRITY = "JWBTpxXcH7KR/kzaHeUUydDWODuU4i3H4fL9gCgKzyYfyN4qLJJE8keV+zSVHSTeI6aEyC2tbSza/NGmkflQ/UgaNZSN9SKxz7tcdQckHY25n6mOaDZ9PPMQmF4sKZqDwebce/c1SNGNn6qvTULW/L348aJvy7Vii6dyPTu3OSPV9AwKwGwQKNHN61HyK3jx/fa8Os5ux9u3Q654YLZrAJ99QGEm/C9nEBPmlHC98RjovLGBnuJOGx6k7fnyrt/Ogy5fNg+tBgi5HEsoXDAwutX7TOWfx4YKHpKW//TvPRQgp69e2Xqa+CvGJJ+a/WlPMPhRCSsfo0OG04mVvlkc8eXiLzV/GPuJCEmcRf9Z6V+xoDyMtU7OZ3XT5BMhI/D/N68LsRn/9dIBH6X7n0WAW3tzeKZK1zENWFKrd7aLlzEdwFzO/1JTQsEDom5TRie0Kd5yic4BGvS1C1BsA2wJhzyiZ2j7RUE9m8tOAkPEIs929FYIfmH8XcCQKHT0TqT0+N+wCiyfNawPlDhZWcObscFZeEmKgvqiUFCoCj6xI1hvyHK0nu7fnZ/sGc6oNT/SrFjubYWjOyoYFL7gMnlYAhyjZhjuAwN1m1/wjwrOx8DbFr2NW8qb3hv+CIzK1zL3LDryKjqNkTxcOp4aJnmSTa73guCEmWc7pnLkLw5O8RgW7RKHrObeeQ0l9lu4HWXwlhdWRxvVMQDimhtTrGASL6sIuaxyhOkrH4HFImP70SaCoK9+euMxnzkPjg9HqPIFj+I0KSMloVxW"

# Cache للـ OTP (لتسريع التحقق)
OTP_CACHE = {}
CACHE_TTL = 300  # 5 دقائق

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

# ═══════════════════════════════════════════════════════════
# HTTP Session (Connection Pooling)
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
# Ooredoo Endpoints
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

    # ⭐ Cache hit
    cached = cache_get(msisdn)
    if cached:
        logger.info(f"send-otp: cache hit for {msisdn}")
        return {"success": True, "cached": True}

    logger.info(f"send-otp: processing {msisdn}")

    # 1) Checkpoint
    h1 = {
        "user-agent": "Dart/3.11 (dart:io)",
        "accept": "*/*",
        "accept-encoding": "gzip",
        "x-msisdn": msisdn,
        "x-device-fingerprint": iid,
        "x-platform-origin": "mobile-android",
        "platform": "android",
        "x-version": "1.5.17",
        "x-signature": X_SIG,
        "x-timestamp": now_iso(),
        "x-instance-id": iid,
        "x-correlation-id": new_corr(),
        "x-native-integrity-token": X_INTEGRITY,
        "x-path": "/api/auth/realms/myooredoo/protocol/openid-connect/token",
        "x-method": "POST",
        "content-type": "application/json; charset=utf-8",
    }

    r1 = await async_post(f"{OOREDOO_BFF}/checkpoint/token", h1, json_data={})
    if not r1:
        return {"success": False, "error": "checkpoint: no response"}

    nonce = r1["headers"].get("x-nonce-id") or r1["headers"].get("X-Nonce-Id")
    chronos = r1["headers"].get("x-chronos-id") or r1["headers"].get("X-Chronos-Id")

    if not nonce or not chronos:
        logger.warning(f"send-otp: no nonce (code={r1['code']}) body={r1['body'][:200]}")
        return {"success": False, "error": f"WAF ({r1['code']})"}

    # 2) OTP request
    h2 = {
        "user-agent": "Dart/3.11 (dart:io)",
        "accept": "*/*",
        "accept-encoding": "gzip",
        "x-msisdn": msisdn,
        "x-device-fingerprint": iid,
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
        logger.info(f"send-otp: success for {msisdn} (HTTP {r2['code']})")
        return {"success": True}

    return {"success": False, "error": f"OTP request failed (HTTP {r2['code'] if r2 else 'net'})"}


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

    # ⭐ استخدام Cache
    cached = cache_get(msisdn)
    if cached:
        nonce = cached["nonce"]
        chronos = cached["chronos"]
        logger.info(f"verify-otp: cache hit for {msisdn}")
    else:
        # إعادة Checkpoint
        h1 = {
            "user-agent": "Dart/3.11 (dart:io)",
            "accept": "*/*",
            "accept-encoding": "gzip",
            "x-msisdn": msisdn,
            "x-device-fingerprint": iid,
            "x-platform-origin": "mobile-android",
            "platform": "android",
            "x-version": "1.5.17",
            "x-signature": X_SIG,
            "x-timestamp": now_iso(),
            "x-instance-id": iid,
            "x-correlation-id": new_corr(),
            "x-native-integrity-token": X_INTEGRITY,
            "x-path": "/api/auth/realms/myooredoo/protocol/openid-connect/token",
            "x-method": "POST",
            "content-type": "application/json; charset=utf-8",
        }
        r1 = await async_post(f"{OOREDOO_BFF}/checkpoint/token", h1, json_data={})
        if not r1:
            return {"success": False, "error": "checkpoint: no response"}
        nonce = r1["headers"].get("x-nonce-id") or r1["headers"].get("X-Nonce-Id")
        chronos = r1["headers"].get("x-chronos-id") or r1["headers"].get("X-Chronos-Id")
        if not nonce:
            return {"success": False, "error": "WAF"}

    # OTP verify
    h2 = {
        "user-agent": "Dart/3.11 (dart:io)",
        "accept": "*/*",
        "accept-encoding": "gzip",
        "x-msisdn": msisdn,
        "x-device-fingerprint": iid,
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
            logger.info(f"verify-otp: SUCCESS for {msisdn} (token_len={len(token)})")
            # حذف من Cache بعد النجاح
            OTP_CACHE.pop(msisdn, None)
            return {"success": True, "token": token}

    logger.warning(f"verify-otp: failed for {msisdn} (HTTP {r2['code'] if r2 else 'net'})")
    return {"success": False, "error": "OTP invalid or WAF"}


if __name__ == "__main__":
    print("🚀 Hell Info Server starting on port 5000...")
    uvicorn.run(app, host="0.0.0.0", port=5000, log_level="info")
