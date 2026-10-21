#!/usr/bin/env python3
"""
🎙️ Sinhala Audio to SRT Subtitle Generator (OpenAI Whisper & Gemini Dual Engine)
Converts spoken Sinhala audio (.mp3, .wav, .m4a, .ogg, .aac, .flac) into SubRip (.srt) subtitles.
Runs 100% free inside GitHub Actions with timestamp accuracy.
"""

import os
import sys
import glob
import time
import json
import base64
import argparse
import subprocess
import urllib.request

SUPPORTED_AUDIO_EXTS = ('.mp3', '.wav', '.m4a', '.ogg', '.aac', '.flac', '.webm', '.mp4')

def format_timestamp_srt(seconds: float) -> str:
    """Formats seconds into SRT format: 00:00:00,000"""
    millis = int((seconds % 1) * 1000)
    total_seconds = int(seconds)
    mins, secs = divmod(total_seconds, 60)
    hours, mins = divmod(mins, 60)
    return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"

def format_timestamp_vtt(seconds: float) -> str:
    """Formats seconds into WebVTT format: 00:00:00.000"""
    millis = int((seconds % 1) * 1000)
    total_seconds = int(seconds)
    mins, secs = divmod(total_seconds, 60)
    hours, mins = divmod(mins, 60)
    return f"{hours:02d}:{mins:02d}:{secs:02d}.{millis:03d}"

def download_audio_from_url(url: str, output_path: str = "downloaded_audio.mp3") -> str:
    """Downloads audio file from direct link, Seedr, Telegram, or cloud drive."""
    print(f"📥 [Downloader] Fetching audio from URL: {url}")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=60) as resp, open(output_path, 'wb') as out_f:
            out_f.write(resp.read())
        print(f"✅ Successfully downloaded audio ({os.path.getsize(output_path)} bytes) to {output_path}")
        return output_path
    except Exception as e:
        print(f"⚠️ Standard download warning: {e}. Trying aria2c/curl...")
        try:
            subprocess.run(["curl", "-L", "-s", "-o", output_path, url], check=True)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
                print(f"✅ Curl downloaded {output_path}")
                return output_path
        except Exception as curl_err:
            print(f"❌ Failed to download audio: {curl_err}")
            raise e

def find_latest_audio(search_dir: str = "audio") -> str:
    """Finds the most recent audio file in the specified directory."""
    if not os.path.exists(search_dir):
        return None
    files = []
    for ext in SUPPORTED_AUDIO_EXTS:
        files.extend(glob.glob(os.path.join(search_dir, f"*{ext}")))
        files.extend(glob.glob(os.path.join(search_dir, "**", f"*{ext}"), recursive=True))
    if not files:
        return None
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]

def transcribe_with_whisper(audio_file: str, model_name: str = "small", language: str = "si"):
    """Transcribes audio using OpenAI Whisper."""
    print(f"🧠 [Whisper Engine] Loading model '{model_name}' for language '{language}'...")
    import whisper

    model = whisper.load_model(model_name)
    print(f"⚡ [Whisper Engine] Transcribing audio: {audio_file}")
    
    # We pass language='si' for Sinhala. If auto, whisper detects language.
    transcribe_options = {
        "verbose": False,
        "task": "transcribe"
    }
    if language and language != "auto":
        transcribe_options["language"] = language

    result = model.transcribe(audio_file, **transcribe_options)
    segments = result.get("segments", [])
    text = result.get("text", "").strip()
    return segments, text

def transcribe_with_gemini(audio_file: str, api_key: str):
    """Fallback: Transcribes audio using Gemini Multimodal Speech API."""
    print(f"🤖 [Gemini Engine] Transcribing Sinhala audio via Gemini...")
    with open(audio_file, 'rb') as f:
        audio_b64 = base64.b64encode(f.read()).decode('utf-8')

    mime = "audio/mp3"
    if audio_file.endswith('.wav'): mime = "audio/wav"
    elif audio_file.endswith('.ogg'): mime = "audio/ogg"
    elif audio_file.endswith('.m4a'): mime = "audio/m4a"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [
                {
                    "text": (
                        "You are an expert Sinhala speech recognition engine. "
                        "Transcribe this spoken Sinhala audio with millisecond timestamps into SubRip Subtitle (.srt) format. "
                        "Ensure the Sinhala spelling and grammar are 100% natural and accurate. "
                        "Output ONLY the valid .srt content, with no markdown code blocks, explanations, or extra text."
                    )
                },
                {
                    "inlineData": {
                        "mimeType": mime,
                        "data": audio_b64
                    }
                }
            ]
        }]
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        raw_text = data['candidates'][0]['content']['parts'][0]['text']
        # Clean markdown wrappers if any
        cleaned = raw_text.replace("```srt", "").replace("```", "").strip()
        return cleaned

