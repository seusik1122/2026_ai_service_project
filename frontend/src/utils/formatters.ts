export function formatPrice(price: number): string {
  if (price === -1) return "가격 확인 필요";
  if (price === 0) return "무료";
  return `${price.toLocaleString()}원`;
}

export function formatDday(dDay: number): string {
  if (dDay === 0) return "D-Day";
  if (dDay > 0) return `D-${dDay}`;
  return `D+${Math.abs(dDay)}`;
}
