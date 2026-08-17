export function formatDuration(
  totalSeconds: number,
): string {
  const seconds = Math.max(
    0,
    Math.floor(totalSeconds),
  );

  const hours = Math.floor(
    seconds / 3600,
  );

  const minutes = Math.floor(
    (seconds % 3600) / 60,
  );

  const remainingSeconds =
    seconds % 60;

  if (hours > 0) {
    return `${hours} h ${minutes} min`;
  }

  if (minutes > 0) {
    return `${minutes} min ${remainingSeconds} s`;
  }

  return `${remainingSeconds} s`;
}

export function formatSignedDuration(
  totalSeconds: number,
): string {
  if (totalSeconds === 0) {
    return "0 s";
  }

  const sign = totalSeconds > 0 ? "+" : "-";

  return `${sign}${formatDuration(
    Math.abs(totalSeconds),
  )}`;
}