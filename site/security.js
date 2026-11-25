"use strict";
fetch("data/portal.json", { cache: "no-store" })
  .then((r) => r.json())
  .then((d) => {
    const a = d.anchor;
    document.getElementById("anchor").textContent = a
      ? `${a.sha256}${a.environment !== "production" ? "  (DEVELOPMENT registry)" : ""}`
      : "No trust root published yet.";
  })
  .catch(() => { document.getElementById("anchor").textContent = "Could not load."; });
