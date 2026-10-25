import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils";

const alertVariants = cva(
  "relative grid w-full grid-cols-[auto_1fr] items-start gap-x-3 gap-y-1 rounded-xl border px-4 py-3 text-sm [&>svg]:mt-0.5 [&>svg]:size-4",
  {
    variants: {
      variant: {
        default: "border-border bg-card text-card-foreground",
        destructive:
          "border-destructive/25 bg-destructive/8 text-destructive dark:bg-destructive/12 [&>svg]:text-destructive",
        success:
          "border-success/25 bg-success/8 text-success dark:bg-success/12 [&>svg]:text-success",
        warning:
          "border-warning/30 bg-warning/10 text-warning-foreground dark:bg-warning/12 dark:text-warning [&>svg]:text-warning",
        info: "border-info/25 bg-info/8 text-info dark:bg-info/12 [&>svg]:text-info",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

function Alert({ className, variant, ...props }) {
  return (
    <div
      data-slot="alert"
      role="alert"
      className={cn(alertVariants({ variant }), className)}
      {...props}
    />
  );
}

function AlertTitle({ className, ...props }) {
  return (
    <div
      data-slot="alert-title"
      className={cn("col-start-2 min-h-4 font-semibold tracking-tight", className)}
      {...props}
    />
  );
}

function AlertDescription({ className, ...props }) {
  return (
    <div
      data-slot="alert-description"
      className={cn(
        "col-start-2 text-sm leading-relaxed text-muted-foreground",
        className
      )}
      {...props}
    />
  );
}

export { Alert, AlertDescription, AlertTitle };
