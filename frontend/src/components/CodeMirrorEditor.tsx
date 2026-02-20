"use client";

import React from "react";
import CodeMirror from "@uiw/react-codemirror";

interface CodeMirrorEditorProps {
  value: string;
  onChange?: (value: string) => void;
  readOnly?: boolean;
  editable?: boolean;
  height?: string;
  maxHeight?: string;
  theme?: "light" | "dark";
  basicSetup?: {
    lineNumbers?: boolean;
    foldGutter?: boolean;
    bracketMatching?: boolean;
  };
  className?: string;
}

export function CodeMirrorEditor({
  value,
  onChange,
  readOnly = false,
  editable = true,
  height = "200px",
  maxHeight,
  theme = "dark",
  basicSetup = { lineNumbers: true, foldGutter: true, bracketMatching: true },
  className,
}: CodeMirrorEditorProps) {
  return (
    <CodeMirror
      value={value}
      onChange={onChange}
      readOnly={readOnly}
      editable={editable}
      height={height}
      maxHeight={maxHeight}
      theme={theme}
      basicSetup={basicSetup}
      className={className}
    />
  );
}
