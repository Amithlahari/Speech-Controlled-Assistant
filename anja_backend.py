import asyncio
import json
import re
import threading
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write
from faster_whisper import WhisperModel
from rapidfuzz import process, fuzz
import websockets

# =========================
# Robot stub actions
# =========================


def robot_freeze():
    print("ROBOT: FREEZE (stop all motion)")


def robot_go_idle():
    print("ROBOT: IDLE (safe posture, waiting)")


def robot_bring(item: str):
    print(f"ROBOT: BRING '{item}' (simulate fetch & deliver)")


def robot_hold():
    print("ROBOT: HOLD POSITION (simulate holding tray/pose)")


# =========================
# Command system
# =========================
WAKE_WORD_REQUIRED = True
WAKE_WORD = "anja"  # <-- keep consistent with the UI

ITEM_SYNONYMS = {
    "gauze": ["gauze", "swab", "compress", "pad", "4x4", "four by four", "gauze pad"],
    "scalpel": ["scalpel", "blade", "knife", "no. 10 blade", "number 10 blade", "no. 11 blade", "number 11 blade"],
    "syringe_10ml": ["10 ml syringe", "ten ml syringe", "10ml syringe", "ten milliliter syringe", "10 cc syringe", "ten cc syringe"],
    "saline": ["saline", "normal saline", "ns", "flush", "saline flush"],
}

pending_action = None          # (callable, description, item)
pending_set_time = None
PENDING_TIMEOUT_S = 30

SAMPLE_RATE = 16000
import queue


audio_queue = queue.Queue()


def audio_callback(indata, frames, time_info, status):
    if status:
        print(status)
        audio_queue.put(indata.copy())
# =========================
# Helpers
# =========================


def normalize_text(t: str) -> str:
    t = re.sub(r"[^a-z0-9\s]", " ", t.lower())
    return " ".join(t.strip().split())


def detect_item_with_score(text: str):
    t = normalize_text(text)

    for canonical, syns in ITEM_SYNONYMS.items():
        for s in syns:
            s_norm = normalize_text(s)
            if s_norm in t:
                return canonical, 0.95

    all_synonyms = []
    syn_to_canonical = {}
    for canonical, syns in ITEM_SYNONYMS.items():
        for s in syns:
            s_norm = normalize_text(s)
            all_synonyms.append(s_norm)
            syn_to_canonical[s_norm] = canonical

    best = process.extractOne(t, all_synonyms, scorer=fuzz.partial_ratio)
    if best:
        score = best[1] / 100.0
        if score >= 0.80:
            return syn_to_canonical[best[0]], min(0.90, score)
        if score >= 0.65:
            return syn_to_canonical[best[0]], min(0.70, score)

    return None, 0.0


def clear_pending():
    global pending_action, pending_set_time
    pending_action = None
    pending_set_time = None


def pending_is_active():
    if not pending_action:
        return False
    if pending_set_time is None:
        return True
    return (time.time() - pending_set_time) <= PENDING_TIMEOUT_S


def set_pending(fn, description: str, item: str):
    global pending_action, pending_set_time
    pending_action = (fn, description, item)
    pending_set_time = time.time()

# =========================
# AUDIO (same behavior as your script: press ENTER to record)
# =========================


def save_wav(path: str, audio: np.ndarray):
    audio_int16 = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
    write(path, SAMPLE_RATE, audio_int16)


def transcribe_whisper(model: WhisperModel, wav_path: str) -> str:
    segments, info = model.transcribe(
        wav_path,
        language="en",
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        beam_size=5
    )
    return " ".join(seg.text for seg in segments).strip()

# =========================
# CORE: handle_command now RETURNS a UI-friendly response dict
# =========================


