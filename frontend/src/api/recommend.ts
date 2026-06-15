import client from "./client";
import { Lecture, StepGroup } from "../types/lecture";

interface RecommendRequest {
  question: string;
  limit?: number;
}

export interface RoadmapStep {
  step: number;
  title: string;
  description: string;
  duration?: string;
  keywords: string[];
  preferred_platforms: string[];
  content_types: string[];
}

export interface RecommendedCert {
  name: string;
  why: string;
  level: string;
  typical_prep_months?: number;
}

export interface Roadmap {
  user_level: string;
  goal: string;
  roadmap: RoadmapStep[];
  recommended_certs?: RecommendedCert[];
}

export interface RecommendResponse {
  question: string;
  roadmap: Roadmap;
  yt_supplements: Lecture[];
  step_groups: StepGroup[];
  total: number;
  lectures: Lecture[];
}

export async function fetchRecommendation(req: RecommendRequest): Promise<RecommendResponse> {
  const resp = await client.post("/api/recommend", req);
  return resp.data;
}

export async function sendRecommendEmail(params: {
  question: string;
  email: string;
  roadmap: Roadmap;
  lectures: Lecture[];
  certs?: RecommendedCert[];
}): Promise<{ status: string; message: string }> {
  const resp = await client.post("/api/recommend/email", params);
  return resp.data;
}
