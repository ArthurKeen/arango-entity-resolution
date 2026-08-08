import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { KeyRound } from "lucide-react";
import { getAuthToken, setAuthToken } from "../../api/client";

interface AuthTokenControlProps {
  required: boolean;
}

export function AuthTokenControl({ required }: AuthTokenControlProps) {
  const queryClient = useQueryClient();
  const [token, setToken] = useState(() => getAuthToken() ?? "");
  const [saved, setSaved] = useState(Boolean(getAuthToken()));

  if (!required) return null;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAuthToken(token);
    setSaved(Boolean(token.trim()));
    void queryClient.invalidateQueries();
  }

  return (
    <form
      onSubmit={submit}
      className="flex items-center gap-1.5"
      aria-label="API authentication"
    >
      <KeyRound
        className={`h-4 w-4 ${saved ? "text-emerald-600" : "text-amber-600"}`}
        aria-hidden="true"
      />
      <label htmlFor="api-auth-token" className="sr-only">
        API token
      </label>
      <input
        id="api-auth-token"
        type="password"
        autoComplete="current-password"
        value={token}
        onChange={(event) => {
          setToken(event.target.value);
          setSaved(false);
        }}
        placeholder="API token"
        className="w-32 rounded-md border border-gray-300 bg-white px-2 py-1 text-xs text-gray-900 placeholder:text-gray-400 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
      />
      <button
        type="submit"
        className="rounded-md bg-gray-900 px-2 py-1 text-xs font-medium text-white hover:bg-gray-700 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-white"
      >
        {saved ? "Saved" : "Connect"}
      </button>
    </form>
  );
}
