interface ReviewFiltersProps {
  status: string;
  onStatusChange: (status: string) => void;
  minScore: string;
  onMinScoreChange: (v: string) => void;
  maxScore: string;
  onMaxScoreChange: (v: string) => void;
  source: string;
  onSourceChange: (source: string) => void;
}

const selectClass =
  "rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-2.5 py-1.5 text-sm text-gray-700 dark:text-gray-200 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500";

const inputClass =
  "w-20 rounded-md border border-gray-300 dark:border-gray-600 px-2 py-1.5 text-sm text-gray-700 dark:text-gray-200 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500";

export function ReviewFilters({
  status,
  onStatusChange,
  minScore,
  onMinScoreChange,
  maxScore,
  onMaxScoreChange,
  source,
  onSourceChange,
}: ReviewFiltersProps) {
  return (
    <div className="flex flex-wrap items-end gap-4">
      <label className="space-y-1">
        <span className="block text-xs font-medium text-gray-500 dark:text-gray-400">Status</span>
        <select
          value={status}
          onChange={(e) => onStatusChange(e.target.value)}
          className={selectClass}
        >
          <option value="">All</option>
          <option value="match">Match</option>
          <option value="no_match">No Match</option>
        </select>
      </label>

      <label className="space-y-1">
        <span className="block text-xs font-medium text-gray-500 dark:text-gray-400">Min Score</span>
        <input
          type="number"
          step="0.05"
          min="0"
          max="1"
          placeholder="0.00"
          value={minScore}
          onChange={(e) => onMinScoreChange(e.target.value)}
          className={inputClass}
        />
      </label>

      <label className="space-y-1">
        <span className="block text-xs font-medium text-gray-500 dark:text-gray-400">Max Score</span>
        <input
          type="number"
          step="0.05"
          min="0"
          max="1"
          placeholder="1.00"
          value={maxScore}
          onChange={(e) => onMaxScoreChange(e.target.value)}
          className={inputClass}
        />
      </label>

      <label className="space-y-1">
        <span className="block text-xs font-medium text-gray-500 dark:text-gray-400">Source</span>
        <select
          value={source}
          onChange={(e) => onSourceChange(e.target.value)}
          className={selectClass}
        >
          <option value="">All</option>
          <option value="llm">LLM Only</option>
          <option value="human">Human Only</option>
        </select>
      </label>
    </div>
  );
}
