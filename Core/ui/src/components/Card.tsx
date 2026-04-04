import React from "react";

export interface CardProps {
  title?: string;
  children: React.ReactNode;
  variant?: "default" | "outlined" | "elevated";
  padding?: "none" | "sm" | "md" | "lg";
}

const variantStyles: Record<NonNullable<CardProps["variant"]>, string> = {
  default: "border border-[var(--border)] bg-[var(--surface)]",
  outlined: "border border-[var(--border)]",
  elevated: "border border-[var(--border)] bg-[var(--surface)] shadow-lg",
};

const paddingStyles: Record<NonNullable<CardProps["padding"]>, string> = {
  none: "",
  sm: "p-3",
  md: "p-5",
  lg: "p-8",
};

export function Card({
  title,
  children,
  variant = "default",
  padding = "md",
}: CardProps) {
  return (
    <div className={`rounded-lg ${variantStyles[variant]} ${paddingStyles[padding]}`}>
      {title && <h3 className="font-semibold mb-2">{title}</h3>}
      {children}
    </div>
  );
}
