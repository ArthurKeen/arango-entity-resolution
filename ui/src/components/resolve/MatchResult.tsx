import { ScoreBadge } from "../shared/ScoreBadge";

interface MatchResultProps {
  rank: number;
  matchKey: string;
  score: number;
  record: Record<string, unknown>;
}

export function MatchResult({
  rank,
  matchKey,
  score,
  record,
}: MatchResultProps) {
  const displayFields = Object.entries(record).filter(
    ([k]) => !k.startsWith("_"),
  );

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 shadow-sm transition-shadow hover:shadow-md">
      <div className="mb-3 flex items-start justify-between">
        <div className="flex items-center gap-3">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-gray-100 dark:bg-gray-800 text-xs font-semibold text-gray-600 dark:text-gray-300">
            #{rank}
          </span>
          <div>
            <p className="text-sm font-semibold text-gray-900 dark:text-gray-100 font-mono">
              {matchKey}
            </p>
          </div>
        </div>
        <ScoreBadge score={score} />
      </div>

      <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2">
        {displayFields.map(([key, value]) => (
          <div key={key} className="flex items-baseline gap-2">
            <dt className="shrink-0 text-xs font-medium text-gray-500 dark:text-gray-400">
              {key}:
            </dt>
            <dd className="truncate text-sm text-gray-800 dark:text-gray-100" title={String(value ?? "")}>
              {value != null ? String(value) : "—"}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
