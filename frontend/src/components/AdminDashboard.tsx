import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { LoadingSpinner } from './LoadingSpinner';
import { InlineError } from './EmptyState';
import {
  ShieldAlert, Users, GraduationCap, Building2, TrendingUp,
  AlertTriangle, CheckCircle2, XCircle, ArrowUpRight, BarChart3,
  Calendar, RefreshCw, Key
} from 'lucide-react';

export const AdminDashboard: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [threshold, setThreshold] = useState<number>(75);
  const [probeResult, setProbeResult] = useState<{ status: number; message: string; ok: boolean } | null>(null);

  const fetchDashboardData = async (thresh: number = threshold) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getAdminDashboard(thresh);
      setData(res);
    } catch (err: any) {
      console.error('Failed to load admin dashboard data:', err);
      setError(err.message || 'Failed to load institutional dashboard data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData(threshold);
  }, []);

  const runAdminProbe = async () => {
    try {
      const depts = await api.getAdminDepartments();
      setProbeResult({
        status: 200,
        message: `HTTP 200 OK: Admin token authenticated. Retrieved ${depts.length} departments.`,
        ok: true
      });
    } catch (err: any) {
      setProbeResult({
        status: err.status || 500,
        message: err.message || 'RBAC probe failed',
        ok: false
      });
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Top Banner */}
      <div className="glass-panel" style={{ borderLeft: '4px solid #3b82f6' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div className="header-badge" style={{ marginBottom: '0.4rem' }}>
              <ShieldAlert size={14} />
              Administrative Governance Center
            </div>
            <h2 style={{ fontSize: '1.6rem', fontWeight: 800 }}>Institutional Statutory Attendance Audit</h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '0.2rem' }}>
              Real-time cross-departmental compliance monitoring, statutory shortfall detection, and cohort analytics.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', background: 'rgba(15, 23, 42, 0.6)', padding: '0.4rem 0.8rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>Threshold:</span>
              <select
                value={threshold}
                onChange={(e) => {
                  const val = Number(e.target.value);
                  setThreshold(val);
                  fetchDashboardData(val);
                }}
                style={{
                  background: 'transparent',
                  color: '#fff',
                  border: 'none',
                  outline: 'none',
                  fontSize: '0.85rem',
                  fontWeight: 700,
                  cursor: 'pointer'
                }}
              >
                <option value={75} style={{ background: '#0f172a' }}>75% (Statutory Default)</option>
                <option value={80} style={{ background: '#0f172a' }}>80% (Strict Honor Roll)</option>
                <option value={65} style={{ background: '#0f172a' }}>65% (Condonation Floor)</option>
              </select>
            </div>

            <button
              className="btn btn-secondary btn-sm"
              onClick={() => fetchDashboardData(threshold)}
              title="Refresh dashboard data"
              aria-label="Refresh dashboard"
            >
              <RefreshCw size={13} />
              Refresh
            </button>

            <button
              className="btn btn-secondary btn-sm"
              onClick={runAdminProbe}
              title="Verify admin RBAC token"
            >
              <Key size={13} />
              Verify RBAC
            </button>
          </div>
        </div>

        {probeResult && (
          <div style={{
            marginTop: '1rem',
            padding: '0.75rem 1rem',
            borderRadius: '8px',
            background: probeResult.ok ? 'rgba(16, 185, 129, 0.1)' : 'rgba(244, 63, 94, 0.1)',
            border: `1px solid ${probeResult.ok ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`,
            color: probeResult.ok ? '#6ee7b7' : '#fda4af',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem'
          }}>
            {probeResult.ok ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
            <span>{probeResult.message}</span>
          </div>
        )}
      </div>

      {loading ? (
        <div className="glass-panel">
          <LoadingSpinner message="Calculating institutional metrics…" />
        </div>
      ) : error ? (
        <div className="glass-panel">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <AlertTriangle size={20} />
            <span style={{ fontWeight: 700 }}>Error loading dashboard:</span>
            <span>{error}</span>
          </div>
        </div>
      ) : data ? (
        <>
          {/* Key Metrics Row */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.25rem' }}>
            <div className="glass-panel">
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 600 }}>
                <span>Total Students</span>
                <GraduationCap size={18} style={{ color: '#60a5fa' }} />
              </div>
              <div style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.5rem' }}>
                {data.total_students}
              </div>
              <div style={{ fontSize: '0.8rem', color: '#93c5fd', marginTop: '0.3rem' }}>
                Enrolled active cohort
              </div>
            </div>

            <div className="glass-panel">
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 600 }}>
                <span>Total Faculty</span>
                <Users size={18} style={{ color: '#34d399' }} />
              </div>
              <div style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.5rem' }}>
                {data.total_faculty}
              </div>
              <div style={{ fontSize: '0.8rem', color: '#6ee7b7', marginTop: '0.3rem' }}>
                Teaching faculty members
              </div>
            </div>

            <div className="glass-panel">
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 600 }}>
                <span>Academic Departments</span>
                <Building2 size={18} style={{ color: '#a78bfa' }} />
              </div>
              <div style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.5rem' }}>
                {data.total_departments}
              </div>
              <div style={{ fontSize: '0.8rem', color: '#a5f3fc', marginTop: '0.3rem' }}>
                Undergraduate & postgrad
              </div>
            </div>

            <div className="glass-panel">
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 600 }}>
                <span>Overall Attendance</span>
                <TrendingUp size={18} style={{ color: data.overall_attendance_percentage >= threshold ? '#34d399' : '#fbbf24' }} />
              </div>
              <div style={{
                fontSize: '2rem',
                fontWeight: 800,
                marginTop: '0.5rem',
                color: data.overall_attendance_percentage >= threshold ? '#34d399' : '#f87171'
              }}>
                {data.overall_attendance_percentage}%
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
                {data.total_sessions} sessions recorded
              </div>
            </div>

            <div className="glass-panel" style={{ borderLeft: data.low_attendance_count > 0 ? '4px solid #f43f5e' : '4px solid #10b981' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 600 }}>
                <span>At-Risk Students (&lt;{data.threshold_used}%)</span>
                <AlertTriangle size={18} style={{ color: '#f87171' }} />
              </div>
              <div style={{ fontSize: '2rem', fontWeight: 800, marginTop: '0.5rem', color: data.low_attendance_count > 0 ? '#f87171' : '#34d399' }}>
                {data.low_attendance_count}
              </div>
              <div style={{ fontSize: '0.8rem', color: '#fda4af', marginTop: '0.3rem' }}>
                {data.institutional_at_risk_percentage}% institutional rate
              </div>
            </div>
          </div>

          {/* Attendance Trends & Department Breakdown Section */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '1.5rem' }}>
            {/* Attendance Trends Card */}
            <div className="glass-panel">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <BarChart3 size={18} style={{ color: '#60a5fa' }} />
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Attendance Trends</h3>
                </div>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Daily Institutional %</span>
              </div>

              {data.attendance_trends && data.attendance_trends.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                  {data.attendance_trends.map((t: any, idx: number) => {
                    const isAbove = t.attendance_percentage >= threshold;
                    return (
                      <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                          <span style={{ fontWeight: 600 }}>{t.date}</span>
                          <span style={{ fontWeight: 700, color: isAbove ? '#6ee7b7' : '#fda4af' }}>
                            {t.attendance_percentage}% ({t.attended_records}/{t.total_records} students)
                          </span>
                        </div>
                        <div style={{ width: '100%', height: '8px', background: 'rgba(255,255,255,0.06)', borderRadius: '4px', overflow: 'hidden' }}>
                          <div style={{
                            width: `${Math.min(100, t.attendance_percentage)}%`,
                            height: '100%',
                            background: isAbove ? 'linear-gradient(90deg, #10b981, #34d399)' : 'linear-gradient(90deg, #f43f5e, #fb7185)',
                            borderRadius: '4px',
                            transition: 'width 0.4s ease'
                          }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                  No historical session trend data recorded yet.
                </div>
              )}
            </div>

            {/* Attendance by Department Card */}
            <div className="glass-panel">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Building2 size={18} style={{ color: '#a78bfa' }} />
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Attendance by Department</h3>
                </div>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Statutory Breakdown</span>
              </div>

              {data.departments && data.departments.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem' }}>
                  {data.departments.map((dept: any, idx: number) => (
                    <div key={idx} style={{
                      background: 'rgba(15, 23, 42, 0.4)',
                      padding: '0.85rem 1rem',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-color)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center'
                    }}>
                      <div>
                        <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>{dept.department_name}</div>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                          Total Students: {dept.total_students} • Critical: {dept.critical_count}
                        </div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{
                          fontWeight: 800,
                          fontSize: '1rem',
                          color: dept.low_attendance_count > 0 ? '#f87171' : '#34d399'
                        }}>
                          {dept.low_attendance_count} Low Att.
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          {dept.low_attendance_percentage}% at-risk
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                  No department breakdown available.
                </div>
              )}
            </div>
          </div>

          {/* Low Attendance Students Table */}
          <div className="glass-panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <AlertTriangle size={20} style={{ color: '#f87171' }} />
                <h3 style={{ fontSize: '1.2rem', fontWeight: 800 }}>Low Attendance Students (&lt;{data.threshold_used}%)</h3>
              </div>
              <span className="badge" style={{ background: 'rgba(244, 63, 94, 0.15)', color: '#fda4af', border: '1px solid rgba(244, 63, 94, 0.3)' }}>
                {data.low_attendance_students?.length || 0} Critical Flag(s)
              </span>
            </div>

            {data.low_attendance_students && data.low_attendance_students.length > 0 ? (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
                      <th style={{ padding: '0.75rem' }}>Roll Number</th>
                      <th style={{ padding: '0.75rem' }}>Student Name</th>
                      <th style={{ padding: '0.75rem' }}>Department</th>
                      <th style={{ padding: '0.75rem' }}>Section</th>
                      <th style={{ padding: '0.75rem' }}>Attendance %</th>
                      <th style={{ padding: '0.75rem' }}>Conducted / Attended</th>
                      <th style={{ padding: '0.75rem' }}>Recovery Classes Needed</th>
                      <th style={{ padding: '0.75rem' }}>Compliance Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.low_attendance_students.map((s: any, idx: number) => {
                      const isCritical = s.status === 'CRITICAL' || s.overall_percentage < 65;
                      return (
                        <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                          <td style={{ padding: '0.75rem', fontWeight: 700, color: '#93c5fd' }}>{s.roll_number}</td>
                          <td style={{ padding: '0.75rem', fontWeight: 600 }}>{s.full_name}</td>
                          <td style={{ padding: '0.75rem', color: 'var(--text-muted)' }}>{s.department}</td>
                          <td style={{ padding: '0.75rem', color: 'var(--text-muted)' }}>{s.section}</td>
                          <td style={{ padding: '0.75rem', fontWeight: 800, color: isCritical ? '#f43f5e' : '#fbbf24' }}>
                            {s.overall_percentage}%
                          </td>
                          <td style={{ padding: '0.75rem' }}>{s.attended} / {s.conducted}</td>
                          <td style={{ padding: '0.75rem', fontWeight: 700, color: '#60a5fa' }}>
                            +{s.classes_needed} consecutive
                          </td>
                          <td style={{ padding: '0.75rem' }}>
                            <span style={{
                              padding: '0.25rem 0.6rem',
                              borderRadius: '4px',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              background: isCritical ? 'rgba(244, 63, 94, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                              color: isCritical ? '#fda4af' : '#fde68a',
                              border: `1px solid ${isCritical ? 'rgba(244, 63, 94, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`
                            }}>
                              {isCritical ? 'CRITICAL DEBARMENT' : 'CONDONATION REQ'}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
                <CheckCircle2 size={32} style={{ color: '#10b981', margin: '0 auto 0.75rem' }} />
                <p style={{ fontWeight: 600 }}>All students satisfy the {data.threshold_used}% statutory attendance requirement!</p>
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
};
