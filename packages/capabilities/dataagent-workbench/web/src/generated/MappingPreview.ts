/* Generated from dataagent-contracts. Do not edit. */

export type Digest = string;
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions = {
  [k: string]: unknown;
} | null;
export type Id = string;
export type EntityType = string;
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions1 = {
  [k: string]: unknown;
} | null;
export type Id1 = string;
export type Scope = string;
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions2 = {
  [k: string]: unknown;
} | null;
export type ExtractionRef = string | null;
export type Selector =
  | PdfBBoxSelector
  | PdfTextSpanSelector
  | TextSpanSelector
  | JsonPointerSelector
  | ExcelCellSelector
  | RecordKeySelector
  | GuiControlSelector;
/**
 * @minItems 4
 * @maxItems 4
 */
export type Bbox = [unknown, unknown, unknown, unknown];
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions3 = {
  [k: string]: unknown;
} | null;
export type Kind = "pdf_bbox";
export type Page = number;
export type Unit = "pt";
export type CharEnd = number;
export type CharStart = number;
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions4 = {
  [k: string]: unknown;
} | null;
export type Kind1 = "pdf_text_span";
export type Page1 = number;
export type CharEnd1 = number;
export type CharStart1 = number;
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions5 = {
  [k: string]: unknown;
} | null;
export type Kind2 = "text_span";
export type UnitRef = string;
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions6 = {
  [k: string]: unknown;
} | null;
export type Kind3 = "json_pointer";
export type Pointer = string;
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions7 = {
  [k: string]: unknown;
} | null;
export type Kind4 = "excel_cell";
export type Range = string;
export type Sheet = string;
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions8 = {
  [k: string]: unknown;
} | null;
export type Field = string;
export type Kind5 = "record_key";
export type Control = string;
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions9 = {
  [k: string]: unknown;
} | null;
export type Kind6 = "gui_control";
export type ObservationRef = string;
export type ScreenshotRef = string;
/**
 * @minItems 2
 * @maxItems 2
 */
export type Viewport = [unknown, unknown];
export type SourceRef = string;
export type SourceRevision = string;
export type Unresolved = string[];
export type Instances = EntityInstance[];
export type Issues = {
  [k: string]: unknown;
}[];
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions10 = {
  [k: string]: unknown;
} | null;
export type SourceField = string;
export type Transform =
  "identity" | "decimal" | "minor_to_major" | "integer" | "date" | "datetime" | "enum" | "combine" | "choose";
export type Concept = string;
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions11 = {
  [k: string]: unknown;
} | null;
export type Id2 = string;
export type IdentityStrategy = string;
export type OntologyRevision = string;
export type Revision = string;
export type Scope1 = string;
export type SourceFingerprint = string;
export type ValidationRef = string | null;
export type OntologyRevision1 = string;
export type Revision1 = string;

export interface MappingPreview {
  digest: Digest;
  extensions?: Extensions;
  id: Id;
  instances: Instances;
  issues: Issues;
  mapping: MappingSpec;
  ontology_revision: OntologyRevision1;
  revision: Revision1;
  source_revisions: SourceRevisions;
}
export interface EntityInstance {
  entity_type: EntityType;
  extensions?: Extensions1;
  id: Id1;
  scope: Scope;
  source_anchors?: SourceAnchors;
  unresolved?: Unresolved;
  values: Values;
}
export interface SourceAnchors {
  [k: string]: SourceAnchor[];
}
export interface SourceAnchor {
  extensions?: Extensions2;
  extraction_ref?: ExtractionRef;
  selector: Selector;
  source_ref: SourceRef;
  source_revision: SourceRevision;
}
export interface PdfBBoxSelector {
  bbox: Bbox;
  extensions?: Extensions3;
  kind?: Kind;
  page: Page;
  unit?: Unit;
}
export interface PdfTextSpanSelector {
  char_end: CharEnd;
  char_start: CharStart;
  extensions?: Extensions4;
  kind?: Kind1;
  page: Page1;
}
export interface TextSpanSelector {
  char_end: CharEnd1;
  char_start: CharStart1;
  extensions?: Extensions5;
  kind?: Kind2;
  unit_ref: UnitRef;
}
export interface JsonPointerSelector {
  extensions?: Extensions6;
  kind?: Kind3;
  pointer: Pointer;
}
export interface ExcelCellSelector {
  extensions?: Extensions7;
  kind?: Kind4;
  range: Range;
  sheet: Sheet;
}
export interface RecordKeySelector {
  extensions?: Extensions8;
  field: Field;
  keys: Keys;
  kind?: Kind5;
}
export interface Keys {
  [k: string]: unknown;
}
export interface GuiControlSelector {
  control: Control;
  extensions?: Extensions9;
  kind?: Kind6;
  observation_ref: ObservationRef;
  screenshot_ref: ScreenshotRef;
  viewport: Viewport;
}
export interface Values {
  [k: string]: unknown;
}
export interface MappingSpec {
  bindings: Bindings;
  concept?: Concept;
  extensions?: Extensions11;
  id: Id2;
  identity_strategy?: IdentityStrategy;
  ontology_revision: OntologyRevision;
  relation_bindings?: RelationBindings;
  revision: Revision;
  scope?: Scope1;
  source_fingerprint: SourceFingerprint;
  unmapped?: Unmapped;
  validation_ref?: ValidationRef;
}
export interface Bindings {
  [k: string]: FieldBinding;
}
export interface FieldBinding {
  extensions?: Extensions10;
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
export interface SourceRevisions {
  [k: string]: string;
}
