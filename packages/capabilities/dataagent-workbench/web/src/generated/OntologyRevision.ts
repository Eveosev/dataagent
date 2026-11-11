/* Generated from dataagent-contracts. Do not edit. */

export type EntityType = string;
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions = {
  [k: string]: unknown;
} | null;
export type Id = string;
/**
 * @minItems 1
 */
export type IdentityFields = [string, ...string[]];
export type Description = string;
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions1 = {
  [k: string]: unknown;
} | null;
export type Required = boolean;
export type ValueType = "string" | "decimal" | "integer" | "boolean" | "date" | "datetime" | "reference";
export type Revision = string;

export interface OntologyRevision {
  entity_type: EntityType;
  extensions?: Extensions;
  id: Id;
  identity_fields: IdentityFields;
  properties: Properties;
  relations?: Relations;
  revision: Revision;
}
export interface Properties {
  [k: string]: PropertyDefinition;
}
export interface PropertyDefinition {
  description?: Description;
  extensions?: Extensions1;
  required?: Required;
  value_type: ValueType;
}
export interface Relations {
  [k: string]: string[];
}
