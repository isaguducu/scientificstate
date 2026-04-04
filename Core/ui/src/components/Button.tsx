import React from "react";

export interface ButtonProps {
  variant: "primary" | "secondary" | "ghost" | "danger";
  size: "sm" | "md" | "lg";
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit";
}

const variantStyles: Record<ButtonProps["variant"], string> = {
  primary:
    "bg-[var(--accent)] text-black hover:opacity-90",
  secondary:
    "border border-[var(--border)] bg-[var(--surface)] text-[var(--foreground)] hover:bg-[var(--surface-hover)]",
  ghost:
    "text-[var(--muted)] hover:text-[var(--foreground)] hover:bg-[var(--surface-hover)]",
  danger:
    "bg-[#ef4444] text-white hover:opacity-90",
};

const sizeStyles: Record<ButtonProps["size"], string> = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-6 py-2.5 text-sm",
};

export function Button({
  variant,
  size,
  children,
  onClick,
  disabled = false,
  type = "button",
}: ButtonProps) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center rounded-lg font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none ${variantStyles[variant]} ${sizeStyles[size]}`}
    >
      {children}
    </button>
  );
}
