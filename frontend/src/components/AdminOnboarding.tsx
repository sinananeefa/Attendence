/**
 * AdminOnboarding — User Account Management & Profile Assignment
 *
 * Provides an institutional administrator with:
 * - A list of all registered user accounts with search + role filter
 * - A "Pending Profiles" badge for accounts that still need academic setup
 * - Inline role assignment (Faculty / HOD / Mentor / Student) with department
 * - A step-by-step Student Profile wizard (roll number, section, semester, dates)
 * - A step-by-step Faculty Profile wizard (employee ID, designation, department)
 * - Account activation / deactivation
 *
 * All validation errors come from the backend and are displayed verbatim
 * in plain language next to the relevant field.
 */

import React, { useEffect, useState, useCallback } from 'react';
import { api } from '../services/api';
import { LoadingSpinner } from './LoadingSpinner';
import {
  Users, UserCheck, UserX, ChevronDown, ChevronUp,
  CheckCircle2, XCircle, AlertTriangle, RefreshCw,
  GraduationCap, BookOpen, Building2, Edit3, ShieldCheck,
  Search, ArrowRight, Loader2, PlusCircle, X, UserPlus
} from 'lucide-react';

// ── Type helpers ─────────────────────────────────────────────────────────────

interface UserRow {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  role: string;
  role_display: string;
  department: number | null;
  department_name: string | null;
  is_active?: boolean;
  phone?: string;
  student_profile?: {
    id: number;
    roll_number: string;
    registration_number: string;
    section_id: number;
    section_name: string | null;
    current_semester: number;
    admission_date: string;
  } | null;
  faculty_profile?: {
    id: number;
    employee_id: string;
    designation: string;
    department_id: number;
    department_name: string | null;
    qualification: string;
  } | null;
}

type PanelMode = null | 'role' | 'student_profile' | 'faculty_profile' | 'deactivate';

interface FieldError { [key: string]: string }

// ── Small reusable helpers ────────────────────────────────────────────────────

const roleBadgeStyle = (role: string): React.CSSProperties => {
  const map: Record<string, [string, string]> = {
    ADMIN:   ['rgba(167,139,250,0.15)', '#c4b5fd'],
    HOD:     ['rgba(56,189,248,0.15)',  '#7dd3fc'],
    FACULTY: ['rgba(52,211,153,0.15)',  '#6ee7b7'],
    MENTOR:  ['rgba(251,191,36,0.15)',  '#fde68a'],
    STUDENT: ['rgba(148,163,184,0.12)', '#94a3b8'],
  };
  const [bg, color] = map[role] ?? ['rgba(255,255,255,0.07)', '#cbd5e1'];
  return {
    background: bg, color, border: `1px solid ${color}30`,
    padding: '2px 8px', borderRadius: '4px', fontSize: '0.72rem', fontWeight: 700, whiteSpace: 'nowrap',
  };
};

const FieldErr: React.FC<{ msg?: string }> = ({ msg }) =>
  msg ? <p style={{ color: '#fda4af', fontSize: '0.78rem', marginTop: '0.2rem' }}>{msg}</p> : null;

const inputStyle: React.CSSProperties = {
  width: '100%', background: 'var(--bg-input)', border: '1px solid var(--border-subtle)',
  borderRadius: 'var(--radius-xs)', color: 'var(--text-main)', padding: '0.55rem 0.75rem',
  fontSize: '0.88rem', outline: 'none', boxSizing: 'border-box',
};

const labelStyle: React.CSSProperties = {
  fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '0.3rem',
};

// ── Main component ────────────────────────────────────────────────────────────

interface AdminOnboardingProps {
  initialAddType?: 'STUDENT' | 'FACULTY' | null;
  onClearInitialAddType?: () => void;
}

