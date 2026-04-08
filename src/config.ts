import { AppConfig } from "./types.ts";

// Devnet USDC mint (Circle's official devnet USDC)
const DEVNET_USDC_MINT = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU";
const DEVNET_RPC = "https://api.devnet.solana.com";

export function getConfig(): AppConfig {
  return {
    groqApiKey: Deno.env.get("GROQ_API_KEY") ?? "",
    agentWalletPrivateKey: Deno.env.get("AGENT_WALLET_PRIVATE_KEY") ?? "",
    solanaRpcUrl: Deno.env.get("SOLANA_RPC_URL") ?? DEVNET_RPC,
    usdcMint: Deno.env.get("USDC_MINT") ?? DEVNET_USDC_MINT,
    creditsPerUsdc: parseInt(Deno.env.get("CREDITS_PER_USDC") ?? "1000"),
  };
}
