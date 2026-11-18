/* Generated from dataagent-contracts. Do not edit. */

export type EntityType = string;
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions = {
  [k: string]: unknown;
} | null;
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
export type EntityType1 = string;
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions2 = {
  [k: string]: unknown;
} | null;
export type Id = string;
export type IdentityFields1 = string[];
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions3 = {
  [k: string]: unknown;
} | null;
export type ObjectConcept = string;
/**
 * @minItems 2
 */
export type Roles = [string, string, ...string[]];
export type SubjectConcept = string;
export type Revision = string;

/**
 * A versioned domain ontology: one or more concepts plus relations.
 *
 * A definition carries either ``concepts`` (concept name → definition) or
 * the legacy single-concept fields ``entity_type`` / ``properties`` /
 * ``identity_fields``; the legacy shape names its only concept after the
 * entity type and serializes exactly as before, so stored revisions keep
 * their bytes.  Relation values may stay bare ordered role lists (legacy);
 * a multi-concept definition must give every relation explicit endpoint
 * concepts and direction (subject → object).
 */
export interface OntologyRevision {
  concepts?: Concepts;
  entity_type?: EntityType1;
  extensions?: Extensions2;
  id: Id;
  identity_fields?: IdentityFields1;
  properties?: Properties1;
  relations?: Relations;
  revision: Revision;
}
export interface Concepts {
  [k: string]: ConceptDefinition;
}
/**
 * One concept of a domain ontology: its entities, attributes and identity.
 */
export interface ConceptDefinition {
  entity_type: EntityType;
  extensions?: Extensions;
  identity_fields: IdentityFields;
  properties: Properties;
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
export interface Properties1 {
  [k: string]: PropertyDefinition;
}
export interface Relations {
  [k: string]: string[] | RelationDefinition;
}
/**
 * A directed relation between two concepts with ordered role names.
 */
export interface RelationDefinition {
  extensions?: Extensions3;
  object_concept?: ObjectConcept;
  roles: Roles;
  subject_concept?: SubjectConcept;
}
