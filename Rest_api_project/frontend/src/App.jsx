import { useState } from "react";
import axios from "axios";

export default function RobotDashboard() {
  const [mode, setMode] = useState("maintenance");
  const [survMode, setSurvMode] = useState("manual"); // manual | auto
  const [loading, setLoading] = useState(false);

  // ✅ Separate response per tab
  const [response, setResponse] = useState({
    maintenance: null,
    surveillance: null
  });

const SERVER_IP = window.location.hostname;
const API_ENDPOINT = `http://${SERVER_IP}:8000/api/robot/send-task`;
const CAMERA_FEED_URL = `http://${SERVER_IP}:8080/stream`;

  const [maintenance, setMaintenance] = useState({
    task_id: "",
    fault_type: "",
    location_x: "",
    location_y: "",
    priority: 1,
    direction: "",
    movement_duration: 3
  });

  const [survManual, setSurvManual] = useState({
    task_id: "",
    priority: 1,
    direction: "",
    movement_duration: 3
  });

  const [survAuto, setSurvAuto] = useState({
    rounds: 1
  });

  const handleChange = (setter) => (e) => {
    const { name, value } = e.target;
    setter((prev) => ({ ...prev, [name]: value }));
  };

  const setDirection = (setter, dir) => {
    setter((prev) => ({ ...prev, direction: dir }));
  };

  const handleSubmit = async () => {
    setLoading(true);

    // ✅ Clear only current tab response
    setResponse((prev) => ({ ...prev, [mode]: null }));

    try {
      let payload = {};

      if (mode === "maintenance") {
        payload = { ...maintenance };
      } else {
        payload =
          survMode === "manual"
            ? { surveillance_mode: "manual", ...survManual }
            : { surveillance_mode: "auto", ...survAuto };
      }

      const res = await axios.post(API_ENDPOINT, payload);

      // ✅ Save response only for current tab
      setResponse((prev) => ({
        ...prev,
        [mode]: { ok: true, data: res.data }
      }));
    } catch (err) {
      setResponse((prev) => ({
        ...prev,
        [mode]: { ok: false, error: err.response?.data || err.message }
      }));
    }

    setLoading(false);
  };

  return (
    <div style={{ maxWidth: 1100, margin: "auto", padding: 30, fontFamily: "Arial" }}>
      <h1 style={{ textAlign: "center", color: "#3b82f6" }}>
        🤖 Robot Control Dashboard (REST)
      </h1>

      {/* Main Mode */}
      <div style={{ marginBottom: 20 }}>
        <label style={{ fontWeight: 600, marginRight: 10 }}>Select Mode:</label>
        <select
          value={mode}
          onChange={(e) => {
            const newMode = e.target.value;
            setMode(newMode);
            // ✅ Optional: clear the newly selected tab response
            // setResponse((prev) => ({ ...prev, [newMode]: null }));
          }}
          style={{ padding: 8 }}
        >
          <option value="maintenance">Maintenance</option>
          <option value="surveillance">Surveillance</option>
        </select>
      </div>

      {/* ================= MAINTENANCE ================= */}
      {mode === "maintenance" && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 20,
            background: "#f9fafb",
            padding: 20,
            borderRadius: 10
          }}
        >
          <Input label="Task ID" name="task_id" value={maintenance.task_id} onChange={handleChange(setMaintenance)} />
          <Input label="Fault Type" name="fault_type" value={maintenance.fault_type} onChange={handleChange(setMaintenance)} />
          <Input label="Location X" name="location_x" value={maintenance.location_x} onChange={handleChange(setMaintenance)} />
          <Input label="Location Y" name="location_y" value={maintenance.location_y} onChange={handleChange(setMaintenance)} />
          <Input label="Priority" name="priority" type="number" value={maintenance.priority} onChange={handleChange(setMaintenance)} />
          <Input
            label="Movement Duration (sec)"
            name="movement_duration"
            type="number"
            value={maintenance.movement_duration}
            onChange={handleChange(setMaintenance)}
          />

          <div style={{ gridColumn: "1 / -1" }}>
            <label style={{ fontWeight: 600 }}>Direction</label>
            <DirectionButtons active={maintenance.direction} onPick={(dir) => setDirection(setMaintenance, dir)} />
          </div>
        </div>
      )}

      {/* ================= SURVEILLANCE ================= */}
      {mode === "surveillance" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          {/* LEFT SIDE CONTROLS */}
          <div style={{ background: "#f9fafb", padding: 20, borderRadius: 10 }}>
            <div style={{ marginBottom: 15 }}>
              <label style={{ fontWeight: 600, marginRight: 10 }}>Surveillance Mode:</label>
              <select value={survMode} onChange={(e) => setSurvMode(e.target.value)} style={{ padding: 8 }}>
                <option value="manual">Manual</option>
                <option value="auto">Auto</option>
              </select>
            </div>

            {survMode === "manual" && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
                <Input label="Task ID" name="task_id" value={survManual.task_id} onChange={handleChange(setSurvManual)} />
                <Input
                  label="Priority"
                  name="priority"
                  type="number"
                  value={survManual.priority}
                  onChange={handleChange(setSurvManual)}
                />
                <Input
                  label="Movement Duration (sec)"
                  name="movement_duration"
                  type="number"
                  value={survManual.movement_duration}
                  onChange={handleChange(setSurvManual)}
                />

                <div style={{ gridColumn: "1 / -1" }}>
                  <label style={{ fontWeight: 600 }}>Direction</label>
                  <DirectionButtons active={survManual.direction} onPick={(dir) => setDirection(setSurvManual, dir)} />
                </div>
              </div>
            )}

            {survMode === "auto" && (
              <Input label="Rounds" name="rounds" type="number" value={survAuto.rounds} onChange={handleChange(setSurvAuto)} />
            )}
          </div>

          {/* RIGHT SIDE CAMERA */}
          <div style={{ background: "#111827", padding: 20, borderRadius: 10 }}>
            <div style={{ color: "white", fontWeight: 700, marginBottom: 10 }}>📷 Live Camera Feed</div>
            <img src={CAMERA_FEED_URL} alt="Camera Feed" style={{ width: "100%", borderRadius: 8 }} />
          </div>
        </div>
      )}

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={loading}
        style={{
          marginTop: 20,
          padding: "10px 20px",
          fontSize: 16,
          background: "#10b981",
          color: "white",
          border: "none",
          borderRadius: 6
        }}
      >
        {loading ? "Sending..." : "🚀 Send Task"}
      </button>

      {/* ✅ Show response ONLY for current tab */}
      {response[mode] && (
        <pre style={{ marginTop: 20, background: "#f3f4f6", padding: 15 }}>
          {JSON.stringify(response[mode], null, 2)}
        </pre>
      )}
    </div>
  );
}

function Input({ label, ...props }) {
  return (
    <div>
      <label style={{ fontWeight: 600 }}>{label}</label>
      <input
        {...props}
        style={{
          width: "100%",
          padding: 8,
          borderRadius: 4,
          border: "1px solid #ccc"
        }}
      />
    </div>
  );
}

function DirectionButtons({ active, onPick }) {
  const buttons = [
    { label: "⬅️", dir: "left" },
    { label: "⬆️", dir: "forward" },
    { label: "⬇️", dir: "backward" },
    { label: "➡️", dir: "right" }
  ];

  return (
    <div>
      {buttons.map(({ label, dir }) => (
        <button
          key={dir}
          onClick={() => onPick(dir)}
          style={{
            margin: 5,
            padding: 10,
            background: active === dir ? "#2563eb" : "#e5e7eb",
            color: active === dir ? "white" : "black",
            border: "none",
            borderRadius: 6
          }}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
