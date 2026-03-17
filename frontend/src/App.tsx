import { useState, useEffect, useRef, useCallback } from 'react'
import './index.css'

// Dynamisch — funktioniert egal von welchem Gerät aus zugegriffen wird
const BACKEND = `http://${window.location.hostname}:8000`
// App.css intentionally not imported

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

const BASE_SIZE = 80
const KNOB_SIZE = 28
const JOYSTICK_MAX = (BASE_SIZE - KNOB_SIZE) / 2

function JoystickWidget({ zoom, onZoomChange }: { zoom: number; onZoomChange: (z: number) => void }) {
  const offsetRef   = useRef(0)
  const dragging    = useRef(false)
  const animFrame   = useRef(0)
  const zoomRef     = useRef(zoom)
  const startY      = useRef(0)
  const [offsetDisplay, setOffsetDisplay] = useState(0)
  const [isDragging, setIsDragging]       = useState(false)

  useEffect(() => { zoomRef.current = zoom }, [zoom])

  const tick = useCallback(() => {
    const rate = -(offsetRef.current / JOYSTICK_MAX) * 0.04
    const next = Math.max(1.0, Math.min(3.0, zoomRef.current + rate))
    zoomRef.current = next
    onZoomChange(next)
    if (dragging.current) animFrame.current = requestAnimationFrame(tick)
  }, [onZoomChange])

  const onPointerDown = (e: React.PointerEvent) => {
    dragging.current = true
    setIsDragging(true)
    startY.current = e.clientY
    ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    animFrame.current = requestAnimationFrame(tick)
  }

  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragging.current) return
    const dy = e.clientY - startY.current
    const clamped = Math.max(-JOYSTICK_MAX, Math.min(JOYSTICK_MAX, dy))
    offsetRef.current = clamped
    setOffsetDisplay(clamped)
  }

  const onPointerUp = () => {
    dragging.current = false
    setIsDragging(false)
    cancelAnimationFrame(animFrame.current)
    offsetRef.current = 0
    setOffsetDisplay(0)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, padding: '12px 0' }}>
      <div style={{ fontSize: 9, letterSpacing: 2, color: 'var(--text-dim)', marginBottom: 4 }}>KAMERA-ZOOM</div>
      <div style={{
        width: BASE_SIZE, height: BASE_SIZE, borderRadius: '50%',
        border: '1px solid var(--border)', background: 'rgba(255,255,255,0.02)',
        position: 'relative', userSelect: 'none',
      }}>
        {/* Vertikale Führungslinie */}
        <div style={{
          position: 'absolute', left: '50%', top: 6, bottom: 6,
          width: 1, background: 'rgba(255,255,255,0.08)',
          transform: 'translateX(-50%)',
        }} />
        {/* Knob */}
        <div
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          style={{
            width: KNOB_SIZE, height: KNOB_SIZE, borderRadius: '50%',
            background: isDragging ? 'var(--green)' : 'rgba(0,255,100,0.6)',
            border: '1px solid var(--green)',
            boxShadow: isDragging ? '0 0 10px var(--green)' : '0 0 4px var(--green)',
            position: 'absolute', left: '50%', top: '50%',
            transform: `translate(-50%, calc(-50% + ${offsetDisplay}px))`,
            transition: isDragging ? 'none' : 'transform 0.25s cubic-bezier(.22,1,.36,1)',
            cursor: isDragging ? 'grabbing' : 'grab',
            touchAction: 'none',
          }}
        />
      </div>
      <div style={{ fontSize: 10, color: zoom > 1.05 ? 'var(--green)' : 'var(--text-dim)', letterSpacing: 1, fontFamily: 'monospace' }}>
        {zoom.toFixed(1)}×
      </div>
      {zoom > 1.05 && (
        <div
          onClick={() => { zoomRef.current = 1.0; onZoomChange(1.0) }}
          style={{ fontSize: 8, letterSpacing: 1, color: 'var(--text-dim)', cursor: 'pointer', textDecoration: 'underline' }}
        >
          RESET
        </div>
      )}
    </div>
  )
}

export default function App() {
  const [person, setPerson]     = useState<Person | null>(null)
  const [stats, setStats]       = useState<Stats>({ total_persons: 0, detections_today: 0 })
  const [connected, setConnected] = useState(false)
  const [log, setLog]           = useState<LogEntry[]>([])
  const [zoomLevel, setZoomLevel] = useState(1.0)
  const logIdRef                = useRef(0)
  const now                     = useClock()

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
        }
      } catch (err) {
        console.error('Failed to parse event data', err)
      }
    }

    evtSource.onerror = () => setConnected(false)
    return () => evtSource.close()
  }, [])

  const threatLevel = person ? 3 : connected ? 1 : 2

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>

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
                  style={{ transform: `scale(${zoomLevel})`, transformOrigin: 'center', transition: 'transform 0.1s' }}
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

          {/* Joystick Zoom */}
          <div className="panel" style={{ borderTop: '1px solid var(--border)', alignItems: 'center' }}>
            <div className="panel-header">
              <span className="panel-label">Kamera-Steuerung</span>
            </div>
            <JoystickWidget zoom={zoomLevel} onZoomChange={setZoomLevel} />
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
