import { useState, useEffect, useRef } from 'react'
import './index.css'

const BACKEND = `http://${window.location.hostname}:8000`

// ─── ENROLL PAGE ──────────────────────────────────────────────────────────────
function EnrollPage({ onBack }: { onBack: () => void }) {
  const [capturing, setCapturing]   = useState(false)
  const [captured, setCaptured]     = useState<{ photo: string; encoding: number[] } | null>(null)
  const [captureErr, setCaptureErr] = useState('')
  const [firstName, setFirstName]   = useState('')
  const [lastName, setLastName]     = useState('')
  const [department, setDepartment] = useState('')
  const [pin, setPin]               = useState('')
  const [saving, setSaving]         = useState(false)
  const [saved, setSaved]           = useState<{ id: number; name: string } | null>(null)
  const [saveErr, setSaveErr]       = useState('')

  async function captureFace() {
    setCapturing(true)
    setCaptureErr('')
    try {
      const res  = await fetch(`${BACKEND}/api/capture_face`)
      const data = await res.json()
      if (data.success) {
        setCaptured({ photo: data.photo, encoding: data.encoding })
      } else {
        setCaptureErr(data.error || 'Fehler')
      }
    } catch {
      setCaptureErr('Verbindungsfehler')
    } finally {
      setCapturing(false)
    }
  }

  async function handleSave() {
    if (!captured)       return setSaveErr('Zuerst Gesicht aufnehmen')
    if (!firstName.trim()) return setSaveErr('Vorname erforderlich')
    if (!lastName.trim())  return setSaveErr('Nachname erforderlich')
    setSaving(true)
    setSaveErr('')
    try {
      const res  = await fetch(`${BACKEND}/api/enroll`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          first_name: firstName.trim(),
          last_name:  lastName.trim(),
          department: department.trim(),
          pin:        pin || null,
          encoding:   captured.encoding,
          photo:      captured.photo,
        }),
      })
      const data = await res.json()
      if (data.success) {
        setSaved({ id: data.id, name: data.name })
      } else {
        setSaveErr(data.error || 'Fehler beim Speichern')
      }
    } catch {
      setSaveErr('Verbindungsfehler')
    } finally {
      setSaving(false)
    }
  }

  if (saved) {
    return (
      <div className="enroll-success">
        <div className="enroll-success-icon">■</div>
        <div className="enroll-success-title">BENUTZER REGISTRIERT</div>
        <div className="enroll-success-name">{saved.name}</div>
        <div className="enroll-success-id">ID #{String(saved.id).padStart(6, '0')}</div>
        <div className="enroll-success-sub">Gesicht wird ab sofort erkannt</div>
        <button className="enroll-btn" style={{ marginTop: 24, maxWidth: 240 }} onClick={onBack}>
          ← ZURÜCK ZUR ÜBERSICHT
        </button>
      </div>
    )
  }

  return (
    <div className="enroll-page">
      {/* Header */}
      <div className="enroll-header">
        <button className="enroll-back-btn" onClick={onBack}>← ZURÜCK</button>
        <span className="enroll-header-title">NEUEN BENUTZER REGISTRIEREN</span>
        <span className="enroll-header-id">ENROLLMENT · SEKTOR A1</span>
      </div>

      <div className="enroll-body">
        {/* LEFT: Kamera + Capture */}
        <div className="enroll-left">
          <div className="panel-header"><span className="panel-label">Live-Kamera</span></div>
          <div className="enroll-cam-wrap">
            <img src={`${BACKEND}/video_feed`} alt="Kamera" className="enroll-cam" />
            <div className="cam-corner tl"/><div className="cam-corner tr"/>
            <div className="cam-corner bl"/><div className="cam-corner br"/>
          </div>
          <button
            className={`enroll-capture-btn ${capturing ? 'enrolling' : ''}`}
            onClick={captureFace}
            disabled={capturing}
          >
            {capturing ? '◌ ERKENNUNG LÄUFT...' : '⊙ GESICHT AUFNEHMEN'}
          </button>
          {captureErr && <div className="enroll-err">{captureErr}</div>}

          {captured && (
            <div className="enroll-face-preview">
              <div className="panel-header" style={{ marginTop: 12 }}>
                <span className="panel-label">Aufgenommenes Gesicht</span>
                <span className="panel-id" style={{ color: 'var(--green)' }}>● BEREIT</span>
              </div>
              <img src={captured.photo} alt="Gesicht" className="enroll-face-img" />
            </div>
          )}
        </div>

        {/* RIGHT: Formular */}
        <div className="enroll-right">
          <div className="panel-header"><span className="panel-label">Benutzerdaten</span></div>

          <div className="enroll-form">
            <label className="enroll-label">VORNAME</label>
            <input className="enroll-input" value={firstName} onChange={e => setFirstName(e.target.value)} placeholder="Max" />

            <label className="enroll-label">NACHNAME</label>
            <input className="enroll-input" value={lastName} onChange={e => setLastName(e.target.value)} placeholder="Mustermann" />

            <label className="enroll-label">ABTEILUNG</label>
            <input className="enroll-input" value={department} onChange={e => setDepartment(e.target.value)} placeholder="z.B. IT, Verwaltung ..." />

            <label className="enroll-label">
              PIN
              <span style={{ fontSize: 8, color: 'var(--text-dim)', marginLeft: 8 }}>WIRD NICHT ANGEZEIGT</span>
            </label>
            <input
              className="enroll-input"
              type="password"
              value={pin}
              onChange={e => setPin(e.target.value.replace(/\D/g, '').slice(0, 8))}
              placeholder="••••"
              autoComplete="new-password"
            />
            {pin && (
              <div className="enroll-pin-hint">
                {'•'.repeat(pin.length)} · {pin.length} Stellen
              </div>
            )}

            <div className="enroll-id-note">
              <span className="sys-key">ID</span>
              <span className="sys-val" style={{ color: 'var(--text-dim)' }}>WIRD AUTOMATISCH VERGEBEN</span>
            </div>

            {saveErr && <div className="enroll-err">{saveErr}</div>}

            <button
              className={`enroll-capture-btn ${saving ? 'enrolling' : ''} ${!captured ? 'disabled' : ''}`}
              style={{ marginTop: 16 }}
              onClick={handleSave}
              disabled={saving || !captured}
            >
              {saving ? '◌ WIRD GESPEICHERT...' : '+ IN DATENBANK EINTRAGEN'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

interface Person {
  name: string
  id: string | number
}

interface Stats {
  total_persons: number
  detections_today: number
}

interface LogEntry {
  time: string
  name: string
  status: 'granted' | 'denied' | 'unknown'
  id: number
}

function useClock() {
  const [time, setTime] = useState(new Date())
  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(t)
  }, [])
  return time
}

