# 큰 녹화 파일을 300MB 조각으로 나눔 (원본은 그대로 둠). 사용: py split_video.py [영상경로]
import os, sys
src = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\admin\Videos\BlueStacks-Pie64_3\Recording-2026-10-24-013013.mp4"
out = r"C:\macro\vidparts"
os.makedirs(out, exist_ok=True)
CH = 300 * 1024 * 1024
base = os.path.splitext(os.path.basename(src))[0]
with open(src, "rb") as f:
    i = 0
    while True:
        b = f.read(CH)
        if not b:
            break
        p = os.path.join(out, f"{base}.part{i}")
        open(p, "wb").write(b)
        print("저장:", p, len(b))
        i += 1
print("완료:", i, "조각")
