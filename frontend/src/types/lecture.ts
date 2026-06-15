export interface Lecture {
  id: number;
  platform: string;
  title: string;
  instructor_name?: string;
  category?: string;
  price: number;
  rating?: number;
  student_count?: number;
  url?: string;
  thumbnail_url?: string;
  tags?: string[];
  is_free: boolean;
  trust_score?: number;
  roadmap_step?: number | null;
  description?: string;
  curriculum?: string;
  level?: string;
  keywords?: string[];
  reason?: string;
  pros?: string[];
  diff?: string;
  fit_score?: number;
  caution?: string;
}

export interface StepGroup {
  step: number;
  candidates: Lecture[];
}
