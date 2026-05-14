// Augments Express.User so route handlers can read the OIDC claims attached
// in replit_integrations/auth/replitAuth.ts (`updateUserSession` mutates the
// session user with these fields after token verification).

declare global {
  namespace Express {
    interface User {
      claims?: {
        sub?: string;
        email?: string;
        first_name?: string;
        last_name?: string;
        exp?: number;
        [key: string]: unknown;
      };
      id?: string;
      access_token?: string;
      refresh_token?: string;
      expires_at?: number;
    }
  }
}

export {};
