export interface SocraticOption {
  id: string;
  text: string;
}

export interface Layer2Branch {
  layer_2_question: string;
  layer_2_options: SocraticOption[];
}

export interface McqBranch {
  layer_1_question: string;
  layer_1_options: SocraticOption[];
  layer_2_branches: Record<string, Layer2Branch>;
  layer_3_question: string;
  layer_3_options: SocraticOption[];
}

export interface SocraticAssessment {
  question_text: string;
  options: Record<string, string>;
  correct_option: string;
  option_feedback?: Record<string, string>;
  socratic_tree: Record<string, McqBranch>;
  reasoning_feedback?: Record<string, string>;
  topper_path: string[];
  topper_explanation: string;
}

export interface TreeNode {
  id: string;
  heading: string;
  is_completed: boolean;
}

export interface TreeEdge {
  source: string;
  target: string;
}

export interface TreeResponse {
  nodes: TreeNode[];
  edges: TreeEdge[];
}

export interface GenerateAssessmentResponse {
  node_id: string;
  heading: string;
  full_chunk_text: string;
  socratic_assessment: SocraticAssessment;
}

export interface UploadResponse {
  session_id: string;
  status: string;
  node_count: number;
}

export type McqKey = "A" | "B" | "C" | "D";

export type Step =
  | "idle"
  | "loading"
  | "mcq"
  | "layer_1"
  | "layer_2"
  | "layer_3"
  | "complete"
  | "error";
