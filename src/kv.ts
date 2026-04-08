// Singleton Deno KV store
let _kv: Deno.Kv | undefined;

export async function getKv(): Promise<Deno.Kv> {
  if (!_kv) {
    const path = Deno.env.get("KV_PATH"); // optional explicit path for testing
    _kv = await Deno.openKv(path);
  }
  return _kv;
}
