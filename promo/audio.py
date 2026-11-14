"""宣传视频的背景音乐：使用你自己提供的音乐文件（例如官方 OST），截取、淡入淡出后合进视频。"""
from __future__ import annotations

import subprocess


def mux_music(video, music, out, ffmpeg, dur, start=0.0, volume_db=-3.0, fade_in=1.0, fade_out=2.0):
    """把音乐从 start 秒开始截取 dur 秒，淡入淡出，作为视频的音轨（视频画面不重新编码）"""
    af = (f"atrim=start={start}:duration={dur},asetpts=PTS-STARTPTS,"
          f"afade=t=in:st=0:d={fade_in},afade=t=out:st={max(0.0, dur - fade_out)}:d={fade_out},"
          f"volume={volume_db}dB")
    subprocess.run([ffmpeg, "-v", "error", "-y", "-i", video, "-i", music, "-filter_complex", f"[1:a]{af}[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                    "-movflags", "+faststart", out], check=True)
