import { useQuery } from "@tanstack/react-query";
import { getProfile } from "../api/profile";

export function useProfile(
  collection: string | null,
  opts?: { sampleSize?: number; emitConfig?: boolean },
) {
  return useQuery({
    queryKey: ["profile", collection, opts?.sampleSize, opts?.emitConfig],
    queryFn: () => getProfile(collection!, opts),
    enabled: !!collection,
  });
}
