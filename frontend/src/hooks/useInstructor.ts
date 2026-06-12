import { useQuery } from "@tanstack/react-query";
import { fetchInstructor } from "../api/instructors";

export function useInstructor(name: string) {
  return useQuery({
    queryKey: ["instructor", name],
    queryFn: () => fetchInstructor(name),
    enabled: !!name,
  });
}
