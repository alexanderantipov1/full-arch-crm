import express, {
  type Express,
  type Request,
  type Response,
  type NextFunction,
} from "express";
import { createServer, type Server } from "http";
import { registerRoutes } from "./routes";

declare module "http" {
  interface IncomingMessage {
    rawBody: unknown;
  }
}

export function log(message: string, source = "express") {
  const formattedTime = new Date().toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  });

  console.log(`${formattedTime} [${source}] ${message}`);
}

// Lightweight per-request logger for /api paths. Captures the JSON body so the
// log line includes the actual response payload — useful for tracing what the
// API said, not just the status code.
function requestLogger(req: Request, res: Response, next: NextFunction) {
  const start = Date.now();
  const path = req.path;
  let capturedJsonResponse: Record<string, any> | undefined = undefined;

  const originalResJson = res.json;
  res.json = function (bodyJson, ...args) {
    capturedJsonResponse = bodyJson;
    return originalResJson.apply(res, [bodyJson, ...args]);
  };

  res.on("finish", () => {
    const duration = Date.now() - start;
    if (path.startsWith("/api")) {
      let logLine = `${req.method} ${path} ${res.statusCode} in ${duration}ms`;
      if (capturedJsonResponse) {
        logLine += ` :: ${JSON.stringify(capturedJsonResponse)}`;
      }
      log(logLine);
    }
  });

  next();
}

// Exported so tests can mount it directly and verify the response contract
// without needing the full app boot (registerRoutes hits the DB / OIDC).
//
// Contract:
//   - 4xx: surface `err.message` (intentional user-facing validation text)
//   - 5xx / no status: generic "Internal Server Error" — never leak driver
//     errors, schema names, or stack details to the client
//   - Always log the full error server-side regardless of response
export function errorHandler(
  err: any,
  req: Request,
  res: Response,
  next: NextFunction,
) {
  const status = err.status || err.statusCode || 500;

  console.error(`Error handling ${req.method} ${req.path}:`, err);

  if (res.headersSent) {
    return next(err);
  }

  const isClientError = status >= 400 && status < 500;
  const message = isClientError && err.message ? err.message : "Internal Server Error";

  return res.status(status).json({ message });
}

export interface CreateAppResult {
  app: Express;
  httpServer: Server;
}

// Build the production Express pipeline:
//   body parsers → /api/health → request logger → registerRoutes
//   (auth + rate limiters + all /api/* handlers) → error handler
//
// Does NOT call httpServer.listen() and does NOT mount Vite or the static
// client bundle — those are entry-point concerns handled in server/index.ts.
export async function createApp(): Promise<CreateAppResult> {
  const app = express();
  const httpServer = createServer(app);

  app.use(
    express.json({
      verify: (req, _res, buf) => {
        req.rawBody = buf;
      },
    }),
  );
  app.use(express.urlencoded({ extended: false }));

  app.get("/api/health", (_req, res) => {
    res.status(200).json({ status: "ok" });
  });

  app.use(requestLogger);

  await registerRoutes(httpServer, app);

  app.use(errorHandler);

  return { app, httpServer };
}
