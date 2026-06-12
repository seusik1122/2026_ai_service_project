import client from "./client";
import { Exam } from "../types/exam";

export async function fetchExams(params: { keyword?: string; d_day_within?: number }): Promise<{ exams: Exam[] }> {
  const resp = await client.get("/api/exams", { params });
  return resp.data;
}
