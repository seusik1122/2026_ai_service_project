#!/bin/bash
# 딸깍 한 번으로 전체 크롤링 + AI 분석 실행
# 사용법: bash crawl.sh
#         bash crawl.sh --resume      # 실패한 것만 재시도
#         bash crawl.sh --only inflearn hackers

cd "$(dirname "$0")"

LOG_DIR="logs"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
MAIN_LOG="$LOG_DIR/main_$TIMESTAMP.log"

echo "========================================"
echo " 크롤링 시작: $(date)"
echo " 로그: $MAIN_LOG"
echo "========================================"

# venv 자동 활성화 (있으면)
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f "../venv/bin/activate" ]; then
    source ../venv/bin/activate
fi

# 1단계: 전체 크롤러 실행
echo "[1/2] 강의 수집 중..."
python scripts/run_crawlers.py "$@" 2>&1 | tee -a "$MAIN_LOG"
CRAWL_EXIT=${PIPESTATUS[0]}

if [ $CRAWL_EXIT -ne 0 ]; then
    echo "크롤러 오류 발생 (exit=$CRAWL_EXIT). 로그 확인: $MAIN_LOG"
    echo "재시도: bash crawl.sh --resume"
    exit $CRAWL_EXIT
fi

# 2단계: AI 분석 (광고 필터링 + 감성분석 + 신뢰도)
echo ""
echo "[2/2] AI 분석 중 (오래 걸릴 수 있음)..."
python scripts/collect_and_analyze.py 2>&1 | tee -a "$MAIN_LOG"

echo ""
echo "========================================"
echo " 전체 완료: $(date)"
echo " 로그: $MAIN_LOG"
echo "========================================"
