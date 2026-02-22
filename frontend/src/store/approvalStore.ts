import { create } from "zustand";

export type PendingApproval = {
  path: string;
  args: Record<string, unknown>;
  approvalId: string;
  preview?: string;
};

type ApprovalState = {
  pending: PendingApproval | null;
  setPending: (value: PendingApproval) => void;
  clearPending: () => void;
};

export const useApprovalStore = create<ApprovalState>((set) => ({
  pending: null,
  setPending: (value) => set({ pending: value }),
  clearPending: () => set({ pending: null }),
}));
