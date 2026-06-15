# 재부팅 후 재시작 명령어

```bash
cd /mnt/c/ai_service/backend && nohup python3 -m scripts.enrich_lectures > logs/enrich.log 2>&1 &
```

## 진행 상황 확인
```bash
tail -f /mnt/c/ai_service/backend/logs/enrich.log
```

## 완료 건수 확인
```bash
python3 -c "
from dotenv import load_dotenv; load_dotenv()
from app.db.supabase_client import supabase
done = supabase.table('lectures').select('id', count='exact').not_.is_('tags', 'null').neq('platform','youtube').execute().count
total = supabase.table('lectures').select('id', count='exact').neq('platform','youtube').execute().count
print(f'완료: {done}건 / 전체: {total}건 ({done/total*100:.1f}%)')
"
```

## 참고
- 이미 처리된 강의는 자동으로 건너뜀 (이어서 실행됨)
- 완료 시 kkhlhj485@gmail.com 으로 이메일 발송됨
- 전체 9,203건 / 재부팅 시점 기준 약 419건 완료
