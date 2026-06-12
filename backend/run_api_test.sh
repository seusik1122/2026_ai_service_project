#!/bin/bash
# FastAPI 서버를 자동으로 띄우고 통합 테스트를 실행한다.

cd "$(dirname "$0")"

echo "▶ FastAPI 서버 시작..."
uvicorn main:app --port 8000 &
SERVER_PID=$!

# 서버가 뜰 때까지 대기 (최대 10초)
for i in $(seq 1 10); do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✔ 서버 준비 완료 (${i}초)"
        break
    fi
    sleep 1
done

echo ""
echo "▶ 통합 테스트 실행..."
pytest tests/test_api_integration.py -v
TEST_EXIT=$?

echo ""
echo "▶ 서버 종료..."
kill $SERVER_PID 2>/dev/null

exit $TEST_EXIT
