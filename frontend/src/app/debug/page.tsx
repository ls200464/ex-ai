"use client";

import { useEffect, useState } from "react";

export default function DebugPage() {
  const [step1, setStep1] = useState("pending");
  const [step2, setStep2] = useState("pending");
  const [step3, setStep3] = useState("pending");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    console.log("[DEBUG] useEffect fired");
    setStep1("ok");

    // Test 1: direct fetch
    fetch("/api/personas?status=&page=1&page_size=20")
      .then((res) => {
        console.log("[DEBUG] fetch response:", res.status);
        setStep2(`ok (status=${res.status})`);
        return res.json();
      })
      .then((data) => {
        console.log("[DEBUG] fetch data:", data);
        setStep3(`ok (${data.total} personas)`);
      })
      .catch((err) => {
        console.error("[DEBUG] fetch error:", err);
        setError("Step2/3 failed: " + err.message);
        setStep2("failed");
        setStep3("failed");
      });
  }, []);

  return (
    <div style={{ padding: 40, fontFamily: "monospace" }}>
      <h1>Debug Page - Isolate Issue</h1>
      <table style={{ marginTop: 20, borderCollapse: "collapse" }}>
        <tbody>
          <tr>
            <td style={{ padding: 8, fontWeight: "bold" }}>Step 1: useEffect fires</td>
            <td style={{ padding: 8, color: step1 === "ok" ? "green" : "orange" }}>{step1}</td>
          </tr>
          <tr>
            <td style={{ padding: 8, fontWeight: "bold" }}>Step 2: fetch /api/personas</td>
            <td style={{ padding: 8, color: step2.startsWith("ok") ? "green" : "orange" }}>{step2}</td>
          </tr>
          <tr>
            <td style={{ padding: 8, fontWeight: "bold" }}>Step 3: parse JSON</td>
            <td style={{ padding: 8, color: step3.startsWith("ok") ? "green" : "orange" }}>{step3}</td>
          </tr>
        </tbody>
      </table>
      {error && (
        <div style={{ marginTop: 20, padding: 16, background: "#f8d7da", borderRadius: 8, color: "red" }}>
          {error}
        </div>
      )}
      <p style={{ marginTop: 20, color: "#666" }}>
        Open browser console (F12) to see console.log output
      </p>
    </div>
  );
}
