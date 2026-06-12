export interface Exam {
  id: number;
  exam_name: string;
  exam_type?: string;
  application_start?: string;
  application_end?: string;
  exam_date?: string;
  result_date?: string;
  d_day?: number;
  related_keywords?: string[];
}
