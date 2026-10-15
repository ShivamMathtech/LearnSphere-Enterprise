export type Entity = { id: string; [key: string]: unknown };
export interface Page<T = Entity> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
export interface User {
  id: string;
  name: string;
  email: string;
  institution_id: string | null;
  roles: string[];
  permissions: string[];
  mfa_enabled: boolean;
  verified: boolean;
}
export interface AuthResult {
  access_token: string;
  expires_in: number;
  user: User;
}
export interface Progress {
  completed: number;
  total: number;
  percent: number;
  completed_lesson_ids: string[];
  last_lesson_id: string | null;
  eligible: boolean;
  remaining: string[];
}
export interface Lesson extends Entity {
  title: string;
  kind: string;
  content?: string;
  url?: string;
  section_id: string;
  position: number;
  duration_minutes: number;
  prerequisite_id: string | null;
  drip_days: number;
  file_ids?: string[];
}
export interface Section extends Entity {
  title: string;
  position: number;
  lessons: Lesson[];
}
export interface Enrollment extends Entity {
  user_id: string;
  course_id: string;
  status: string;
  course_title?: string;
  student_name?: string;
  progress?: Progress;
}
export interface Course extends Entity {
  title: string;
  slug: string;
  description: string;
  objectives: string;
  prerequisites: string;
  status: string;
  difficulty: string;
  estimated_minutes: number;
  enrollment_policy: string;
  max_learners: number;
  version: number;
  visibility: string;
  require_assessments: boolean;
  sections?: Section[];
  enrollment?: Enrollment | null;
  progress?: Progress;
  can_author?: boolean;
  instructors?: (Entity & { name: string })[];
}
export interface Option {
  id: string;
  text: string;
  correct?: boolean;
}
export interface Question extends Entity {
  prompt: string;
  kind: "single" | "multiple" | "boolean" | "short";
  points: number;
  options: Option[];
  explanation?: string;
}
export interface Answer {
  id?: string;
  question_id: string;
  value: { selected?: string[]; text?: string };
  marks?: number | null;
  feedback?: string;
}
export interface Attempt extends Entity {
  quiz_id: string;
  quiz_title: string;
  user_id: string;
  status: string;
  deadline: string;
  server_time: string;
  score: number | null;
  max_score: number;
  result_released: boolean;
  questions: Question[];
  answers: Answer[];
  student_name?: string;
}
export interface Assignment extends Entity {
  title: string;
  course_id: string;
  instructions: string;
  due_at: string | null;
  max_marks: number;
  rubric: { id: string; title: string; max_marks: number }[];
  file_ids: string[];
}
export interface Submission extends Entity {
  assignment_id: string;
  assignment_title: string;
  user_id: string;
  student_name: string;
  text: string;
  version: number;
  status: string;
  late: boolean;
  file_ids: string[];
  grade: { marks: number; released: boolean } | null;
  feedback: { text: string }[];
}
export interface DashboardData {
  scope: string;
  metrics: Record<string, number>;
  trend: { date: string; enrollments: number; completions: number }[];
  courses: {
    id: string;
    title: string;
    status: string;
    difficulty: string;
    learners: number;
    progress: number;
  }[];
  deadlines: {
    id: string;
    course_id: string;
    title: string;
    due_at: string;
    kind: string;
  }[];
  activity: Entity[];
}
