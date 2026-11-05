#!/bin/sh
# 포터블 zip 만들기(내부에서 ./build.sh로 먼저 빌드). 사용: ./package.sh [버전]
cd "$(dirname "$0")" || exit 1
./build.sh || exit 1
V=${1:-0.1.0}
mkdir -p release
python3 - "$V" <<'PY' || exit 1
import sys, zipfile
out = f"release/PhotoAI-{sys.argv[1]}-portable.zip"
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.write("dist/PhotoAI.exe", "PhotoAI/PhotoAI.exe")
print("포터블:", out)
PY
