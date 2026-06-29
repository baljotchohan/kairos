import crypto from "crypto";

function secret(): string {
  const s = process.env.MCP_CONNECT_SECRET;
  if (!s) throw new Error("MCP_CONNECT_SECRET not set");
  return s;
}

export function mintMcpToken(userId: string): string {
  const uid_b64 = Buffer.from(userId).toString("base64url");
  const sig = crypto
    .createHmac("sha256", secret())
    .update(userId)
    .digest("hex")
    .slice(0, 40);
  return `${uid_b64}.${sig}`;
}

export function signPayload(payload: object): string {
  const data = Buffer.from(JSON.stringify(payload)).toString("base64url");
  const sig = crypto
    .createHmac("sha256", secret())
    .update(data)
    .digest("hex")
    .slice(0, 40);
  return `${data}.${sig}`;
}

export function verifyPayload<T>(token: string): T | null {
  const dotIdx = token.lastIndexOf(".");
  if (dotIdx === -1) return null;
  const data = token.slice(0, dotIdx);
  const sig = token.slice(dotIdx + 1);
  const expected = crypto
    .createHmac("sha256", secret())
    .update(data)
    .digest("hex")
    .slice(0, 40);
  try {
    if (sig !== expected) return null;
    return JSON.parse(Buffer.from(data, "base64url").toString("utf8")) as T;
  } catch {
    return null;
  }
}

export async function verifyFirebaseToken(
  idToken: string
): Promise<string | null> {
  const apiKey = process.env.NEXT_PUBLIC_FIREBASE_API_KEY;
  if (!apiKey) return null;
  try {
    const resp = await fetch(
      `https://identitytoolkit.googleapis.com/v1/accounts:lookup?key=${apiKey}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idToken }),
      }
    );
    if (!resp.ok) return null;
    const data = await resp.json();
    return (data.users?.[0]?.localId as string) ?? null;
  } catch {
    return null;
  }
}
