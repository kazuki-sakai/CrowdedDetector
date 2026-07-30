const refreshIntervalMilliseconds = 10000;
let refreshTimer;

function scheduleRefresh() {
  refreshTimer = window.setTimeout(() => {
    if (document.visibilityState === "visible") {
      window.location.reload();
      return;
    }
    scheduleRefresh();
  }, refreshIntervalMilliseconds);
}

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    window.clearTimeout(refreshTimer);
    window.location.reload();
  }
});

scheduleRefresh();
