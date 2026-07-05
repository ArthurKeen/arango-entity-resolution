import { useNavigate } from "react-router-dom";
import { Table2, Wand2 } from "lucide-react";
import { useSelectedCollection } from "../contexts/CollectionContext";
import { useProfile } from "../hooks/useProfile";
import { LoadingSpinner } from "../components/shared/LoadingSpinner";
import { EmptyState } from "../components/shared/EmptyState";

const TYPE_COLORS: Record<string, string> = {
  email: "bg-blue-50 text-blue-700",
  phone: "bg-purple-50 text-purple-700",
  date: "bg-teal-50 text-teal-700",
  numeric: "bg-amber-50 text-amber-700",
  id: "bg-gray-100 text-gray-700",
  person_name: "bg-green-50 text-green-700",
  org_name: "bg-emerald-50 text-emerald-700",
  address: "bg-orange-50 text-orange-700",
  free_text: "bg-slate-100 text-slate-600",
  short_string: "bg-indigo-50 text-indigo-700",
};

export function ProfilePage() {
  const { selectedCollection } = useSelectedCollection();
  const navigate = useNavigate();
  const { data, isLoading, error } = useProfile(selectedCollection, {
    emitConfig: true,
  });

  if (!selectedCollection) {
    return (
      <EmptyState
        icon={Table2}
        title="No collection selected"
        description="Select a collection from the sidebar to profile its fields."
      />
    );
  }

  if (isLoading) return <LoadingSpinner className="py-24" size="lg" />;

  if (error) {
    return (
      <EmptyState
        icon={Table2}
        title="Error profiling collection"
        description={error instanceof Error ? error.message : "An error occurred"}
      />
    );
  }

  const fields = data ? Object.entries(data.fields) : [];

  const handleGenerateConfig = () => {
    const sim = data?.config?.similarity;
    if (!sim) return;
    const weightFields = Object.entries(sim.field_weights).map(([field, weight]) => ({
      field,
      weight,
    }));
    const generatedConfig = {
      collection_name: selectedCollection,
      entity_type: selectedCollection,
      blocking: { fields: Object.keys(sim.field_weights).slice(0, 3) },
      similarity: { algorithm: sim.algorithm, fields: weightFields },
    };
    navigate("/config", { state: { generatedConfig } });
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">Data Profile</h1>
          <p className="mt-1 text-sm text-gray-500">
            Detected field types, completeness, cardinality, and sample values for{" "}
            <span className="font-medium text-gray-700">{selectedCollection}</span>
            {data ? ` (sampled ${data.sampled_docs} docs)` : ""}.
          </p>
        </div>
        <button
          onClick={handleGenerateConfig}
          disabled={!data?.config}
          className="inline-flex items-center gap-2 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
        >
          <Wand2 className="h-4 w-4" />
          Generate config
        </button>
      </div>

      {fields.length === 0 ? (
        <EmptyState
          icon={Table2}
          title="No fields detected"
          description="The sampled documents had no non-system fields to profile."
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                {["Field", "Type", "Completeness", "Distinct", "Samples"].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {fields.map(([name, f]) => (
                <tr key={name} className="hover:bg-gray-50">
                  <td className="whitespace-nowrap px-4 py-3 font-mono font-medium text-gray-800">
                    {name}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <span
                      className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${
                        TYPE_COLORS[f.type] ?? "bg-gray-100 text-gray-700"
                      }`}
                    >
                      {f.type}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-gray-100">
                        <div
                          className="h-full rounded-full bg-indigo-500"
                          style={{ width: `${Math.round(f.completeness * 100)}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-500">
                        {Math.round(f.completeness * 100)}%
                      </span>
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-gray-600">
                    {f.stats.distinct}
                    <span className="ml-1 text-xs text-gray-400">
                      ({Math.round(f.stats.cardinality * 100)}%)
                    </span>
                  </td>
                  <td className="max-w-xs px-4 py-3 text-gray-500">
                    <span className="line-clamp-1 font-mono text-xs">
                      {f.samples.join(" · ") || "—"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
