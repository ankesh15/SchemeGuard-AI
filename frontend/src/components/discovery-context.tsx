"use client";
import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";
import type { ProfileData } from "@/lib/citizen";
import type { Recommendation } from "@/lib/recommendations";

interface DiscoveryState {
  profile: ProfileData | null;
  ownerId: string | null;
  setProfile: (value: ProfileData | null, ownerId?: string) => void;
  matches: Record<string, Recommendation>;
  remember: (items: Recommendation[]) => void;
  clear: () => void;
}
const DiscoveryContext = createContext<DiscoveryState | null>(null);
// Deliberately memory-only: no PII in URLs, localStorage, sessionStorage or cookies.
export function DiscoveryProvider({ children }: { children: ReactNode }) {
  const [profile, updateProfile] = useState<ProfileData | null>(null);
  const [ownerId, setOwnerId] = useState<string | null>(null);
  const [matches, setMatches] = useState<Record<string, Recommendation>>({});
  const setProfile = useCallback(
    (value: ProfileData | null, owner?: string) => {
      updateProfile(value);
      setOwnerId(owner || null);
      setMatches({});
    },
    [],
  );
  const remember = useCallback(
    (items: Recommendation[]) =>
      setMatches((old) => ({
        ...old,
        ...Object.fromEntries(items.map((item) => [item.id, item])),
      })),
    [],
  );
  const clear = useCallback(() => {
    updateProfile(null);
    setOwnerId(null);
    setMatches({});
  }, []);
  return (
    <DiscoveryContext.Provider
      value={{ profile, ownerId, setProfile, matches, remember, clear }}
    >
      {children}
    </DiscoveryContext.Provider>
  );
}
export const useOptionalDiscovery = () => useContext(DiscoveryContext);
export function useDiscovery() {
  const value = useOptionalDiscovery();
  if (!value) throw new Error("Discovery provider is required");
  return value;
}
