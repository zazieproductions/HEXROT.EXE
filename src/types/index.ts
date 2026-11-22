export type Page = 'autopsy' | 'metadata' | 'mutator' | 'decoder' | 'differential' | 'crash' | 'evidence';

export interface Chunk {
  id: string; name: string; offset: number; end: number; declared_size: number; actual_size: number;
  kind: string; status: string; detail: string; audio_offset?: number;
}
export interface Warning { severity: string; message: string; offset: number | null }
export interface Heuristic { kind: string; detail: string; offset: number | null }
export interface MetadataField { key: string; value: string; source: string; offset: number | null; byte_length: number; truncated: boolean }
export interface Analysis {
  filename: string; size: number; sha256: string; magic: string; format: string; extension: string;
  extension_mismatch: boolean; facts: { container: string; codec: string | null; sample_rate: number | null;
    channels: number | null; bit_depth: number | null; duration: number | null; block_align?: number };
  chunks: Chunk[]; metadata: MetadataField[]; artwork: {source:string; mime:string; byte_length:number; sha256:string}[];
  warnings: Warning[]; heuristics: Heuristic[]; trailing_bytes: number;
}
export interface Edit { offset:number; old_length:number; new_length:number; before_hex:string; after_hex:string; before_sha256:string; after_sha256:string; preview_truncated:boolean; description:string }
export interface Mutation { strategy:string; seed:number; index:number; region:string; size_limit:number|null; metadata_size:number; edits:Edit[]; original_sha256:string; sha256:string }
export interface MutationManifest { session_id:string; seed:number; count_requested:number; count_generated:number; deduplicated:boolean;
  strategies:string[]; max_file_size:number|null; metadata_size:number; region:string; original_sha256:string | null; output_hashes:string[] }
export interface MutationResponse { files:FileRecord[]; manifest:MutationManifest }
export interface FileRecord { id:string; session_id:string; name:string; kind:string; created_at:string; analysis:Analysis; mutation:Mutation | null }
export interface Session { id:string; name:string; created_at:string; file_count?:number }
export interface Tool { id:string; label:string; available:boolean; version:string | null }
export interface IsolationStatus { available:boolean; mechanism:string; reason:string; egress?:'blocked'|'unavailable' }
export interface Health { status:string; version:string; isolation:IsolationStatus; decoders:Tool[]; limits:{max_file_size:number|null; max_mutations:number; strategies?:string[]} }
export interface RunResult { decoder:string; version:string | null; invocation:string[]; sandbox_invocation:string[]; exit_code:number | null;
  sandbox_exit_code:number; infrastructure_error:string | null; resource_exceeded:string | null; accepted:boolean | null; abnormal:boolean; signal:number | null; stdout:string; stderr:string; stdout_truncated:boolean; stderr_truncated:boolean;
  duration_seconds:number; timed_out:boolean; canceled:boolean; peak_memory_bytes:number | null; cpu_seconds:number; duration:number | null;
  channels:number | null; sample_rate:number | null; output_sha256:string | null; repeat:number;
  limits:{timeout_seconds:number; memory_mb:number; output_bytes:number} }
export interface Run { id:string; job_id:string; session_id:string; file_id:string; decoder:string; created_at:string; result:RunResult }
export interface Job { id:string; session_id:string; status:string; total:number; completed:number; created_at:string; error:string | null; worker_pid?:number | null; config:Record<string,unknown> }
export interface TriageMinimizationResult { dropped_edit_index:number; dropped_edit_description:string; still_crashes:boolean | null;
  exit_code:number | null; signal:number | null; note?:string }
export interface TriageMinimization { method:string; skipped?:boolean; edit_count:number; edits_tested?:number; expected_signal?:number;
  critical_edits?:TriageMinimizationResult[]; results?:TriageMinimizationResult[]; note:string }
export interface Triage { id:string; run_id:string; created_at:string; result:{reproducible:boolean; note:string; reproduction:string[];
  reproduction_command?:string; minimization?:TriageMinimization | null; [key:string]:unknown} }
export interface Detail { session:Session; files:FileRecord[]; jobs:Job[]; runs:Run[]; triage:Triage[] }
export interface Finding { classification:string; detail:string }
export interface Comparison { file_id:string; filename:string; findings:Finding[]; runs:Run[] }
export interface CompareBytes { offset:number; original:string; mutated:string; original_size:number; mutated_size:number; changed_offsets:number[]; alignment:string }
