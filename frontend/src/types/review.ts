export interface Review {
  id: number;
  instructor_name?: string;
  platform_source: string;
  content: string;
  is_ad: boolean;
  sentiment?: "positive" | "negative" | "neutral";
  sentiment_score?: number;
  original_url?: string;
  collected_at: string;
}
