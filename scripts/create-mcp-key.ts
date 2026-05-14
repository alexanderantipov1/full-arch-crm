// One-shot CLI to mint an MCP API key. Useful for the first deployment
// when the admin UI hasn't been wired and there's no key yet to bootstrap
// the system. After this runs, set up additional keys via the
// `POST /api/admin/mcp-keys` endpoint.
//
// Usage:
//   tsx scripts/create-mcp-key.ts <label> [capability ...]
//
// Examples:
//   tsx scripts/create-mcp-key.ts "claude-code-local" phi.read phi.write
//   tsx scripts/create-mcp-key.ts "marketing-agent"
//
// The plaintext token is printed to stdout EXACTLY ONCE. Capture it
// immediately into your AI client's secrets store; the DB stores only
// the SHA-256 hash, so a lost token cannot be recovered — only revoked
// and reissued.

import { generateMcpApiKey } from "../server/mcp/keys";

async function main(): Promise<void> {
  const [, , labelArg, ...capabilityArgs] = process.argv;
  if (!labelArg) {
    console.error("usage: tsx scripts/create-mcp-key.ts <label> [capability ...]");
    process.exit(2);
  }

  const allowed = new Set(["phi.read", "phi.write"]);
  const capabilities = capabilityArgs.filter((c) => allowed.has(c)) as any;
  const dropped = capabilityArgs.filter((c) => !allowed.has(c));
  if (dropped.length > 0) {
    console.warn(`[warn] ignored unknown capabilities: ${dropped.join(", ")}`);
  }

  const created = await generateMcpApiKey({
    label: labelArg,
    capabilities,
    createdBy: "cli",
  });

  console.log("\n=== MCP API key created ===");
  console.log(`id:           ${created.id}`);
  console.log(`label:        ${created.label}`);
  console.log(`capabilities: ${created.capabilities.join(", ") || "(none — read-only access)"}`);
  console.log(`\ntoken (save this NOW, it cannot be retrieved later):`);
  console.log(`  ${created.token}\n`);
  console.log("Use as: Authorization: Bearer <token>");
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("[create-mcp-key] FAILED:", err);
    process.exit(1);
  });
