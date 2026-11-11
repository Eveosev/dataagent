/* Generated from dataagent-contracts. Do not edit. */

/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions = {
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
export type Extensions1 = {
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
export type Extensions2 = {
  [k: string]: unknown;
} | null;
export type Kind1 = "pdf_text_span";
export type Page1 = number;
export type CharEnd1 = number;
export type CharStart1 = number;
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions3 = {
  [k: string]: unknown;
} | null;
export type Kind2 = "text_span";
export type UnitRef = string;
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions4 = {
  [k: string]: unknown;
} | null;
export type Kind3 = "json_pointer";
export type Pointer = string;
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions5 = {
  [k: string]: unknown;
} | null;
export type Kind4 = "excel_cell";
export type Range = string;
export type Sheet = string;
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions6 = {
  [k: string]: unknown;
} | null;
export type Field = string;
export type Kind5 = "record_key";
export type Control = string;
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions7 = {
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
export type CompletedPartitions = (number | string)[];
export type Coverage = "full" | "partial" | "sampled" | "unknown";
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions8 = {
  [k: string]: unknown;
} | null;
export type Fields = string[];
export type Code = string;
export type Detail = string;
/**
 * Namespaced vendor extensions. Core logic never interprets this map; unknown top-level fields are still rejected.
 */
export type Extensions9 = {
  [k: string]: unknown;
} | null;
export type Partition = number | string;
export type Gaps = CoverageGap[];
export type Issues = {
  [k: string]: unknown;
}[];
export type Kind7 = string;
export type ObservedAt = string;
export type Records = {
  [k: string]: unknown;
}[];
export type Sampled = boolean;
export type SourceId = string;
export type SourceRevision1 = string;
export type TotalPartitions = number | null;

export interface SourceProfile {
  anchors?: Anchors;
  completed_partitions?: CompletedPartitions;
  coverage: Coverage;
  extensions?: Extensions8;
  fields?: Fields;
  gaps?: Gaps;
  issues?: Issues;
  kind: Kind7;
  metadata?: Metadata;
  observed_at?: ObservedAt;
  records?: Records;
  sampled?: Sampled;
  source_id: SourceId;
  source_revision: SourceRevision1;
  total_partitions?: TotalPartitions;
}
export interface Anchors {
  [k: string]: SourceAnchor[];
}
export interface SourceAnchor {
  extensions?: Extensions;
  extraction_ref?: ExtractionRef;
  selector: Selector;
  source_ref: SourceRef;
  source_revision: SourceRevision;
}
export interface PdfBBoxSelector {
  bbox: Bbox;
  extensions?: Extensions1;
  kind?: Kind;
  page: Page;
  unit?: Unit;
}
export interface PdfTextSpanSelector {
  char_end: CharEnd;
  char_start: CharStart;
  extensions?: Extensions2;
  kind?: Kind1;
  page: Page1;
}
export interface TextSpanSelector {
  char_end: CharEnd1;
  char_start: CharStart1;
  extensions?: Extensions3;
  kind?: Kind2;
  unit_ref: UnitRef;
}
export interface JsonPointerSelector {
  extensions?: Extensions4;
  kind?: Kind3;
  pointer: Pointer;
}
export interface ExcelCellSelector {
  extensions?: Extensions5;
  kind?: Kind4;
  range: Range;
  sheet: Sheet;
}
export interface RecordKeySelector {
  extensions?: Extensions6;
  field: Field;
  keys: Keys;
  kind?: Kind5;
}
export interface Keys {
  [k: string]: unknown;
}
export interface GuiControlSelector {
  control: Control;
  extensions?: Extensions7;
  kind?: Kind6;
  observation_ref: ObservationRef;
  screenshot_ref: ScreenshotRef;
  viewport: Viewport;
}
export interface CoverageGap {
  code: Code;
  detail?: Detail;
  extensions?: Extensions9;
  partition: Partition;
}
export interface Metadata {
  [k: string]: unknown;
}
