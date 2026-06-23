/**
 * Monitor API 封装
 */

import type {
  MonitorListResponse,
  MonitorDetailResponse,
  MonitorSegmentsResponse,
  MonitorSpawnRequest,
  MonitorSpawnResponse,
  GlobalMonitorListResponse,
  GlobalMonitorSummaryResponse,
} from "@/types/monitors";
import { apiRequest } from "@/lib/api/httpClient";

export function listSessionMonitors(
  userId: string,
  sessionId: string,
): Promise<MonitorListResponse> {
  return apiRequest<MonitorListResponse>(
    `/api/sessions/${userId}/${sessionId}/monitors`,
  );
}

export function getMonitorDetail(
  userId: string,
  sessionId: string,
  monitorId: string,
): Promise<MonitorDetailResponse> {
  return apiRequest<MonitorDetailResponse>(
    `/api/sessions/${userId}/${sessionId}/monitors/${monitorId}`,
  );
}

export function getMonitorSegments(
  userId: string,
  sessionId: string,
  monitorId: string,
  sinceIndex: number,
): Promise<MonitorSegmentsResponse> {
  return apiRequest<MonitorSegmentsResponse>(
    `/api/sessions/${userId}/${sessionId}/monitors/${monitorId}/segments?since_index=${sinceIndex}`,
  );
}

export function killMonitor(
  userId: string,
  sessionId: string,
  monitorId: string,
): Promise<{ success: boolean; monitor_id: string }> {
  return apiRequest<{ success: boolean; monitor_id: string }>(
    `/api/sessions/${userId}/${sessionId}/monitors/${monitorId}/kill`,
    { method: "POST" },
  );
}

export function spawnMonitor(
  userId: string,
  sessionId: string,
  req: MonitorSpawnRequest,
): Promise<MonitorSpawnResponse> {
  return apiRequest<MonitorSpawnResponse>(
    `/api/sessions/${userId}/${sessionId}/monitors/spawn`,
    {
      method: "POST",
      body: JSON.stringify(req),
    },
  );
}

export function deleteMonitor(
  userId: string,
  sessionId: string,
  monitorId: string,
): Promise<{ success: boolean; monitor_id: string }> {
  return apiRequest<{ success: boolean; monitor_id: string }>(
    `/api/sessions/${userId}/${sessionId}/monitors/${monitorId}`,
    { method: "DELETE" },
  );
}

export function updateMonitorMode(
  userId: string,
  sessionId: string,
  monitorId: string,
  mode: "notify" | "silent",
): Promise<{ success: boolean; monitor_id: string; mode: string }> {
  return apiRequest<{ success: boolean; monitor_id: string; mode: string }>(
    `/api/sessions/${userId}/${sessionId}/monitors/${monitorId}/mode?mode=${mode}`,
    { method: "PUT" },
  );
}

export function listGlobalMonitors(
  status?: string,
): Promise<GlobalMonitorListResponse> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return apiRequest<GlobalMonitorListResponse>(`/api/sessions/monitors${query}`);
}

export function getGlobalMonitorSummary(): Promise<GlobalMonitorSummaryResponse> {
  return apiRequest<GlobalMonitorSummaryResponse>(`/api/sessions/monitors/summary`);
}
