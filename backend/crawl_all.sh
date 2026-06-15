#!/bin/bash
# 전체 플랫폼 크롤러 일괄 실행
# PowerShell: wsl -e bash -c "cd /mnt/c/ai_service/backend && bash crawl_all.sh"
# 특정 플랫폼만: bash crawl_all.sh --only inflearn udemy
# 특정 플랫폼부터 재시작: bash crawl_all.sh --from hackers
# 특정 플랫폼 건너뜀: bash crawl_all.sh --skip class101 fastcampus

set -e
cd "$(dirname "$0")"

LOG_DIR="logs"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/crawl_all_${TIMESTAMP}.log"

echo "========================================"
echo " 전체 크롤링 시작: $(date '+%Y-%m-%d %H:%M:%S')"
echo " 로그: $LOG_FILE"
echo "========================================"

python3 scripts/crawl_all.py "$@" 2>&1 | tee "$LOG_FILE"

echo ""
echo "========================================"
echo " 전체 완료: $(date '+%Y-%m-%d %H:%M:%S')"
echo " 로그: $LOG_FILE"
echo "========================================"
