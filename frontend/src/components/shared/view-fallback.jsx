import { Skeleton } from "@/components/ui/skeleton";

function ViewFallback() {
  return (
    <div className="space-y-5" aria-busy="true" aria-label="Loading view">
      <div className="space-y-2">
        <Skeleton className="h-2.5 w-24" />
        <Skeleton className="h-8 w-64 max-w-full" />
        <Skeleton className="h-3.5 w-full max-w-xl" />
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <Skeleton className="h-80 rounded-2xl" />
        <Skeleton className="h-80 rounded-2xl" />
      </div>
    </div>
  );
}

export { ViewFallback };
