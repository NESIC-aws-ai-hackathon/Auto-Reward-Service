/**
 * 日付関連のユーティリティ。
 * 日付の境界はユーザー体感に合わせて常にJSTで判断する。
 * （toISOString() はUTC基準のため、日本時間の0〜9時で前日に倒れて
 *   「夜遅くに話したライフログが昨日の日付になる」事故が起きていた。）
 */

export function getJstDateString(date: Date = new Date()): string {
  // UTC+9 にシフトしてから ISO 表現の YYYY-MM-DD 部分を切り出す
  const shifted = new Date(date.getTime() + 9 * 60 * 60 * 1000);
  return shifted.toISOString().slice(0, 10);
}

export function getJstMonthString(date: Date = new Date()): string {
  return getJstDateString(date).slice(0, 7);
}
