#!/bin/sh
# exe 빌드 + 배포 폴더의 DB 초기화(개발 단계). PhotoAI.exe를 닫은 뒤 실행.
cd "$(dirname "$0")" || exit 1
./venv/Scripts/python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name PhotoAI --collect-all customtkinter --collect-all pillow_heif main.py || exit 1
rm -f dist/photoai.db dist/photoai.db-wal dist/photoai.db-shm dist/photoai.db-journal || { echo "빌드는 끝났지만 DB를 지우지 못했습니다(PhotoAI나 DB 툴이 열고 있는지 확인)"; exit 1; }
echo "빌드 완료, dist/photoai.db 초기화"
