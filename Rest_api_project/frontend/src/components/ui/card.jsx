import * as React from "react";
export function Card({ children }) {
  return <div style={{ border: "1px solid #ccc", padding: 16, borderRadius: 8 }}>{children}</div>;
}
export function CardContent({ children }) {
  return <div>{children}</div>;
}