function formatDate(d: Date) {
  return d.toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' })
    .toUpperCase()
}

function formatTime(d: Date) {
  return d.toTimeString().slice(0, 8)
}


export default function App() {
  const [page, setPage]         = useState<'main' | 'enroll'>('main')
  const [person, setPerson]     = useState<Person | null>(null)
  const [stats, setStats]       = useState<Stats>({ total_persons: 0, detections_today: 0 })
  const [connected, setConnected] = useState(false)
  const [log, setLog]           = useState<LogEntry[]>([])
  const [doorStatus, setDoorStatus] = useState<'closed' | 'checking' | 'open' | 'denied'>('closed')
  const [toast, setToast]       = useState<{ msg: string; type: 'ok' | 'err' } | null>(null)
  const logIdRef                = useRef(0)
  const toastTimer              = useRef<ReturnType<typeof setTimeout> | null>(null)
  const now                     = useClock()

  function showToast(msg: string, type: 'ok' | 'err') {
    setToast({ msg, type })
    if (toastTimer.current) clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(null), 2000)
  }

  useEffect(() => {
    const evtSource = new EventSource(`${BACKEND}/api/events`)

    evtSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        setConnected(true)

        if (data.event === 'status') {
          const detected = !!data.detected
          const incoming: Person | null = detected ? { name: data.name, id: data.id } : null

          setPerson(prev => {
            if (detected && (!prev || prev.id !== data.id)) {
              const entry: LogEntry = {
                time: new Date().toTimeString().slice(0, 8),
                name: data.name,
                status: 'granted',
                id: ++logIdRef.current,
              }
              setLog(l => [entry, ...l].slice(0, 50))
            }
            return incoming
          })

          setStats({
            total_persons:    data.total_persons    ?? 0,
            detections_today: data.detections_today ?? 0,
          })
          if (data.door_status && data.door_status !== doorStatus) {
            setDoorStatus(data.door_status)
            if (data.door_status === 'open')   showToast('ZUGANG GEWÄHRT', 'ok')
            if (data.door_status === 'denied') showToast('ZUGANG VERWEIGERT', 'err')
          }
        }
      } catch (err) {
        console.error('Failed to parse event data', err)
      }
    }

    evtSource.onerror = () => setConnected(false)
    return () => evtSource.close()
  }, [])

  const threatLevel = person ? 3 : connected ? 1 : 2

  function handleEnroll() {
    setPage('enroll')
  }

  if (page === 'enroll') return <EnrollPage onBack={() => setPage('main')} />

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>

      {/* ── TOAST ── */}
      {toast && (
        <div className={`toast toast-${toast.type}`}>
          {toast.type === 'ok' ? '■' : '◆'} {toast.msg}
        </div>
      )}

      {/* ── HEADER ── */}
      <header className="header">
        <div className="header-logo">
          <span className="facility">Justizvollzugsanstalt · Sektor A</span>
          <span className="title">Sicherheits-Zentrale</span>
        </div>
        <div className="header-meta">
          <span className="clock">{formatTime(now)}</span>
          <span className="date-line">{formatDate(now)}</span>
        </div>
      </header>

      {/* ── STATUS BAR ── */}
      <div className="statusbar">
        <div className={`status-item ${connected ? 'active' : ''}`}>
          <div className={`status-dot ${connected ? 'online' : 'offline'}`} />
          {connected ? 'System Online' : 'Verbindung getrennt'}
        </div>
        <div className="status-divider" />
        <div className="status-item">
          <div className={`status-dot ${person ? 'warning' : 'online'}`} />
          {person ? 'Person Erkannt' : 'Kein Alarm'}
        </div>
        <div className="status-divider" />
        <div className="status-item">
          <div className="status-dot online" />
          Kamera A1 Aktiv
        </div>
        <div className="status-divider" />
        <div className="status-item">
          Terminal · v2.4.1
        </div>
      </div>

      {/* ── ALERT BANNER ── */}
      {person ? (
        <div className="alert-banner detected">
          <span className="alert-icon">⚠</span>
          <span className="alert-text">ACHTUNG — PERSON IDENTIFIZIERT: {person.name.toUpperCase()}</span>
          <span className="alert-level">ALARMSTUFE 3</span>
        </div>
      ) : connected ? (
        <div className="alert-banner clear">
          <span className="alert-icon">■</span>
          <span className="alert-text">Bereich gesichert — Keine unautorisierten Personen</span>
          <span className="alert-level">GRÜNSTUFE</span>
        </div>
      ) : (
        <div className="alert-banner unknown">
          <span className="alert-icon">◆</span>
          <span className="alert-text">Verbindung zu Überwachungssystem unterbrochen</span>
          <span className="alert-level">UNBEKANNT</span>
        </div>
      )}

      {/* ── MAIN GRID ── */}
      <div className="main-grid" style={{ flex: 1 }}>

        {/* LEFT — Detection Dossier */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-label">Erkennungs-Protokoll</span>
            <span className="panel-id">MODUL-01</span>
          </div>
          {person ? (
            <div className="panel-body">
              <div className="dossier">
                <div className="dossier-info">
                  <div className="dossier-photo">👤</div>
                  <div className="dossier-fields">
                    <div className="field-row">
                      <span className="field-label">Identifiziert</span>
                      <span className="field-value name">{person.name}</span>
                    </div>
                    <div className="field-row">
                      <span className="field-label">Datensatz-ID</span>
                      <span className="field-value id">#{String(person.id).padStart(6, '0')}</span>
                    </div>
                  </div>
                </div>
                <div className="field-divider" />
                <div className="field-row">
                  <span className="field-label">Erkennungszeit</span>
                  <span className="field-value">{formatTime(now)}</span>
                </div>
                <div className="field-row">
                  <span className="field-label">Status</span>
                  <span className="field-value" style={{ color: 'var(--red)' }}>● AKTIV ÜBERWACHT</span>
                </div>
                <div className="field-row">
                  <span className="field-label">Sektor</span>
                  <span className="field-value">A1 · HAUPTEINGANG</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="scanning">
              <div className="scan-ring" />
              <span className="scan-text">Gesichtsabgleich läuft...</span>
            </div>
          )}

          {/* Log */}
          <div className="panel-header" style={{ marginTop: 'auto' }}>
            <span className="panel-label">Ereignisprotokoll</span>
            <span className="panel-id">{log.length} Einträge</span>
          </div>
          <div className="log-list">
            {log.length === 0 ? (
              <div className="log-entry" style={{ opacity: 1 }}>
                <span className="log-time">--:--:--</span>
                <span className="log-name" style={{ color: 'var(--text-dim)' }}>Keine Ereignisse</span>
              </div>
            ) : log.map(e => (
              <div key={e.id} className="log-entry">
                <span className="log-time">{e.time}</span>
                <span className="log-name">{e.name}</span>
                <span className={`log-badge ${e.status}`}>{e.status === 'granted' ? 'OK' : e.status === 'denied' ? 'ABGELEHNT' : 'UNBEKANNT'}</span>
              </div>
            ))}
          </div>
        </div>

        {/* CENTER — Camera Feed */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-label">Kamera A1 — Haupteingang</span>
            <span className="panel-id">LIVE</span>
          </div>
          <div className="camera-wrap" style={{ flex: 1, overflow: 'hidden' }}>
            {connected ? (
              <>
                <img
                  src={`${BACKEND}/video_feed`}
                  alt="Kamera Stream"
                />
                <div className="camera-overlay">
                  <div className="cam-corner tl" />
                  <div className="cam-corner tr" />
                  <div className="cam-corner bl" />
                  <div className="cam-corner br" />
                  <div className="cam-label">KAM-A1 · SEKTOR NORD</div>
                  <div className="cam-rec">
                    <div className="cam-rec-dot" />
                    REC
                  </div>
                  <div className="cam-crosshair" />
                  <div className="cam-bottom">
                    <span>CAM:{String(1).padStart(3,'0')}</span>
                    <span>{formatTime(now)}</span>
                    <span>JVA-ZENTRALE</span>
                  </div>
                </div>
              </>
            ) : (
              <div className="cam-offline">
                <div className="cam-offline-icon">📷</div>
                <div className="cam-offline-text">Signal unterbrochen</div>
                <div className="cam-offline-text" style={{ fontSize: '8px', letterSpacing: '1px' }}>
                  Verbinde mit localhost:8000...
                </div>
              </div>
            )}
          </div>
          <div className="panel-header">
            <span className="panel-label">Analyse</span>
            <span className="panel-id" style={{ color: person ? 'var(--red)' : 'var(--green)' }}>
              {person ? '● PERSON ERKANNT' : '○ KEIN GESICHT'}
            </span>
          </div>
        </div>

        {/* RIGHT — Stats + Threat */}
        <div className="sidebar-right">
          {/* Threat level */}
          <div className="panel">
            <div className="panel-header">
              <span className="panel-label">Bedrohungsstufe</span>
            </div>
            <div className="threat-level">
              <span className="threat-label">Aktuell</span>
              <div className={`threat-value ${threatLevel >= 3 ? 'elevated' : ''} ${threatLevel >= 4 ? 'high' : ''}`}>
                STUFE {threatLevel}
              </div>
              <div className="threat-meter">
                {[1,2,3,4,5].map(n => (
                  <div key={n} className={`threat-bar ${n <= threatLevel ? `active-${n}` : ''}`} />
                ))}
              </div>
            </div>
          </div>

          {/* Tür-Status */}
          <div className="panel" style={{ borderTop: '1px solid var(--border)' }}>
            <div className="panel-header">
              <span className="panel-label">Türstatus</span>
              <span className="panel-id">SEKTOR A1</span>
            </div>
            <div style={{ padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{
                  width: 10, height: 10, borderRadius: '50%', flexShrink: 0,
                  background: doorStatus === 'open' ? 'var(--green)' : doorStatus === 'checking' ? '#f0c040' : doorStatus === 'denied' ? 'var(--red)' : 'var(--text-dim)',
                  boxShadow: doorStatus === 'open' ? '0 0 8px var(--green)' : doorStatus === 'checking' ? '0 0 8px #f0c040' : doorStatus === 'denied' ? '0 0 8px var(--red)' : 'none',
                }} />
                <span style={{
                  fontSize: 11, letterSpacing: 2, fontFamily: 'monospace',
                  color: doorStatus === 'open' ? 'var(--green)' : doorStatus === 'checking' ? '#f0c040' : doorStatus === 'denied' ? 'var(--red)' : 'var(--text-dim)',
                }}>
                  {doorStatus === 'open' ? 'GEÖFFNET' : doorStatus === 'checking' ? 'PRÜFUNG...' : doorStatus === 'denied' ? 'ZUGANG VERWEIGERT' : 'GESICHERT'}
                </span>
              </div>
              <div style={{ fontSize: 8, color: 'var(--text-dim)', letterSpacing: 1 }}>
                {doorStatus === 'open' ? 'Tür offen · Schließt automatisch' : doorStatus === 'checking' ? 'Warte auf Zentrale-Entscheidung' : doorStatus === 'denied' ? 'Zugriff wurde abgelehnt' : 'Tür verriegelt · Kein Zutritt'}
              </div>
            </div>
          </div>

          {/* Stats */}
          <div className="panel" style={{ borderTop: '1px solid var(--border)' }}>
            <div className="panel-header">
              <span className="panel-label">Tagesstatistik</span>
              <span className="panel-id">HEUTE</span>
            </div>
            <div className="stat-grid">
              <div className="stat-item">
                <span className="stat-label">Erkennungen Heute</span>
                <span className="stat-value">{stats.detections_today}</span>
                <span className="stat-sub">Vorgänge protokolliert</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Registrierte Personen</span>
                <span className="stat-value green">{stats.total_persons}</span>
                <span className="stat-sub">In der Datenbank</span>
              </div>
            </div>
          </div>

          {/* System info */}
          <div className="panel" style={{ borderTop: '1px solid var(--border)' }}>
            <div className="panel-header">
              <span className="panel-label">Systemstatus</span>
            </div>
            <div className="sys-info">
              <div className="sys-row">
                <span className="sys-key">Backend</span>
                <span className={`sys-val ${connected ? 'ok' : 'error'}`}>{connected ? 'ONLINE' : 'OFFLINE'}</span>
              </div>
              <div className="sys-row">
                <span className="sys-key">Datenbank</span>
                <span className="sys-val ok">ONLINE</span>
              </div>
              <div className="sys-row">
                <span className="sys-key">KI-Modul</span>
                <span className={`sys-val ${connected ? 'ok' : 'warn'}`}>{connected ? 'BEREIT' : 'WARTEN'}</span>
              </div>
              <div className="sys-row">
                <span className="sys-key">Speicher</span>
                <span className="sys-val ok">OK</span>
              </div>
              <div className="sys-row">
                <span className="sys-key">Version</span>
                <span className="sys-val">2.4.1</span>
              </div>
            </div>
          </div>

          {/* Enrollment */}
          <div className="panel" style={{ borderTop: '1px solid var(--border)', padding: '12px' }}>
            <div className="panel-header" style={{ marginBottom: 8 }}>
              <span className="panel-label">Zentrale</span>
            </div>
            <button
              className="enroll-btn"
              onClick={handleEnroll}
              disabled={!connected}
            >
              + BENUTZER HINZUFÜGEN
            </button>
          </div>
        </div>

      </div>

      {/* ── FOOTER ── */}
      <footer className="footer">
        <span>JVA Sicherheitssystem © 2025</span>
        <span>Alle Aktivitäten werden protokolliert und überwacht</span>
        <span>Terminal ID: PT-A1-0042</span>
      </footer>
    </div>
  )
}