def handle_command(text: str) -> dict:
    global pending_action

    t = normalize_text(text)
    if not t:
        return {"action": "unknown", "mode": "idle", "message": "Heard nothing."}

    followup_mode = pending_is_active()

    if pending_action and not followup_mode:
        clear_pending()
        return {"action": "unknown", "mode": "idle", "message": "Pending request expired. Please repeat your command."}

    # Safety always honored (wake word not required)
    if ("freeze" in t) or ("emergency" in t) or ("stop" in t and "standby" not in t):
        clear_pending()
        robot_freeze()
        return {"action": "freeze", "mode": "active", "message": "EMERGENCY STOP: Freeze activated."}

    # Confirm / Cancel if pending exists
    if followup_mode:
        if "cancel" in t or "abort" in t:
            clear_pending()
            return {"action": "cancel", "mode": "idle", "message": "Cancelled."}

        if "confirm" in t or t == "yes" or t.endswith(" yes"):
            fn, desc, item = pending_action
            clear_pending()
            fn()
            return {"action": "bring", "item": item, "mode": "active", "message": f"Confirmed: {desc}"}

        return {"action": "pending", "mode": "active", "message": "Waiting for CONFIRM or CANCEL."}

    # Wake word gating (only outside follow-up)
    if WAKE_WORD_REQUIRED and WAKE_WORD not in t:
        return {"action": "ignored", "mode": "idle", "message": f"Wake word not detected. Start with '{WAKE_WORD} ...'."}

    # Idle / Standby
    if "idle" in t or "standby" in t:
        clear_pending()
        robot_go_idle()
        return {"action": "idle", "mode": "idle", "message": "Mode set to IDLE."}

    # Hold
    if "hold" in t:
        clear_pending()
        robot_hold()
        return {"action": "hold", "mode": "active", "message": "Holding position."}

    # Bring / Fetch / Get (confirmation gated)
    if "bring" in t or "fetch" in t or "get" in t:
        item, _slot_conf = detect_item_with_score(t)
        if not item:
            return {
                "action": "unknown",
                "mode": "active",
                "message": f"Couldn't identify the tool. Try: '{WAKE_WORD} bring gauze' / '{WAKE_WORD} bring scalpel' / '{WAKE_WORD} bring saline'"
            }

        desc = "Bring 10 mL syringe" if item == "syringe_10ml" else f"Bring {item}"
        set_pending(lambda: robot_bring(item), desc, item)
        return {"action": "pending", "item": item, "mode": "active", "message": f"Confirm required: {desc}. Say 'confirm' or 'cancel'."}

    return {"action": "unknown", "mode": "active", "message": "Command not recognized."}


# =========================
# WEBSOCKET SERVER (matches the UI expectations)
# =========================
CLIENTS = set()
ASYNC_LOOP = None


async def broadcast(payload: dict):
    if not CLIENTS:
        return
    msg = json.dumps(payload)
    dead = []
    for ws in list(CLIENTS):
        try:
            await ws.send(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        CLIENTS.discard(ws)


def push(payload: dict):
    # safe to call from any thread
    if ASYNC_LOOP is None:
        return
    asyncio.run_coroutine_threadsafe(broadcast(payload), ASYNC_LOOP)


async def ws_handler(ws):
    CLIENTS.add(ws)
    try:
        await ws.send(json.dumps({"type": "status", "message": "Connected to ANJA backend"}))
        async for message in ws:
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                continue

            if data.get("type") == "manual_command":
                text = data.get("text", "")
                push({"type": "heard", "text": text})
                resp = handle_command(text)
                await ws.send(json.dumps({"type": "command", "text": text, "response": resp}))
    finally:
        CLIENTS.discard(ws)


def voice_thread_fn():
    model_size = "small"
    print(f"Loading Whisper model: {model_size} (offline)")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    print("🎤 Anja is listening continuously...")

    silence_threshold = 0.01
    silence_duration = 1.0  # seconds
    max_buffer_seconds = 6

    buffer = []
    silence_time = 0

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        callback=audio_callback
    )

    with stream:
        while True:
            chunk = audio_queue.get()
            buffer.append(chunk)

            rms = np.sqrt(np.mean(chunk**2))
            if rms < silence_threshold:
                silence_time += len(chunk) / SAMPLE_RATE
            else:
                silence_time = 0

            total_time = sum(len(b) for b in buffer) / SAMPLE_RATE

            # Speech ended OR buffer too long
            if silence_time > silence_duration or total_time > max_buffer_seconds:
                audio = np.concatenate(buffer).squeeze()
                buffer.clear()
                silence_time = 0

                if len(audio) < SAMPLE_RATE * 0.5:
                    continue  # too short

                wav_path = str(Path(__file__).resolve().parent / "command.wav")
                save_wav(wav_path, audio)

                text = transcribe_whisper(model, wav_path)
                if not text:
                    continue

                print(f"🎧 HEARD: {text}")
                push({"type": "heard", "text": text})

                resp = handle_command(text)
                push({"type": "command", "text": text, "response": resp})


async def main():
    global ASYNC_LOOP
    ASYNC_LOOP = asyncio.get_running_loop()

    # start voice in a background thread
    t = threading.Thread(target=voice_thread_fn, daemon=True)
    t.start()

    print("WebSocket server listening on ws://localhost:8765")
    async with websockets.serve(ws_handler, "localhost", 8765):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
