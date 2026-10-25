import { cn } from "@/lib/utils";

function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
  compact = false,
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-muted/20 px-6 text-center",
        compact ? "py-8" : "py-14",
        className
      )}
    >
      {Icon && (
        <div className="mb-3 grid size-11 place-items-center rounded-2xl bg-primary/8 text-primary">
          <Icon className="size-5" />
        </div>
      )}
      <h3 className="text-sm font-bold">{title}</h3>
      {description && (
        <p className="mt-1 max-w-sm text-xs leading-relaxed text-muted-foreground">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export { EmptyState };
