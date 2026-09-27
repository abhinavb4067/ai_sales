export function extractErrorMessage(error) {
  const payload = error?.response?.data;
  if (payload?.error?.message) {
    const details = payload.error.details;
    if (details && typeof details === "object") {
      const firstKey = Object.keys(details)[0];
      const firstMsg = Array.isArray(details[firstKey]) ? details[firstKey][0] : details[firstKey];
      if (firstMsg) return `${firstKey}: ${firstMsg}`;
    }
    return payload.error.message;
  }
  return error?.message || "Something went wrong. Please try again.";
}
