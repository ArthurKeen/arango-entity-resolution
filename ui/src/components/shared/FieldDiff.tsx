import { cn } from "../../lib/cn";

interface FieldDiffProps {
  fields: {
    label: string;
    valueA: string | null | undefined;
    valueB: string | null | undefined;
  }[];
}

export function FieldDiff({ fields }: FieldDiffProps) {
  return (
    <div className="overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
      <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700 text-sm">
        <thead className="bg-gray-50 dark:bg-gray-900">
          <tr>
            <th className="px-4 py-2 text-left text-xs font-medium tracking-wider text-gray-500 dark:text-gray-400 uppercase">
              Field
            </th>
            <th className="px-4 py-2 text-left text-xs font-medium tracking-wider text-gray-500 dark:text-gray-400 uppercase">
              Value A
            </th>
            <th className="px-4 py-2 text-left text-xs font-medium tracking-wider text-gray-500 dark:text-gray-400 uppercase">
              Value B
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 dark:divide-gray-700 bg-white dark:bg-gray-800">
          {fields.map(({ label, valueA, valueB }) => {
            const differs =
              (valueA ?? "") !== (valueB ?? "") &&
              valueA != null &&
              valueB != null;

            return (
              <tr key={label}>
                <td className="px-4 py-2 font-medium text-gray-700 dark:text-gray-200">
                  {label}
                </td>
                <td
                  className={cn(
                    "px-4 py-2",
                    valueA == null
                      ? "text-gray-400 dark:text-gray-500 italic"
                      : differs
                        ? "bg-amber-50 text-amber-900"
                        : "text-gray-700 dark:text-gray-200",
                  )}
                >
                  {valueA ?? "\u2014"}
                </td>
                <td
                  className={cn(
                    "px-4 py-2",
                    valueB == null
                      ? "text-gray-400 dark:text-gray-500 italic"
                      : differs
                        ? "bg-amber-50 text-amber-900"
                        : "text-gray-700 dark:text-gray-200",
                  )}
                >
                  {valueB ?? "\u2014"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
