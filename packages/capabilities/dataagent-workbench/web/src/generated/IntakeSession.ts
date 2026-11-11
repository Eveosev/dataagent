/* Generated from dataagent-contracts. Do not edit. */

/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions = {
  [k: string]: unknown;
} | null;
export type GoalRef = string;
export type Id = string;
export type Issues = {
  [k: string]: unknown;
}[];
export type JobRef = string;
export type NextActions = string[];
export type Phase = "queued" | "probing" | "needs_input" | "preview" | "saved" | "failed";
export type Revision = string;
export type CredentialBindingRef = string | null;
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions1 = {
  [k: string]: unknown;
} | null;
export type Kind = "file" | "sqlite" | "postgres" | "rest" | "web_ui";
export type LocatorRef = string;
export type SourceId = string;
export type Sources = SourceSelection[];

export interface IntakeSession {
  extensions?: Extensions;
  goal_ref: GoalRef;
  id: Id;
  issues?: Issues;
  job_ref: JobRef;
  next_actions?: NextActions;
  phase?: Phase;
  revision: Revision;
  selected_versions?: SelectedVersions;
  sources: Sources;
}
export interface SelectedVersions {
  [k: string]: string;
}
export interface SourceSelection {
  credential_binding_ref?: CredentialBindingRef;
  extensions?: Extensions1;
  kind: Kind;
  locator_ref: LocatorRef;
  options?: Options;
  requested_scope?: RequestedScope;
  source_id: SourceId;
}
export interface Options {
  [k: string]: unknown;
}
export interface RequestedScope {
  [k: string]: unknown;
}
