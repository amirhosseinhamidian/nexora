import type { AuthenticationOptionsResponse, RegistrationOptionsResponse } from "@nexora/contracts";

function decodeBase64Url(value: string): ArrayBuffer {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  const bytes = Uint8Array.from(atob(padded), (character) => character.charCodeAt(0));
  return bytes.buffer;
}

function encodeBase64Url(value: ArrayBuffer): string {
  const bytes = new Uint8Array(value);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function requireWebAuthn(): CredentialsContainer {
  if (!window.isSecureContext || !window.PublicKeyCredential || !navigator.credentials) {
    throw new Error("WEBAUTHN_UNAVAILABLE");
  }
  return navigator.credentials;
}

function credentialJson(credential: PublicKeyCredential): string {
  const response = credential.response;
  const base = {
    authenticatorAttachment: credential.authenticatorAttachment,
    clientExtensionResults: credential.getClientExtensionResults(),
    id: credential.id,
    rawId: encodeBase64Url(credential.rawId),
    type: credential.type,
  };
  if (response instanceof AuthenticatorAttestationResponse) {
    return JSON.stringify({
      ...base,
      response: {
        attestationObject: encodeBase64Url(response.attestationObject),
        clientDataJSON: encodeBase64Url(response.clientDataJSON),
        transports: response.getTransports(),
      },
    });
  }
  if (response instanceof AuthenticatorAssertionResponse) {
    return JSON.stringify({
      ...base,
      response: {
        authenticatorData: encodeBase64Url(response.authenticatorData),
        clientDataJSON: encodeBase64Url(response.clientDataJSON),
        signature: encodeBase64Url(response.signature),
        userHandle: response.userHandle ? encodeBase64Url(response.userHandle) : null,
      },
    });
  }
  throw new Error("WEBAUTHN_RESPONSE_INVALID");
}

export async function createPasskeyAssertion(options: AuthenticationOptionsResponse) {
  const credential = await requireWebAuthn().get({
    publicKey: {
      allowCredentials: options.allow_credentials.map((item) => ({
        id: decodeBase64Url(item.credential_id),
        transports: item.transports as AuthenticatorTransport[],
        type: "public-key",
      })),
      challenge: decodeBase64Url(options.challenge),
      rpId: options.rp_id,
      timeout: options.timeout_ms,
      userVerification: "required",
    },
  });
  if (!(credential instanceof PublicKeyCredential)) throw new Error("WEBAUTHN_CANCELLED");
  return {
    challenge: options.challenge,
    credential_id: credential.id,
    response_json: credentialJson(credential),
  };
}

export async function createPasskeyRegistration(
  options: RegistrationOptionsResponse,
  userSeed: string,
) {
  const userId = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(userSeed));
  const algorithmByName = { ES256: -7, EdDSA: -8 } as const;
  const credential = await requireWebAuthn().create({
    publicKey: {
      attestation: "none",
      authenticatorSelection: {
        residentKey: "required",
        userVerification: "required",
      },
      challenge: decodeBase64Url(options.challenge),
      pubKeyCredParams: (options.algorithms ?? ["ES256", "EdDSA"]).map((name) => ({
        alg: algorithmByName[name],
        type: "public-key",
      })),
      rp: { id: options.rp_id, name: options.rp_name ?? "Nexora" },
      timeout: options.timeout_ms,
      user: {
        displayName: options.user_name ?? "primary_owner",
        id: userId,
        name: options.user_name ?? "primary_owner",
      },
    },
  });
  if (!(credential instanceof PublicKeyCredential)) throw new Error("WEBAUTHN_CANCELLED");
  return credentialJson(credential);
}
