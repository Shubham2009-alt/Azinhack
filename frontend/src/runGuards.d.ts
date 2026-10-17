export function isCurrentRun(
  activeRunId: string,
  expectedRunId: string,
  cancelled?: boolean,
): boolean;

export function isCurrentRefresh(
  activeRunId: string,
  expectedRunId: string,
  currentGeneration: number,
  expectedGeneration: number,
): boolean;
