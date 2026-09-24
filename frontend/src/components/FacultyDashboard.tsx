import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Student } from '../types';
import { LoadingSpinner } from './LoadingSpinner';
import { EmptyState, InlineError } from './EmptyState';
import {
  Briefcase, BookOpen, Users, ShieldAlert, CheckCircle2, XCircle,
  Clock, AlertTriangle, CheckSquare, Layers, FileCheck, RefreshCw,
  Send, ExternalLink, Calendar, ChevronRight
} from 'lucide-react';
import { FacultyAttendanceRecorder } from './FacultyAttendanceRecorder';

export const FacultyDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'overview' | 'record' | 'corrections' | 'roster'>('overview');
  const [dashboardData, setDashboardData] = useState<any>(null);
  const [corrections, setCorrections] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Allocations & Roster state
  const [allocations, setAllocations] = useState<any[]>([]);
  const [selectedSection, setSelectedSection] = useState<number | null>(null);
  const [roster, setRoster] = useState<Student[]>([]);

  // Resolution state
  const [reviewNote, setReviewNote] = useState<string>('');
  const [processingId, setProcessingId] = useState<number | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const fetchFacultyData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [dash, corrData, allocData] = await Promise.all([
        api.getFacultyDashboard(),
        api.getCorrections(),
        api.getFacultyAllocations(),
      ]);
      setDashboardData(dash);
      setCorrections(corrData.results || []);
      setAllocations(allocData.allocations || []);

      if (allocData.allocations && allocData.allocations.length > 0) {
        const firstSection = allocData.allocations[0].section;
        setSelectedSection(firstSection);
        const rosterData = await api.getFacultyRoster(firstSection);
        setRoster(rosterData.roster || []);
      }
    } catch (err: any) {
      console.error('Failed to load faculty dashboard data:', err);
      setError(err.message || 'Failed to load faculty data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFacultyData();
  }, []);

  const handleSectionSelect = async (secId: number) => {
    setSelectedSection(secId);
    try {
      const rosterData = await api.getFacultyRoster(secId);
      setRoster(rosterData.roster || []);
    } catch (err: any) {
      console.error('Failed to load section roster:', err);
    }
  };

  const handleApproveCorrection = async (id: number) => {
    setProcessingId(id);
    try {
      await api.approveCorrection(id, reviewNote);
      setActionMessage(`Correction #${id} approved successfully. Historical attendance reconciled.`);
      setReviewNote('');
      fetchFacultyData();
    } catch (err: any) {
      setActionMessage(`Error approving #${id}: ${err.message}`);
    } finally {
      setProcessingId(null);
    }
  };

  const handleRejectCorrection = async (id: number) => {
    setProcessingId(id);
    try {
      await api.rejectCorrection(id, reviewNote || 'Rejected by instructor');
      setActionMessage(`Correction #${id} rejected. Attendance record untouched.`);
      setReviewNote('');
      fetchFacultyData();
    } catch (err: any) {
      setActionMessage(`Error rejecting #${id}: ${err.message}`);
    } finally {
      setProcessingId(null);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Top Banner */}
      <div className="glass-panel" style={{ borderLeft: '4px solid #10b981' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div className="header-badge" style={{ marginBottom: '0.4rem', background: 'rgba(16, 185, 129, 0.15)', color: '#6ee7b7', borderColor: 'rgba(16, 185, 129, 0.3)' }}>
              <Briefcase size={14} />
              Faculty Academic Teaching Scope
            </div>
            <h2 style={{ fontSize: '1.6rem', fontWeight: 800 }}>
              Faculty Classroom Hub: {dashboardData?.faculty_name || 'Instructor'}
            </h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '0.2rem' }}>
              Allocated subject timetables, classroom roster tracking, attendance recording, and dispute adjudication.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button
              onClick={() => setActiveTab('record')}
              style={{
                background: 'linear-gradient(135deg, #10b981, #059669)',
                color: '#fff',
                padding: '0.6rem 1.1rem',
                borderRadius: 'var(--radius-sm)',
                border: 'none',
                cursor: 'pointer',
                fontWeight: 700,
                fontSize: '0.85rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                boxShadow: '0 4px 12px rgba(16, 185, 129, 0.3)'
              }}
            >
              <CheckSquare size={16} />
              Mark Attendance Now
            </button>
            <button
              onClick={fetchFacultyData}
              style={{
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-muted)',
                padding: '0.6rem 0.9rem',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '0.85rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem'
              }}
            >
              <RefreshCw size={14} />
              Refresh
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem', flexWrap: 'wrap' }}>
          <button
            onClick={() => setActiveTab('overview')}
            style={{
              background: activeTab === 'overview' ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
              color: activeTab === 'overview' ? '#6ee7b7' : 'var(--text-muted)',
              border: activeTab === 'overview' ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid transparent',
              padding: '0.5rem 1rem',
              borderRadius: 'var(--radius-sm)',
              fontWeight: 600,
              fontSize: '0.85rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem'
            }}
          >
            <Layers size={14} />
            Classroom Overview & Schedule
          </button>

          <button
            onClick={() => setActiveTab('record')}
            style={{
              background: activeTab === 'record' ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
              color: activeTab === 'record' ? '#6ee7b7' : 'var(--text-muted)',
              border: activeTab === 'record' ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid transparent',
              padding: '0.5rem 1rem',
              borderRadius: 'var(--radius-sm)',
              fontWeight: 600,
              fontSize: '0.85rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem'
            }}
          >
            <CheckSquare size={14} />
            Mark Attendance Form
          </button>

          <button
            onClick={() => setActiveTab('corrections')}
            style={{
              background: activeTab === 'corrections' ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
              color: activeTab === 'corrections' ? '#6ee7b7' : 'var(--text-muted)',
              border: activeTab === 'corrections' ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid transparent',
              padding: '0.5rem 1rem',
              borderRadius: 'var(--radius-sm)',
              fontWeight: 600,
              fontSize: '0.85rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem'
            }}
          >
            <FileCheck size={14} />
            Correction Requests
            {corrections.filter((c: any) => c.status === 'PENDING').length > 0 && (
              <span style={{
                background: '#f43f5e',
                color: '#fff',
                fontSize: '0.7rem',
                padding: '0.1rem 0.4rem',
                borderRadius: '999px',
                fontWeight: 700
              }}>
                {corrections.filter((c: any) => c.status === 'PENDING').length}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('roster')}
            style={{
              background: activeTab === 'roster' ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
              color: activeTab === 'roster' ? '#6ee7b7' : 'var(--text-muted)',
              border: activeTab === 'roster' ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid transparent',
              padding: '0.5rem 1rem',
              borderRadius: 'var(--radius-sm)',
              fontWeight: 600,
              fontSize: '0.85rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem'
            }}
          >
            <Users size={14} />
            Classroom Roster Inspector
          </button>
        </div>
      </div>

      {actionMessage && (
        <div className="glass-panel" style={{ borderLeft: '4px solid #3b82f6', color: '#93c5fd', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer' }}>×</button>
        </div>
      )}

      {loading ? (
        <div className="glass-panel">
          <LoadingSpinner message="Retrieving classroom schedule & compliance stats…" />
        </div>
      ) : activeTab === 'record' ? (
        <FacultyAttendanceRecorder />
      ) : activeTab === 'overview' && dashboardData ? (
        <>
          {/* Key Metrics Row */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.25rem' }}>
            <div className="glass-panel">
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 600 }}>
                <span>Today's Classes</span>
                <Calendar size={18} style={{ color: '#60a5fa' }} />
              </div>
              <div style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.5rem' }}>
                {dashboardData.today_classes_count}
              </div>
              <div style={{ fontSize: '0.8rem', color: '#93c5fd', marginTop: '0.3rem' }}>
                Scheduled for {dashboardData.today}
              </div>
            </div>

            <div className="glass-panel" style={{ borderLeft: dashboardData.pending_attendance_count > 0 ? '4px solid #f59e0b' : '4px solid #10b981' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 600 }}>
                <span>Pending Attendance</span>
                <Clock size={18} style={{ color: dashboardData.pending_attendance_count > 0 ? '#fbbf24' : '#34d399' }} />
              </div>
              <div style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.5rem', color: dashboardData.pending_attendance_count > 0 ? '#fbbf24' : '#34d399' }}>
                {dashboardData.pending_attendance_count}
              </div>
              <div style={{ fontSize: '0.8rem', color: dashboardData.pending_attendance_count > 0 ? '#fde68a' : '#6ee7b7', marginTop: '0.3rem' }}>
                {dashboardData.pending_attendance_count > 0 ? 'Requires recording today' : 'All classes submitted!'}
              </div>
            </div>

            <div className="glass-panel">
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 600 }}>
                <span>Allocations</span>
                <BookOpen size={18} style={{ color: '#a78bfa' }} />
              </div>
              <div style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.5rem' }}>
                {dashboardData.total_allocations}
              </div>
              <div style={{ fontSize: '0.8rem', color: '#a5f3fc', marginTop: '0.3rem' }}>
                Assigned courses & sections
              </div>
            </div>

            <div className="glass-panel" style={{ borderLeft: dashboardData.low_attendance_students?.length > 0 ? '4px solid #f43f5e' : '4px solid #10b981' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 600 }}>
                <span>At-Risk Students (&lt;{dashboardData.threshold_used}%)</span>
                <AlertTriangle size={18} style={{ color: '#f87171' }} />
              </div>
              <div style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.5rem', color: dashboardData.low_attendance_students?.length > 0 ? '#f87171' : '#34d399' }}>
                {dashboardData.low_attendance_students?.length || 0}
              </div>
              <div style={{ fontSize: '0.8rem', color: '#fda4af', marginTop: '0.3rem' }}>
                Across your teaching sections
              </div>
            </div>
          </div>

          {/* Today's Classes List */}
          <div className="glass-panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Clock size={20} style={{ color: '#60a5fa' }} />
                <h3 style={{ fontSize: '1.2rem', fontWeight: 800 }}>Today's Classes & Attendance Status</h3>
              </div>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Date: {dashboardData.today}</span>
            </div>

            {dashboardData.today_classes && dashboardData.today_classes.length > 0 ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1rem' }}>
                {dashboardData.today_classes.map((cls: any, idx: number) => {
                  const isDone = cls.is_attendance_taken;
                  return (
                    <div key={idx} style={{
                      background: 'rgba(15, 23, 42, 0.5)',
                      border: `1px solid ${isDone ? 'rgba(16, 185, 129, 0.3)' : 'rgba(245, 158, 11, 0.4)'}`,
                      borderRadius: 'var(--radius-sm)',
                      padding: '1.25rem',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      gap: '1rem'
                    }}>
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 800, fontSize: '1.1rem', color: '#fff' }}>
                            {cls.subject_code} - {cls.subject_title}
                          </span>
                          <span style={{
                            padding: '0.2rem 0.6rem',
                            borderRadius: '4px',
                            fontSize: '0.75rem',
                            fontWeight: 700,
                            background: isDone ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                            color: isDone ? '#6ee7b7' : '#fde68a',
                            border: `1px solid ${isDone ? 'rgba(16, 185, 129, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`
                          }}>
                            {isDone ? 'RECORDED' : 'PENDING'}
                          </span>
                        </div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.4rem' }}>
                          Section: <strong style={{ color: '#fff' }}>{cls.section_label}</strong> • Cohort: {cls.total_students} Enrolled
                        </div>
                        {isDone && cls.attendance_percentage !== null && (
                          <div style={{ fontSize: '0.85rem', color: '#6ee7b7', marginTop: '0.4rem', fontWeight: 600 }}>
                            Recorded Attendance: {cls.attendance_percentage}%
                          </div>
                        )}
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                        <button
                          onClick={() => setActiveTab('record')}
                          style={{
                            background: isDone ? 'rgba(255,255,255,0.05)' : 'rgba(16, 185, 129, 0.2)',
                            color: isDone ? 'var(--text-muted)' : '#6ee7b7',
                            border: `1px solid ${isDone ? 'var(--border-color)' : 'rgba(16, 185, 129, 0.4)'}`,
                            padding: '0.45rem 0.85rem',
                            borderRadius: 'var(--radius-sm)',
                            cursor: 'pointer',
                            fontSize: '0.8rem',
                            fontWeight: 600,
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.3rem'
                          }}
                        >
                          {isDone ? 'Review Session' : 'Record Now'}
                          <ChevronRight size={14} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                No classes scheduled for today.
              </div>
            )}
          </div>

          {/* Class Attendance & Analytics */}
          <div className="glass-panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <BookOpen size={20} style={{ color: '#a78bfa' }} />
                <h3 style={{ fontSize: '1.2rem', fontWeight: 800 }}>Class Attendance Analytics</h3>
              </div>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Cohort Breakdown</span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1rem' }}>
              {dashboardData.class_attendance?.map((ca: any, idx: number) => (
                <div key={idx} style={{
                  background: 'rgba(15, 23, 42, 0.4)',
                  padding: '1rem',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-color)'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '1rem' }}>{ca.subject_code} - {ca.subject_title}</div>
                      <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{ca.section_label} • {ca.total_students} students</div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '1.3rem', fontWeight: 800, color: ca.class_average_percentage >= 75 ? '#34d399' : '#fbbf24' }}>
                        {ca.class_average_percentage}%
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Class Average</div>
                    </div>
                  </div>

                  {ca.distribution && (
                    <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.8rem', fontSize: '0.75rem' }}>
                      <span style={{ padding: '0.2rem 0.5rem', background: 'rgba(16, 185, 129, 0.1)', color: '#6ee7b7', borderRadius: '4px' }}>
                        Eligible (&ge;75%): {ca.distribution.eligible_above_75}
                      </span>
                      <span style={{ padding: '0.2rem 0.5rem', background: 'rgba(245, 158, 11, 0.1)', color: '#fde68a', borderRadius: '4px' }}>
                        65-75%: {ca.distribution.condonation_65_to_75}
                      </span>
                      <span style={{ padding: '0.2rem 0.5rem', background: 'rgba(244, 63, 94, 0.1)', color: '#fda4af', borderRadius: '4px' }}>
                        Critical (&lt;65%): {ca.distribution.critical_below_65}
                      </span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Low Attendance Students in Faculty Classes */}
          <div className="glass-panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <AlertTriangle size={20} style={{ color: '#f87171' }} />
                <h3 style={{ fontSize: '1.2rem', fontWeight: 800 }}>Low Attendance Students in Your Courses</h3>
              </div>
              <span className="badge" style={{ background: 'rgba(244, 63, 94, 0.15)', color: '#fda4af', border: '1px solid rgba(244, 63, 94, 0.3)' }}>
                {dashboardData.low_attendance_students?.length || 0} Student(s) Below 75%
              </span>
            </div>

            {dashboardData.low_attendance_students && dashboardData.low_attendance_students.length > 0 ? (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
                      <th style={{ padding: '0.75rem' }}>Roll Number</th>
                      <th style={{ padding: '0.75rem' }}>Student Name</th>
                      <th style={{ padding: '0.75rem' }}>Section</th>
                      <th style={{ padding: '0.75rem' }}>Overall Attendance</th>
                      <th style={{ padding: '0.75rem' }}>Conducted / Attended</th>
                      <th style={{ padding: '0.75rem' }}>Recovery Needed</th>
                      <th style={{ padding: '0.75rem' }}>Compliance Level</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dashboardData.low_attendance_students.map((s: any, idx: number) => {
                      const isCrit = s.overall_percentage < 65;
                      return (
                        <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                          <td style={{ padding: '0.75rem', fontWeight: 700, color: '#93c5fd' }}>{s.roll_number}</td>
                          <td style={{ padding: '0.75rem', fontWeight: 600 }}>{s.full_name}</td>
                          <td style={{ padding: '0.75rem', color: 'var(--text-muted)' }}>{s.section_label}</td>
                          <td style={{ padding: '0.75rem', fontWeight: 800, color: isCrit ? '#f43f5e' : '#fbbf24' }}>
                            {s.overall_percentage}%
                          </td>
                          <td style={{ padding: '0.75rem' }}>{s.classes_attended} / {s.classes_conducted}</td>
                          <td style={{ padding: '0.75rem', fontWeight: 700, color: '#60a5fa' }}>
                            +{s.classes_needed_for_75} consecutive
                          </td>
                          <td style={{ padding: '0.75rem' }}>
                            <span style={{
                              padding: '0.2rem 0.5rem',
                              borderRadius: '4px',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              background: isCrit ? 'rgba(244, 63, 94, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                              color: isCrit ? '#fda4af' : '#fde68a',
                              border: `1px solid ${isCrit ? 'rgba(244, 63, 94, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`
                            }}>
                              {isCrit ? 'CRITICAL DEBARMENT' : 'CONDONATION REQ'}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                <CheckCircle2 size={32} style={{ color: '#10b981', margin: '0 auto 0.5rem' }} />
                <p>All students in your classes maintain satisfactory attendance (&ge;75%).</p>
              </div>
            )}
          </div>
        </>
      ) : activeTab === 'corrections' ? (
        /* Correction Requests Adjudication */
        <div className="glass-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <FileCheck size={20} style={{ color: '#60a5fa' }} />
              <h3 style={{ fontSize: '1.2rem', fontWeight: 800 }}>Student Attendance Correction Disputes</h3>
            </div>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Authorized to approve or reject requests for your courses
            </span>
          </div>

          <div style={{ marginBottom: '1rem', display: 'flex', gap: '0.5rem' }}>
            <input
              type="text"
              placeholder="Optional review notes / verification justification..."
              value={reviewNote}
              onChange={(e) => setReviewNote(e.target.value)}
              style={{
                flex: 1,
                background: 'rgba(15, 23, 42, 0.6)',
                border: '1px solid var(--border-color)',
                color: '#fff',
                padding: '0.5rem 0.8rem',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.85rem'
              }}
            />
          </div>

          {corrections && corrections.length > 0 ? (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
                    <th style={{ padding: '0.75rem' }}>ID</th>
                    <th style={{ padding: '0.75rem' }}>Student</th>
                    <th style={{ padding: '0.75rem' }}>Subject & Date</th>
                    <th style={{ padding: '0.75rem' }}>Current &rarr; Requested</th>
                    <th style={{ padding: '0.75rem' }}>Justification</th>
                    <th style={{ padding: '0.75rem' }}>Status</th>
                    <th style={{ padding: '0.75rem' }}>Adjudication</th>
                  </tr>
                </thead>
                <tbody>
                  {corrections.map((c: any) => {
                    const isPending = c.status === 'PENDING';
                    return (
                      <tr key={c.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                        <td style={{ padding: '0.75rem', fontWeight: 700 }}>#{c.id}</td>
                        <td style={{ padding: '0.75rem' }}>
                          <div style={{ fontWeight: 600 }}>{c.student_name}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{c.student_roll}</div>
                        </td>
                        <td style={{ padding: '0.75rem' }}>
                          <div style={{ fontWeight: 600 }}>{c.subject_code}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{c.session_date} (P{c.period_number})</div>
                        </td>
                        <td style={{ padding: '0.75rem' }}>
                          <span style={{ color: '#fda4af', fontWeight: 700 }}>{c.old_status}</span>
                          {' '}&rarr;{' '}
                          <span style={{ color: '#6ee7b7', fontWeight: 700 }}>{c.requested_status}</span>
                        </td>
                        <td style={{ padding: '0.75rem', maxWidth: '250px' }}>
                          <div style={{ fontSize: '0.8rem' }}>{c.reason}</div>
                          {c.document_url && (
                            <a href={c.document_url} target="_blank" rel="noreferrer" style={{ fontSize: '0.75rem', color: '#60a5fa', display: 'flex', alignItems: 'center', gap: '0.2rem', marginTop: '0.2rem' }}>
                              Proof Certificate <ExternalLink size={10} />
                            </a>
                          )}
                        </td>
                        <td style={{ padding: '0.75rem' }}>
                          <span style={{
                            padding: '0.2rem 0.5rem',
                            borderRadius: '4px',
                            fontSize: '0.75rem',
                            fontWeight: 700,
                            background: c.status === 'APPROVED' ? 'rgba(16, 185, 129, 0.15)' : c.status === 'REJECTED' ? 'rgba(244, 63, 94, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                            color: c.status === 'APPROVED' ? '#6ee7b7' : c.status === 'REJECTED' ? '#fda4af' : '#fde68a',
                            border: `1px solid ${c.status === 'APPROVED' ? 'rgba(16, 185, 129, 0.3)' : c.status === 'REJECTED' ? 'rgba(244, 63, 94, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`
                          }}>
                            {c.status}
                          </span>
                        </td>
                        <td style={{ padding: '0.75rem' }}>
                          {isPending ? (
                            <div style={{ display: 'flex', gap: '0.4rem' }}>
                              <button
                                disabled={processingId === c.id}
                                onClick={() => handleApproveCorrection(c.id)}
                                style={{
                                  background: 'rgba(16, 185, 129, 0.2)',
                                  border: '1px solid rgba(16, 185, 129, 0.4)',
                                  color: '#6ee7b7',
                                  padding: '0.35rem 0.65rem',
                                  borderRadius: '4px',
                                  cursor: 'pointer',
                                  fontSize: '0.75rem',
                                  fontWeight: 700
                                }}
                              >
                                Approve
                              </button>
                              <button
                                disabled={processingId === c.id}
                                onClick={() => handleRejectCorrection(c.id)}
                                style={{
                                  background: 'rgba(244, 63, 94, 0.15)',
                                  border: '1px solid rgba(244, 63, 94, 0.35)',
                                  color: '#fda4af',
                                  padding: '0.35rem 0.65rem',
                                  borderRadius: '4px',
                                  cursor: 'pointer',
                                  fontSize: '0.75rem',
                                  fontWeight: 700
                                }}
                              >
                                Reject
                              </button>
                            </div>
                          ) : (
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                              Resolved by {c.reviewed_by_name || 'Staff'}
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
              No attendance correction requests filed yet.
            </div>
          )}
        </div>
      ) : activeTab === 'roster' ? (
        /* Roster Inspector */
        <div className="glass-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Classroom Students Roster</h3>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              {allocations.map((alloc) => (
                <button
                  key={alloc.id}
                  onClick={() => handleSectionSelect(alloc.section)}
                  style={{
                    background: selectedSection === alloc.section ? 'var(--primary-color)' : 'rgba(255,255,255,0.05)',
                    border: '1px solid var(--border-color)',
                    color: '#fff',
                    padding: '0.4rem 0.8rem',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.8rem',
                    cursor: 'pointer'
                  }}
                >
                  Section {alloc.section_name} ({alloc.subject_code})
                </button>
              ))}
            </div>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '0.75rem' }}>Roll Number</th>
                  <th style={{ padding: '0.75rem' }}>Student Name</th>
                  <th style={{ padding: '0.75rem' }}>Registration</th>
                  <th style={{ padding: '0.75rem' }}>Email</th>
                  <th style={{ padding: '0.75rem' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {roster.map((s: any) => (
                  <tr key={s.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                    <td style={{ padding: '0.75rem', fontWeight: 700, color: '#93c5fd' }}>{s.roll_number}</td>
                    <td style={{ padding: '0.75rem', fontWeight: 600 }}>{s.full_name}</td>
                    <td style={{ padding: '0.75rem', color: 'var(--text-muted)' }}>{s.registration_number}</td>
                    <td style={{ padding: '0.75rem', color: 'var(--text-muted)' }}>{s.email}</td>
                    <td style={{ padding: '0.75rem' }}>
                      <span className="badge" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#6ee7b7' }}>Active</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
};
