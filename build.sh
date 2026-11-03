#!/bin/sh
# exe 빌드 + 배포 폴더의 DB 초기화(개발 단계). PhotoAI.exe를 닫은 뒤 실행.
cd "$(dirname "$0")" || exit 1
./venv/Scripts/python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name PhotoAI --collect-all customtkinter --collect-all pillow_heif main.py || exit 1
rm -f dist/photoai.db dist/photoai.db-journal
echo "빌드 완료, dist/photoai.db 초기화"
