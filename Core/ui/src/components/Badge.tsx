import React from "react";

export interface BadgeProps {
  variant: "success" | "warning" | "error" | "info" | "neutral";
  children: React.ReactNode;
  size?: "sm" | "md";
}

const variantStyles: Record<BadgeProps["variant"], string> = {
  success: "bg-[#22c55e]/15 text-[#22c55e]",
  warning: "bg-[#f59e0b]/15 text-[#f59e0b]",
  error: "bg-[#ef4444]/15 text-[#ef4444]",
  info: "bg-[#3b82f6]/15 text-[#3b82f6]",
  neutral: "bg-[var(--muted)]/15 text-[var(--muted)]",
};

const sizeStyles: Record<NonNullable<BadgeProps["size"]>, string> = {
  sm: "px-2 py-0.5 text-xs",
  md: "px-2.5 py-1 text-xs",
};

export function Badge({ variant, children, size = "md" }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full font-medium ${variantStyles[variant]} ${sizeStyles[size]}`}
    >
      {children}
    </span>
  );
}
