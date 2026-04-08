import { CreditBuyResponse, PendingPayment } from "./types.ts";
import { getConfig } from "./config.ts";
import { getKv } from "./kv.ts";

/**
 * Get or initialize the agent's Solana wallet public key.
 * The private key is stored in env var AGENT_WALLET_PRIVATE_KEY (base58, 64 bytes).
 */
export async function getAgentWalletAddress(): Promise<string> {
  const kv = await getKv();
  const cached = await kv.get<string>(["agent_wallet_pubkey"]);
  if (cached.value) return cached.value;

  const config = getConfig();
  const privKeyB58 = config.agentWalletPrivateKey;
  if (!privKeyB58) {
    throw new Error("AGENT_WALLET_PRIVATE_KEY env var not set");
  }

  // Decode base58 private key (64 bytes: 32 private + 32 public)
  const privKeyBytes = base58Decode(privKeyB58);
  const pubKeyBytes = privKeyBytes.slice(32);
  const pubKeyB58 = base58Encode(pubKeyBytes);

  await kv.set(["agent_wallet_pubkey"], pubKeyB58);
  return pubKeyB58;
}

/**
 * Create a buy-credits intent. Returns wallet address and payment memo.
 */
export async function createCreditBuyIntent(
  apiKey: string,
  usdcAmount: number,
): Promise<CreditBuyResponse> {
  if (usdcAmount < 1) throw new Error("Minimum top-up is 1 USDC");
  if (usdcAmount > 1000) throw new Error("Maximum single top-up is 1000 USDC");

  const config = getConfig();
  const kv = await getKv();
  const wallet = await getAgentWalletAddress();
  const memo = `pay_${apiKey.slice(3, 11)}_${Date.now()}`;
  const creditsToReceive = usdcAmount * config.creditsPerUsdc;
  const network = config.solanaRpcUrl.includes("devnet") ? "devnet" : "mainnet-beta";

  const pending: PendingPayment = { apiKey, usdcAmount, createdAt: Date.now(), memo };
  await kv.set(["pending", memo], pending, { expireIn: 3_600_000 }); // 1 hour

  return {
    wallet,
    usdcAmount,
    memo,
    creditsToReceive,
    instructions: `Send exactly ${usdcAmount} USDC to ${wallet} on Solana ${network}. Include memo: "${memo}". Then call POST /credits/confirm with your txSignature.`,
  };
}

/**
 * Verify a Solana transaction and credit the user if valid.
 */
export async function confirmUsdcPayment(
  txSignature: string,
  apiKey: string,
): Promise<{ success: boolean; creditsAdded?: number; error?: string }> {
  const kv = await getKv();

  // Prevent double-spend
  const alreadyConfirmed = await kv.get(["confirmed_tx", txSignature]);
  if (alreadyConfirmed.value) {
    return { success: false, error: "Transaction already processed" };
  }

  const config = getConfig();
  const rpcUrl = config.solanaRpcUrl;

  const rpcResponse = await fetch(rpcUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "getTransaction",
      params: [txSignature, { encoding: "jsonParsed", commitment: "confirmed", maxSupportedTransactionVersion: 0 }],
    }),
  });

  if (!rpcResponse.ok) {
    return { success: false, error: "Solana RPC unavailable" };
  }

  const rpcData: any = await rpcResponse.json();
  const tx = rpcData?.result;

  if (!tx) return { success: false, error: "Transaction not found or not yet confirmed" };
  if (tx.meta?.err) return { success: false, error: "Transaction failed on-chain" };

  const agentWallet = await getAgentWalletAddress();
  const usdcMint = config.usdcMint;

  let usdcReceived = 0;
  const instructions = tx.transaction?.message?.instructions ?? [];

  for (const ix of instructions) {
    if (
      ix.programId === "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA" &&
      ix.parsed?.type === "transferChecked"
    ) {
      const info = ix.parsed.info;
      if (info.mint === usdcMint && info.destination) {
        const isAgent = await isAgentTokenAccount(rpcUrl, info.destination, agentWallet, usdcMint);
        if (isAgent) {
          usdcReceived = parseFloat(info.tokenAmount?.uiAmount ?? "0");
        }
      }
    }
  }

  if (usdcReceived <= 0) {
    return { success: false, error: "No USDC transfer to agent wallet found in this transaction" };
  }

  const creditsToAdd = Math.floor(usdcReceived * config.creditsPerUsdc);
  await kv.set(
    ["confirmed_tx", txSignature],
    { apiKey, usdcReceived, creditsAdded: creditsToAdd, confirmedAt: Date.now() },
    { expireIn: 86_400_000 * 365 },
  );

  return { success: true, creditsAdded: creditsToAdd };
}

async function isAgentTokenAccount(
  rpcUrl: string,
  tokenAccount: string,
  ownerWallet: string,
  mint: string,
): Promise<boolean> {
  try {
    const resp = await fetch(rpcUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 1,
        method: "getAccountInfo",
        params: [tokenAccount, { encoding: "jsonParsed" }],
      }),
    });
    const data: any = await resp.json();
    const info = data?.result?.value?.data?.parsed?.info;
    return info?.owner === ownerWallet && info?.mint === mint;
  } catch {
    return false;
  }
}

// ---- Base58 utilities ----

const BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";

export function base58Decode(str: string): Uint8Array {
  const bytes = [0];
  for (const char of str) {
    const value = BASE58_ALPHABET.indexOf(char);
    if (value < 0) throw new Error(`Invalid base58 character: ${char}`);
    let carry = value;
    for (let i = 0; i < bytes.length; i++) {
      carry += bytes[i] * 58;
      bytes[i] = carry & 0xff;
      carry >>= 8;
    }
    while (carry > 0) {
      bytes.push(carry & 0xff);
      carry >>= 8;
    }
  }
  for (const char of str) {
    if (char === "1") bytes.push(0);
    else break;
  }
  return new Uint8Array(bytes.reverse());
}

export function base58Encode(bytes: Uint8Array): string {
  const digits = [0];
  for (const byte of bytes) {
    let carry = byte;
    for (let i = 0; i < digits.length; i++) {
      carry += digits[i] << 8;
      digits[i] = carry % 58;
      carry = Math.floor(carry / 58);
    }
    while (carry > 0) {
      digits.push(carry % 58);
      carry = Math.floor(carry / 58);
    }
  }
  let result = "";
  for (const byte of bytes) {
    if (byte === 0) result += "1";
    else break;
  }
  return result + digits.reverse().map((d) => BASE58_ALPHABET[d]).join("");
}