export const AdminOnboarding: React.FC<AdminOnboardingProps> = ({ initialAddType, onClearInitialAddType }) => {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [pending, setPending] = useState<{ students_without_profile: any[]; faculty_without_profile: any[]; total_unprofiled: number } | null>(null);
  const [departments, setDepartments] = useState<any[]>([]);
  const [sections, setSections] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('ALL');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [panelMode, setPanelMode] = useState<PanelMode>(null);
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldError>({});

  // Modal for adding new Student or Faculty
  const [showAddModal, setShowAddModal] = useState<'STUDENT' | 'FACULTY' | null>(null);
  const [newUserData, setNewUserData] = useState({
    role: 'STUDENT' as 'STUDENT' | 'FACULTY' | 'HOD' | 'MENTOR',
    username: '',
    first_name: '',
    last_name: '',
    email: '',
    password: '',
    roll_number: '',
    registration_number: '',
    section: '',
    current_semester: '1',
    admission_date: new Date().toISOString().split('T')[0],
    guardian_name: '',
    guardian_phone: '',
    employee_id: '',
    department: '',
    designation: 'Assistant Professor',
    qualification: 'M.Tech',
  });
  const [modalErrors, setModalErrors] = useState<FieldError>({});

  // Role panel state
  const [roleForm, setRoleForm] = useState({ role: '', department: '' });

  // Student profile panel state
  const [stuForm, setStuForm] = useState({
    roll_number: '', registration_number: '', section: '',
    admission_date: '', current_semester: '', guardian_name: '', guardian_phone: '',
  });

  // Faculty profile panel state
  const [facForm, setFacForm] = useState({
    employee_id: '', department: '', designation: 'Assistant Professor', qualification: 'M.Tech',
  });

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [usersData, pendingData, deptData, sectData] = await Promise.all([
        api.getAdminUsers(),
        api.getPendingProfiles(),
        api.getDepartments(),
        api.getSections(),
      ]);
      setUsers(usersData as any);
      setPending(pendingData);
      setDepartments(deptData);
      setSections(sectData);
    } catch (e: any) {
      setError(e.message || 'Failed to load user data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const openAddModal = (type: 'STUDENT' | 'FACULTY') => {
    setShowAddModal(type);
    setModalErrors({});
    const defaultDept = departments[0]?.id?.toString() || '';
    const defaultSection = sections[0]?.id?.toString() || '';
    setNewUserData({
      role: type,
      username: '',
      first_name: '',
      last_name: '',
      email: '',
      password: type === 'STUDENT' ? 'Student@123' : 'Faculty@123',
      roll_number: '',
      registration_number: '',
      section: defaultSection,
      current_semester: '1',
      admission_date: new Date().toISOString().split('T')[0],
      guardian_name: '',
      guardian_phone: '',
      employee_id: '',
      department: defaultDept,
      designation: 'Assistant Professor',
      qualification: 'M.Tech',
    });
  };

  useEffect(() => {
    if (initialAddType) {
      openAddModal(initialAddType);
      if (onClearInitialAddType) onClearInitialAddType();
    }
  }, [initialAddType]);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setModalErrors({});
    try {
      const payload: any = {
        role: newUserData.role,
        username: newUserData.username.trim(),
        first_name: newUserData.first_name.trim(),
        last_name: newUserData.last_name.trim(),
        email: newUserData.email.trim() || `${newUserData.username.trim().toLowerCase()}@edumerge.ac.in`,
        password: newUserData.password || (newUserData.role === 'STUDENT' ? 'Student@123' : 'Faculty@123'),
      };

      if (newUserData.role === 'STUDENT') {
        payload.roll_number = newUserData.roll_number.trim();
        payload.registration_number = newUserData.registration_number.trim() || `REG-${newUserData.roll_number.trim()}`;
        payload.section = Number(newUserData.section);
        payload.current_semester = Number(newUserData.current_semester) || 1;
        payload.admission_date = newUserData.admission_date;
        if (newUserData.guardian_name) payload.guardian_name = newUserData.guardian_name.trim();
        if (newUserData.guardian_phone) payload.guardian_phone = newUserData.guardian_phone.trim();
      } else {
        payload.employee_id = newUserData.employee_id.trim();
        payload.department = Number(newUserData.department);
        payload.designation = newUserData.designation.trim();
        payload.qualification = newUserData.qualification.trim();
      }

      await api.createAdminUser(payload);
      setSuccessMsg(`Successfully created ${newUserData.role === 'STUDENT' ? 'student' : 'faculty'} account "${newUserData.username}" in MySQL!`);
      setShowAddModal(null);
      await loadData();
    } catch (err: any) {
      try {
        setModalErrors(JSON.parse(err.message));
      } catch {
        setModalErrors({ general: err.message || 'Failed to create account.' });
      }
    } finally {
      setSaving(false);
    }
  };

  const openPanel = (userId: number, mode: PanelMode) => {
    if (expandedId === userId && panelMode === mode) {
      setExpandedId(null);
      setPanelMode(null);
    } else {
      setExpandedId(userId);
      setPanelMode(mode);
      setFieldErrors({});
      setSuccessMsg(null);
      const user = users.find(u => u.id === userId);
      if (mode === 'role' && user) {
        setRoleForm({ role: user.role, department: user.department?.toString() ?? '' });
      }
      if (mode === 'student_profile') setStuForm({ roll_number: '', registration_number: '', section: '', admission_date: '', current_semester: '', guardian_name: '', guardian_phone: '' });
      if (mode === 'faculty_profile') setFacForm({ employee_id: '', department: '', designation: 'Assistant Professor', qualification: 'M.Tech' });
    }
  };

  const handleSaveRole = async (userId: number) => {
    setSaving(true); setFieldErrors({}); setSuccessMsg(null);
    try {
      await api.updateUser(userId, {
        role: roleForm.role,
        department: roleForm.department ? Number(roleForm.department) : undefined,
      } as any);
      setSuccessMsg('Role and department updated.');
      await loadData();
    } catch (e: any) {
      // Try to parse field errors from response
      try { setFieldErrors(JSON.parse(e.message)); } catch { setFieldErrors({ general: e.message }); }
    } finally { setSaving(false); }
  };

  const handleSaveStudentProfile = async (userId: number) => {
    setSaving(true); setFieldErrors({}); setSuccessMsg(null);
    try {
      const payload: any = {
        roll_number: stuForm.roll_number,
        registration_number: stuForm.registration_number,
        section: Number(stuForm.section),
        admission_date: stuForm.admission_date,
      };
      if (stuForm.current_semester) payload.current_semester = Number(stuForm.current_semester);
      if (stuForm.guardian_name) payload.guardian_name = stuForm.guardian_name;
      if (stuForm.guardian_phone) payload.guardian_phone = stuForm.guardian_phone;
      const result = await api.assignStudentProfile(userId, payload);
      setSuccessMsg(result.detail || 'Student profile saved.');
      await loadData();
    } catch (e: any) {
      try { setFieldErrors(JSON.parse(e.message)); } catch { setFieldErrors({ general: e.message }); }
    } finally { setSaving(false); }
  };

  const handleSaveFacultyProfile = async (userId: number) => {
    setSaving(true); setFieldErrors({}); setSuccessMsg(null);
    try {
      await api.assignFacultyProfile(userId, {
        employee_id: facForm.employee_id,
        department: Number(facForm.department),
        designation: facForm.designation,
        qualification: facForm.qualification,
      });
      setSuccessMsg('Faculty profile saved.');
      await loadData();
    } catch (e: any) {
      try { setFieldErrors(JSON.parse(e.message)); } catch { setFieldErrors({ general: e.message }); }
    } finally { setSaving(false); }
  };

  const handleToggleActive = async (user: UserRow) => {
    setSaving(true);
    try {
      await api.updateUser(user.id, { is_active: !user.is_active } as any);
      await loadData();
    } catch (e: any) {
      setFieldErrors({ general: e.message });
    } finally { setSaving(false); }
  };

  // ── Filtered users ────────────────────────────────────────────────────────

  const filteredUsers = users.filter(u => {
    const matchSearch =
      !search ||
      u.username.toLowerCase().includes(search.toLowerCase()) ||
      u.email.toLowerCase().includes(search.toLowerCase()) ||
      (u.first_name + ' ' + u.last_name).toLowerCase().includes(search.toLowerCase());
    const matchRole = roleFilter === 'ALL' || u.role === roleFilter;
    return matchSearch && matchRole;
  });

  // ── Render ────────────────────────────────────────────────────────────────

  if (loading) return <div className="glass-panel"><LoadingSpinner message="Loading user accounts…" /></div>;
  if (error) return (
    <div className="glass-panel" style={{ color: '#fda4af' }}>
      <AlertTriangle size={20} style={{ display: 'inline', marginRight: 8 }} />
      {error}
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', position: 'relative' }}>

      {/* Add User Modal */}
      {showAddModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0, 0, 0, 0.75)', backdropFilter: 'blur(6px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 9999, padding: '1rem',
        }}>
          <div className="glass-panel" style={{
            maxWidth: '680px', width: '100%', maxHeight: '90vh', overflowY: 'auto',
            border: '1px solid var(--border-active)', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)',
            position: 'relative',
          }}>
            {/* Modal Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.75rem', marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                {showAddModal === 'STUDENT' ? (
                  <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(16,185,129,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#34d399' }}>
                    <GraduationCap size={18} />
                  </div>
                ) : (
                  <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(59,130,246,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#60a5fa' }}>
                    <BookOpen size={18} />
                  </div>
                )}
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 700 }}>
                    {showAddModal === 'STUDENT' ? 'Add New Student Record' : 'Add New Faculty / Staff Member'}
                  </h3>
                  <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    Save verified identity and academic profile directly to MySQL database.
                  </p>
                </div>
              </div>
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => setShowAddModal(null)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', padding: 4 }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Error banner */}
            {modalErrors.general && (
              <div style={{ background: 'rgba(244,63,94,0.1)', border: '1px solid rgba(244,63,94,0.3)', color: '#fda4af', padding: '0.6rem 0.8rem', borderRadius: 'var(--radius-xs)', fontSize: '0.85rem', marginBottom: '1rem' }}>
                <AlertTriangle size={15} style={{ display: 'inline', marginRight: 6 }} />
                {modalErrors.general}
              </div>
            )}

            <form onSubmit={handleCreateUser} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {/* Type Switcher tabs */}
              <div style={{ display: 'flex', gap: '0.5rem', background: 'rgba(255,255,255,0.03)', padding: '4px', borderRadius: 'var(--radius-sm)' }}>
                <button
                  type="button"
                  onClick={() => openAddModal('STUDENT')}
                  style={{
                    flex: 1, padding: '0.5rem', border: 'none', borderRadius: 'var(--radius-xs)',
                    background: showAddModal === 'STUDENT' ? 'var(--primary)' : 'transparent',
                    color: '#fff', fontWeight: 600, fontSize: '0.85rem', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem',
                  }}
                >
                  <GraduationCap size={14} /> Student Account
                </button>
                <button
                  type="button"
                  onClick={() => openAddModal('FACULTY')}
                  style={{
                    flex: 1, padding: '0.5rem', border: 'none', borderRadius: 'var(--radius-xs)',
                    background: showAddModal === 'FACULTY' ? 'var(--primary)' : 'transparent',
                    color: '#fff', fontWeight: 600, fontSize: '0.85rem', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem',
                  }}
                >
                  <BookOpen size={14} /> Faculty / Staff Account
                </button>
              </div>

              {/* Basic User Information */}
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '0.9rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-dim)', fontWeight: 700, display: 'block', marginBottom: '0.6rem' }}>
                  Account Credentials & Personal Details
                </span>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '0.75rem' }}>
                  <div>
                    <label style={labelStyle}>Username *</label>
                    <input
                      required
                      placeholder={showAddModal === 'STUDENT' ? 'e.g. 24cse015' : 'e.g. fac_suresh'}
                      value={newUserData.username}
                      onChange={e => {
                        const val = e.target.value;
                        setNewUserData(d => ({
                          ...d,
                          username: val,
                          email: d.email === '' || d.email.endsWith('@edumerge.ac.in') ? (val ? `${val.toLowerCase()}@edumerge.ac.in` : '') : d.email,
                          roll_number: showAddModal === 'STUDENT' && !d.roll_number ? val.toUpperCase() : d.roll_number,
                        }));
                      }}
                      style={inputStyle}
                    />
                    <FieldErr msg={modalErrors.username} />
                  </div>

                  <div>
                    <label style={labelStyle}>Password</label>
                    <input
                      type="text"
                      placeholder={showAddModal === 'STUDENT' ? 'Student@123' : 'Faculty@123'}
                      value={newUserData.password}
                      onChange={e => setNewUserData(d => ({ ...d, password: e.target.value }))}
                      style={inputStyle}
                    />
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>Default: {showAddModal === 'STUDENT' ? 'Student@123' : 'Faculty@123'}</span>
                  </div>

                  <div>
                    <label style={labelStyle}>First Name *</label>
                    <input
                      required
                      placeholder="e.g. Rahul"
                      value={newUserData.first_name}
                      onChange={e => setNewUserData(d => ({ ...d, first_name: e.target.value }))}
                      style={inputStyle}
                    />
                    <FieldErr msg={modalErrors.first_name} />
                  </div>

                  <div>
                    <label style={labelStyle}>Last Name</label>
                    <input
                      placeholder="e.g. Sharma"
                      value={newUserData.last_name}
                      onChange={e => setNewUserData(d => ({ ...d, last_name: e.target.value }))}
                      style={inputStyle}
                    />
                  </div>

                  <div style={{ gridColumn: '1 / -1' }}>
                    <label style={labelStyle}>Institutional Email</label>
                    <input
                      type="email"
                      placeholder="username@edumerge.ac.in"
                      value={newUserData.email}
                      onChange={e => setNewUserData(d => ({ ...d, email: e.target.value }))}
                      style={inputStyle}
                    />
                    <FieldErr msg={modalErrors.email} />
                  </div>
                </div>
              </div>

              {/* Student Academic Details */}
              {showAddModal === 'STUDENT' && (
                <div style={{ background: 'rgba(255,255,255,0.02)', padding: '0.9rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                  <span style={{ fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#38bdf8', fontWeight: 700, display: 'block', marginBottom: '0.6rem' }}>
                    Student Academic Enrollment (MySQL)
                  </span>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '0.75rem' }}>
                    <div>
                      <label style={labelStyle}>Roll Number *</label>
                      <input
                        required
                        placeholder="e.g. 24CSE015"
                        value={newUserData.roll_number}
                        onChange={e => setNewUserData(d => ({
                          ...d,
                          roll_number: e.target.value,
                          registration_number: d.registration_number ? d.registration_number : `REG-${e.target.value.toUpperCase()}`
                        }))}
                        style={inputStyle}
                      />
                      <FieldErr msg={modalErrors.roll_number} />
                    </div>

                    <div>
                      <label style={labelStyle}>Registration Number *</label>
                      <input
                        required
                        placeholder="e.g. REG-24CSE015"
                        value={newUserData.registration_number}
                        onChange={e => setNewUserData(d => ({ ...d, registration_number: e.target.value }))}
                        style={inputStyle}
                      />
                      <FieldErr msg={modalErrors.registration_number} />
                    </div>

                    <div>
                      <label style={labelStyle}>Allocated Class Section *</label>
                      <select
                        required
                        value={newUserData.section}
                        onChange={e => {
                          const secId = e.target.value;
                          const found = sections.find((s: any) => s.id.toString() === secId);
                          setNewUserData(d => ({
                            ...d,
                            section: secId,
                            current_semester: found?.semester?.toString() || d.current_semester,
                          }));
                        }}
                        style={{ ...inputStyle, cursor: 'pointer' }}
                      >
                        <option value="">— Select Section —</option>
                        {sections.map((s: any) => (
                          <option key={s.id} value={s.id}>
                            {s.program_code} Sem {s.semester} — Section {s.name}
                          </option>
                        ))}
                      </select>
                      <FieldErr msg={modalErrors.section} />
                    </div>

                    <div>
                      <label style={labelStyle}>Current Semester</label>
                      <select
                        value={newUserData.current_semester}
                        onChange={e => setNewUserData(d => ({ ...d, current_semester: e.target.value }))}
                        style={{ ...inputStyle, cursor: 'pointer' }}
                      >
                        {[1, 2, 3, 4, 5, 6, 7, 8].map(sem => (
                          <option key={sem} value={sem}>Semester {sem}</option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label style={labelStyle}>Admission Date *</label>
                      <input
                        type="date"
                        required
                        value={newUserData.admission_date}
                        onChange={e => setNewUserData(d => ({ ...d, admission_date: e.target.value }))}
                        style={inputStyle}
                      />
                    </div>

                    <div>
                      <label style={labelStyle}>Guardian Contact (Optional)</label>
                      <input
                        placeholder="Guardian Name & Phone"
                        value={newUserData.guardian_name}
                        onChange={e => setNewUserData(d => ({ ...d, guardian_name: e.target.value }))}
                        style={inputStyle}
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Faculty Academic Details */}
              {showAddModal === 'FACULTY' && (
                <div style={{ background: 'rgba(255,255,255,0.02)', padding: '0.9rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                  <span style={{ fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#34d399', fontWeight: 700, display: 'block', marginBottom: '0.6rem' }}>
                    Faculty Appointment & Department (MySQL)
                  </span>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '0.75rem' }}>
                    <div>
                      <label style={labelStyle}>Specific Role *</label>
                      <select
                        value={newUserData.role}
                        onChange={e => setNewUserData(d => ({ ...d, role: e.target.value as any }))}
                        style={{ ...inputStyle, cursor: 'pointer' }}
                      >
                        <option value="FACULTY">Faculty (Teaching Staff)</option>
                        <option value="HOD">Head of Department (HOD)</option>
                        <option value="MENTOR">Class Mentor / Advisor</option>
                      </select>
                    </div>

                    <div>
                      <label style={labelStyle}>Employee ID *</label>
                      <input
                        required
                        placeholder="e.g. FAC-CSE-105"
                        value={newUserData.employee_id}
                        onChange={e => setNewUserData(d => ({ ...d, employee_id: e.target.value }))}
                        style={inputStyle}
                      />
                      <FieldErr msg={modalErrors.employee_id} />
                    </div>

                    <div>
                      <label style={labelStyle}>Department *</label>
                      <select
                        required
                        value={newUserData.department}
                        onChange={e => setNewUserData(d => ({ ...d, department: e.target.value }))}
                        style={{ ...inputStyle, cursor: 'pointer' }}
                      >
                        <option value="">— Select Department —</option>
                        {departments.map(d => (
                          <option key={d.id} value={d.id}>{d.code} — {d.name}</option>
                        ))}
                      </select>
                      <FieldErr msg={modalErrors.department} />
                    </div>

                    <div>
                      <label style={labelStyle}>Designation</label>
                      <select
                        value={newUserData.designation}
                        onChange={e => setNewUserData(d => ({ ...d, designation: e.target.value }))}
                        style={{ ...inputStyle, cursor: 'pointer' }}
                      >
                        <option value="Assistant Professor">Assistant Professor</option>
                        <option value="Associate Professor">Associate Professor</option>
                        <option value="Professor">Professor</option>
                        <option value="HOD & Professor">HOD & Professor</option>
                        <option value="Lecturer">Lecturer</option>
                      </select>
                    </div>

                    <div style={{ gridColumn: '1 / -1' }}>
                      <label style={labelStyle}>Qualification</label>
                      <input
                        placeholder="e.g. M.Tech in Artificial Intelligence, Ph.D"
                        value={newUserData.qualification}
                        onChange={e => setNewUserData(d => ({ ...d, qualification: e.target.value }))}
                        style={inputStyle}
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Submit Buttons */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowAddModal(null)}
                  disabled={saving}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={saving}
                  style={{
                    background: showAddModal === 'STUDENT' ? 'linear-gradient(135deg, #10b981, #059669)' : 'linear-gradient(135deg, #3b82f6, #2563eb)',
                    border: 'none', color: '#fff', fontWeight: 700, padding: '0.6rem 1.4rem'
                  }}
                  id="submit-create-user-btn"
                >
                  {saving ? (
                    <><Loader2 size={15} className="spin" /> Saving to MySQL...</>
                  ) : (
                    <><PlusCircle size={15} /> Save to Database</>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="glass-panel" style={{ borderLeft: '4px solid var(--primary)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div className="header-badge" style={{ marginBottom: '0.4rem' }}>
              <Users size={13} /> User Account Management
            </div>
            <h2 style={{ fontSize: '1.4rem', fontWeight: 800 }}>Account Onboarding & Role Assignment</h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', marginTop: '0.2rem' }}>
              Add new student and faculty records directly into MySQL and manage institutional roles.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => openAddModal('STUDENT')}
              style={{ background: 'linear-gradient(135deg, #10b981, #059669)', border: 'none', color: '#fff' }}
              id="btn-add-student"
            >
              <GraduationCap size={14} /> + Add Student
            </button>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => openAddModal('FACULTY')}
              style={{ background: 'linear-gradient(135deg, #3b82f6, #2563eb)', border: 'none', color: '#fff' }}
              id="btn-add-faculty"
            >
              <BookOpen size={14} /> + Add Faculty
            </button>
            <button className="btn btn-secondary btn-sm" onClick={loadData} disabled={saving}>
              <RefreshCw size={13} /> Refresh
            </button>
          </div>
        </div>

        {/* Success message banner */}
        {successMsg && (
          <div style={{
            marginTop: '1rem', padding: '0.75rem 1rem', borderRadius: 'var(--radius-sm)',
            background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)',
            display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.87rem', color: '#6ee7b7'
          }}>
            <CheckCircle2 size={16} style={{ color: '#10b981', flexShrink: 0 }} />
            <span>{successMsg}</span>
          </div>
        )}

        {/* Pending profiles alert */}
        {pending && pending.total_unprofiled > 0 && (
          <div style={{
            marginTop: '1rem', padding: '0.75rem 1rem', borderRadius: 'var(--radius-sm)',
            background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.25)',
            display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.87rem',
          }}>
            <AlertTriangle size={16} style={{ color: '#fbbf24', flexShrink: 0 }} />
            <span>
              <strong style={{ color: '#fde68a' }}>{pending.total_unprofiled} account{pending.total_unprofiled !== 1 ? 's' : ''}</strong>
              {' '}still need academic profile setup:
              {pending.students_without_profile.length > 0 && (
                <span style={{ color: '#94a3b8', marginLeft: 6 }}>
                  {pending.students_without_profile.length} student{pending.students_without_profile.length !== 1 ? 's' : ''}
                </span>
              )}
              {pending.faculty_without_profile.length > 0 && (
                <span style={{ color: '#94a3b8', marginLeft: 6 }}>
                  · {pending.faculty_without_profile.length} faculty/staff
                </span>
              )}
            </span>
          </div>
        )}
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: '1 1 220px' }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }} />
          <input
            placeholder="Search by name, username, or email…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ ...inputStyle, paddingLeft: '2rem' }}
          />
        </div>
        <select
          value={roleFilter}
          onChange={e => setRoleFilter(e.target.value)}
          style={{ ...inputStyle, width: 'auto', minWidth: '140px', cursor: 'pointer' }}
        >
          <option value="ALL">All Roles</option>
          <option value="ADMIN">Administrator</option>
          <option value="HOD">Head of Dept</option>
          <option value="FACULTY">Faculty</option>
          <option value="MENTOR">Mentor</option>
          <option value="STUDENT">Student</option>
        </select>
        <span style={{ fontSize: '0.82rem', color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>
          {filteredUsers.length} account{filteredUsers.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* User list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
        {filteredUsers.length === 0 && (
          <div className="glass-panel" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2.5rem' }}>
            No accounts match your search.
          </div>
        )}

        {filteredUsers.map(user => {
          const isExpanded = expandedId === user.id;
          const isPendingProfile =
            (pending?.students_without_profile.some(u => u.id === user.id)) ||
            (pending?.faculty_without_profile.some(u => u.id === user.id));

          return (
            <div
              key={user.id}
              className="glass-panel"
              style={{ padding: '0', overflow: 'hidden', transition: 'border-color 0.2s', borderColor: isExpanded ? 'var(--border-active)' : undefined }}
            >
              {/* Row header */}
              <div
                style={{
                  display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.85rem 1.1rem',
                  cursor: 'pointer', flexWrap: 'wrap',
                }}
                onClick={() => { setExpandedId(isExpanded ? null : user.id); setPanelMode(null); setSuccessMsg(null); setFieldErrors({}); }}
              >
                {/* Avatar */}
                <div style={{
                  width: 36, height: 36, borderRadius: '50%', flexShrink: 0,
                  background: 'linear-gradient(135deg, var(--primary-deeper), var(--primary))',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontWeight: 800, fontSize: '0.9rem', color: '#fff',
                }}>
                  {(user.first_name?.[0] || user.username[0]).toUpperCase()}
                </div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>
                      {user.first_name && user.last_name ? `${user.first_name} ${user.last_name}` : user.username}
                    </span>
                    <span style={roleBadgeStyle(user.role)}>{user.role_display}</span>
                    {!user.is_active && (
                      <span style={{ ...roleBadgeStyle(''), background: 'rgba(244,63,94,0.12)', color: '#fda4af', border: '1px solid rgba(244,63,94,0.25)' }}>
                        Deactivated
                      </span>
                    )}
                    {isPendingProfile && (
                      <span style={{ background: 'rgba(251,191,36,0.12)', color: '#fde68a', border: '1px solid rgba(251,191,36,0.25)', padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 700 }}>
                        ⚠ Profile Pending
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)', marginTop: '0.2rem', display: 'flex', gap: '0.6rem', flexWrap: 'wrap', alignItems: 'center' }}>
                    <span>@{user.username}</span>
                    <span>· {user.email}</span>
                    {user.department_name && <span>· Dept: {user.department_name}</span>}
                    {user.student_profile && (
                      <span style={{ color: '#38bdf8', fontWeight: 600 }}>
                        · Roll: {user.student_profile.roll_number} {user.student_profile.section_name ? `(${user.student_profile.section_name})` : ''}
                      </span>
                    )}
                    {user.faculty_profile && (
                      <span style={{ color: '#34d399', fontWeight: 600 }}>
                        · ID: {user.faculty_profile.employee_id} ({user.faculty_profile.designation})
                      </span>
                    )}
                  </div>
                </div>

                <div style={{ flexShrink: 0, color: 'var(--text-dim)' }}>
                  {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </div>
              </div>

              {/* Expanded actions */}
              {isExpanded && (
                <div style={{ borderTop: '1px solid var(--border-subtle)', padding: '1rem 1.1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>

                  {/* Action buttons */}
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <button
                      className={`btn btn-sm ${panelMode === 'role' ? 'btn-primary' : 'btn-secondary'}`}
                      onClick={() => openPanel(user.id, 'role')}
                    >
                      <ShieldCheck size={13} /> Assign Role &amp; Dept
                    </button>

                    {user.role === 'STUDENT' && (
                      <button
                        className={`btn btn-sm ${panelMode === 'student_profile' ? 'btn-primary' : 'btn-secondary'}`}
                        onClick={() => openPanel(user.id, 'student_profile')}
                      >
                        <GraduationCap size={13} /> Set Student Profile
                      </button>
                    )}

                    {['FACULTY', 'HOD', 'MENTOR'].includes(user.role) && (
                      <button
                        className={`btn btn-sm ${panelMode === 'faculty_profile' ? 'btn-primary' : 'btn-secondary'}`}
                        onClick={() => openPanel(user.id, 'faculty_profile')}
                      >
                        <BookOpen size={13} /> Set Faculty Profile
                      </button>
                    )}

                    <button
                      className="btn btn-sm btn-secondary"
                      onClick={() => handleToggleActive(user)}
                      disabled={saving}
                      style={{ marginLeft: 'auto', color: user.is_active ? '#fda4af' : '#6ee7b7' }}
                    >
                      {user.is_active ? <><UserX size={13} /> Deactivate</> : <><UserCheck size={13} /> Reactivate</>}
                    </button>
                  </div>

                  {/* Inline success / global error */}
                  {successMsg && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#6ee7b7', fontSize: '0.86rem' }}>
                      <CheckCircle2 size={15} /> {successMsg}
                    </div>
                  )}
                  {fieldErrors.general && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#fda4af', fontSize: '0.86rem' }}>
                      <XCircle size={15} /> {fieldErrors.general}
                    </div>
                  )}

                  {/* ── Role assignment panel ── */}
                  {panelMode === 'role' && (
                    <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 'var(--radius-sm)', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                      <h4 style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
                        Assign Role &amp; Department
                      </h4>

                      <div>
                        <label style={labelStyle}>Role *</label>
                        <select
                          value={roleForm.role}
                          onChange={e => setRoleForm(f => ({ ...f, role: e.target.value }))}
                          style={{ ...inputStyle, cursor: 'pointer' }}
                        >
                          <option value="">— Select a role —</option>
                          <option value="STUDENT">Student</option>
                          <option value="FACULTY">Faculty (Subject Teacher)</option>
                          <option value="HOD">Head of Department (HOD)</option>
                          <option value="MENTOR">Class Mentor</option>
                        </select>
                        <FieldErr msg={fieldErrors.role} />
                        {roleForm.role === 'ADMIN' && (
                          <p style={{ color: '#fbbf24', fontSize: '0.78rem', marginTop: '0.25rem' }}>
                            ℹ️ Administrator role must be set via the Django admin panel for security.
                          </p>
                        )}
                      </div>

                      <div>
                        <label style={labelStyle}>Affiliated Department</label>
                        <select
                          value={roleForm.department}
                          onChange={e => setRoleForm(f => ({ ...f, department: e.target.value }))}
                          style={{ ...inputStyle, cursor: 'pointer' }}
                        >
                          <option value="">— None / Not applicable —</option>
                          {departments.map(d => (
                            <option key={d.id} value={d.id}>{d.code} — {d.name}</option>
                          ))}
                        </select>
                        <FieldErr msg={fieldErrors.department} />
                      </div>

                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => handleSaveRole(user.id)}
                        disabled={saving || !roleForm.role}
                      >
                        {saving ? <Loader2 size={13} className="spin" /> : <ArrowRight size={13} />}
                        Save Role Assignment
                      </button>
                    </div>
                  )}

                  {/* ── Student profile panel ── */}
                  {panelMode === 'student_profile' && (
                    <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 'var(--radius-sm)', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                      <h4 style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
                        <GraduationCap size={14} style={{ display: 'inline', marginRight: 6 }} />
                        Student Academic Profile
                      </h4>
                      <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>
                        Fills in institutional identity. Until this is saved, the student sees a "profile pending" state and cannot view attendance.
                      </p>

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem' }}>
                        <div>
                          <label style={labelStyle}>Roll Number *</label>
                          <input placeholder="e.g. 24CSE001" value={stuForm.roll_number} onChange={e => setStuForm(f => ({ ...f, roll_number: e.target.value }))} style={inputStyle} />
                          <FieldErr msg={fieldErrors.roll_number} />
                        </div>
                        <div>
                          <label style={labelStyle}>Registration Number *</label>
                          <input placeholder="e.g. REG24-CSE-001" value={stuForm.registration_number} onChange={e => setStuForm(f => ({ ...f, registration_number: e.target.value }))} style={inputStyle} />
                          <FieldErr msg={fieldErrors.registration_number} />
                        </div>
                        <div>
                          <label style={labelStyle}>Class Section *</label>
                          <select value={stuForm.section} onChange={e => setStuForm(f => ({ ...f, section: e.target.value }))} style={{ ...inputStyle, cursor: 'pointer' }}>
                            <option value="">— Select section —</option>
                            {sections.map((s: any) => (
                              <option key={s.id} value={s.id}>{s.program_code} Sem {s.semester} — Section {s.name}</option>
                            ))}
                          </select>
                          <FieldErr msg={fieldErrors.section} />
                        </div>
                        <div>
                          <label style={labelStyle}>Current Semester</label>
                          <input type="number" min={1} max={12} placeholder="Auto-filled from section" value={stuForm.current_semester} onChange={e => setStuForm(f => ({ ...f, current_semester: e.target.value }))} style={inputStyle} />
                          <FieldErr msg={fieldErrors.current_semester} />
                        </div>
                        <div>
                          <label style={labelStyle}>Admission Date *</label>
                          <input type="date" value={stuForm.admission_date} onChange={e => setStuForm(f => ({ ...f, admission_date: e.target.value }))} style={inputStyle} />
                          <FieldErr msg={fieldErrors.admission_date} />
                        </div>
                        <div>
                          <label style={labelStyle}>Guardian Name</label>
                          <input placeholder="Optional" value={stuForm.guardian_name} onChange={e => setStuForm(f => ({ ...f, guardian_name: e.target.value }))} style={inputStyle} />
                        </div>
                        <div>
                          <label style={labelStyle}>Guardian Phone</label>
                          <input placeholder="Optional" value={stuForm.guardian_phone} onChange={e => setStuForm(f => ({ ...f, guardian_phone: e.target.value }))} style={inputStyle} />
                        </div>
                      </div>

                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => handleSaveStudentProfile(user.id)}
                        disabled={saving || !stuForm.roll_number || !stuForm.registration_number || !stuForm.section || !stuForm.admission_date}
                      >
                        {saving ? <Loader2 size={13} className="spin" /> : <GraduationCap size={13} />}
                        Save Student Profile
                      </button>
                    </div>
                  )}

                  {/* ── Faculty profile panel ── */}
                  {panelMode === 'faculty_profile' && (
                    <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 'var(--radius-sm)', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                      <h4 style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
                        <Edit3 size={14} style={{ display: 'inline', marginRight: 6 }} />
                        Faculty / Staff Profile
                      </h4>

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem' }}>
                        <div>
                          <label style={labelStyle}>Employee ID *</label>
                          <input placeholder="e.g. FAC-CSE-001" value={facForm.employee_id} onChange={e => setFacForm(f => ({ ...f, employee_id: e.target.value }))} style={inputStyle} />
                          <FieldErr msg={fieldErrors.employee_id} />
                        </div>
                        <div>
                          <label style={labelStyle}>Department *</label>
                          <select value={facForm.department} onChange={e => setFacForm(f => ({ ...f, department: e.target.value }))} style={{ ...inputStyle, cursor: 'pointer' }}>
                            <option value="">— Select department —</option>
                            {departments.map(d => (
                              <option key={d.id} value={d.id}>{d.code} — {d.name}</option>
                            ))}
                          </select>
                          <FieldErr msg={fieldErrors.department} />
                        </div>
                        <div>
                          <label style={labelStyle}>Designation</label>
                          <input placeholder="e.g. Assistant Professor" value={facForm.designation} onChange={e => setFacForm(f => ({ ...f, designation: e.target.value }))} style={inputStyle} />
                        </div>
                        <div>
                          <label style={labelStyle}>Qualification</label>
                          <input placeholder="e.g. M.Tech, Ph.D" value={facForm.qualification} onChange={e => setFacForm(f => ({ ...f, qualification: e.target.value }))} style={inputStyle} />
                        </div>
                      </div>

                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => handleSaveFacultyProfile(user.id)}
                        disabled={saving || !facForm.employee_id || !facForm.department}
                      >
                        {saving ? <Loader2 size={13} className="spin" /> : <Building2 size={13} />}
                        Save Faculty Profile
                      </button>
                    </div>
                  )}

                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
