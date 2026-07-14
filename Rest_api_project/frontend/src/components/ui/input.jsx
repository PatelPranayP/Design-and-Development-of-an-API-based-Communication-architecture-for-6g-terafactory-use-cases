import * as React from "react";
export function Input(props) {
  return (
    <input
      {...props}
      style={{
        padding: 8,
        width: "100%",
        marginBottom: 12,
        border: "1px solid #ccc",
        borderRadius: 4
      }}
    />
  );
}
