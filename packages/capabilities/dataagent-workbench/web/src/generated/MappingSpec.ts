/* Generated from dataagent-contracts. Do not edit. */

/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions = {
  [k: string]: unknown;
} | null;
export type SourceField = string;
export type Transform =
  "identity" | "decimal" | "minor_to_major" | "integer" | "date" | "datetime" | "enum" | "combine" | "choose";
export type Concept = string;
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions1 = {
  [k: string]: unknown;
} | null;
export type Id = string;
export type IdentityStrategy = string;
export type OntologyRevision = string;
export type Revision = string;
export type Scope = string;
export type SourceFingerprint = string;
export type ValidationRef = string | null;

export interface MappingSpec {
  bindings: Bindings;
  concept?: Concept;
  extensions?: Extensions1;
  id: Id;
  identity_strategy?: IdentityStrategy;
  ontology_revision: OntologyRevision;
  relation_bindings?: RelationBindings;
  revision: Revision;
  scope?: Scope;
  source_fingerprint: SourceFingerprint;
  unmapped?: Unmapped;
  validation_ref?: ValidationRef;
}
export interface Bindings {
  [k: string]: FieldBinding;
}
export interface FieldBinding {
  extensions?: Extensions;
  options?: Options;
  source_field: SourceField;
  transform?: Transform;
}
export interface Options {
  [k: string]: unknown;
}
export interface RelationBindings {
  [k: string]: {
    [k: string]: FieldBinding;
  };
}
export interface Unmapped {
  [k: string]: "extension" | "unresolved" | "exclude";
}