def write_subtitles(segments, full_text, output_dir: str, base_name: str):
    """Writes .srt, .vtt, and .txt files."""
    os.makedirs(output_dir, exist_ok=True)
    srt_path = os.path.join(output_dir, f"{base_name}.srt")
    vtt_path = os.path.join(output_dir, f"{base_name}.vtt")
    txt_path = os.path.join(output_dir, f"{base_name}.txt")

    # 1. Write SRT (SubRip)
    with open(srt_path, "w", encoding="utf-8") as srt_file:
        for idx, seg in enumerate(segments, 1):
            start = format_timestamp_srt(seg["start"])
            end = format_timestamp_srt(seg["end"])
            caption = seg["text"].strip()
            srt_file.write(f"{idx}\n{start} --> {end}\n{caption}\n\n")

    # 2. Write WebVTT
    with open(vtt_path, "w", encoding="utf-8") as vtt_file:
        vtt_file.write("WEBVTT\n\n")
        for idx, seg in enumerate(segments, 1):
            start = format_timestamp_vtt(seg["start"])
            end = format_timestamp_vtt(seg["end"])
            caption = seg["text"].strip()
            vtt_file.write(f"{idx}\n{start} --> {end}\n{caption}\n\n")

    # 3. Write TXT
    with open(txt_path, "w", encoding="utf-8") as txt_file:
        txt_file.write(full_text + "\n")

    return srt_path, vtt_path, txt_path

def main():
    parser = argparse.ArgumentParser(description="Sinhala Audio to SRT Subtitle Generator")
    parser.add_argument("--audio", type=str, default="", help="Path to local audio file")
    parser.add_argument("--url", type=str, default="", help="Direct URL to download audio file")
    parser.add_argument("--model", type=str, default="small", choices=["tiny", "base", "small", "medium", "large-v3"], help="Whisper model size")
    parser.add_argument("--lang", type=str, default="si", help="Target language code (default: si for Sinhala)")
    parser.add_argument("--output_dir", type=str, default="subtitles", help="Output directory for subtitles")
    parser.add_argument("--engine", type=str, default="whisper", choices=["whisper", "gemini", "auto"], help="Transcription engine")
    args = parser.parse_args()

    audio_file = args.audio
    if args.url:
        audio_file = download_audio_from_url(args.url)

    if not audio_file or not os.path.exists(audio_file):
        # Look in ./audio directory
        found = find_latest_audio("audio")
        if found:
            audio_file = found
            print(f"🔍 Found recent audio in audio/ folder: {audio_file}")
        else:
            # Also search current directory
            root_audios = []
            for ext in SUPPORTED_AUDIO_EXTS:
                root_audios.extend(glob.glob(f"*{ext}"))
            if root_audios:
                audio_file = root_audios[0]
                print(f"🔍 Found audio in root directory: {audio_file}")

    if not audio_file or not os.path.exists(audio_file):
        print("❌ Error: No audio file found! Please provide --audio path, --url, or put an audio file in 'audio/' folder.")
        sys.exit(1)

    print(f"🎵 [Audio Target] Processing: {audio_file} ({os.path.getsize(audio_file) / 1024:.1f} KB)")
    base_name = os.path.splitext(os.path.basename(audio_file))[0]
    os.makedirs(args.output_dir, exist_ok=True)

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    segments = []
    full_text = ""

    # Engine execution
    if args.engine == "gemini" or (args.engine == "auto" and gemini_key and not gemini_key.startswith("AQ.")):
        try:
            srt_content = transcribe_with_gemini(audio_file, gemini_key)
            srt_path = os.path.join(args.output_dir, f"{base_name}.srt")
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)
            print(f"🎉 [Gemini] SRT Subtitles written to: {srt_path}")
            return
        except Exception as e:
            print(f"⚠️ Gemini transcription notice: {e}. Falling back to Whisper...")

    # Default: OpenAI Whisper
    try:
        segments, full_text = transcribe_with_whisper(audio_file, model_name=args.model, language=args.lang)
    except ImportError:
        print("ℹ️ 'whisper' package not pre-installed. Attempting pip install...")
        subprocess.run([sys.executable, "-m", "pip", "install", "openai-whisper"], check=True)
        segments, full_text = transcribe_with_whisper(audio_file, model_name=args.model, language=args.lang)

    if not segments:
        print("⚠️ Warning: No speech segments detected in audio file.")
        sys.exit(0)

    srt_path, vtt_path, txt_path = write_subtitles(segments, full_text, args.output_dir, base_name)

    print("=" * 60)
    print(f"🎉 [SUCCESS] Sinhala Subtitles Generated Successfully!")
    print(f"📄 SRT Subtitle File : {srt_path}")
    print(f"🌐 WebVTT File       : {vtt_path}")
    print(f"📝 Text Transcript   : {txt_path}")
    print(f"📊 Total Subtitles   : {len(segments)} caption blocks")
    print("=" * 60)
    print("\n💡 Preview of generated SRT:")
    with open(srt_path, "r", encoding="utf-8") as f:
        print("\n".join(f.readlines()[:18]))

if __name__ == "__main__":
    main()
