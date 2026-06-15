import { useMutation } from "@tanstack/react-query";
import { fetchRecommendation, RecommendResponse } from "../api/recommend";

export function useRecommend() {
  const mutation = useMutation<RecommendResponse, Error, { question: string; limit?: number }>({
    mutationFn: fetchRecommendation,
  });
  return { ...mutation, stage: mutation.isPending ? "loading" : "done" };
}
