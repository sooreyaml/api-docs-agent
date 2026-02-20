/**
 * TypeScript types for GET /api/agent-docs, POST /api-reference/generate-example,
 * and POST /api/try-it-out.
 */

/** One parameter (query, path, header) */
export interface DocsParameter {
  name: string;
  in: string;
  required: boolean;
  description: string;
  type: string;
  example: string | number | boolean | null;
}

/** Schema summary for request/response body */
export interface DocsSchemaProperty {
  name: string;
  type: string;
  required: boolean;
  description: string;
  example: string | number | boolean | null;
}

export interface DocsSchema {
  type: string;
  properties?: DocsSchemaProperty[];
  $ref?: string;
}

/** Request body for an endpoint */
export interface DocsRequestBody {
  description: string;
  schema: DocsSchema | null;
}

/** One response (status code + description + optional body schema) */
export interface DocsResponse {
  code: string;
  description: string;
  body_schema?: DocsSchema | null;
}

/** "How to call" summary for an endpoint */
export interface DocsHowToCall {
  full_url: string;
  needs_auth: boolean;
  has_body: boolean;
}

/** One endpoint in a tag */
export interface DocsEndpoint {
  endpoint_id: string;
  path: string;
  method: string;
  summary: string;
  description: string;
  how_to_call: DocsHowToCall;
  parameters: DocsParameter[];
  request_body_schema: DocsRequestBody | null;
  example_body: Record<string, unknown> | null;
  responses: DocsResponse[];
}

/** One tag (module) with its endpoints */
export interface DocsTag {
  name: string;
  endpoints: DocsEndpoint[];
}

/** Stack option for "Implement in your stack" */
export interface DocsStack {
  value: string;
  label: string;
}

/** Response of GET /api/agent-docs */
export interface AgentDocsResponse {
  title: string;
  version: string;
  description: string;
  /** LLM-generated introduction when OPENAI_API_KEY is set; use for overview section. */
  overview_summary?: string;
  /** Use this for "how to call" URLs and for POST /api-reference/generate-example base_url. Do NOT prefix with /agent-docs. */
  base_url: string;
  tags: DocsTag[];
  stacks: DocsStack[];
}

/** Body for POST /api-reference/generate-example */
export interface GenerateExampleRequest {
  path: string;
  method: string;
  stack: string;
  /** API base URL (same as AgentDocsResponse.base_url). Required for external API. */
  base_url?: string | null;
  /** When documenting an external API, pass the same URL used in GET /api/agent-docs?openapi_url=... */
  openapi_url?: string | null;
}

/** Response of POST /api-reference/generate-example */
export interface GenerateExampleResponse {
  code: string;
}

/** Body for POST /api/try-it-out */
export interface TryItOutRequest {
  url: string;
  method: string;
  headers: Record<string, string>;
  body?: string | null;
  openapi_url?: string | null;
}

/** Response of POST /api/try-it-out */
export interface TryItOutResponse {
  status_code: number;
  headers: Record<string, string>;
  body: string;
  elapsed_ms: number;
}
