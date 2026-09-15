import { queryOptions } from "@tanstack/react-query";
import { getAssessment, listAssessments } from "@/lib/api";

export const assessmentsQuery = () =>
  queryOptions({
    queryKey: ["assessments"],
    queryFn: listAssessments,
  });

export const assessmentQuery = (id: string) =>
  queryOptions({
    queryKey: ["assessments", id],
    queryFn: () => getAssessment(id),
  });
