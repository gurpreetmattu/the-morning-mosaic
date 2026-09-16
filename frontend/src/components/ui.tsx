import type { ButtonHTMLAttributes, LabelHTMLAttributes, ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded border border-rule bg-surface p-6 shadow-sm ${className}`}>
      {children}
    </div>
  );
}

export function PageTitle({ children }: { children: ReactNode }) {
  return <h1 className="mb-2 text-3xl font-bold tracking-tight">{children}</h1>;
}

export function Lede({ children }: { children: ReactNode }) {
  return <p className="mb-8 text-muted">{children}</p>;
}

export function Field({
  label,
  children,
  ...props
}: LabelHTMLAttributes<HTMLLabelElement> & { label: ReactNode; children: ReactNode }) {
  return (
    <label {...props} className="mb-4 block text-sm">
      <span className="mb-1 block font-semibold text-foreground">{label}</span>
      {children}
    </label>
  );
}

const inputClasses =
  "w-full rounded border border-rule bg-surface px-3 py-2 text-base text-foreground outline-none focus:border-accent";

export function textInputClasses(extra = ""): string {
  return `${inputClasses} ${extra}`.trim();
}

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" }) {
  const base =
    "rounded px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50";
  const variants: Record<string, string> = {
    primary: "bg-accent text-white hover:opacity-90",
    secondary: "border border-rule bg-surface text-foreground hover:border-accent",
    danger: "border border-accent text-accent hover:bg-accent-soft",
  };
  return <button {...props} className={`${base} ${variants[variant]} ${className}`} />;
}

export function Notice({
  kind,
  children,
}: {
  kind: "error" | "success" | "info";
  children: ReactNode;
}) {
  const styles: Record<string, string> = {
    error: "border-accent bg-accent-soft text-accent",
    success: "border-rule bg-accent-soft text-foreground",
    info: "border-rule bg-background text-muted",
  };
  return (
    <div role="status" className={`mb-6 rounded border px-4 py-3 text-sm ${styles[kind]}`}>
      {children}
    </div>
  );
}
