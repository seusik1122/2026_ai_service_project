import { useQuery, useMutation } from "@tanstack/react-query";
import { fetchLectureDetail, fetchWhyRecommend } from "../api/lectures";

export function useLectureDetail(id: number | null) {
  return useQuery({
    queryKey: ["lectureDetail", id],
    queryFn: () => fetchLectureDetail(id!),
    enabled: id !== null,
    staleTime: 1000 * 60 * 5,
  });
}

export function useWhyRecommend() {
  return useMutation({
    mutationFn: ({ id, question }: { id: number; question: string }) =>
      fetchWhyRecommend(id, question),
  });
}
