import { createApp, log } from "./app";
import { serveStatic } from "./static";

(async () => {
  const { app, httpServer } = await createApp();

  if (process.env.NODE_ENV === "production") {
    serveStatic(app);
  } else {
    const { setupVite } = await import("./vite");
    await setupVite(httpServer, app);
  }

  const port = parseInt(process.env.PORT || "5000", 10);
  // `reusePort` enables socket-sharing across worker processes (Replit's
  // autoscale spawns several). On a single-process local dev box it's
  // unnecessary, and recent macOS+Node combos throw ENOTSUP when it's
  // set with host '0.0.0.0'. Opt in via env so prod keeps the optimization
  // while local dev just binds.
  const reusePort = process.env.REUSE_PORT === "true";
  httpServer.listen(
    {
      port,
      host: "0.0.0.0",
      ...(reusePort ? { reusePort: true } : {}),
    },
    () => {
      log(`serving on port ${port}`);
    },
  );

  log("all routes registered");
})();
