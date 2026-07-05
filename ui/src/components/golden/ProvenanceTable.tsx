import { Badge } from "../shared/Badge";
import { ScoreBadge } from "../shared/ScoreBadge";

interface ProvenanceEntry {
  source: string;
  strategy?: string;
  confidence: number;
}

interface ProvenanceTableProps {
  provenance: Record<string, ProvenanceEntry>;
}

const strategyVariant = (strategy: string) => {
  switch (strategy) {
    case "consensus":
      return "success" as const;
    case "source_preference":
      return "info" as const;
    case "conflict_resolution":
      return "warning" as const;
    default:
      return "default" as const;
  }
};

export function ProvenanceTable({ provenance }: ProvenanceTableProps) {
  const entries = Object.entries(provenance);

  if (entries.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-gray-400 dark:text-gray-500">
        No provenance data available
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
      <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700 text-sm">
        <thead className="bg-gray-50 dark:bg-gray-900">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium tracking-wider text-gray-500 dark:text-gray-400 uppercase">
              Field
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium tracking-wider text-gray-500 dark:text-gray-400 uppercase">
              Source
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium tracking-wider text-gray-500 dark:text-gray-400 uppercase">
              Strategy
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium tracking-wider text-gray-500 dark:text-gray-400 uppercase">
              Confidence
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 dark:divide-gray-700 bg-white dark:bg-gray-800">
          {entries.map(([field, entry]) => (
            <tr key={field} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
              <td className="whitespace-nowrap px-4 py-2.5 font-medium text-gray-700 dark:text-gray-200">
                {field}
              </td>
              <td className="whitespace-nowrap px-4 py-2.5 text-gray-600 dark:text-gray-300">
                {entry.source}
              </td>
              <td className="whitespace-nowrap px-4 py-2.5">
                {entry.strategy ? (
                  <Badge variant={strategyVariant(entry.strategy)}>
                    {entry.strategy}
                  </Badge>
                ) : (
                  <span className="text-gray-400 dark:text-gray-500">—</span>
                )}
              </td>
              <td className="whitespace-nowrap px-4 py-2.5">
                {entry.confidence > 0 ? (
                  <ScoreBadge score={entry.confidence} />
                ) : (
                  <span className="text-gray-400 dark:text-gray-500">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
