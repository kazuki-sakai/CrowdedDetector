window.setTimeout(() => {
  if (document.visibilityState === "visible") {
    window.location.reload();
  }
}, 10000);

