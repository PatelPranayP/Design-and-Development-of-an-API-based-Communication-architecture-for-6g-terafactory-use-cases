import * as React from "react";
export function Button({ children, ...props }) {
  return (
    <button
      style={{ padding: "8px 16px", background: "#007bff", color: "white", border: "none", borderRadius: 4 }}
      {...props}
    >
      {children}
    </button>
  );
}
