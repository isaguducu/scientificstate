import React from "react";

export interface FormFieldProps {
  label: string;
  error?: string;
  help?: string;
  required?: boolean;
  children: React.ReactNode;
}

export function FormField({
  label,
  error,
  help,
  required = false,
  children,
}: FormFieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium">
        {label}
        {required && <span className="ml-0.5 text-[#ef4444]">*</span>}
      </label>
      {children}
      {error && (
        <p className="text-xs text-[#ef4444]">{error}</p>
      )}
      {!error && help && (
        <p className="text-xs text-[var(--muted)]">{help}</p>
      )}
    </div>
  );
}
