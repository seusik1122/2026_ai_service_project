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
