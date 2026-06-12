import { useQuery } from "@tanstack/react-query";
import { fetchExams } from "../api/exams";

export function useExams(params: { keyword?: string; d_day_within?: number }) {
  return useQuery({
    queryKey: ["exams", params],
    queryFn: () => fetchExams(params),
  });
}
