import { fetchApi } from "./client";

export interface FieldStats {
  sampled: number;
  distinct: number;
  cardinality: number;
  avg_length: number;
  avg_tokens: number;
}

export interface FieldConfig {
  field: string;
  type: string;
  algorithm: string;
  transformers: string[];
  agreement_threshold: number;
  m_prior: number;
  u_prior: number;
  weight: number;
}

export interface FieldProfile {
  type: string;
  completeness: number;
  stats: FieldStats;
  config: FieldConfig;
  samples: string[];
}

export interface EmittedSimilarityConfig {
  similarity: {
    algorithm: string;
    field_weights: Record<string, number>;
    transformers: Record<string, string[]>;
    agreement_thresholds: Record<string, number>;
    m_priors: Record<string, number>;
    u_priors: Record<string, number>;
  };
}

export interface ProfileResponse {
  collection: string;
  sampled_docs: number;
  fields: Record<string, FieldProfile>;
  config?: EmittedSimilarityConfig;
}

export function getProfile(
  collection: string,
  opts?: { sampleSize?: number; emitConfig?: boolean },
) {
  const search = new URLSearchParams();
  if (opts?.sampleSize) search.set("sample_size", String(opts.sampleSize));
  if (opts?.emitConfig) search.set("emit_config", "true");
  const qs = search.toString();
  return fetchApi<ProfileResponse>(
    `/api/profile/${collection}${qs ? `?${qs}` : ""}`,
  );
}
