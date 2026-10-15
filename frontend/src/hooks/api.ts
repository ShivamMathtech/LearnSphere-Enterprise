import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { get, send } from "../services/api";
export function useApi<T>(path: string, enabled = true) {
  return useQuery<T>({
    queryKey: [path],
    queryFn: () => get<T>(path),
    enabled,
    retry: 1,
  });
}
export function useAction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      path,
      body,
      method,
    }: {
      path: string;
      body?: unknown;
      method?: string;
    }) => send(path, body, method),
    onSuccess: () => {
      void client.invalidateQueries();
    },
  });
}
