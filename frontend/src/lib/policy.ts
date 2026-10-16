import { BRAND } from "@/content/brand";
import { serverGet } from "@/lib/server-api";
import type { SiteConfig } from "@/lib/types";

export interface PolicyFacts {
  operatorName: string;
  /** The policy version label (a date), or null when the backend could not be reached. */
  version: string | null;
  /**
   * Where privacy questions and grievances go. Comes only from the backend's configuration
   * (the admin email today). There is deliberately no hardcoded fallback address: if the
   * backend is unreachable the pages say so instead of showing a stale or personal address.
   */
  contactEmail: string | null;
}

export async function getPolicyFacts(): Promise<PolicyFacts> {
  const config = await serverGet<SiteConfig>("/api/config");
  return {
    operatorName: config?.policy_operator_name || BRAND,
    version: config?.policy_version || null,
    contactEmail: config?.policy_contact_email || null,
  };
}
