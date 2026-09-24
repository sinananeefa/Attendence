export type Role = 'ADMIN' | 'HOD' | 'FACULTY' | 'MENTOR' | 'STUDENT';

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  role: Role;
  role_display: string;
  phone?: string;
  avatar?: string;
  department?: number | null;
  department_name?: string | null;
  created_at: string;
}

export interface Department {
  id: number;
  code: string;
  name: string;
  created_at: string;
}

export interface Program {
  id: number;
  department: number;
  department_code?: string;
  code: string;
  name: string;
  total_semesters: number;
}

export interface AcademicYear {
  id: number;
  year_label: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
}

export interface Section {
  id: number;
  program: number;
  program_code?: string;
  academic_year: number;
  semester: number;
  name: string;
  mentor?: number | null;
  mentor_name?: string;
}

export interface Subject {
  id: number;
  department: number;
  department_code?: string;
  code: string;
  title: string;
  credits: number;
  semester: number;
  min_attendance_pct: number;
  condonation_min_pct: number;
}

export interface Student {
  id: number;
  roll_number: string;
  registration_number: string;
  full_name: string;
  email: string;
  section: number;
  section_label?: string;
  current_semester: number;
  admission_date: string;
  guardian_name?: string;
  guardian_phone?: string;
}

export interface Faculty {
  id: number;
  employee_id: string;
  full_name: string;
  email: string;
  designation: string;
  department: number;
  department_code?: string;
  qualification?: string;
}

export type AttendanceStatus = 'PRESENT' | 'ABSENT' | 'LATE' | 'ON_DUTY' | 'MEDICAL_LEAVE';
export type SessionStatus = 'DRAFT' | 'SUBMITTED' | 'LOCKED';
export type SessionType = 'REGULAR' | 'LAB' | 'TUTORIAL' | 'REMEDIAL';
export type CorrectionStatus = 'PENDING' | 'APPROVED' | 'REJECTED';
export type AuditAction = 'SESSION_CREATED' | 'SESSION_EDITED' | 'CORRECTION_APPROVED' | 'ADMIN_OVERRIDE';

export interface AttendanceSession {
  id: number;
  timetable_slot?: number | null;
  faculty: number;
  faculty_name?: string;
  section: number;
  section_label?: string;
  subject: number;
  subject_code?: string;
  subject_title?: string;
  session_date: string;
  period_number: number;
  session_type: SessionType;
  status: SessionStatus;
  topic_covered: string;
  is_locked: boolean;
  records_count?: number;
  total_students?: number;
  present_count?: number;
  absent_count?: number;
  late_count?: number;
  on_duty_count?: number;
  medical_count?: number;
  attendance_percentage?: number;
  department_name?: string;
  academic_class_name?: string;
  records?: AttendanceRecord[];
  created_at: string;
}

export interface AttendanceRecord {
  id: number;
  session: number;
  student: number;
  student_roll?: string;
  student_name?: string;
  status: AttendanceStatus;
  status_display?: string;
  remarks?: string;
  marked_at: string;
}

export interface BatchAttendanceSubmissionPayload {
  section_id: number;
  subject_id: number;
  session_date: string;
  period_number: number;
  session_type?: SessionType;
  topic_covered?: string;
  records: Array<{
    student_id: number;
    status: AttendanceStatus;
    remarks?: string;
  }>;
}

export interface AttendanceRosterResponse {
  section: {
    id: number;
    name: string;
    label: string;
    class_name: string;
    department: string;
    semester: number;
  };
  subject: {
    id: number;
    code: string;
    title: string;
    credits: number;
  };
  selected_date: string;
  recorded_periods: number[];
  existing_sessions: Array<{
    id: number;
    period_number: number;
    session_type: SessionType;
    status: SessionStatus;
    created_at: string;
  }>;
  students_count: number;
  students: Array<{
    id: number;
    user_id: number;
    roll_number: string;
    registration_number: string;
    full_name: string;
    email: string;
  }>;
}

export interface AttendanceCorrection {
  id: number;
  record: number;
  student_roll?: string;
  student_name?: string;
  subject_code?: string;
  requested_by: number;
  requested_by_name?: string;
  old_status: AttendanceStatus;
  requested_status: AttendanceStatus;
  reason: string;
  document_url?: string;
  status: CorrectionStatus;
  reviewed_by?: number | null;
  reviewed_by_name?: string | null;
  review_notes?: string;
  created_at: string;
  resolved_at?: string | null;
}

export interface AttendanceAuditLog {
  id: number;
  record: number;
  student_roll?: string;
  action: AuditAction;
  action_display?: string;
  previous_status: string;
  new_status: string;
  changed_by?: number | null;
  changed_by_name?: string;
  reason: string;
  ip_address?: string | null;
  timestamp: string;
}

export interface SystemOverviewResponse {
  architecture_phase: string;
  stats: {
    users_count: number;
    departments_count: number;
    programs_count: number;
    sections_count: number;
    subjects_count: number;
    students_count: number;
    faculty_count: number;
    attendance_sessions_count: number;
    attendance_records_count: number;
    corrections_count: number;
    audit_logs_count: number;
  };
  enums: {
    roles: Array<{ code: Role; label: string }>;
    attendance_statuses: Array<{ code: AttendanceStatus; label: string }>;
    session_statuses: Array<{ code: SessionStatus; label: string }>;
    correction_statuses: Array<{ code: CorrectionStatus; label: string }>;
  };
  statutory_rules: {
    statutory_min_attendance_pct: number;
    condonation_min_pct: number;
    debarment_threshold_pct: number;
    session_edit_grace_hours: number;
  };
}
