import client from "./client";
import { Lecture } from "../types/lecture";

interface LectureParams {
  keyword?: string;
  category?: string;
  is_free?: boolean;
  platform?: string;
  sort?: string;
  limit?: number;
}

export async function fetchLectures(params: LectureParams): Promise<{ total: number; lectures: Lecture[] }> {
  const resp = await client.get("/api/lectures", { params });
  return resp.data;
}

export interface LectureDetail {
  lecture: Lecture;
  instructor: {
    name: string;
    platform: string;
    trust_score?: number;
    review_count?: number;
    positive_ratio?: number;
  } | null;
  reviews: {
    id: string;
    content: string;
    sentiment?: string;
    sentiment_score?: number;
    collected_at?: string;
  }[];
}

export async function fetchLectureDetail(id: number): Promise<LectureDetail> {
  const resp = await client.get(`/api/lectures/${id}/detail`);
  return resp.data;
}

export async function fetchWhyRecommend(id: number, question: string): Promise<{ reason: string }> {
  const resp = await client.post(`/api/lectures/${id}/why`, { question });
  return resp.data;
}
