import { useQuery } from "@tanstack/react-query";
import { fetchLectures } from "../api/lectures";

export function useLectures(params: {
  keyword?: string;
  category?: string;
  is_free?: boolean;
  platform?: string;
  sort?: string;
  limit?: number;
}) {
  return useQuery({
    queryKey: ["lectures", params],
    queryFn: () => fetchLectures(params),
  });
}
