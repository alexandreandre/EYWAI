import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function SectionSkeleton(): JSX.Element {
  return (
    <Card>
      <CardHeader className="p-4 pb-2">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="mt-1 h-3 w-full max-w-md" />
      </CardHeader>
      <CardContent className="space-y-2 p-4 pt-0">
        <Skeleton className="h-[220px] w-full" />
      </CardContent>
    </Card>
  );
}
