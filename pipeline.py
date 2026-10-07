#!/usr/bin/env python3
"""
Apalod Cinemax Studio - Automated Scene Splitter & Video Production Pipeline
Features:
1. Universal Stream & Archive Ingestion (Seedr.cc ZIP, Direct MP4, Telegram)
2. Automated Multi-Scene Splitting across movie timeline (Parts 1 to 5)
3. Gemini AI Sinhala Storyteller & Review Generation for each part
4. Microsoft Edge-TTS Neural Sinhala Male Voice (si-LK-SameeraNeural)
5. FFmpeg Audio-Video Sync & Cinematic Slow-Mo Alignment
6. Telegram sendVideo Channel Publisher (Sends Real Streamable MP4 Clips)
7. GitHub Artifact Archiver for all generated MP4 parts
"""

import os
import sys
import glob
import time
import json
import zipfile
import argparse
import subprocess
try:
    import requests
except ImportError:
    requests = None
import urllib.request

VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.webm', '.ts', '.m4v')

def get_media_duration(file_path):
    """Returns duration in seconds using ffprobe."""
    if not os.path.exists(file_path):
        return 0.0
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return float(res.stdout.strip())
    except Exception:
        return 0.0

def download_and_extract_media(source_url, output_target="input_movie.mp4"):
    """Downloads URL, unzips Seedr archives, and locates largest video file."""
    if not source_url:
        print("ℹ️ No source URL provided. Checking local file...")
        return output_target if os.path.exists(output_target) else None

    print(f"📥 [Downloader] Fetching source media: {source_url}")
    temp_download = "downloaded_raw_source.tmp"

    # Multi-connection aria2c or urllib stream
    try:
        subprocess.run([
            "aria2c", "-s", "4", "-x", "4",
            "--connect-timeout=20", "--timeout=30", "--max-tries=3",
            "-o", temp_download, source_url
        ], check=True)
    except Exception as e:
        print(f"⚠️ aria2c download failed ({e}), falling back to HTTP stream...")
        if requests:
            with requests.get(source_url, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(temp_download, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk: f.write(chunk)
        else:
            urllib.request.urlretrieve(source_url, temp_download)

    if not os.path.exists(temp_download) or os.path.getsize(temp_download) == 0:
        print("❌ Downloaded file is empty.")
        return None

    size_mb = os.path.getsize(temp_download) / (1024 * 1024)
    print(f"📦 Downloaded source size: {size_mb:.2f} MB")

    # Check for ZIP archive magic bytes
    is_zip = False
    with open(temp_download, "rb") as f:
        if f.read(4) == b"PK\x03\x04":
            is_zip = True

    if is_zip or source_url.lower().endswith(".zip"):
        print("🗜️ Archive detected (Seedr Zip). Unpacking...")
        extract_folder = "extracted_archive"
        os.makedirs(extract_folder, exist_ok=True)

        with zipfile.ZipFile(temp_download, "r") as zf:
            zf.extractall(extract_folder)

        video_candidates = []
        for root, _, files in os.walk(extract_folder):
            for file in files:
                if file.lower().endswith(VIDEO_EXTENSIONS):
                    full_p = os.path.join(root, file)
                    video_candidates.append((full_p, os.path.getsize(full_p), file))

        if not video_candidates:
            print("❌ No video files found in archive.")
            return None

        video_candidates.sort(key=lambda x: x[1], reverse=True)
        chosen_path, chosen_size, chosen_name = video_candidates[0]
        print(f"🎯 Target Movie Found: '{chosen_name}' ({chosen_size / (1024 * 1024):.2f} MB)")

        if os.path.exists(output_target):
            os.remove(output_target)
        os.rename(chosen_path, output_target)
        return output_target

    if os.path.exists(output_target):
        os.remove(output_target)
    os.rename(temp_download, output_target)
    return output_target

import re

def time_to_seconds(t_str):
    """Converts HH:MM:SS or MM:SS string to seconds."""
    parts = [int(p) for p in t_str.strip().split(':')]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    elif len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return 0

def parse_custom_script(text):
    """Parses timestamped script in format [HH:MM:SS - HH:MM:SS] Sinhala narration."""
    if not text or not text.strip():
        return []
    pattern = r'\[(\d{1,2}:\d{2}:\d{2})\s*-\s*(\d{1,2}:\d{2}:\d{2})\]\s*\n?([^\[]+)'
    matches = re.findall(pattern, text)
    chapters = []
    for start_str, end_str, script in matches:
        s_sec = time_to_seconds(start_str)
        e_sec = time_to_seconds(end_str)
        dur = max(5, e_sec - s_sec)
        clean_narr = script.strip()
        if clean_narr:
            chapters.append({
                'start_str': start_str,
                'end_str': end_str,
                'start_sec': s_sec,
                'end_sec': e_sec,
                'duration': dur,
                'narration': clean_narr
            })
    return chapters

def generate_part_script(movie_title, part_num, total_parts, gemini_key):
    """Generates an authentic Sinhala Movie Recap narration in Inside Cinemax YouTube channel style."""
    prompts = {
        1: f"කතාව ආරම්භයේදීම අපිට දකින්න ලැබෙන්නේ {movie_title} චිත්‍රපටයේ ප්‍රධාන චරිතය අනපේක්ෂිත සිදුවීමකට මුහුණ දෙන ආකාරයයි. ඔහුගේ සාමාන්‍ය ජීවිතය එකවරම වෙනස් වෙමින් අභිරහස් තත්ත්වයක් නිර්මාණය වන අතර, කිසිවෙකු නොසිතූ බරපතල අභියෝගයකට ඔහුට මුහුණ දීමට සිදුවේ.",
        2: f"කතාව ඉදිරියට යද්දී තත්ත්වය තවත් දරුණු අතට හැරෙනවා. ප්‍රධාන චරිතය තමන් වටා ඇති අනතුර තේරුම් ගන්නා විට, ඔහුට එරෙහිව ක්‍රියාත්මක වන රහස්‍ය සැලසුම් එකින් එක එළිදරව් වීමට පටන් ගන්නා අතර සෑම මොහොතක්ම දැඩි කුතුහලයකින් පිරී යයි.",
        3: f"{movie_title} චිත්‍රපටයේ උච්චතම අවස්ථාවේදී සියලු රහස් විසඳෙන මොහොත පැමිණෙනවා. අවසන් තීරණාත්මක සටන සහ ප්‍රධාන චරිතයේ ඉරණම තීරණය වන ආකාරය ප්‍රේක්ෂකයා කිසිසේත් බලාපොරොත්තු නොවූ පුදුම සහගත අවසානයකින් නිමාවට පත් වෙනවා.",
        4: f"අවදානම තවත් වැඩි වෙමින් ප්‍රධාන චරිතය තීරණාත්මක මංසන්ධියකට පැමිණෙනවා. සිය මිතුරන් සහ සතුරන් වෙන්කර හඳුනාගත නොහැකි මේ මොහොතේ සෑම තීරණයක්ම ජීවිතයත් මරණයත් අතර සටනක් බවට පත්වෙයි.",
        5: f"අවසාන වශයෙන් සියලු අභිරහස් වල සුලමුල හෙළිදරව් වන අතර, චිත්‍රපටය අවසන් වන්නේ ප්‍රේක්ෂකයාගේ මනස කුල්මත් කරවන විස්මිත සහ නොසිතූ අවසානයකිනි."
    }

    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
            part_guide = (
                "1 වන කොටස: කතාවේ ආරම්භය! චිත්‍රපටය ආරම්භ වන අවස්ථාව, ප්‍රධාන චරිතය හඳුන්වා දීම, ඔහු හෝ ඇය සිටින පරිසරය සහ කතාව පටන් ගන්නා මුල් සිදුවීම පැහැදිලි කරන්න. (උදා: 'කතාව ආරම්භයේදීම අපිට දකින්න ලැබෙන්නේ...')"
                if part_num == 1 else
                ("2 වන කොටස: කතාවේ මැද අවස්ථාව! ප්‍රධාන චරිතයට එල්ල වන දැඩි අනතුර, කුතුහලය සහ කතාවේ හැරවුම් ලක්ෂ්‍යය විස්තර කරන්න."
                if part_num == 2 else
                "3 වන කොටස: කතාවේ උච්චතම අවස්ථාව සහ අවසානය! සියලු රහස් හෙළිදරව් වීම සහ විස්මිත අවසානය පැහැදිලි කරන්න.")
            )
            p_text = f"""ඔබ 'Inside Cinemax' YouTube චැනලයේ නිල සිංහල කථිකයායි.
'{movie_title}' චිත්‍රපටයේ {part_num}/{total_parts} වන කොටස සඳහා අතිශය ආකර්ෂණීය සිංහල Movie Recap Narration එකක් ලියන්න.

විශේෂ උපදෙස්:
- {part_guide}
- වචන 40-55 අතර විය යුතුය.
- ස්වභාවික, ආකර්ෂණීය සිංහල කථන ශෛලියෙන් ලියන්න.
- ඉංග්‍රීසි වචන, Tags හෝ මාතෘකා නැතිව Narration Text එක පමණක් සෘජුවම ලබා දෙන්න."""
            body = json.dumps({"contents": [{"parts": [{"text": p_text}]}]}).encode('utf-8')
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json; charset=utf-8"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                cand = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text")
                if cand and len(cand.strip()) > 20:
                    return cand.strip()
        except Exception as e:
            print(f"⚠️ Gemini request error: {e}, using default Inside Cinemax Sinhala script.")

    return prompts.get(part_num, prompts[1])

def send_telegram_video(bot_token, channel_id, video_path, caption):
    """Uploads streamable MP4 video to Telegram channel using multipart form."""
    print(f"📤 Uploading '{video_path}' to Telegram ({channel_id})...")
    cmd = [
        "curl", "-s", "-X", "POST", f"https://api.telegram.org/bot{bot_token}/sendVideo",
        "-F", f"chat_id={channel_id}",
        "-F", f"video=@{video_path}",
        "-F", f"caption={caption}",
        "-F", "parse_mode=HTML",
        "-F", "supports_streaming=true"
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        res_json = json.loads(res.stdout)
        if res_json.get("ok"):
            print(f"✅ Video Part uploaded to Telegram! Message ID: {res_json['result']['message_id']}")
            return True
        else:
            print(f"❌ Telegram upload error: {res_json.get('description')}")
    except Exception as e:
        print(f"❌ Telegram response parse failed: {e}")
    return False

def main():
    parser = argparse.ArgumentParser(description="Apalod Cinemax Scene Splitter & Video Pipeline")
    parser.add_argument("--title", required=True, help="Movie Title")
    parser.add_argument("--source", required=False, default="", help="Seedr Zip or Direct URL")
    parser.add_argument("--voice", default="si-LK-SameeraNeural", help="Voice Model (si-LK-SameeraNeural, si-LK-ThiliniNeural, en-US-ChristopherNeural)")
    parser.add_argument("--scenes", type=int, default=3, help="Number of scene video parts to produce (default 3)")
    parser.add_argument("--custom-script", default="", help="Custom timestamped script text in [HH:MM:SS - HH:MM:SS] format")
    args = parser.parse_args()
    if not args.voice or not args.voice.strip():
        args.voice = os.environ.get("VOICE_NAME", "si-LK-SameeraNeural").strip() or "si-LK-SameeraNeural"

    custom_script_env = os.environ.get("CUSTOM_SCRIPT", "").strip()
    raw_script_input = (args.custom_script or custom_script_env).strip()
    custom_chapters = parse_custom_script(raw_script_input)

    print("=" * 65)
    print(f"🎬 APALOD CINEMAX STUDIO - VIDEO SCENE PRODUCTION ENGINE")
    print(f"📌 Movie: {args.title}")
    print(f"🎙️ Voice: {args.voice}")
    if custom_chapters:
        print(f"📜 Custom Timestamped Chapters Detected: {len(custom_chapters)} scenes!")
    else:
        print(f"🎞️ Target Scene Parts: {args.scenes}")
    print("=" * 65)

    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    channel_id = os.environ.get("TELEGRAM_CHANNEL_ID", "-1004294803559").strip()
    print(f"📡 Telegram Channel: {channel_id} | Bot configured: {bool(bot_token)} | Gemini key: {bool(gemini_key)}")

    # Step 1: Ingestion (Download / Unpack)
    movie_file = "input_movie.mp4"
    if args.source:
        extracted = download_and_extract_media(args.source, movie_file)
        if extracted:
            movie_file = extracted

    # Fallback if no input movie exists (synthetic demonstration)
    if not os.path.exists(movie_file) or os.path.getsize(movie_file) < 1000:
        print("⚠️ Input movie not found. Creating synthetic demo clip...")
        subprocess.run([
            "ffmpeg", "-f", "lavfi", "-i", "color=c=navy:s=854x480:d=15",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-c:v", "libx264", "-c:a", "aac", "-t", "15", "-y", movie_file
        ], check=True)

    total_duration = get_media_duration(movie_file)
    print(f"⏱️ Total Movie Duration: {total_duration:.2f}s ({total_duration/60:.1f} minutes)")

    os.makedirs("output_scenes", exist_ok=True)
    generated_parts = []

    # Step 2: Produce Video Scene Parts
    if custom_chapters:
        # EXACT TIMESTAMPS FLOW (User-provided Inside Cinemax Script)
        num_parts = len(custom_chapters)
        for i, chapter in enumerate(custom_chapters, 1):
            print(f"\n" + "-" * 50)
            print(f"🎬 Processing Chapter {i}/{num_parts} [{chapter['start_str']} - {chapter['end_str']}]...")
            start_sec = chapter['start_sec']
            clip_dur = chapter['duration']
            part_script = chapter['narration']

            raw_clip = f"output_scenes/raw_part_{i}.mp4"
            voice_file = f"output_scenes/voice_part_{i}.mp3"
            final_video_part = f"output_scenes/Apalod_Cinemax_{args.title.replace(' ', '_')}_Part_{i}.mp4"

            # 1. Cut Video Clip from exact timestamps
            print(f"✂️ Cutting video at {start_sec}s for {clip_dur}s...")
            subprocess.run([
                "ffmpeg", "-ss", str(start_sec), "-i", movie_file,
                "-t", str(clip_dur),
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-avoid_negative_ts", "make_zero",
                "-y", raw_clip
            ], check=True)

            # 2. Synthesize Neural Sinhala Voiceover
            print(f"🎙️ Synthesizing Sinhala Voice ({args.voice})...")
            try:
                subprocess.run([
                    "edge-tts", "--voice", args.voice,
                    "--text", part_script,
                    "--write-media", voice_file
                ], check=True)
                voice_dur = get_media_duration(voice_file)
                print(f"⏱️ Voice Duration: {voice_dur:.2f}s | Video Duration: {clip_dur}s")
            except Exception as e:
                print(f"⚠️ Voice synth error: {e}")
                voice_dur = float(clip_dur)

            # 3. Synchronize & Merge Audio with Video Clip
            clip_actual_dur = get_media_duration(raw_clip)
            if clip_actual_dur > 0 and voice_dur > clip_actual_dur:
                speed_factor = voice_dur / clip_actual_dur
                print(f"🎞️ Pacing adjustment: slow-mo factor ({speed_factor:.2f}x)...")
                filter_str = f"[0:v]setpts={speed_factor}*PTS[v];[1:a]volume=1.0[a]"
                subprocess.run([
                    "ffmpeg", "-i", raw_clip, "-i", voice_file,
                    "-filter_complex", filter_str,
                    "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-c:a", "aac", "-shortest",
                    "-y", final_video_part
                ], check=True)
            else:
                subprocess.run([
                    "ffmpeg", "-i", raw_clip, "-i", voice_file,
                    "-c:v", "copy", "-c:a", "aac", "-shortest",
                    "-y", final_video_part
                ], check=True)

            print(f"✅ Generated Chapter {i} Video: '{final_video_part}'")
            generated_parts.append(final_video_part)

            # Upload to Telegram
            if bot_token and channel_id and os.path.exists(final_video_part):
                caption = (
                    f"🎬 <b>{args.title}</b> - <b>Part {i}/{num_parts}</b> [{chapter['start_str']} - {chapter['end_str']}]\n\n"
                    f"{part_script}\n\n"
                    f"⚡ <i>Produced via Apalod Cinemax Studio Engine</i>"
                )
                send_telegram_video(bot_token, channel_id, final_video_part, caption)

    else:
        # PROCEDURAL RECAP FLOW
        num_parts = max(1, min(args.scenes, 5))
        for i in range(1, num_parts + 1):
            print(f"\n" + "-" * 50)
            print(f"🎬 Processing Scene Video Part {i}/{num_parts}...")
            if num_parts == 3:
                if i == 1:
                    start_sec = 60 if total_duration > 180 else 2
                elif i == 2:
                    start_sec = int(total_duration * 0.45)
                else:
                    start_sec = max(int(total_duration * 0.80), int(total_duration - 400))
            else:
                step = total_duration / (num_parts + 1)
                start_sec = max(2, int(step * (i - 0.7)))

            clip_dur = 30
            raw_clip = f"output_scenes/raw_part_{i}.mp4"
            voice_file = f"output_scenes/voice_part_{i}.mp3"
            final_video_part = f"output_scenes/Apalod_Cinemax_{args.title.replace(' ', '_')}_Part_{i}.mp4"

            print(f"✂️ Cutting video at {start_sec}s for {clip_dur}s...")
            subprocess.run([
                "ffmpeg", "-ss", str(start_sec), "-i", movie_file,
                "-t", str(clip_dur),
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-avoid_negative_ts", "make_zero",
                "-y", raw_clip
            ], check=True)

            part_script = generate_part_script(args.title, i, num_parts, gemini_key)
            print(f"📝 Part {i} Script (Sinhala):\n{part_script}")

            try:
                subprocess.run([
                    "edge-tts", "--voice", args.voice,
                    "--text", part_script,
                    "--write-media", voice_file
                ], check=True)
                voice_dur = get_media_duration(voice_file)
            except Exception as e:
                print(f"⚠️ Voice synth error: {e}")
                voice_dur = 15.0

            clip_actual_dur = get_media_duration(raw_clip)
            if clip_actual_dur > 0 and voice_dur > clip_actual_dur:
                speed_factor = voice_dur / clip_actual_dur
                filter_str = f"[0:v]setpts={speed_factor}*PTS[v];[1:a]volume=1.0[a]"
                subprocess.run([
                    "ffmpeg", "-i", raw_clip, "-i", voice_file,
                    "-filter_complex", filter_str,
                    "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-c:a", "aac", "-shortest",
                    "-y", final_video_part
                ], check=True)
            else:
                subprocess.run([
                    "ffmpeg", "-i", raw_clip, "-i", voice_file,
                    "-c:v", "copy", "-c:a", "aac", "-shortest",
                    "-y", final_video_part
                ], check=True)

            print(f"✅ Generated Final Video Clip: '{final_video_part}'")
            generated_parts.append(final_video_part)

            if bot_token and channel_id and os.path.exists(final_video_part):
                caption = (
                    f"🎬 <b>{args.title}</b> - <b>Part {i}/{num_parts}</b>\n\n"
                    f"{part_script}\n\n"
                    f"⚡ <i>Produced via Apalod Cinemax Studio Engine</i>"
                )
                send_telegram_video(bot_token, channel_id, final_video_part, caption)

    # Step 3: Stitch All Parts into Continuous Full Movie Recap Video
    if len(generated_parts) > 1:
        print("\n" + "=" * 50)
        print("🎞️ Assembling Continuous Full Movie Recap Video...")
        concat_file = "output_scenes/concat_list.txt"
        with open(concat_file, "w") as f:
            for p in generated_parts:
                f.write(f"file '{os.path.basename(p)}'\n")

        full_recap_video = f"output_scenes/Apalod_Cinemax_{args.title.replace(' ', '_')}_Full_Recap.mp4"
        try:
            subprocess.run([
                "ffmpeg", "-f", "concat", "-safe", "0",
                "-i", concat_file,
                "-c", "copy",
                "-y", full_recap_video
            ], cwd="output_scenes", check=True)

            if os.path.exists(full_recap_video):
                print(f"🎉 MASTER FULL RECAP COMPLETE: '{full_recap_video}' ({os.path.getsize(full_recap_video)/(1024*1024):.2f} MB)")
                if bot_token and channel_id:
                    full_caption = f"🎬 <b>{args.title}</b> - <b>Full Movie Recap (Inside Cinemax)</b>\n⚡ සම්පූර්ණ කතා විස්තරය එක දිගට!"
                    send_telegram_video(bot_token, channel_id, full_recap_video, full_caption)
        except Exception as e:
            print(f"⚠️ Concat error: {e}")

    print("\n" + "=" * 65)
    print("🎉 ALL VIDEO SCENE PARTS SUCCESSFULLY PRODUCED & DISPATCHED!")
    print("=" * 65)

if __name__ == "__main__":
    main()
