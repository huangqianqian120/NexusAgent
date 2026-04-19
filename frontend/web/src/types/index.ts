// Protocol types matching backend FrontendRequest and BackendEvent

export type FrontendRequest =
  | { type: 'submit_line'; line: string }
  | { type: 'permission_response'; request_id: string; allowed: boolean }
  | { type: 'question_response'; request_id: string; answer: string }
  | { type: 'list_sessions' }
  | { type: 'select_command'; command: string }
  | { type: 'apply_select_command'; command: string; value: string }
  | { type: 'clear_session' }
  | { type: 'shutdown' };

export type BackendEventType =
  | 'ready'
  | 'state_snapshot'
  | 'tasks_snapshot'
  | 'transcript_item'
  | 'compact_progress'
  | 'assistant_delta'
  | 'assistant_complete'
  | 'line_complete'
  | 'tool_started'
  | 'tool_completed'
  | 'clear_transcript'
  | 'modal_request'
  | 'select_request'
  | 'todo_update'
  | 'plan_mode_change'
  | 'swarm_status'
  | 'error'
  | 'shutdown';

export interface TranscriptItem {
  role: 'system' | 'user' | 'assistant' | 'tool' | 'tool_result' | 'log';
  text: string;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  is_error?: boolean;
  timestamp?: number;
}

export interface TaskSnapshot {
  id: string;
  type: string;
  status: string;
  description: string;
  metadata: Record<string, string>;
}

export interface SelectOption {
  value: string;
  label: string;
  description?: string;
  active?: boolean;
}

export interface Modal {
  kind: 'select' | 'permission' | 'question' | 'mcp_auth';
  title?: string;
  command?: string;
  request_id?: string;
  tool_name?: string;
  reason?: string;
  question?: string;
}

export interface BackendEvent {
  type: BackendEventType;
  select_options?: SelectOption[];
  message?: string;
  item?: TranscriptItem;
  state?: AppState;
  tasks?: TaskSnapshot[];
  mcp_servers?: McpServerStatus[];
  bridge_sessions?: BridgeSession[];
  commands?: string[];
  modal?: Modal;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  output?: string;
  is_error?: boolean;
  compact_phase?: string;
  compact_trigger?: string;
  attempt?: number;
  compact_checkpoint?: string;
  compact_metadata?: Record<string, unknown>;
  todo_markdown?: string;
  plan_mode?: string;
  swarm_teammates?: unknown[];
  swarm_notifications?: unknown[];
}

export interface AppState {
  model: string;
  cwd: string;
  provider: string;
  auth_status: string;
  base_url: string;
  permission_mode: string;
  theme: string;
  vim_enabled: boolean;
  voice_enabled: boolean;
  voice_available: boolean;
  voice_reason?: string;
  fast_mode: boolean;
  effort: string;
  passes: number;
  mcp_connected: number;
  mcp_failed: number;
  bridge_sessions: unknown[];
  output_style: string;
  keybindings: Record<string, string>;
}

export interface McpServerStatus {
  name: string;
  state: string;
  detail: string;
  transport: string;
  auth_configured: boolean;
  tool_count: number;
  resource_count: number;
}

export interface BridgeSession {
  session_id: string;
  command: string;
  cwd: string;
  pid: number;
  status: string;
  started_at: string;
  output_path: string;
}

export interface SelectRequest {
  title: string;
  command: string;
  options: SelectOption[];
}

export interface PermissionRequest {
  request_id: string;
  tool_name: string;
  reason: string;
}

export interface QuestionRequest {
  request_id: string;
  question: string;
}
