import {
  SystemOverviewResponse, Department, Subject, Student, Faculty, User,
  AttendanceSession, BatchAttendanceSubmissionPayload, AttendanceRosterResponse
} from '../types';

const API_BASE = '/api';

const handleResponse = async (res: Response) => {
  if (!res.ok) {
    let errorDetail = `Request failed with status ${res.status}`;
    try {
      const data = await res.json();
      errorDetail = data.detail || data.message || (typeof data === 'object' ? JSON.stringify(data) : data);
    } catch (e) {
      errorDetail = res.statusText || errorDetail;
    }
    const err = new Error(errorDetail);
    (err as any).status = res.status;
    throw err;
  }
  return res.json();
};

const authHeader = (token?: string | null): Record<string, string> => {
  const activeToken = token || localStorage.getItem('access_token');
  return activeToken ? { Authorization: `Bearer ${activeToken}` } : {};
};

export const api = {
  // Public / Meta APIs
  async getHealth(): Promise<{ status: string; database_connected: boolean; timestamp: string }> {
    const res = await fetch(`${API_BASE}/health/`);
    return handleResponse(res);
  },

  async getSystemOverview(): Promise<SystemOverviewResponse> {
    const res = await fetch(`${API_BASE}/system/overview/`);
    return handleResponse(res);
  },

  // Auth APIs
  async login(username: string, password: string): Promise<any> {
    const res = await fetch(`${API_BASE}/auth/login/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    return handleResponse(res);
  },

  async register(payload: {
    username: string;
    email: string;
    password: string;
    password_confirm: string;
    first_name?: string;
    last_name?: string;
  }): Promise<any> {
    const res = await fetch(`${API_BASE}/auth/register/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  async getMe(token?: string): Promise<{ user: User; permissions: any }> {
    const headers: Record<string, string> = { ...authHeader(token) };
    const res = await fetch(`${API_BASE}/auth/me/`, { headers });
    return handleResponse(res);
  },

  // Admin Protected APIs
  async getAdminDepartments(token?: string): Promise<Department[]> {
    const headers: Record<string, string> = { ...authHeader(token) };
    const res = await fetch(`${API_BASE}/academic/admin/departments/`, { headers });
    const data = await handleResponse(res);
    return Array.isArray(data) ? data : data.results || [];
  },

  async getAdminUsers(token?: string): Promise<User[]> {
    const headers: Record<string, string> = { ...authHeader(token) };
    const res = await fetch(`${API_BASE}/auth/admin/users/`, { headers });
    const data = await handleResponse(res);
    return Array.isArray(data) ? data : data.results || [];
  },

  // Faculty Protected APIs
  async getFacultyAllocations(token?: string): Promise<{ faculty_name: string; faculty_id: string; allocations: any[]; total_active_classes: number }> {
    const headers: Record<string, string> = { ...authHeader(token) };
    const res = await fetch(`${API_BASE}/academic/faculty/my-allocations/`, { headers });
    return handleResponse(res);
  },

  async getFacultyRoster(sectionId: number, token?: string): Promise<{ section_id: number; students_count: number; roster: Student[] }> {
    const headers: Record<string, string> = { ...authHeader(token) };
    const res = await fetch(`${API_BASE}/academic/faculty/roster/${sectionId}/`, { headers });
    return handleResponse(res);
  },

  // Student Protected APIs
  async getStudentProfile(token?: string): Promise<any> {
    const headers: Record<string, string> = { ...authHeader(token) };
    const res = await fetch(`${API_BASE}/academic/student/my-profile/`, { headers });
    return handleResponse(res);
  },

  // General Academic APIs (Authenticated)
  async getDepartments(token?: string): Promise<Department[]> {
    const headers: Record<string, string> = { ...authHeader(token) };
    const res = await fetch(`${API_BASE}/academic/departments/`, { headers });
    const data = await handleResponse(res);
    return Array.isArray(data) ? data : data.results || [];
  },

  async getSubjects(token?: string): Promise<Subject[]> {
    const headers: Record<string, string> = { ...authHeader(token) };
    const res = await fetch(`${API_BASE}/academic/subjects/`, { headers });
    const data = await handleResponse(res);
    return Array.isArray(data) ? data : data.results || [];
  },

  async getStudents(token?: string): Promise<Student[]> {
    const headers: Record<string, string> = { ...authHeader(token) };
    const res = await fetch(`${API_BASE}/academic/students/`, { headers });
    const data = await handleResponse(res);
    return Array.isArray(data) ? data : data.results || [];
  },

  async getFaculty(token?: string): Promise<Faculty[]> {
    const headers: Record<string, string> = { ...authHeader(token) };
    const res = await fetch(`${API_BASE}/academic/faculty/`, { headers });
    const data = await handleResponse(res);
    return Array.isArray(data) ? data : data.results || [];
  },

  // Attendance APIs
  async getAttendanceRoster(
    sectionId: number,
    subjectId: number,
    date?: string,
    token?: string
  ): Promise<AttendanceRosterResponse> {
    const headers: Record<string, string> = { ...authHeader(token) };
    const dateParam = date ? `&date=${encodeURIComponent(date)}` : '';
    const res = await fetch(
      `${API_BASE}/attendance/roster/?section_id=${sectionId}&subject_id=${subjectId}${dateParam}`,
      { headers }
    );
    return handleResponse(res);
  },

  async submitAttendance(
    payload: BatchAttendanceSubmissionPayload,
    token?: string
  ): Promise<{ message: string; session: AttendanceSession; stats: any }> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...authHeader(token),
    };
    const res = await fetch(`${API_BASE}/attendance/record/`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  async getAttendanceHistory(
    params?: { section_id?: number; subject_id?: number; date?: string },
    token?: string
  ): Promise<AttendanceSession[]> {
    const headers: Record<string, string> = { ...authHeader(token) };
    const query = new URLSearchParams();
    if (params?.section_id) query.append('section_id', params.section_id.toString());
    if (params?.subject_id) query.append('subject_id', params.subject_id.toString());
    if (params?.date) query.append('date', params.date);

    const queryString = query.toString() ? `?${query.toString()}` : '';
    const res = await fetch(`${API_BASE}/attendance/history/${queryString}`, { headers });
    const data = await handleResponse(res);
    return Array.isArray(data) ? data : data.results || [];
  },

  async getAttendanceSessionDetail(sessionId: number, token?: string): Promise<AttendanceSession> {
    const headers: Record<string, string> = { ...authHeader(token) };
    const res = await fetch(`${API_BASE}/attendance/sessions/${sessionId}/`, { headers });
    return handleResponse(res);
  },

  async getStudentAttendanceSummary(studentId?: number, token?: string): Promise<any> {
    const headers: Record<string, string> = { ...authHeader(token) };
    const query = studentId ? `?student_id=${studentId}` : '';
    const res = await fetch(`${API_BASE}/attendance/student/my-summary/${query}`, { headers });
    return handleResponse(res);
  },

  async getSectionAttendanceAnalytics(sectionId: number, subjectId?: number, token?: string): Promise<any> {
    const headers: Record<string, string> = { ...authHeader(token) };
    const query = subjectId ? `?subject_id=${subjectId}` : '';
    const res = await fetch(`${API_BASE}/attendance/analytics/section/${sectionId}/${query}`, { headers });
    return handleResponse(res);
  },

  // Phase 8: Unified Role-Based Dashboards
  async getAdminDashboard(threshold?: number, token?: string): Promise<any> {
    const headers: Record<string, string> = { ...authHeader(token) };
    const query = threshold ? `?threshold=${threshold}` : '';
    const res = await fetch(`${API_BASE}/attendance/dashboard/admin/${query}`, { headers });
    return handleResponse(res);
  },

  async getFacultyDashboard(threshold?: number, token?: string): Promise<any> {
    const headers: Record<string, string> = { ...authHeader(token) };
    const query = threshold ? `?threshold=${threshold}` : '';
    const res = await fetch(`${API_BASE}/attendance/dashboard/faculty/${query}`, { headers });
    return handleResponse(res);
  },

  async getStudentDashboard(studentId?: number, threshold?: number, token?: string): Promise<any> {
    const headers: Record<string, string> = { ...authHeader(token) };
    const params = new URLSearchParams();
    if (studentId) params.append('student_id', studentId.toString());
    if (threshold) params.append('threshold', threshold.toString());
    const query = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/attendance/dashboard/student/${query}`, { headers });
    return handleResponse(res);
  },

  // Phase 7: Correction Workflow
  async getCorrections(params?: { status?: string; record_id?: number }, token?: string): Promise<any> {
    const headers: Record<string, string> = { ...authHeader(token) };
    const query = new URLSearchParams();
    if (params?.status) query.append('status', params.status);
    if (params?.record_id) query.append('record_id', params.record_id.toString());
    const qStr = query.toString() ? `?${query.toString()}` : '';
    const res = await fetch(`${API_BASE}/attendance/corrections/${qStr}`, { headers });
    return handleResponse(res);
  },

  async submitCorrection(payload: { record_id: number; requested_status: string; reason: string; document_url?: string }, token?: string): Promise<any> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...authHeader(token),
    };
    const res = await fetch(`${API_BASE}/attendance/corrections/`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  async approveCorrection(id: number, reviewNotes?: string, token?: string): Promise<any> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...authHeader(token),
    };
    const res = await fetch(`${API_BASE}/attendance/corrections/${id}/approve/`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ review_notes: reviewNotes || '' }),
    });
    return handleResponse(res);
  },

  async rejectCorrection(id: number, reviewNotes?: string, token?: string): Promise<any> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...authHeader(token),
    };
    const res = await fetch(`${API_BASE}/attendance/corrections/${id}/reject/`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ review_notes: reviewNotes || '' }),
    });
    return handleResponse(res);
  },

  async getRecordAuditLogs(recordId: number, token?: string): Promise<any> {
    const headers: Record<string, string> = { ...authHeader(token) };
    const res = await fetch(`${API_BASE}/attendance/records/${recordId}/audit-logs/`, { headers });
    return handleResponse(res);
  }
};

