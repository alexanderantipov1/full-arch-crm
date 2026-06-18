import type { Express } from "express";
import { authStorage } from "./storage";
import { isAuthenticated } from "./replitAuth";

// Register auth-specific routes
export function registerAuthRoutes(app: Express): void {
  // Get current authenticated user
  app.get("/api/auth/user", isAuthenticated, async (req: any, res) => {
    try {
      const userId = req.user.claims.sub;
      // Under LOCAL_DEV_AUTH_BYPASS, the synthetic user from the
      // isAuthenticated bypass doesn't have a real DB row. Return the
      // claims directly so the SPA's `useAuth` hook sees a logged-in
      // user and the app renders.
      if (process.env.LOCAL_DEV_AUTH_BYPASS === "true") {
        return res.json({
          id: userId,
          email: req.user.claims.email,
          firstName: req.user.claims.first_name,
          lastName: req.user.claims.last_name,
        });
      }
      const user = await authStorage.getUser(userId);
      res.json(user);
    } catch (error) {
      console.error("Error fetching user:", error);
      res.status(500).json({ message: "Failed to fetch user" });
    }
  });
}
