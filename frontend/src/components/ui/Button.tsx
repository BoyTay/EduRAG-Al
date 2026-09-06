import type { ButtonHTMLAttributes } from "react";
import { cn } from "../../utils/cn";
export function Button({ className, variant = "primary", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger" }) {
  const styles = { primary: "bg-brand text-white shadow-brand hover:bg-brand-dark", secondary: "border border-line bg-white text-ink hover:border-brand hover:bg-green-50", ghost: "text-muted hover:bg-green-50 hover:text-brand", danger: "text-red-700 hover:bg-red-50" };
  return <button className={cn("inline-flex min-h-11 items-center justify-center gap-2 rounded-full px-4 text-sm font-semibold transition duration-200 ease-out hover:-translate-y-0.5 active:translate-y-0 active:scale-[.98] focus:outline-none focus:ring-4 focus:ring-green-200 disabled:pointer-events-none disabled:opacity-50", styles[variant], className)} {...props} />;
}
