import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [person, setPerson] = useState<any>(null);
  const [stats, setStats] = useState({ total_persons: 0, detections_today: 0 });
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    // Connect to Backend SSE Events
    const evtSource = new EventSource("http://localhost:8000/api/events");

    evtSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setConnected(true);
        if (data.event === 'status') {
          if (data.detected) {
            setPerson({ name: data.name, id: data.id });
          } else {
            setPerson(null);
          }
          setStats({
            total_persons: data.total_persons,
            detections_today: data.detections_today
          });
        }
      } catch (err) {
        console.error("Failed to parse event data", err);
      }
    };

    evtSource.onerror = () => {
      setConnected(false);
    };

    return () => {
      evtSource.close();
    };
  }, []);

  return (
    <div style={{ padding: '2rem', fontFamily: 'sans-serif', textAlign: 'center' }}>
      <h1>Pi-Top Camera Dashboard</h1>
      <div style={{ marginBottom: '20px' }}>
        <strong>Status: </strong> 
        <span style={{ color: connected ? 'green' : 'red' }}>
          {connected ? 'Connected to Backend' : 'Disconnected'}
        </span>
      </div>

      <div style={{ display: 'flex', justifyContent: 'center', gap: '2rem' }}>
        <div style={{ border: '1px solid #ccc', padding: '1rem', borderRadius: '8px' }}>
          <h2>Live Detection</h2>
          {person ? (
            <div style={{ backgroundColor: '#e2f0d9', padding: '10px', borderRadius: '5px' }}>
              <h3>✅ Person Detected</h3>
              <p><strong>Name:</strong> {person.name}</p>
              <p><strong>ID:</strong> {person.id}</p>
            </div>
          ) : (
            <p>Scanning for faces...</p>
          )}
        </div>

        <div style={{ border: '1px solid #ccc', padding: '1rem', borderRadius: '8px' }}>
          <h2>Statistics</h2>
          <p>Total Detections Today: {stats.detections_today}</p>
          <p>Registered Persons: {stats.total_persons}</p>
        </div>
      </div>
      
      <div style={{ marginTop: '2rem' }}>
        <h3>Camera Stream</h3>
        <img 
          src="http://localhost:8000/video_feed" 
          alt="Video Stream" 
          style={{ width: '400px', borderRadius: '10px', backgroundColor: '#000' }} 
        />
      </div>
    </div>
  )
}

export default App
