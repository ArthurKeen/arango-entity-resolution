import { PipelineHistory } from "../pipeline/PipelineHistory";

export function RecentRuns() {
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5">
      <h3 className="mb-4 text-sm font-medium text-gray-700 dark:text-gray-200">
        Recent Pipeline Runs
      </h3>
      <PipelineHistory limit={5} />
    </div>
  );
}
