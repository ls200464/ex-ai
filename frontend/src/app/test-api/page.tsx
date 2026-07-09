"use client";

import { useEffect, useState } from "react";
import { personaApi } from "@/lib/api";

export default function TestApiPage() {
  const [result, setResult] = useState<string>("Testing...");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    personaApi
      .list()
      .then((data) => {
        setResult(`SUCCESS: ${data.total} personas. ${data.items.map(p => p.display_name).join(", ")}`);
        // Also test detail
        if (data.items.length > 0) {
          return personaApi.get(data.items[0].id);
        }
      })
      .then((detail) => {
        if (detail) {
          setResult(prev => prev + ` | Detail: ${detail.display_name} (${detail.status})`);
        }
      })
      .catch((err) => {
        setError(err.message);
        setResult("FAILED");
      });
  }, []);

  return (
    <div style={{ padding: 40, fontFamily: "monospace" }}>
      <h1>API Test Page</h1>
      <div
        style={{
          marginTop: 20,
          padding: 16,
          background: error ? "#f8d7da" : result.includes("SUCCESS") ? "#d4edda" : "#f0f0f0",
          borderRadius: 8,
        }}
      >
        <p><strong>Result:</strong> {result}</p>
        {error && <p style={{ color: "red" }}><strong>Error:</strong> {error}</p>}
      </div>
    </div>
  );
}
