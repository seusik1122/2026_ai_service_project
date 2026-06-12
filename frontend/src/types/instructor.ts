import { Review } from "./review";

export interface Instructor {
  name: string;
  platform?: string;
  trust_score?: number;
  positive_ratio?: number;
  review_count?: number;
  last_calculated_at?: string;
  recent_reviews?: Review[];
}
