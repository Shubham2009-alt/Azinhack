/** Return whether a polling response still belongs to the active run. */
export function isCurrentRun(activeRunId, expectedRunId, cancelled = false) {
  return !cancelled && activeRunId === expectedRunId;
}

/** Return whether a refresh response still belongs to the latest refresh and run. */
export function isCurrentRefresh(activeRunId, expectedRunId, currentGeneration, expectedGeneration) {
  return activeRunId === expectedRunId && currentGeneration === expectedGeneration;
}
